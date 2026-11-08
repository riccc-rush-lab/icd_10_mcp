"""Raw argument policy shared by note-free hosted and local bridge transports."""

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from .privacy import blocked_codes, blocked_phrase, blocked_response


class PublicTerminologyMCP(FastMCP):
    """Screen raw tool arguments before framework coercion/error formatting."""

    async def call_tool(self, name: str, arguments: dict[str, Any]):
        allowed = {
            "phrase_search": {"query", "service_date", "limit"},
            "validate_selected_codes": {"codes", "service_date"},
        }
        invalid = ToolError("Invalid public terminology arguments.")
        if (
            name not in allowed
            or not isinstance(arguments, dict)
            or not arguments.keys() <= allowed[name]
            or not isinstance(arguments.get("service_date"), str)
        ):
            raise invalid
        if name == "phrase_search":
            if not isinstance(arguments.get("query"), str):
                raise invalid
            if blocked_phrase(arguments.get("query")):
                return blocked_response()
            limit = arguments.get("limit", 10)
            if type(limit) is not int or not 1 <= limit <= 25:
                raise invalid
        else:
            codes = arguments.get("codes")
            if not isinstance(codes, list) or any(not isinstance(code, str) for code in codes):
                raise invalid
            if blocked_codes(codes):
                return blocked_response()
        return await super().call_tool(name, arguments)
