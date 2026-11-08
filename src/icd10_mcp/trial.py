"""Read-only local trial checks; never a clinical or privacy acceptance gate."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from tempfile import TemporaryFile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .catalog import DISCLAIMER, configured_catalog
from .releases import APRIL_ID, FY2027_ID
from .smoke import smoke_check


async def _probe_mcp(config: Path) -> dict:
    checks = []

    def check(condition, name):
        if not condition:
            raise ValueError(name)
        checks.append(name)

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "icd10_mcp.server"],
        env={
            "ICD10_CATALOGS": str(config.resolve()),
            "ICD10_TRANSPORT": "stdio",
            "PYTHONNOUSERSITE": "1",
        },
    )
    with TemporaryFile(mode="w+", encoding="utf-8") as errors:
        async with stdio_client(params, errlog=errors) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = sorted(tool.name for tool in (await session.list_tools()).tools)
                check(
                    tools == ["phrase_search", "suggest_candidates", "validate_selected_codes"],
                    "tool_listing",
                )

                async def search(query, day):
                    response = await session.call_tool(
                        "phrase_search", {"query": query, "service_date": day}
                    )
                    if response.isError or not isinstance(response.structuredContent, dict):
                        raise ValueError("lookup_failed")
                    return response.structuredContent

                for day, release, name in [
                    ("2026-09-30", APRIL_ID, "april_exact_code"),
                    ("2026-10-01", FY2027_ID, "fy2027_exact_code"),
                ]:
                    data = await search("E11.9", day)
                    check(
                        data["release"]["id"] == release
                        and data["candidates"][0]["code"] == "E11.9"
                        and data["candidates"][0]["is_assignable"] is True,
                        name,
                    )
                data = await search("pneumonia", "2026-10-01")
                check(
                    any(item["code"] == "J18.9" for item in data["candidates"]),
                    "phrase_lookup",
                )
                data = await search("E11", "2026-10-01")
                check(
                    data["candidates"][0]["code"] == "E11"
                    and data["candidates"][0]["is_assignable"] is False,
                    "header_not_assignable",
                )
                data = await search("C78.31", "2026-10-01")
                check(
                    data["release"]["id"] == FY2027_ID
                    and data["candidates"][0]["code"] == "C78.31",
                    "fy2027_only_code",
                )
                data = await search("C78.31", "2026-09-30")
                check(
                    data["release"]["id"] == APRIL_ID
                    and data["status"] == "abstain"
                    and data["candidates"] == [],
                    "april_rejects_future_code",
                )
                data = await search("A00..1", "2026-10-01")
                check(
                    data["status"] == "needs_clarification"
                    and data["code_validity"]["status"] == "invalid_format"
                    and data["candidates"] == [],
                    "malformed_code_clarification",
                )
                data = await search("E11.9", "2027-10-01")
                check(data["status"] == "release_unavailable", "unavailable_release")
                response = await session.call_tool(
                    "validate_selected_codes",
                    {"codes": ["E11.9"], "service_date": "2026-10-01"},
                )
                check(
                    not response.isError
                    and response.structuredContent["results"][0]["code_validity"]["status"]
                    == "valid",
                    "selected_code_validity",
                )
    return {"status": "passed", "transport": "stdio", "tools": tools, "checks": checks}


def check_local_trial(config: Path) -> dict:
    """Verify both full catalogs and a fresh official-client stdio session."""
    result = {
        "status": "not_ready",
        "ready_for_clinical_use": False,
        "ready_for_patient_data": False,
        "optional_nlp": "not_checked",
        "disclaimer": DISCLAIMER,
    }
    try:
        catalogs = configured_catalog("", config).catalogs
    except (OSError, ValueError, TypeError, KeyError):
        return {**result, "reason": "catalog_configuration_unavailable"}
    if set(catalogs) != {APRIL_ID, FY2027_ID}:
        return {**result, "reason": "both_releases_required"}
    result["catalogs"] = []
    for release in [APRIL_ID, FY2027_ID]:
        try:
            result["catalogs"].append(smoke_check(catalogs[release]))
        except Exception:
            return {**result, "reason": "full_catalog_check_failed", "failed_release": release}
    try:
        result["mcp"] = asyncio.run(asyncio.wait_for(_probe_mcp(config), timeout=45))
    except Exception:
        return {**result, "reason": "mcp_check_failed"}
    return {**result, "status": "ready_for_local_trial"}
