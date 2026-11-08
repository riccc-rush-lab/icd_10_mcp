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


class RecordingHTTP(httpx.AsyncBaseTransport):
    """Observe the external HTTP interface while using the real MCP application."""

    def __init__(self, app):
        self.inner = httpx.ASGITransport(app=app)
        self.requests = []

    async def handle_async_request(self, request):
        self.requests.append((str(request.url), bytes(request.content)))
        return await self.inner.handle_async_request(request)


def test_local_client_blocks_email_before_network_but_preserves_phrase_lookup(catalog_path):
    from icd10_mcp.reference_client import ReferenceClient

    async def run():
        app = create_demo_app(catalog_path, token=TOKEN, hostname="trial.onrender.com")
        transport = RecordingHTTP(app)
        client = ReferenceClient(URL, TOKEN, transport=transport)
        async with app.router.lifespan_context(app):
            blocked = await client.lookup("avery@example.invalid pneumonia", "2026-04-01")
            assert blocked["status"] == "privacy_blocked"
            assert "avery@example.invalid" not in json.dumps(blocked)
            assert transport.requests == []
            result = await client.lookup("pneumonia", "2026-04-01")
            assert result["candidates"][0]["code"] == "J18.9"
            assert transport.requests
            assert all(b"avery@example.invalid" not in body for _, body in transport.requests)

    asyncio.run(run())


def test_local_client_blocks_identifier_and_note_forms_without_echoing_or_sending_them():
    from icd10_mcp.reference_client import ReferenceClient

    requests = []

    def outside(request):
        requests.append(request)
        raise AssertionError("No network request is allowed for blocked input.")

    async def run():
        client = ReferenceClient(URL, TOKEN, transport=httpx.MockTransport(outside))
        for text in (
            "Call (202) 555-0142 about pneumonia",
            "SSN 123-45-6789 pneumonia",
            "DOB: 2000-01-01 pneumonia",
            "MRN: 987654321 pneumonia",
            "Name: Avery Example pneumonia",
            "Patient Avery Example has pneumonia",
            "Avery Example pneumonia",
            "123 Example Street pneumonia",
            "https://example.invalid/patient/123",
            "pneumonia\nDOB 2000-01-01",
            "avery＠example.invalid pneumonia",
            "avery\u200b@example.invalid pneumonia",
        ):
            result = await client.lookup(text, "2026-04-01")
            assert result["status"] == "privacy_blocked"
            assert text not in json.dumps(result)
            assert result["privacy"]["pii_absence_guaranteed"] is False
        assert requests == []

    asyncio.run(run())


def test_public_eponyms_and_common_terms_are_not_blocked(catalog_path):
    from icd10_mcp.reference_client import ReferenceClient

    async def run():
        app = create_demo_app(catalog_path, token=TOKEN, hostname="trial.onrender.com")
        client = ReferenceClient(URL, TOKEN, transport=httpx.ASGITransport(app=app))
        async with app.router.lifespan_context(app):
            for query in (
                "E11.9",
                "pneumonia",
                "Parkinson Disease",
                "Hodgkin lymphoma",
                "Down Syndrome",
                "Wolff Parkinson White syndrome",
                "HIV AIDS",
                "Type II Diabetes",
                "Chronic Kidney Disease",
                "Abscess Mastoid",
            ):
                result = await client.lookup(query, "2026-04-01")
                assert result["status"] in {"candidates", "abstain", "needs_clarification"}
                assert result["release"]["id"] == "icd10cm-2026-04-01"
                assert result["privacy"]["pii_absence_guaranteed"] is False

    asyncio.run(run())


def test_local_client_keeps_original_date_local_and_sends_public_release_anchor(catalog_path):
    from icd10_mcp.reference_client import ReferenceClient

    async def run():
        app = create_demo_app(catalog_path, token=TOKEN, hostname="trial.onrender.com")
        transport = RecordingHTTP(app)
        client = ReferenceClient(URL, TOKEN, transport=transport)
        async with app.router.lifespan_context(app):
            result = await client.lookup("E11.9", "2026-09-30")
            assert result["candidates"][0]["code"] == "E11.9"
            assert result["service_date"] == "2026-09-30"
            calls = [
                json.loads(body)
                for _, body in transport.requests
                if body and json.loads(body).get("method") == "tools/call"
            ]
            assert calls[0]["params"]["arguments"]["service_date"] == "2026-04-01"
            assert all(b"2026-09-30" not in body for _, body in transport.requests)

    asyncio.run(run())


