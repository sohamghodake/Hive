"""MCP tool wrappers exposed to LangGraph as LangChain tools."""
from __future__ import annotations

import time

import httpx
from langchain_core.tools import tool

from api.config import settings


async def _mcp_call(server_url: str, tool_name: str, params: dict) -> dict:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{server_url}/tools/{tool_name}",
            json={"params": params},
        )
        resp.raise_for_status()
        return resp.json()


@tool
async def read_file(path: str) -> str:
    """Read a file from the sandboxed workspace. Path is relative to /workspace."""
    result = await _mcp_call(settings.mcp_file_url, "read_file", {"path": path})
    return result.get("content", "")


@tool
async def write_file(path: str, content: str) -> str:
    """Write content to a file in the sandboxed workspace."""
    await _mcp_call(settings.mcp_file_url, "write_file", {"path": path, "content": content})
    return f"Written to {path}"


@tool
async def query_database(sql: str) -> list[dict]:
    """Run a read-only SQL query against the Hive PostgreSQL database."""
    result = await _mcp_call(settings.mcp_db_url, "query", {"sql": sql})
    return result.get("rows", [])


@tool
async def web_search(query: str, num_results: int = 5) -> list[dict]:
    """Search the web and return a list of results with title, url, and snippet."""
    result = await _mcp_call(settings.mcp_search_url, "search", {"query": query, "num_results": num_results})
    return result.get("results", [])


ALL_TOOLS = [read_file, write_file, query_database, web_search]
TOOL_MAP = {t.name: t for t in ALL_TOOLS}
