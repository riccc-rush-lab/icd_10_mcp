"""Explicitly configured terminology hosting, not institutional auth."""

from __future__ import annotations

import argparse
import logging
import os
import re
import secrets
import sys

from mcp.server.transport_security import TransportSecuritySettings
from starlette.datastructures import Headers
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse

from .catalog import CatalogSet, configured_catalog
from .public_http import PublicHTTPGuard, PublicLimits
from .releases import APRIL_ID, FY2027_ID
from .server import create_server


class _DemoGuard:
    def __init__(self, app, *, token: str | None, origin: str):
        self.app = app
        self.token = token
        self.origin = origin

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        if headers.get("origin") not in {None, self.origin}:
            await JSONResponse({"status": "forbidden"}, status_code=403)(scope, receive, send)
            return
        if scope["method"] == "GET" and scope["path"] in {"/healthz", "/readyz"}:
            await self.app(scope, receive, send)
            return
        credentials = headers.getlist("authorization")
        scheme, _, value = credentials[0].partition(" ") if len(credentials) == 1 else ("", "", "")
        if self.token is not None and (
            scheme.lower() != "bearer"
            or not secrets.compare_digest(value.encode(), self.token.encode())
        ):
            await JSONResponse(
                {"status": "unauthorized"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
            )(scope, receive, send)
            return
        if scope["method"] == "POST" and (
            headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json"
        ):
            await JSONResponse({"status": "invalid_request"}, status_code=400)(scope, receive, send)
            return
        if scope["method"] == "POST":
            # The SDK checks media types case-sensitively; omit unneeded parameters.
            scope = {
                **scope,
                "headers": [
                    (name, b"application/json" if name == b"content-type" else value)
                    for name, value in scope["headers"]
                ],
            }
        await self.app(scope, receive, send)


def create_demo_app(
    catalog_path,
    *,
    token: str | None = None,
    hostname: str,
    catalog_config=None,
    public_access: bool = False,
    public_limits: PublicLimits | None = None,
):
    """Create a terminology-only app; the caller controls binding and TLS termination."""
    if type(public_access) is not bool:
        raise ValueError("Configure an explicit public-access boolean.")
    if not public_access and (
        not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9._~+/-]{32,256}={0,2}", token)
    ):
        raise ValueError("Configure a random demo token of at least 32 characters.")
    if len(hostname) > 253 or not re.fullmatch(
        r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*"
        r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?",
        hostname,
    ):
        raise ValueError("Configure one exact demo hostname, without a URL or wildcard.")
    catalog = configured_catalog(catalog_path, catalog_config)
    mcp = create_server(
        catalog_path,
        catalog_config=catalog_config,
        include_note_tools=False,
        transport_security=TransportSecuritySettings(
            allowed_hosts=[hostname, f"{hostname}:*"],
            allowed_origins=[f"https://{hostname}"],
        ),
    )

    @mcp.custom_route("/healthz", methods=["GET"])
    async def health(request):
        return JSONResponse({"status": "alive"})

    @mcp.custom_route("/readyz", methods=["GET"])
    async def readiness(request):
        catalogs = catalog.catalogs.values() if isinstance(catalog, CatalogSet) else [catalog]
        ready = all(
            item.select_release(item.release["effective_from"])[1] is None for item in catalogs
        )
        return JSONResponse(
            {"status": "ready" if ready else "not_ready"}, status_code=200 if ready else 503
        )

    app = mcp.streamable_http_app()
    app.add_middleware(
        _DemoGuard, token=None if public_access else token, origin=f"https://{hostname}"
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[hostname])
    if public_access:
        app.add_middleware(PublicHTTPGuard, limits=public_limits or PublicLimits())
    return app


def main():
    parser = argparse.ArgumentParser(
        description="Synthetic terminology demo, not for patient data."
    )
    parser.add_argument(
        "--public-bind",
        action="store_true",
        help="Explicit opt-in to 0.0.0.0; requires approved TLS hosting.",
    )
    args = parser.parse_args()
    try:
        public_access = os.environ.get("ICD10_PUBLIC_ACCESS", "0")
        if public_access not in {"0", "1"}:
            raise ValueError
        config = os.environ["ICD10_CATALOGS"]
        app = create_demo_app(
            "",
            catalog_config=config,
            token=os.environ.get("ICD10_DEMO_TOKEN"),
            public_access=public_access == "1",
            hostname=os.environ.get("ICD10_DEMO_HOSTNAME")
            or os.environ["RENDER_EXTERNAL_HOSTNAME"],
        )
        catalogs = configured_catalog("", config).catalogs
        if set(catalogs) != {APRIL_ID, FY2027_ID}:
            raise ValueError
        for catalog in catalogs.values():
            metadata, error = catalog.select_release(catalog.release["effective_from"])
            if error or metadata["scope"] != "full_cdc_corpus":
                raise ValueError
        port = int(os.environ.get("PORT", "10000"))
        if not 1 <= port <= 65535:
            raise ValueError
    except (OSError, ValueError, KeyError, TypeError):
        print(
            "Demo startup check failed: configure token, hostname and both catalogs.",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
    import uvicorn

    logging.getLogger("mcp").setLevel(logging.CRITICAL)
    uvicorn.run(
        app,
        host="0.0.0.0" if args.public_bind else "127.0.0.1",
        port=port,
        access_log=False,
        log_level="error",
        log_config=None,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
