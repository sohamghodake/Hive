"""mcp-db — Model Context Protocol server for read-only SQL and document retrieval.

Tools: query, list_tables, describe_table, list_documents, read_document and
search_documents (pgvector semantic search over embedded document chunks).
"""
import asyncio
import os
import re
import uuid
from datetime import date, datetime
from decimal import Decimal

import asyncpg
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from starlette.responses import JSONResponse

from rag.embeddings import embed_query, to_pgvector

# In docker-compose this is the hive_reader role (migration 003): SELECT on the
# application tables and nothing else. The READ ONLY transaction below stops
# writes, but it does not stop a superuser's reads — run as `hive`, the model's
# SQL could call pg_read_file() on the database server's filesystem.
DATABASE_URL = os.getenv("DATABASE_URL", "").replace("+asyncpg", "")
MAX_ROWS = 200
STATEMENT_TIMEOUT_MS = int(os.getenv("MCP_DB_STATEMENT_TIMEOUT_MS", "5000"))

mcp = FastMCP(
    "mcp-db",
    instructions="Read-only access to the Hive PostgreSQL database and semantic search over uploaded documents.",
)

_pool: asyncpg.Pool | None = None
_pool_lock = asyncio.Lock()


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        async with _pool_lock:
            if _pool is None:
                _pool = await asyncpg.create_pool(
                    DATABASE_URL,
                    min_size=1,
                    max_size=5,
                    # Behind PgBouncer in transaction mode, a server connection is
                    # shared between clients, so a statement prepared on it by one
                    # client cannot be assumed to exist for the next.
                    statement_cache_size=0,
                )
    return _pool


_BLOCKED = {
    "drop", "truncate", "delete", "insert", "update", "alter", "create",
    "grant", "revoke", "copy", "call", "do", "merge", "vacuum", "refresh",
}


def _check_readonly(sql: str) -> None:
    """Reject anything that is not a plain read.

    Checking only the leading keyword is not enough: `WITH t AS (...) DELETE ...`
    starts with WITH, and a trailing `; DROP ...` hides behind a valid SELECT.
    This is a fast first filter; the READ ONLY transaction in _fetch is the
    actual guarantee.
    """
    stripped = re.sub(r"--[^\n]*|/\*.*?\*/", " ", sql, flags=re.DOTALL)

    if ";" in stripped.rstrip().rstrip(";"):
        raise ToolError("Multiple statements are not permitted")

    first = stripped.strip().split()[0].lower() if stripped.strip() else ""
    if first not in {"select", "with", "show", "explain", "table"}:
        raise ToolError(f"Only read queries are permitted, got: {first.upper()}")

    for word in re.findall(r"\b[a-z]+\b", stripped.lower()):
        if word in _BLOCKED:
            raise ToolError(f"Write operation not permitted: {word.upper()}")


def _jsonable(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (uuid.UUID, Decimal)):
        return str(value)
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, memoryview)):
        return "<binary>"
    return value


async def _fetch(sql: str, *args, limit: int | None = None) -> list[dict]:
    pool = await _get_pool()
    # Postgres rejects any write inside a READ ONLY transaction, including
    # writes hidden in functions the keyword filter cannot see.
    async with pool.acquire() as conn, conn.transaction(readonly=True):
        # Set per transaction, not per connection: behind PgBouncer in
        # transaction mode a session-level setting would leak to whichever
        # client gets this server connection next. Without it, pg_sleep()
        # or an accidental cross join holds a backend indefinitely.
        await conn.execute(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_MS}")
        if limit is None:
            rows = await conn.fetch(sql, *args)
        else:
            # A cursor stops the server after `limit` rows; fetch() would
            # materialise the whole result in this process before slicing.
            rows = await (await conn.cursor(sql, *args)).fetch(limit)
    return [{k: _jsonable(v) for k, v in r.items()} for r in rows]


def _as_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ToolError(f"Not a valid document id: {value!r}. Call list_documents first.") from exc


@mcp.tool
async def query(sql: str) -> dict:
    """Run a single read-only SQL statement (SELECT/WITH/EXPLAIN). Returns up to 200 rows;
    `truncated` is true when there were more."""
    _check_readonly(sql)
    try:
        # One extra row distinguishes "exactly MAX_ROWS" from "more than that".
        rows = await _fetch(sql, limit=MAX_ROWS + 1)
    except asyncpg.PostgresError as exc:
        # Surface the database's message so the model can correct its SQL.
        raise ToolError(f"{type(exc).__name__}: {exc}") from None
    return {"rows": rows[:MAX_ROWS], "count": min(len(rows), MAX_ROWS), "truncated": len(rows) > MAX_ROWS}


@mcp.tool
async def list_tables() -> list[str]:
    """List tables in the public schema."""
    rows = await _fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
    )
    return [r["tablename"] for r in rows]


@mcp.tool
async def describe_table(table_name: str) -> list[dict]:
    """Columns of a public table: name, type and nullability."""
    rows = await _fetch(
        """SELECT column_name, data_type, is_nullable
           FROM information_schema.columns
           WHERE table_name = $1 AND table_schema = 'public'
           ORDER BY ordinal_position""",
        table_name,
    )
    if not rows:
        raise ToolError(f"No such table: {table_name}")
    return rows


@mcp.tool
async def list_documents() -> list[dict]:
    """List documents in the knowledge base with id, name, size and whether they are indexed for search."""
    return await _fetch(
        """SELECT id::text AS id, name, content_type, size_bytes, embedded
           FROM documents ORDER BY created_at DESC LIMIT 100"""
    )


@mcp.tool
async def read_document(document_id: str, offset: int = 0, max_chars: int = 4000) -> dict:
    """Read part of a document's text. Use next_offset to page through long documents."""
    max_chars = max(200, min(max_chars, 8000))
    rows = await _fetch(
        """SELECT name, substr(content, $2 + 1, $3) AS content, length(content) AS total_chars
           FROM documents WHERE id = $1""",
        _as_uuid(document_id), max(offset, 0), max_chars,
    )
    if not rows:
        raise ToolError(f"Document not found: {document_id}")
    row = rows[0]
    end = offset + len(row["content"])
    return {
        "name": row["name"],
        "content": row["content"],
        "total_chars": row["total_chars"],
        "next_offset": end if end < row["total_chars"] else None,
    }


@mcp.tool
async def search_documents(query: str, k: int = 5, document_id: str | None = None) -> list[dict]:
    """Semantic search over document chunks. Returns the k most relevant passages
    with their document, position and a cosine similarity score (higher is closer).
    Pass document_id to search within a single document."""
    k = max(1, min(k, 20))
    vector = to_pgvector(await asyncio.to_thread(embed_query, query))
    sql = """SELECT e.document_id::text AS document_id, d.name AS document_name,
                    e.chunk_index, e.chunk_text,
                    round((1 - (e.embedding <=> $1::vector))::numeric, 4)::float AS score
             FROM embeddings e JOIN documents d ON d.id = e.document_id
             WHERE e.embedding IS NOT NULL {scope}
             ORDER BY e.embedding <=> $1::vector
             LIMIT $2"""
    if document_id:
        rows = await _fetch(sql.format(scope="AND e.document_id = $3"), vector, k, _as_uuid(document_id))
    else:
        rows = await _fetch(sql.format(scope=""), vector, k)
    if not rows:
        raise ToolError("No indexed documents to search. Upload a document first.")
    return rows


@mcp.custom_route("/health", methods=["GET"])
async def health(_request):
    return JSONResponse({"status": "ok"})


app = mcp.http_app()
