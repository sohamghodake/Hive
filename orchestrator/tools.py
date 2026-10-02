"""Agent tools: LangChain wrappers over MCP tool calls.

The docstrings are what the model reads when choosing a tool, so they say when to
use each one, not just what it does.
"""
from __future__ import annotations

import asyncio

from langchain_core.tools import tool

from orchestrator.mcp_client import call_tool

SEARCH_CHAR_BUDGET = 5000    # stays under the generic tool-output cap
SEARCH_PASSAGE_CHARS = 700   # per passage; chunks are ~1000 chars with overlap


# ── mcp-file ──────────────────────────────────────────────────────────────────

@tool
async def read_file(path: str) -> str:
    """Read a text file from the sandboxed workspace. Path is relative to the workspace root."""
    return await call_tool("mcp-file", "read_file", {"path": path})


@tool
async def write_file(path: str, content: str) -> str:
    """Write a text file to the sandboxed workspace (e.g. reports/summary.md). Overwrites existing files."""
    return await call_tool("mcp-file", "write_file", {"path": path, "content": content})


@tool
async def list_files(directory: str = "") -> list[dict]:
    """List files in a workspace directory. Use an empty string for the root."""
    return await call_tool("mcp-file", "list_files", {"directory": directory})


# ── mcp-db ────────────────────────────────────────────────────────────────────

@tool
async def query_database(sql: str) -> dict:
    """Run one read-only SQL query (SELECT/WITH) against the Hive PostgreSQL database.
    Call list_tables and describe_table first so column names are real, not guessed."""
    return await call_tool("mcp-db", "query", {"sql": sql})


@tool
async def list_tables() -> list[str]:
    """List the tables in the Hive database."""
    return await call_tool("mcp-db", "list_tables")


@tool
async def describe_table(table_name: str) -> list[dict]:
    """Show a table's columns and types. Use before writing SQL against it."""
    return await call_tool("mcp-db", "describe_table", {"table_name": table_name})


@tool
async def list_documents() -> list[dict]:
    """List documents uploaded to the knowledge base, with their ids."""
    return await call_tool("mcp-db", "list_documents")


@tool
async def read_document(document_id: str, offset: int = 0) -> dict:
    """Read a document's text by id, about 4000 characters at a time.
    If next_offset is not null, call again with that offset to continue."""
    return await call_tool("mcp-db", "read_document", {"document_id": document_id, "offset": offset})


@tool
async def search_documents(queries: list[str], document_id: str | None = None) -> list[dict]:
    """Semantic search over uploaded documents. Pass several queries at once — e.g. one per
    clause type you need — and get the top passages for each, with similarity scores.
    Prefer this to read_document for finding specific clauses or facts; pass document_id
    to restrict the search to one document."""
    # Each extra tool turn re-sends the whole conversation to the model, which is
    # what exhausts a per-minute token budget. Batching queries into one call
    # keeps a multi-clause review to a single round trip.
    async def one(q: str):
        args = {"query": q, "k": 3}
        if document_id:
            args["document_id"] = document_id
        return q, await call_tool("mcp-db", "search_documents", args)

    results = await asyncio.gather(*(one(q) for q in queries[:8]))

    # Keep the best passages that fit the budget, rather than letting the generic
    # tool-output cap cut the JSON at an arbitrary point and drop hits at random.
    best: dict[tuple[str, int], dict] = {}
    for q, hits in results:
        for h in hits:
            key = (h["document_id"], h["chunk_index"])
            if key not in best or h["score"] > best[key]["score"]:
                best[key] = {"query": q, **h, "chunk_text": h["chunk_text"][:SEARCH_PASSAGE_CHARS]}

    kept, used = [], 0
    for h in sorted(best.values(), key=lambda h: h["score"], reverse=True):
        size = len(h["chunk_text"]) + 160  # metadata overhead per hit
        if kept and used + size > SEARCH_CHAR_BUDGET:
            continue
        kept.append(h)
        used += size
    # Present in document order so neighbouring passages read naturally.
    return sorted(kept, key=lambda h: (h["document_id"], h["chunk_index"]))


# ── mcp-search / mcp-api ─────────────────────────────────────────────────────

@tool
async def web_search(query: str) -> list[dict]:
    """Search the web. Returns results with title, url and snippet."""
    return await call_tool("mcp-search", "web_search", {"query": query, "num_results": 5})


@tool
async def http_get(url: str) -> str:
    """Fetch a public URL and return its body as text. Internal addresses are refused.
    For a GitHub pull request diff use https://github.com/<owner>/<repo>/pull/<number>.diff"""
    result = await call_tool("mcp-api", "http_get", {"url": url})
    return f"HTTP {result['status_code']}\n{result['body']}"


ALL_TOOLS = [
    read_file, write_file, list_files,
    query_database, list_tables, describe_table,
    list_documents, read_document, search_documents,
    web_search, http_get,
]
TOOL_MAP = {t.name: t for t in ALL_TOOLS}

# Which MCP server backs each tool, recorded on every tool call so a run's trace
# shows where the work actually happened.
TOOL_SERVERS = {
    "read_file": "mcp-file",
    "write_file": "mcp-file",
    "list_files": "mcp-file",
    "query_database": "mcp-db",
    "list_tables": "mcp-db",
    "describe_table": "mcp-db",
    "list_documents": "mcp-db",
    "read_document": "mcp-db",
    "search_documents": "mcp-db",
    "web_search": "mcp-search",
    "http_get": "mcp-api",
}
