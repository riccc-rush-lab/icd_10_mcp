"""Local stdio connection to the screened remote public-terminology client."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .catalog import DISCLAIMER
from .client_config import load_token_file
from .privacy import PRIVACY_NOTICE
from .public_mcp import PublicTerminologyMCP
from .reference_client import ReferenceClient


def create_bridge(url: str, token: str | None = None) -> FastMCP:
    client = ReferenceClient(url, token)
    bridge = PublicTerminologyMCP(
        "ICD10 Reference MCP (screened bridge)",
        instructions=DISCLAIMER + " Public terminology only. Never enter patient data.",
        log_level="CRITICAL",
    )
    annotations = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )

    async def bounded(operation):
        try:
            return await asyncio.wait_for(operation, timeout=180)
        except Exception:
            return {
                "status": "remote_unavailable",
                "message": "Reference lookup unavailable.",
                "privacy": dict(PRIVACY_NOTICE),
            }

    @bridge.tool(annotations=annotations)
    async def phrase_search(query: str, service_date: str, limit: int = 10) -> dict[str, Any]:
        """Look up a public ICD-10-CM code/phrase for an explicit YYYY-MM-DD date."""
        return await bounded(client.lookup(query, service_date, limit))

    @bridge.tool(annotations=annotations)
    async def validate_selected_codes(codes: list[str], service_date: str) -> dict[str, Any]:
        """Validate public codes without a note; never certify an encounter or claim."""
        return await bounded(client.validate(codes, service_date))

    return bridge


def main():
    try:
        token_file = os.environ.get("ICD10_REFERENCE_TOKEN_FILE")
        bridge = create_bridge(
            os.environ["ICD10_REFERENCE_URL"],
            load_token_file(token_file) if token_file is not None else None,
        )
    except Exception:
        print(
            "Reference bridge startup failed: configure URL and private token file.",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
    for name in ("mcp", "httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    bridge.run(transport="stdio")


if __name__ == "__main__":
    main()
