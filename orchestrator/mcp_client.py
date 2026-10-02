"""Thin MCP client used by the orchestrator's tools and the API's workspace router.

Each call opens a session (initialize → tools/call → close) over streamable HTTP.
That costs one extra round trip per call, which is negligible beside an LLM turn,
and means a restarted tool server never leaves a stale session behind.
"""
from __future__ import annotations

from datetime import timedelta

from fastmcp import Client

from api.config import settings

SERVERS = {
    "mcp-file": settings.mcp_file_url,
    "mcp-db": settings.mcp_db_url,
    "mcp-search": settings.mcp_search_url,
    "mcp-api": settings.mcp_api_url,
}

TIMEOUT = timedelta(seconds=60)


def endpoint(server: str) -> str:
    return SERVERS[server].rstrip("/") + "/mcp"


async def call_tool(server: str, tool: str, arguments: dict | None = None):
    """Invoke `tool` on an MCP server and return its result.

    Returns the structured result when the tool declares one, else the
    concatenated text content. A tool-side failure raises fastmcp's ToolError
    carrying the server's message, which callers surface to the model.
    """
    async with Client(endpoint(server)) as client:
        result = await client.call_tool(tool, arguments or {}, timeout=TIMEOUT)
    if result.data is not None:
        return result.data
    return "\n".join(getattr(c, "text", "") for c in result.content)
