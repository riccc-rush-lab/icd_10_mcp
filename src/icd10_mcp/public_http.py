"""Per-process public HTTP admission, not a provider-side billing cap."""

import asyncio
import math
import time
from dataclasses import dataclass

from starlette.responses import JSONResponse, Response


@dataclass(frozen=True)
class PublicLimits:
    requests_per_window: int = 120
    window_seconds: float = 60
    max_request_bytes: int = 8192
    max_response_bytes: int = 262144
    max_in_flight: int = 4
    request_timeout_seconds: float = 15

    def __post_init__(self):
        for value in (
            self.requests_per_window,
            self.max_request_bytes,
            self.max_response_bytes,
            self.max_in_flight,
        ):
            if type(value) is not int or value < 1:
                raise ValueError("Invalid public HTTP limits.")
        if self.max_response_bytes < 128:
            raise ValueError("Reserve space for a bounded HTTP error response.")
        for value in (self.window_seconds, self.request_timeout_seconds):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Invalid public HTTP limits.")


class PublicHTTPGuard:
    def __init__(self, app, *, limits: PublicLimits):
        self.app = app
        self.limits = limits
        self.window_started = time.monotonic()
        self.requests = 0
        self.active = 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or (
            scope["method"] == "GET" and scope["path"] in {"/healthz", "/readyz"}
        ):
            return await self.app(scope, receive, send)
        now = time.monotonic()
        if now - self.window_started >= self.limits.window_seconds:
            self.window_started = now
            self.requests = 0
        if self.requests >= self.limits.requests_per_window:
            remaining = self.limits.window_seconds - (now - self.window_started)
            await self._reject(
                JSONResponse(
                    {"status": "rate_limited"},
                    status_code=429,
                    headers={
                        "Retry-After": str(max(1, math.ceil(remaining))),
                        "Cache-Control": "no-store",
                    },
                ),
                scope,
                receive,
                send,
            )
            return
        self.requests += 1
        if self.active >= self.limits.max_in_flight:
            await self._reject(
                JSONResponse(
                    {"status": "busy"},
                    status_code=503,
                    headers={"Retry-After": "1", "Cache-Control": "no-store"},
                ),
                scope,
                receive,
                send,
            )
            return
        self.active += 1
        response_started = False

        async def guarded_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        async def exchange():
            response = await self._handle(scope, receive)
            if response is not None:
                await response(scope, receive, guarded_send)

        try:
            try:
                await asyncio.wait_for(exchange(), self.limits.request_timeout_seconds)
            except TimeoutError:
                if not response_started:
                    await self._reject(
                        JSONResponse(
                            {"status": "request_timed_out"},
                            status_code=504,
                            headers={"Retry-After": "1", "Cache-Control": "no-store"},
                        ),
                        scope,
                        receive,
                        send,
                    )
        finally:
            self.active -= 1

    async def _reject(self, response, scope, receive, send):
        try:
            await asyncio.wait_for(
                response(scope, receive, send),
                min(1.0, self.limits.request_timeout_seconds),
            )
        except TimeoutError:
            pass

    async def _handle(self, scope, receive):
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > self.limits.max_request_bytes:
                return JSONResponse(
                    {"status": "request_too_large"},
                    status_code=413,
                    headers={"Cache-Control": "no-store"},
                )
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        response_start = None
        response_body = bytearray()
        oversized = False

        async def capture(message):
            nonlocal response_start, oversized
            if message["type"] == "http.response.start":
                response_start = message
            elif message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                if len(response_body) + len(chunk) > self.limits.max_response_bytes:
                    oversized = True
                    raise ValueError("Public HTTP response exceeds its limit.")
                response_body.extend(chunk)

        try:
            await self.app(scope, replay, capture)
        except Exception:
            if not oversized:
                return JSONResponse(
                    {"status": "temporarily_unavailable"},
                    status_code=503,
                    headers={"Cache-Control": "no-store"},
                )
        if oversized or response_start is None:
            return JSONResponse(
                {"status": "response_too_large" if oversized else "temporarily_unavailable"},
                status_code=503,
                headers={"Cache-Control": "no-store"},
            )
        if response_start["status"] >= 400:
            return JSONResponse(
                {
                    "status": "invalid_request"
                    if response_start["status"] < 500
                    else "temporarily_unavailable"
                },
                status_code=response_start["status"],
                headers={"Cache-Control": "no-store"},
            )
        response = Response(bytes(response_body), status_code=response_start["status"])
        response.raw_headers = response_start.get("headers", [])
        return response
