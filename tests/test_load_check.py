import asyncio
import json
import os
import subprocess
import sys

import httpx
import pytest

from icd10_mcp.demo import create_demo_app

TOKEN = "synthetic-demo-token-not-a-real-secret-123456"
URL = "https://trial.onrender.com/mcp"


def test_load_check_runs_only_bounded_public_workloads(catalog_path):
    from icd10_mcp.load_check import run_benchmark

    async def run():
        app = create_demo_app(catalog_path, token=TOKEN, hostname="trial.onrender.com")
        async with app.router.lifespan_context(app):
            report = await run_benchmark(
                URL,
                TOKEN,
                max_calls=12,
                max_concurrency=2,
                max_seconds=15,
                service_dates=("2026-04-01",),
                transport=httpx.ASGITransport(app=app),
            )
        assert report["status"] == "passed"
        assert report["completed_calls"] == 12
        assert report["errors"] == 0
        assert [row["concurrency"] for row in report["levels"]] == [1, 2]
        assert report["highest_tested_concurrency"] == 2
        assert 0 < report["http_requests"] <= 1000
        assert report["response_bytes"] <= 20 * 1024 * 1024
        assert report["capacity_guarantee"] is False
        assert report["ready_for_patient_data"] is False
        assert TOKEN not in json.dumps(report)
        for row in report["levels"]:
            assert row["p95_ms"] >= row["p50_ms"] >= 0

    asyncio.run(run())


def test_load_check_rejects_excessive_budgets_before_network():
    from icd10_mcp.load_check import run_benchmark

    def outside(request):
        raise AssertionError("Invalid budgets must not contact a service.")

    async def run():
        for settings in (
            {"max_calls": 301},
            {"max_concurrency": 9},
            {"max_seconds": 121},
            {"max_calls": 0},
            {"service_dates": ("2000-01-01",)},
        ):
            with pytest.raises(ValueError):
                await run_benchmark(URL, TOKEN, transport=httpx.MockTransport(outside), **settings)

    asyncio.run(run())


def test_load_check_stops_before_next_level_when_readiness_fails(catalog_path):
    from icd10_mcp.load_check import run_benchmark

    class HealthChanges(httpx.AsyncBaseTransport):
        def __init__(self, app):
            self.inner = httpx.ASGITransport(app=app)
            self.probes = 0

        async def handle_async_request(self, request):
            if request.url.path == "/readyz":
                self.probes += 1
                if self.probes > 1:
                    return httpx.Response(503, json={"status": "not_ready"})
            return await self.inner.handle_async_request(request)

    async def run():
        app = create_demo_app(catalog_path, token=TOKEN, hostname="trial.onrender.com")
        async with app.router.lifespan_context(app):
            report = await run_benchmark(
                URL,
                TOKEN,
                max_calls=8,
                max_concurrency=2,
                max_seconds=15,
                service_dates=("2026-04-01",),
                transport=HealthChanges(app),
            )
        assert report["status"] == "stopped"
        assert report["stop_reason"] == "not_ready"
        assert report["completed_calls"] == 4
        assert report["highest_tested_concurrency"] == 1

    asyncio.run(run())


def test_benchmark_command_rejects_unapproved_budget_without_echoing_values():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "icd10_mcp.load_check",
            "--url",
            URL,
            "--authorized-target",
            "--max-calls",
            "301",
        ],
        env={**os.environ, "ICD10_DEMO_TOKEN": TOKEN},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "invalid_request"
    assert TOKEN not in result.stdout + result.stderr


def test_load_check_cancels_stalled_readiness_at_its_absolute_deadline():
    from icd10_mcp.load_check import run_benchmark

    cancelled = []

    async def outside(request):
        try:
            await asyncio.sleep(0.5)
            return httpx.Response(200, json={"status": "ready"})
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    report = asyncio.run(
        run_benchmark(
            URL,
            TOKEN,
            max_calls=1,
            max_seconds=0.05,
            transport=httpx.MockTransport(outside),
        )
    )
    assert cancelled == [True]
    assert report["status"] == "stopped"
    assert report["stop_reason"] == "time_limit"
    assert report["completed_calls"] == 0
