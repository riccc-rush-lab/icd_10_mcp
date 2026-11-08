import asyncio
import json
import os
import socket
import subprocess
import sys
import time

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


def test_loopback_http_real_mcp_client_has_lookup_but_no_note_input(catalog_path):
    from icd10_mcp.server import create_http_app

    async def run():
        app = create_http_app(catalog_path)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://127.0.0.1:8000",
            ) as client:
                assert (await client.get("/healthz")).json() == {"status": "alive"}
                assert (await client.get("/readyz")).status_code == 200
                async with streamable_http_client(
                    "http://127.0.0.1:8000/mcp",
                    http_client=client,
                ) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        listing = await session.list_tools()
                        assert {tool.name for tool in listing.tools} == {
                            "phrase_search",
                            "validate_selected_codes",
                        }
                        assert all(
                            "note" not in tool.inputSchema["properties"] for tool in listing.tools
                        )
                        result = await session.call_tool(
                            "phrase_search",
                            {
                                "query": "Pneumonia",
                                "service_date": "2026-04-01",
                            },
                        )
                        assert result.structuredContent["candidates"][0]["code"] == "J18.9"

    asyncio.run(run())


def test_startup_rejects_missing_catalog_without_creating_it(tmp_path):
    path = tmp_path / "missing.sqlite3"
    env = dict(os.environ, ICD10_CATALOG=str(path), ICD10_TRANSPORT="stdio")
    env.pop("ICD10_CATALOGS", None)
    result = subprocess.run(
        [sys.executable, "-m", "icd10_mcp.server"],
        input="",
        text=True,
        capture_output=True,
        env=env,
        timeout=10,
    )
    assert result.returncode == 2
    assert str(path) not in result.stderr
    assert "startup" in result.stderr.lower()
    assert not path.exists()


def test_http_entrypoint_uses_explicit_catalog_config_and_loopback_only(tmp_path, catalog_path):
    config = tmp_path / "catalogs.json"
    config.write_text(json.dumps({"icd10cm-2026-04-01": str(catalog_path)}))
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    env = dict(
        os.environ,
        ICD10_CATALOGS=str(config),
        ICD10_CATALOG=str(tmp_path / "unused"),
        ICD10_TRANSPORT="streamable-http",
        ICD10_PORT=str(port),
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "icd10_mcp.server"],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False) as client:
            for _ in range(100):
                assert process.poll() is None, "Server exited instead of starting local HTTP"
                try:
                    assert client.get("/readyz", timeout=1).status_code == 200
                    break
                except httpx.ConnectError:
                    time.sleep(0.05)
            else:
                raise AssertionError("Loopback HTTP startup timed out")
            assert client.get("/healthz", headers={"host": "attacker.invalid"}).status_code == 400

        async def invalid_request():
            async with httpx.AsyncClient(trust_env=False) as client:
                async with streamable_http_client(
                    f"http://127.0.0.1:{port}/mcp",
                    http_client=client,
                ) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(
                            "phrase_search",
                            {
                                "query": {"marker": "SYNTHETIC-SECRET-TOKEN"},
                                "service_date": "2026-04-01",
                            },
                        )
                        assert result.isError

        asyncio.run(invalid_request())
    finally:
        process.terminate()
        stdout, stderr = process.communicate(timeout=10)
    assert "SYNTHETIC-SECRET-TOKEN" not in stdout + stderr


def test_unavailable_catalog_is_not_ready_and_http_rejects_origin_and_large_body(tmp_path):
    from icd10_mcp.server import create_http_app

    async def run():
        app = create_http_app(tmp_path / "missing")
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://127.0.0.1:8000",
            ) as client:
                assert (await client.get("/healthz")).status_code == 200
                assert (await client.get("/readyz")).status_code == 503
                headers = {
                    "content-type": "application/json",
                    "accept": "application/json, text/event-stream",
                }
                response = await client.post(
                    "/mcp",
                    content="{}",
                    headers=dict(headers, origin="https://attacker.invalid"),
                )
                assert response.status_code == 403
                response = await client.post("/mcp", content="x" * 65_537, headers=headers)
                assert response.status_code == 413

    asyncio.run(run())
