import asyncio

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from icd10_mcp.demo import create_demo_app

URL = "https://trial.onrender.com/mcp"


def test_public_opt_in_supports_note_free_mcp_without_credentials(catalog_path):
    async def run():
        app = create_demo_app(catalog_path, hostname="trial.onrender.com", public_access=True)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="https://trial.onrender.com"
            ) as client:
                async with streamable_http_client(URL, http_client=client) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        initialized = await session.initialize()
                        assert initialized.serverInfo.name == "ICD10 Reference MCP"
                        tools = (await session.list_tools()).tools
                        assert sorted(tool.name for tool in tools) == [
                            "phrase_search",
                            "validate_selected_codes",
                        ]
                        assert all("note" not in tool.inputSchema["properties"] for tool in tools)
                        result = await session.call_tool(
                            "phrase_search",
                            {"query": "pneumonia", "service_date": "2026-04-01"},
                        )
                        assert not result.isError
                        assert result.structuredContent["candidates"][0]["code"] == "J18.9"
                        assert result.structuredContent["candidates"][0]["description"] == (
                            "Synthetic pneumonia, unspecified"
                        )
                        blocked = await session.call_tool(
                            "phrase_search",
                            {"query": ["avery@example.invalid"], "service_date": "2026-04-01"},
                        )
                        assert blocked.isError
                        assert "avery@example.invalid" not in str(blocked)
                        validated = await session.call_tool(
                            "validate_selected_codes",
                            {"codes": ["E11.9"], "service_date": "2026-04-01"},
                        )
                        assert (
                            validated.structuredContent["results"][0]["code_validity"]["status"]
                            == "valid"
                        )

    asyncio.run(run())


def test_public_oversized_response_is_replaced_not_partially_sent(catalog_path):
    from icd10_mcp.public_http import PublicLimits

    async def run():
        app = create_demo_app(
            catalog_path,
            hostname="trial.onrender.com",
            public_access=True,
            public_limits=PublicLimits(max_response_bytes=128),
        )
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="https://trial.onrender.com"
            ) as client:
                response = await client.post(
                    "/mcp",
                    headers={"Accept": "application/json, text/event-stream"},
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2025-11-25",
                            "capabilities": {},
                            "clientInfo": {"name": "public-budget-test", "version": "1"},
                        },
                    },
                )
                assert response.status_code == 503
                assert response.json() == {"status": "response_too_large"}
                assert "serverInfo" not in response.text
                assert len(response.content) < 128

    asyncio.run(run())


def test_public_request_quota_recovers_and_does_not_disable_health(catalog_path):
    from icd10_mcp.public_http import PublicLimits

    async def run():
        app = create_demo_app(
            catalog_path,
            hostname="trial.onrender.com",
            public_access=True,
            public_limits=PublicLimits(requests_per_window=2, window_seconds=0.5),
        )
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="https://trial.onrender.com"
            ) as client:
                for _ in range(2):
                    assert (await client.post("/mcp", content="")).status_code == 400
                limited = await client.post("/mcp", content="")
                assert limited.status_code == 429
                assert limited.json() == {"status": "rate_limited"}
                assert int(limited.headers["retry-after"]) >= 1
                assert (await client.get("/healthz")).json() == {"status": "alive"}
                assert (await client.get("/readyz")).status_code == 200
                await asyncio.sleep(0.55)
                assert (await client.post("/mcp", content="")).status_code == 400

    asyncio.run(run())


def test_public_request_body_cap_handles_declared_and_chunked_payloads(catalog_path, caplog):
    async def run():
        app = create_demo_app(catalog_path, hostname="trial.onrender.com", public_access=True)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="https://trial.onrender.com"
            ) as client:
                body = b"PRIVATE-BODY-MARKER".ljust(8193, b"x")

                async def chunks():
                    yield body[:4096]
                    yield body[4096:]

                for content in (body, chunks()):
                    response = await client.post(
                        "/mcp", content=content, headers={"Content-Type": "application/json"}
                    )
                    assert response.status_code == 413
                    assert response.json() == {"status": "request_too_large"}
                    assert "PRIVATE-BODY-MARKER" not in response.text
        assert "PRIVATE-BODY-MARKER" not in caplog.text

    asyncio.run(run())


def test_public_inflight_limit_rejects_and_then_releases_capacity(catalog_path):
    from icd10_mcp.public_http import PublicLimits

    async def run():
        app = create_demo_app(
            catalog_path,
            hostname="trial.onrender.com",
            public_access=True,
            public_limits=PublicLimits(max_in_flight=1),
        )
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="https://trial.onrender.com"
            ) as client:
                started, finish = asyncio.Event(), asyncio.Event()

                async def slow_body():
                    yield b"{"
                    started.set()
                    await finish.wait()
                    yield b"}"

                first = asyncio.create_task(client.post("/mcp", content=slow_body()))
                try:
                    await asyncio.wait_for(started.wait(), 2)
                    busy = await client.post("/mcp", content="")
                    assert busy.status_code == 503
                    assert busy.json() == {"status": "busy"}
                    assert busy.headers["retry-after"] == "1"
                    assert (await client.get("/readyz")).status_code == 200
                finally:
                    finish.set()
                    await first
                assert (await client.post("/mcp", content="")).status_code == 400

    asyncio.run(run())


def test_public_deadline_cancels_stalled_body_and_releases_capacity(catalog_path, caplog):
    from icd10_mcp.public_http import PublicLimits

    async def run():
        app = create_demo_app(
            catalog_path,
            hostname="trial.onrender.com",
            public_access=True,
            public_limits=PublicLimits(max_in_flight=1, request_timeout_seconds=0.02),
        )
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="https://trial.onrender.com"
            ) as client:

                async def stalled():
                    yield b"PRIVATE-SLOW-MARKER"
                    await asyncio.Event().wait()

                response = await asyncio.wait_for(client.post("/mcp", content=stalled()), 1)
                assert response.status_code == 504
                assert response.json() == {"status": "request_timed_out"}
                assert "PRIVATE-SLOW-MARKER" not in response.text
                assert (await client.post("/mcp", content="")).status_code == 400
        assert "PRIVATE-SLOW-MARKER" not in caplog.text

    asyncio.run(run())


def test_public_protocol_failures_never_echo_envelope_or_header_values(catalog_path, caplog):
    async def run():
        app = create_demo_app(catalog_path, hostname="trial.onrender.com", public_access=True)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="https://trial.onrender.com",
                headers={"Accept": "application/json, text/event-stream"},
            ) as client:
                for payload, headers in (
                    (
                        {"jsonrpc": "2.0", "id": 1, "method": {"name": "PRIVATE-PROTOCOL-MARKER"}},
                        {},
                    ),
                    (
                        {"jsonrpc": "2.0", "id": 1, "method": "ping"},
                        {"MCP-Protocol-Version": "PRIVATE-HEADER-MARKER"},
                    ),
                ):
                    response = await client.post("/mcp", json=payload, headers=headers)
                    assert response.status_code == 400
                    assert "PRIVATE-PROTOCOL-MARKER" not in response.text
                    assert "PRIVATE-HEADER-MARKER" not in response.text
                    assert response.json() == {"status": "invalid_request"}
        assert "PRIVATE-PROTOCOL-MARKER" not in caplog.text
        assert "PRIVATE-HEADER-MARKER" not in caplog.text

    asyncio.run(run())
