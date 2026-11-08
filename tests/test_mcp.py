import asyncio
import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from icd10_mcp.server import create_server


async def call_phrase(catalog_path, arguments):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "icd10_mcp.server"],
        env={**os.environ, "ICD10_CATALOG": str(catalog_path)},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool("phrase_search", arguments)


def test_stdio_phrase_lookup_returns_exact_candidate(catalog_path):
    result = asyncio.run(
        call_phrase(
            catalog_path,
            {
                "query": "Pneumonia",
                "service_date": "2026-04-01",
                "limit": 1,
            },
        )
    )
    assert not result.isError
    data = result.structuredContent
    assert data["status"] == "candidates"
    assert [item["code"] for item in data["candidates"]] == ["J18.9"]
    assert data["release"]["id"] == "icd10cm-2026-04-01"


def test_stdio_malformed_code_returns_structured_clarification(catalog_path):
    result = asyncio.run(
        call_phrase(
            catalog_path,
            {
                "query": "A00..1",
                "service_date": "2026-04-01",
            },
        )
    )
    assert not result.isError
    data = result.structuredContent
    assert data["status"] == "needs_clarification"
    assert data["code_validity"]["status"] == "invalid_format"
    assert data["candidates"] == []


@pytest.mark.parametrize(
    "arguments",
    [
        {"query": "Pneumonia"},
        {"query": ["Pneumonia"], "service_date": "2026-04-01"},
    ],
)
def test_stdio_invalid_arguments_are_protocol_errors_not_candidates(catalog_path, arguments):
    result = asyncio.run(call_phrase(catalog_path, arguments))
    assert result.isError
    assert not result.structuredContent or not result.structuredContent.get("candidates")


def test_tool_schemas_and_adapters(catalog_path):
    async def run():
        server = create_server(catalog_path)
        tools = await server.list_tools()
        assert {tool.name for tool in tools} == {
            "phrase_search",
            "suggest_candidates",
            "validate_selected_codes",
        }
        for tool in tools:
            assert tool.outputSchema
            assert "service_date" in tool.inputSchema["required"]
            assert tool.annotations.readOnlyHint
            assert not tool.annotations.openWorldHint
        _, result = await server.call_tool(
            "phrase_search",
            {"query": "A001", "service_date": "2026-04-01"},
        )
        assert result["candidates"][0]["code"] == "A00.1"

    asyncio.run(run())


def test_real_stdio_handshake_and_all_workflows(catalog_path):
    async def run():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "icd10_mcp.server"],
            env={**os.environ, "ICD10_CATALOG": str(catalog_path)},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listing = await session.list_tools()
                assert len(listing.tools) == 3
                for name, args, key in [
                    ("phrase_search", {"query": "A001"}, "candidates"),
                    ("suggest_candidates", {"note": "Pneumonia."}, "candidates"),
                    ("validate_selected_codes", {"codes": ["A001"]}, "results"),
                ]:
                    result = await session.call_tool(
                        name,
                        {**args, "service_date": "2026-04-01"},
                    )
                    assert not result.isError
                    assert result.structuredContent[key]
                unavailable = await session.call_tool(
                    "phrase_search",
                    {"query": "A001", "service_date": "2026-10-01"},
                )
                assert unavailable.structuredContent["status"] == "release_unavailable"
                assert not unavailable.structuredContent.get("candidates")

    asyncio.run(run())
