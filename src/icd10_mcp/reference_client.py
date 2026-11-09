"""Public-terminology remote client with pre-network, best-effort PII screening."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
from contextlib import asynccontextmanager
from datetime import date
from urllib.parse import urlsplit

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import Implementation

from .cli_safety import SafeArgumentParser
from .client_config import load_token_file
from .privacy import PRIVACY_NOTICE, blocked_codes, blocked_phrase, blocked_response
from .releases import PROFILES

_MAX_REMOTE_RESPONSE_BYTES = 262144


class _BoundedResponseStream(httpx.AsyncByteStream):
    def __init__(self, stream, rejected):
        self.stream = stream
        self.rejected = rejected

    async def __aiter__(self):
        received = 0
        async for chunk in self.stream:
            received += len(chunk)
            if received > _MAX_REMOTE_RESPONSE_BYTES:
                self.rejected.set()
                raise ValueError("Remote response exceeds its limit.")
            yield chunk

    async def aclose(self):
        await self.stream.aclose()


async def _bound_response(response, rejected):
    length = response.headers.get("content-length")
    try:
        declared = int(length) if length is not None else 0
    except ValueError:
        declared = -1
    if (
        response.is_redirect
        or response.headers.get("content-encoding", "identity").strip().lower() != "identity"
        or not 0 <= declared <= _MAX_REMOTE_RESPONSE_BYTES
    ):
        rejected.set()
        await response.aclose()
        raise ValueError("Remote response rejected.") from None
    if response.is_stream_consumed:
        if len(response.content) > _MAX_REMOTE_RESPONSE_BYTES:
            rejected.set()
            await response.aclose()
            raise ValueError("Remote response exceeds its limit.")
    else:
        response.stream = _BoundedResponseStream(response.stream, rejected)


@asynccontextmanager
async def _bounded_http_client(token, transport):
    rejected = asyncio.Event()

    async def inspect(response):
        await _bound_response(response, rejected)

    async def stop_rejected_exchange():
        await rejected.wait()
        raise ValueError("Remote response rejected.")

    async with asyncio.timeout(90), asyncio.TaskGroup() as tasks:
        watcher = tasks.create_task(stop_rejected_exchange())
        try:
            async with httpx.AsyncClient(
                headers={
                    "Accept-Encoding": "identity",
                    **({"Authorization": f"Bearer {token}"} if token is not None else {}),
                },
                transport=transport,
                timeout=90,
                follow_redirects=False,
                trust_env=False,
                event_hooks={"response": [inspect]},
            ) as client:
                yield client
        finally:
            watcher.cancel()


class ReferenceClient:
    """Screen locally before opening a connection; never use for real patient data."""

    def __init__(self, url: str, token: str | None = None, *, transport=None):
        try:
            target = urlsplit(url)
            if (
                not url
                or any(char.isspace() or not char.isprintable() for char in url)
                or target.scheme not in {"http", "https"}
                or (target.scheme == "http" and target.hostname not in {"127.0.0.1", "localhost"})
                or not target.hostname
                or target.username is not None
                or target.password is not None
                or target.query
                or target.fragment
                or target.path != "/mcp"
                or (target.port is not None and not 1 <= target.port <= 65535)
                or (
                    token is not None
                    and not re.fullmatch(r"[A-Za-z0-9._~+/-]{32,256}={0,2}", token)
                )
            ):
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise ValueError("Invalid reference client configuration.") from None
        self.url = url
        self.token = token
        self.transport = transport

    async def lookup(self, query: str, service_date: str, limit: int = 10) -> dict:
        if blocked_phrase(query):
            return blocked_response()
        if type(limit) is not int or not 1 <= limit <= 25:
            return {
                "status": "invalid_request",
                "message": "Use an integer limit from 1 through 25.",
            }
        return await self._call(
            "phrase_search",
            {"query": query, "service_date": service_date, "limit": limit},
        )

    async def validate(self, codes: list[str], service_date: str) -> dict:
        if blocked_codes(codes):
            return blocked_response()
        return await self._call(
            "validate_selected_codes", {"codes": codes, "service_date": service_date}
        )

    async def _call(self, tool: str, arguments: dict) -> dict:
        original_date = arguments["service_date"]
        try:
            if date.fromisoformat(original_date).isoformat() != original_date:
                raise ValueError
        except (ValueError, TypeError):
            return {"status": "invalid_request", "message": "Use a YYYY-MM-DD service_date."}
        anchor = next(
            (
                profile["release"]["effective_from"]
                for profile in PROFILES.values()
                if profile["release"]["effective_from"]
                <= original_date
                <= profile["release"]["effective_through"]
            ),
            None,
        )
        if anchor is None:
            return {
                "status": "release_unavailable",
                "message": "No configured release covers this date.",
            }
        arguments = {**arguments, "service_date": anchor}
        try:
            async with _bounded_http_client(self.token, self.transport) as client:
                async with streamable_http_client(self.url, http_client=client) as (
                    read,
                    write,
                    _,
                ):
                    async with ClientSession(
                        read,
                        write,
                        client_info=Implementation(name="icd10-reference-client", version="0.1.0"),
                    ) as session:
                        await session.initialize()
                        result = await session.call_tool(tool, arguments)
                        if result.isError or not isinstance(result.structuredContent, dict):
                            raise ValueError
                        data = {
                            **result.structuredContent,
                            "privacy": {
                                **PRIVACY_NOTICE,
                                "original_date_sent": False,
                                "remote_service_date": anchor,
                            },
                        }
                        if "service_date" in data:
                            data["service_date"] = original_date
                        return data
        except Exception:
            return {
                "status": "remote_unavailable",
                "message": "Reference lookup unavailable. No input or credential details returned.",
                "privacy": dict(PRIVACY_NOTICE),
            }


def main():
    parser = SafeArgumentParser(description="Public terminology JSON on stdin; never patient data.")
    parser.add_argument("--url", required=True, help="Explicit HTTPS /mcp endpoint")
    credentials = parser.add_mutually_exclusive_group()
    credentials.add_argument(
        "--token-file", help="Absolute private token-file path, never a token value"
    )
    credentials.add_argument(
        "--anonymous", action="store_true", help="Send no credential, ignoring inherited tokens"
    )
    parser.add_argument("--public-terminology", action="store_true", required=True)
    args = parser.parse_args()
    for name in ("mcp", "httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.CRITICAL)

    async def run():
        raw = sys.stdin.buffer.read(65_537)
        if len(raw) > 65_536:
            raise ValueError
        request = json.loads(raw)
        if not isinstance(request, dict):
            raise ValueError
        operation = request["operation"]
        allowed = (
            {"operation", "query", "service_date", "limit"}
            if operation == "lookup"
            else {"operation", "codes", "service_date"}
        )
        if not request.keys() <= allowed:
            raise ValueError
        token = (
            None
            if args.anonymous
            else (
                load_token_file(args.token_file)
                if args.token_file
                else os.environ["ICD10_DEMO_TOKEN"]
            )
        )
        client = ReferenceClient(args.url, token)
        if operation == "lookup":
            limit = request.get("limit", 10)
            return await client.lookup(request["query"], request["service_date"], limit)
        if operation == "validate":
            return await client.validate(request["codes"], request["service_date"])
        raise ValueError

    try:
        result = asyncio.run(asyncio.wait_for(run(), timeout=180))
    except Exception:
        result = {
            "status": "invalid_request",
            "message": "Invalid public-terminology input or client configuration.",
            "privacy": dict(PRIVACY_NOTICE),
        }
    print(json.dumps(result, indent=2))
    if result.get("status") in {
        "privacy_blocked",
        "invalid_request",
        "release_unavailable",
        "catalog_unavailable",
        "remote_unavailable",
    }:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
