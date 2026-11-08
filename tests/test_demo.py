import asyncio
import os
import subprocess
import sys

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

TOKEN = "synthetic-demo-token-not-a-real-secret-123456"


def test_demo_rejects_missing_or_query_string_credentials_but_allows_health(catalog_path):
    from icd10_mcp.demo import create_demo_app

    async def run():
        app = create_demo_app(catalog_path, token=TOKEN, hostname="trial.onrender.com")
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="https://trial.onrender.com",
            ) as client:
                assert (await client.get("/healthz")).json() == {"status": "alive"}
                assert (await client.get("/readyz")).status_code == 200
                for url in ["/mcp", f"/mcp?token={TOKEN}"]:
                    response = await client.post(url, json={})
                    assert response.status_code == 401
                    assert response.headers["www-authenticate"] == "Bearer"
                    assert response.json() == {"status": "unauthorized"}
                    assert TOKEN not in response.text

    asyncio.run(run())


def test_python_demo_check_uses_authenticated_mcp_and_reports_only_technical_success(catalog_path):
    from icd10_mcp.demo import create_demo_app
    from icd10_mcp.demo_client import check_demo

    async def run():
        app = create_demo_app(catalog_path, token=TOKEN, hostname="trial.onrender.com")
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="https://trial.onrender.com",
                headers={"Authorization": f"Bearer {TOKEN}"},
            ) as client:
                report = await check_demo(
                    "https://trial.onrender.com/mcp", "2026-04-01", http_client=client
                )
                assert report["status"] == "passed"
                assert report["release"]["id"] == "icd10cm-2026-04-01"
                assert report["ready_for_clinical_use"] is False
                assert report["ready_for_patient_data"] is False
                assert report["checks"] == [
                    "tool_listing",
                    "exact_code",
                    "phrase_lookup",
                    "header_not_assignable",
                    "selected_code_validity",
                ]
                assert TOKEN not in str(report)

    asyncio.run(run())


def test_demo_startup_fails_closed_without_catalogs_and_does_not_echo_secrets(tmp_path):
    missing = tmp_path / "PRIVATE-CATALOG-MARKER.json"
    result = subprocess.run(
        [sys.executable, "-m", "icd10_mcp.demo"],
        env={
            **os.environ,
            "ICD10_DEMO_TOKEN": TOKEN,
            "ICD10_DEMO_HOSTNAME": "127.0.0.1",
            "ICD10_CATALOGS": str(missing),
        },
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert "Demo startup check failed" in result.stderr
    assert TOKEN not in result.stdout + result.stderr
    assert "PRIVATE-CATALOG-MARKER" not in result.stdout + result.stderr
    assert not missing.exists()


def test_authenticated_demo_supports_real_mcp_client_without_note_tools(catalog_path):
    from icd10_mcp.demo import create_demo_app

    async def run():
        app = create_demo_app(catalog_path, token=TOKEN, hostname="trial.onrender.com")
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="https://trial.onrender.com",
                headers={"Authorization": f"Bearer {TOKEN}"},
            ) as client:
                async with streamable_http_client(
                    "https://trial.onrender.com/mcp", http_client=client
                ) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        listing = await session.list_tools()
                        assert {item.name for item in listing.tools} == {
                            "phrase_search",
                            "validate_selected_codes",
                        }
                        assert all(
                            "note" not in item.inputSchema["properties"] for item in listing.tools
                        )
                        result = await session.call_tool(
                            "phrase_search",
                            {"query": "pneumonia", "service_date": "2026-04-01"},
                        )
                        assert not result.isError
                        assert result.structuredContent["candidates"][0]["code"] == "J18.9"

    asyncio.run(run())


@pytest.mark.parametrize(
    "content_type",
    ["SYNTHETIC-HEADER-MARKER", "Application/JSON; marker=SYNTHETIC-HEADER-MARKER"],
)
def test_demo_does_not_log_untrusted_content_type_values(catalog_path, caplog, content_type):
    from icd10_mcp.demo import create_demo_app

    async def run():
        app = create_demo_app(catalog_path, token=TOKEN, hostname="trial.onrender.com")
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="https://trial.onrender.com",
                headers={"Authorization": f"Bearer {TOKEN}"},
            ) as client:
                result = await client.post(
                    "/mcp",
                    content="{}",
                    headers={
                        "Content-Type": content_type,
                        "Accept": "application/json, text/event-stream",
                    },
                )
                assert result.status_code == 400
                assert "SYNTHETIC-HEADER-MARKER" not in result.text

    asyncio.run(run())
    assert "SYNTHETIC-HEADER-MARKER" not in caplog.text


def test_demo_rejects_wrong_tokens_hosts_origins_duplicate_credentials_and_large_bodies(
    catalog_path,
):
    from icd10_mcp.demo import create_demo_app

    async def run():
        app = create_demo_app(catalog_path, token=TOKEN, hostname="trial.onrender.com")
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="https://trial.onrender.com",
            ) as client:
                assert (
                    await client.post("/mcp", json={}, headers={"Authorization": "Bearer wrong"})
                ).status_code == 401
                assert (
                    await client.post(
                        "/mcp",
                        json={},
                        headers=[
                            ("Authorization", f"Bearer {TOKEN}"),
                            ("Authorization", f"Bearer {TOKEN}"),
                        ],
                    )
                ).status_code == 401
                assert (
                    await client.get("/healthz", headers={"Host": "attacker.invalid"})
                ).status_code == 400
                authorized = {"Authorization": f"Bearer {TOKEN}"}
                assert (
                    await client.post(
                        "/mcp",
                        json={},
                        headers={**authorized, "Origin": "https://attacker.invalid"},
                    )
                ).status_code == 403
                assert (
                    await client.post(
                        "/mcp",
                        content="x" * 65_537,
                        headers={**authorized, "Content-Type": "application/json"},
                    )
                ).status_code == 413

    asyncio.run(run())


@pytest.mark.parametrize(
    ("token", "hostname"),
    [("", "trial.onrender.com"), ("short", "trial.onrender.com"), (TOKEN, "*.onrender.com")],
)
def test_demo_refuses_unsafe_authentication_or_hostname_configuration(
    catalog_path, token, hostname
):
    from icd10_mcp.demo import create_demo_app

    with pytest.raises(ValueError):
        create_demo_app(catalog_path, token=token, hostname=hostname)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/mcp",
        "https://user:PRIVATE-URL-MARKER@example.com/mcp",
        "https://example.com/mcp?token=PRIVATE-URL-MARKER",
    ],
)
def test_demo_client_rejects_unsafe_endpoints_without_printing_credentials(url):
    result = subprocess.run(
        [sys.executable, "-m", "icd10_mcp.demo_client", "--url", url, "--date", "2026-10-01"],
        env={**os.environ, "ICD10_DEMO_TOKEN": TOKEN},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert '"status": "failed"' in result.stdout
    assert "PRIVATE-URL-MARKER" not in result.stdout + result.stderr
    assert TOKEN not in result.stdout + result.stderr