def test_selected_codes_block_identifiers_but_preserve_validation(catalog_path):
    from icd10_mcp.reference_client import ReferenceClient

    async def run():
        app = create_demo_app(catalog_path, token=TOKEN, hostname="trial.onrender.com")
        transport = RecordingHTTP(app)
        client = ReferenceClient(URL, TOKEN, transport=transport)
        async with app.router.lifespan_context(app):
            blocked = await client.validate(["Avery Example"], "2026-09-30")
            assert blocked["status"] == "privacy_blocked"
            assert "Avery Example" not in json.dumps(blocked)
            assert transport.requests == []
            result = await client.validate(["E11.9", "A00..1"], "2026-09-30")
            assert result["results"][0]["code_validity"]["status"] == "valid"
            assert result["results"][1]["code_validity"]["status"] == "invalid_format"
            assert all(b"2026-09-30" not in body for _, body in transport.requests)

    asyncio.run(run())


def test_remote_configuration_rejects_credentialed_or_unsafe_targets_without_echoing():
    from icd10_mcp.reference_client import ReferenceClient

    for url in (
        "http://example.invalid/mcp",
        "https://user:PRIVATE-URL-MARKER@example.invalid/mcp",
        "https://example.invalid/mcp?token=PRIVATE-URL-MARKER",
        "https://example.invalid/mcp#PRIVATE-URL-MARKER",
        "https://example.invalid/PRIVATE-URL-MARKER",
        "https://example.invalid:\n443/mcp",
    ):
        with pytest.raises(ValueError) as error:
            ReferenceClient(url, TOKEN)
        assert "PRIVATE-URL-MARKER" not in str(error.value)
    with pytest.raises(ValueError) as error:
        ReferenceClient(URL, "PRIVATE-TOKEN-MARKER")
    assert "PRIVATE-TOKEN-MARKER" not in str(error.value)


def test_client_command_reads_stdin_and_blocks_without_echoing_private_text():
    payload = json.dumps(
        {
            "operation": "lookup",
            "query": "avery@example.invalid pneumonia",
            "service_date": "2026-04-01",
        }
    )
    result = subprocess.run(
        [sys.executable, "-m", "icd10_mcp.reference_client", "--url", URL, "--public-terminology"],
        input=payload,
        env={**os.environ, "ICD10_DEMO_TOKEN": TOKEN},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "privacy_blocked"
    assert "avery@example.invalid" not in result.stdout + result.stderr
    invalid = subprocess.run(
        [
            sys.executable,
            "-m",
            "icd10_mcp.reference_client",
            "--url",
            URL,
            "--public-terminology",
            "--PRIVATE-CLI-MARKER",
        ],
        input=payload,
        env={**os.environ, "ICD10_DEMO_TOKEN": TOKEN},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert invalid.returncode == 2
    assert "PRIVATE-CLI-MARKER" not in invalid.stdout + invalid.stderr
    assert "avery@example.invalid" not in invalid.stdout + invalid.stderr


def test_invalid_limits_never_cross_the_network_or_echo_their_contents():
    from icd10_mcp.reference_client import ReferenceClient

    requests = []

    def outside(request):
        requests.append(request)
        return httpx.Response(503)

    async def run():
        client = ReferenceClient(URL, TOKEN, transport=httpx.MockTransport(outside))
        for limit in (0, 26, True, 1.5, "avery@example.invalid", {"note": "PRIVATE-LIMIT"}):
            result = await client.lookup("pneumonia", "2026-04-01", limit=limit)
            assert result["status"] == "invalid_request"
            assert "avery@example.invalid" not in str(result)
            assert "PRIVATE-LIMIT" not in str(result)
        assert requests == []

    asyncio.run(run())
