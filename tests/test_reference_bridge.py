import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path, PureWindowsPath

import pytest
import uvicorn
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from icd10_mcp.demo import create_demo_app

TOKEN = "synthetic-demo-token-not-a-real-secret-123456"


@pytest.fixture
def reference_endpoint(catalog_path):
    records = []
    app = create_demo_app(catalog_path, token=TOKEN, hostname="127.0.0.1")

    async def observed(scope, receive, send):
        if scope["type"] != "http":
            return await app(scope, receive, send)
        record = {"path": scope["path"], "body": b""}
        records.append(record)

        async def received():
            message = await receive()
            if message["type"] == "http.request":
                record["body"] += message.get("body", b"")
            return message

        await app(scope, received, send)

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.setblocking(False)
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(observed, log_level="critical", access_log=False))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            for _ in range(200):
                if server.started:
                    break
                time.sleep(0.01)
            assert server.started
            yield f"http://127.0.0.1:{port}/mcp", records
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            assert not thread.is_alive()


def test_screened_stdio_bridge_blocks_locally_and_forwards_public_tools(
    tmp_path, reference_endpoint
):
    url, records = reference_endpoint
    token_file = tmp_path / "token"
    token_file.write_text(TOKEN)
    token_file.chmod(0o600)
    example = json.loads(
        (
            Path(__file__).resolve().parents[1] / "examples/claude-desktop.mac.example.json"
        ).read_text()
    )["mcpServers"]["icd10-reference"]
    assert set(example["env"]) == {"ICD10_REFERENCE_URL", "ICD10_REFERENCE_TOKEN_FILE"}
    example["command"] = sys.executable
    example["env"].update(
        {
            "ICD10_REFERENCE_URL": url,
            "ICD10_REFERENCE_TOKEN_FILE": str(token_file),
            "ICD10_CATALOG": str(tmp_path / "must-not-need-a-catalog.sqlite3"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    parameters = StdioServerParameters(**example, cwd=str(tmp_path))
    with tempfile.TemporaryFile(mode="w+") as errors:

        async def run():
            async with stdio_client(parameters, errlog=errors) as (read, write):
                async with ClientSession(read, write) as session:
                    initialized = await session.initialize()
                    assert initialized.serverInfo.name == "ICD10 Reference MCP (screened bridge)"
                    tools = (await session.list_tools()).tools
                    assert sorted(tool.name for tool in tools) == [
                        "phrase_search",
                        "validate_selected_codes",
                    ]
                    assert all("note" not in tool.inputSchema["properties"] for tool in tools)
                    blocked = await session.call_tool(
                        "phrase_search",
                        {
                            "query": "avery@example.invalid pneumonia",
                            "service_date": "2026-09-30",
                        },
                    )
                    assert blocked.structuredContent["status"] == "privacy_blocked"
                    assert "avery@example.invalid" not in str(blocked)
                    assert records == []
                    for name, arguments in (
                        ("phrase_search", {"query": ["avery@example.invalid"]}),
                        ("phrase_search", {"query": "pneumonia", "limit": "avery@example.invalid"}),
                        ("phrase_search", {"query": "pneumonia", "note": "avery@example.invalid"}),
                        ("validate_selected_codes", {"codes": [{"name": "avery@example.invalid"}]}),
                    ):
                        invalid = await session.call_tool(
                            name, {"service_date": "2026-09-30", **arguments}
                        )
                        assert "avery@example.invalid" not in str(invalid)
                        assert invalid.isError
                        assert invalid.content[0].text == "Invalid public terminology arguments."
                        assert records == []
                    phrase = await session.call_tool(
                        "phrase_search",
                        {
                            "query": "pneumonia",
                            "service_date": "2026-09-30",
                        },
                    )
                    assert phrase.structuredContent["candidates"][0]["code"] == "J18.9"
                    assert phrase.structuredContent["service_date"] == "2026-09-30"
                    assert (
                        phrase.structuredContent["privacy"]["remote_service_date"] == "2026-04-01"
                    )
                    valid = await session.call_tool(
                        "validate_selected_codes",
                        {
                            "codes": ["E11.9"],
                            "service_date": "2026-09-30",
                        },
                    )
                    assert (
                        valid.structuredContent["results"][0]["code_validity"]["status"] == "valid"
                    )

        asyncio.run(run())
        errors.seek(0)
        captured = errors.read()
    assert TOKEN not in captured
    assert "avery@example.invalid" not in captured
    assert records
    assert all(b"2026-09-30" not in item["body"] for item in records)
    assert all(b"avery@example.invalid" not in item["body"] for item in records)


def test_bridge_startup_rejects_bad_configuration_without_echoing_secrets(tmp_path):
    token_file = tmp_path / "PRIVATE-token"
    token_file.write_text(TOKEN)
    token_file.chmod(0o600)
    for url, path in (
        ("https://PRIVATE-user:PRIVATE-password@example.invalid/mcp", token_file),
        ("https://example.invalid/mcp", tmp_path / "PRIVATE-missing"),
        ("http://example.invalid/mcp", token_file),
    ):
        result = subprocess.run(
            [sys.executable, "-m", "icd10_mcp.reference_bridge"],
            env={**os.environ, "ICD10_REFERENCE_URL": url, "ICD10_REFERENCE_TOKEN_FILE": str(path)},
            input="",
            capture_output=True,
            text=True,
            timeout=10,
            cwd=tmp_path,
        )
        assert result.returncode == 2
        assert result.stdout == ""
        assert result.stderr == (
            "Reference bridge startup failed: configure URL and private token file.\n"
        )
        assert TOKEN not in result.stderr
        assert "PRIVATE-" not in result.stderr


def test_desktop_examples_use_absolute_paths_without_embedded_credentials():
    directory = Path(__file__).resolve().parents[1] / "examples"
    for platform, path_type in (("mac", Path), ("windows", PureWindowsPath)):
        entry = json.loads((directory / f"claude-desktop.{platform}.example.json").read_text())[
            "mcpServers"
        ]["icd10-reference"]
        assert path_type(entry["command"]).is_absolute()
        assert entry["args"] == ["-m", "icd10_mcp.reference_bridge"]
        assert set(entry["env"]) == {"ICD10_REFERENCE_URL", "ICD10_REFERENCE_TOKEN_FILE"}
        assert entry["env"]["ICD10_REFERENCE_URL"] == "https://icd10-reference-mcp.onrender.com/mcp"
        assert path_type(entry["env"]["ICD10_REFERENCE_TOKEN_FILE"]).is_absolute()
