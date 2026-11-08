"""Thin MCP adapters, with local-only HTTP and no NLP runtime imports."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse

from .catalog import DISCLAIMER, CatalogSet, configured_catalog
from .service import ICDService


def create_server(
    catalog_path: Path | str,
    *,
    catalog_config: Path | str | None = None,
    include_note_tools: bool = True,
    transport_security: TransportSecuritySettings | None = None,
) -> FastMCP:
    service = ICDService(configured_catalog(catalog_path, catalog_config))
    mcp = FastMCP(
        "Local ICD-10-CM Lookup",
        instructions=DISCLAIMER,
        host="127.0.0.1",
        stateless_http=True,
        json_response=True,
        max_request_body_size=65_536,
        log_level="ERROR",
        transport_security=transport_security,
    )
    annotations = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @mcp.tool(annotations=annotations)
    def phrase_search(query: str, service_date: str, limit: int = 10) -> dict[str, Any]:
        """Primary lookup: ICD-10-CM code (e.g. E11.9) or diagnosis phrase.

        Requires YYYY-MM-DD service_date within an explicitly configured release.
        Returns descriptions, assignable vs header status, hierarchy, index references,
        instructions, source evidence, and release identity. Results require coder review.
        """
        return service.search(query, service_date, limit)

    def suggest_candidates(note: str, service_date: str, limit: int = 10) -> dict[str, Any]:
        """Secondary workflow: deterministic candidates from SYNTHETIC text only.

        No LLM, diagnosis inference, or final assignments. Negated, historical, uncertain,
        and family-history mentions are excluded conservatively. Not whole-note completeness.
        Do not send real patient data; MCP hosts may retain tool arguments.
        """
        return service.suggest(note, service_date, limit)

    def validate_selected_codes(
        codes: list[str],
        service_date: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Check selected codes, in proposed order, against this release.

        Distinguishes code validity, lexical documentation support, and completeness.
        Surfaces inherited exclusions, sequencing, additional-code rules, and missing details.
        Optional note must be synthetic. Rules do not certify principal diagnosis or claims.
        """
        return service.validate(codes, service_date, note)

    if include_note_tools:
        mcp.tool(annotations=annotations)(suggest_candidates)
        mcp.tool(annotations=annotations)(validate_selected_codes)
    else:

        @mcp.tool(name="validate_selected_codes", annotations=annotations)
        def validate_without_notes(codes: list[str], service_date: str) -> dict[str, Any]:
            """Validate codes without a note. No whole-encounter or claim certification."""
            return service.validate(codes, service_date)

    return mcp


def _ready(catalog) -> bool:
    catalogs = catalog.catalogs.values() if isinstance(catalog, CatalogSet) else [catalog]
    return all(item.select_release(item.release["effective_from"])[1] is None for item in catalogs)


def create_http_app(catalog_path: Path | str, *, catalog_config: Path | str | None = None):
    """Terminology-only ASGI app. Callers must keep it loopback-only."""
    catalog = configured_catalog(catalog_path, catalog_config)
    mcp = create_server(catalog_path, catalog_config=catalog_config, include_note_tools=False)

    @mcp.custom_route("/healthz", methods=["GET"])
    async def health(request):
        return JSONResponse({"status": "alive"})

    @mcp.custom_route("/readyz", methods=["GET"])
    async def readiness(request):
        ready = _ready(catalog)
        return JSONResponse(
            {"status": "ready" if ready else "not_ready"},
            status_code=200 if ready else 503,
        )

    app = mcp.streamable_http_app()
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    return app


def main():
    path = Path(os.environ.get("ICD10_CATALOG", "data/catalog.sqlite3"))
    config = os.environ.get("ICD10_CATALOGS")
    transport = os.environ.get("ICD10_TRANSPORT", "stdio")
    try:
        if transport not in {"stdio", "streamable-http"}:
            raise ValueError
        port = int(os.environ.get("ICD10_PORT", "8000"))
        if not 1 <= port <= 65535:
            raise ValueError
        if not _ready(configured_catalog(path, config)):
            raise ValueError
    except (OSError, ValueError, TypeError):
        print("MCP startup check failed: configure valid catalog(s).", file=sys.stderr)
        raise SystemExit(2) from None
    if transport == "stdio":
        create_server(path, catalog_config=config).run(transport="stdio")
    else:
        import uvicorn

        uvicorn.run(
            create_http_app(path, catalog_config=config),
            host="127.0.0.1",
            port=port,
            access_log=False,
            log_level="error",
            log_config=None,
        )


if __name__ == "__main__":
    main()
