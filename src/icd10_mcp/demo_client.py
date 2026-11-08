"""Fixed synthetic/terminology checks using the official HTTP MCP client."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from datetime import date
from urllib.parse import urlsplit

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def check_demo(url: str, service_date: str, *, http_client: httpx.AsyncClient) -> dict:
    """Check an explicitly selected endpoint with a caller-owned authenticated client."""
    target = urlsplit(url)
    if (
        target.scheme not in {"http", "https"}
        or (target.scheme == "http" and target.hostname not in {"127.0.0.1", "localhost"})
        or not target.hostname
        or target.username is not None
        or target.password is not None
        or target.query
        or target.fragment
        or target.path != "/mcp"
        or date.fromisoformat(service_date).isoformat() != service_date
    ):
        raise ValueError("Invalid demo configuration")
    checks = []

    def check(condition, name):
        if not condition:
            raise ValueError(name)
        checks.append(name)

    async with streamable_http_client(url, http_client=http_client) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = sorted(item.name for item in (await session.list_tools()).tools)
            check(tools == ["phrase_search", "validate_selected_codes"], "tool_listing")

            async def search(query):
                response = await session.call_tool(
                    "phrase_search", {"query": query, "service_date": service_date}
                )
                if response.isError or not isinstance(response.structuredContent, dict):
                    raise ValueError("Lookup unavailable")
                return response.structuredContent

            exact = await search("E11.9")
            check(
                exact["candidates"][0]["code"] == "E11.9"
                and exact["candidates"][0]["is_assignable"] is True,
                "exact_code",
            )
            phrase = await search("pneumonia")
            check(any(item["code"] == "J18.9" for item in phrase["candidates"]), "phrase_lookup")
            header = await search("E11")
            check(
                header["candidates"][0]["code"] == "E11"
                and header["candidates"][0]["is_assignable"] is False,
                "header_not_assignable",
            )
            validation = await session.call_tool(
                "validate_selected_codes", {"codes": ["E11.9"], "service_date": service_date}
            )
            check(
                not validation.isError
                and validation.structuredContent["results"][0]["code_validity"]["status"]
                == "valid",
                "selected_code_validity",
            )
    return {
        "status": "passed",
        "checks": checks,
        "tools": tools,
        "release": exact["release"],
        "ready_for_clinical_use": False,
        "ready_for_patient_data": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Fixed terminology-only demo checks; no notes.")
    parser.add_argument(
        "--url", required=True, help="Explicit HTTPS /mcp URL; HTTP only on loopback"
    )
    parser.add_argument("--date", required=True, help="Explicit YYYY-MM-DD service date")
    args = parser.parse_args()
    logging.getLogger("mcp").setLevel(logging.CRITICAL)
    logging.getLogger("httpx").setLevel(logging.CRITICAL)

    async def run():
        token = os.environ["ICD10_DEMO_TOKEN"]
        if not token or len(token) > 258 or not token.isascii() or any(c.isspace() for c in token):
            raise ValueError
        async with httpx.AsyncClient(
            headers={"Authorization": f"Bearer {token}"},
            timeout=90,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            return await check_demo(args.url, args.date, http_client=client)

    try:
        result = asyncio.run(asyncio.wait_for(run(), timeout=180))
    except Exception:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "reason": "demo_check_failed",
                    "ready_for_clinical_use": False,
                    "ready_for_patient_data": False,
                }
            )
        )
        raise SystemExit(2) from None
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
