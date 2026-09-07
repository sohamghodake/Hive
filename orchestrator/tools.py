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
async def list_files(directory: str = "") -> list[str]:
    """List files in the sandboxed workspace directory."""
    result = await _mcp_call(settings.mcp_file_url, "list_files", {"directory": directory})
    return result.get("files", [])


@tool
async def http_get(url: str) -> str:
    """Perform an HTTP GET request and return the response body as text."""
    result = await _mcp_call(settings.mcp_api_url, "http_get", {"url": url})
    return result.get("body", "")


@tool
async def web_search(query: str) -> list[dict]:
    """Search the web and return a list of results with title, url, and snippet."""
    result = await _mcp_call(settings.mcp_search_url, "search", {"query": query, "num_results": 5})
    return result.get("results", [])


@tool
async def list_documents() -> list[dict]:
    """List all documents uploaded to the knowledge base. Returns id, name, and content_type."""
    result = await _mcp_call(
        settings.mcp_db_url, "query",
        {"sql": "SELECT id::text, name, content_type, size_bytes FROM documents ORDER BY created_at DESC LIMIT 50"}
    )
    return result.get("rows", [])


@tool
async def read_document(document_id: str) -> str:
    """Read the full text content of a document from the knowledge base by its UUID.
    Use list_documents first to find the correct document_id."""
    import re
    if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', document_id.lower()):
        return "Error: document_id must be a valid UUID"
    result = await _mcp_call(
        settings.mcp_db_url, "query",
        {"sql": f"SELECT content FROM documents WHERE id = '{document_id}'"}
    )
    rows = result.get("rows", [])
    return rows[0].get("content", "Document not found") if rows else "Document not found"


ALL_TOOLS = [read_file, write_file, list_files, query_database, web_search, http_get, list_documents, read_document]
TOOL_MAP = {t.name: t for t in ALL_TOOLS}

# Which MCP server backs each tool, recorded on every tool call so a run's trace
# shows where the work actually happened.
TOOL_SERVERS = {
    "read_file": "mcp-file",
    "write_file": "mcp-file",
    "list_files": "mcp-file",
    "query_database": "mcp-db",
    "list_documents": "mcp-db",
    "read_document": "mcp-db",
    "web_search": "mcp-search",
    "http_get": "mcp-api",
}
