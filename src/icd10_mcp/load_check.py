"""Bounded public-terminology benchmark, never a maximum-capacity certification."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import time
from urllib.parse import urlsplit

import httpx

from .cli_safety import SafeArgumentParser
from .reference_client import ReferenceClient
from .releases import PROFILES

_CASES = ("exact", "phrase", "header", "validation")


class _BudgetHTTP(httpx.AsyncBaseTransport):
    def __init__(self, inner, deadline):
        self.inner = inner
        self.deadline = deadline
        self.requests = 0
        self.bytes = 0
        self.reason = None

    async def handle_async_request(self, request):
        if self.reason or time.monotonic() >= self.deadline:
            self.reason = self.reason or "time_limit"
            raise RuntimeError("Benchmark stopped.")
        if self.requests >= 1000:
            self.reason = "http_request_limit"
            raise RuntimeError("Benchmark stopped.")
        self.requests += 1
        try:
            response = await self.inner.handle_async_request(request)
            if response.status_code >= 400:
                self.reason = "http_error"
            if response.headers.get("content-type", "").startswith("text/event-stream"):
                self.reason = "unexpected_stream"
                await response.aclose()
                raise RuntimeError("Benchmark stopped.")
            decoded = response.is_stream_consumed

            async def body_chunks():
                if decoded:
                    yield response.content
                else:
                    async for chunk in response.aiter_raw():
                        yield chunk

            chunks = []
            try:
                async for chunk in body_chunks():
                    self.bytes += len(chunk)
                    if self.bytes > 20 * 1024 * 1024 or time.monotonic() >= self.deadline:
                        self.reason = (
                            "response_byte_limit" if self.bytes > 20 * 1024 * 1024 else "time_limit"
                        )
                        raise RuntimeError("Benchmark stopped.")
                    chunks.append(chunk)
            finally:
                await response.aclose()
            headers = [
                (name, value)
                for name, value in response.headers.multi_items()
                if not decoded or name.lower() not in {"content-encoding", "content-length"}
            ]
            return httpx.Response(
                response.status_code,
                headers=headers,
                content=b"".join(chunks),
                request=request,
            )
        except Exception:
            self.reason = self.reason or "transport_error"
            raise RuntimeError("Benchmark transport stopped.") from None

    async def aclose(self):
        # Per-operation clients borrow this adapter. The benchmark owns the pool.
        pass


async def _measure_level(client, budget, count, workers, service_dates):
    position = 0
    successes = 0
    errors = 0
    latencies = []
    started = time.monotonic()

    async def worker():
        nonlocal position, successes, errors
        while position < count and not budget.reason:
            remaining = budget.deadline - time.monotonic()
            if remaining <= 0:
                budget.reason = "time_limit"
                return
            ordinal = position
            position += 1
            case = _CASES[ordinal % len(_CASES)]
            date = service_dates[(ordinal // len(_CASES)) % len(service_dates)]
            before = time.monotonic()
            try:
                if case == "validation":
                    result = await asyncio.wait_for(client.validate(["E11.9"], date), remaining)
                    valid = result["results"][0]["code_validity"]["status"] == "valid"
                else:
                    query = {"exact": "E11.9", "phrase": "pneumonia", "header": "E11"}[case]
                    result = await asyncio.wait_for(client.lookup(query, date), remaining)
                    expected = {"exact": "E11.9", "phrase": "J18.9", "header": "E11"}[case]
                    valid = any(item["code"] == expected for item in result["candidates"])
                    if case == "header":
                        valid = valid and result["candidates"][0]["is_assignable"] is False
                valid = valid and result["service_date"] == date
                if not valid:
                    raise ValueError
                successes += 1
                latencies.append((time.monotonic() - before) * 1000)
            except Exception:
                errors += 1
                budget.reason = budget.reason or "tool_error"
                return

    await asyncio.gather(*(worker() for _ in range(workers)))
    elapsed = time.monotonic() - started
    ordered = sorted(latencies)

    def percentile(fraction):
        return (
            round(ordered[max(0, math.ceil(len(ordered) * fraction) - 1)], 3) if ordered else None
        )

    return {
        "concurrency": workers,
        "status": "passed" if successes == count and errors == 0 else "stopped",
        "completed_calls": successes,
        "errors": errors,
        "elapsed_seconds": round(elapsed, 3),
        "successful_calls_per_second": round(successes / elapsed, 3) if elapsed else 0,
        "p50_ms": percentile(0.5),
        "p95_ms": percentile(0.95),
        "p99_ms": percentile(0.99),
    }


async def run_benchmark(
    url: str,
    token: str,
    *,
    max_calls: int = 300,
    max_concurrency: int = 8,
    max_seconds: float = 120,
    service_dates: tuple[str, ...] = ("2026-04-01", "2026-10-01"),
    transport=None,
) -> dict:
    public_dates = {profile["release"]["effective_from"] for profile in PROFILES.values()}
    if (
        type(max_calls) is not int
        or not 1 <= max_calls <= 300
        or type(max_concurrency) is not int
        or not 1 <= max_concurrency <= 8
        or type(max_seconds) not in {int, float}
        or not math.isfinite(max_seconds)
        or not 0 < max_seconds <= 120
        or not service_dates
        or not set(service_dates) <= public_dates
    ):
        raise ValueError("Benchmark exceeds the approved public-workload budget.")
    started = time.monotonic()
    inner = transport if transport is not None else httpx.AsyncHTTPTransport(trust_env=False)
    budget = _BudgetHTTP(inner, started + max_seconds)
    client = ReferenceClient(url, token, transport=budget)
    levels = [level for level in (1, 2, 4, 8) if level <= min(max_concurrency, max_calls)]
    report = {
        "status": "failed",
        "levels": [],
        "completed_calls": 0,
        "errors": 0,
        "highest_tested_concurrency": 0,
        "capacity_guarantee": False,
        "ready_for_patient_data": False,
        "ready_for_clinical_use": False,
        "workloads": list(_CASES),
        "public_release_dates": list(service_dates),
        "measurement": "end_to_end_screened_client_including_connection_and_MCP_handshake",
        "limits": {
            "tool_calls": max_calls,
            "concurrency": max_concurrency,
            "seconds": max_seconds,
            "http_requests": 1000,
            "response_body_bytes": 20 * 1024 * 1024,
        },
    }
    try:
        for index, level in enumerate(levels):
            if budget.reason:
                break
            remaining = budget.deadline - time.monotonic()
            if remaining <= 0:
                budget.reason = "time_limit"
                break
            async with httpx.AsyncClient(
                transport=budget, trust_env=False, follow_redirects=False, timeout=remaining
            ) as probe:
                response = await asyncio.wait_for(
                    probe.get(urlsplit(url)._replace(path="/readyz").geturl()),
                    timeout=max(0, budget.deadline - time.monotonic()),
                )
                if response.status_code != 200 or response.json() != {"status": "ready"}:
                    budget.reason = "not_ready"
                    break
            count = max_calls // len(levels)
            if index == len(levels) - 1:
                count += max_calls % len(levels)
            workers = min(level, count)
            row = await _measure_level(client, budget, count, workers, service_dates)
            report["levels"].append(row)
            report["completed_calls"] += row["completed_calls"]
            report["errors"] += row["errors"]
            if row["status"] == "passed":
                report["highest_tested_concurrency"] = max(
                    report["highest_tested_concurrency"], workers
                )
        report["status"] = (
            "passed" if report["completed_calls"] == max_calls and not budget.reason else "stopped"
        )
    except TimeoutError:
        budget.reason = "time_limit"
        report["status"] = "stopped"
    except Exception:
        budget.reason = budget.reason or "benchmark_unavailable"
        report["status"] = "stopped"
    finally:
        if transport is None:
            await inner.aclose()
    report.update(
        stop_reason=budget.reason,
        http_requests=budget.requests,
        response_bytes=budget.bytes,
        elapsed_seconds=round(time.monotonic() - started, 3),
    )
    return report


def main():
    parser = SafeArgumentParser(
        description="Bounded fixed public cases; run only on an authorized target."
    )
    parser.add_argument("--url", required=True)
    parser.add_argument("--authorized-target", action="store_true", required=True)
    parser.add_argument("--max-calls", type=int, default=300)
    parser.add_argument("--max-concurrency", type=int, default=8)
    parser.add_argument("--seconds", type=float, default=120)
    parser.add_argument("--date", action="append", choices=["2026-04-01", "2026-10-01"])
    args = parser.parse_args()
    for name in ("mcp", "httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    try:
        report = asyncio.run(
            run_benchmark(
                args.url,
                os.environ["ICD10_DEMO_TOKEN"],
                max_calls=args.max_calls,
                max_concurrency=args.max_concurrency,
                max_seconds=args.seconds,
                service_dates=tuple(args.date or ("2026-04-01", "2026-10-01")),
            )
        )
    except Exception:
        report = {
            "status": "invalid_request",
            "message": "Benchmark input or configuration unavailable; no raw details returned.",
            "capacity_guarantee": False,
            "ready_for_patient_data": False,
        }
    print(json.dumps(report, indent=2))
    if report["status"] != "passed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
