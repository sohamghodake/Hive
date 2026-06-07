"""MCP server for read-only PostgreSQL access via asyncpg."""
import os

import asyncpg
from fastmcp import FastMCP

DATABASE_URL = os.getenv("DATABASE_URL", "").replace("+asyncpg", "")

mcp = FastMCP("mcp-db", port=8002)

_BLOCKED = {"drop", "truncate", "delete", "insert", "update", "alter", "create", "grant", "revoke"}


def _check_readonly(sql: str) -> None:
    first_word = sql.strip().split()[0].lower()
    if first_word in _BLOCKED:
        raise ValueError(f"Write operation not permitted: {first_word.upper()}")


@mcp.tool()
async def query(sql: str, params: list | None = None) -> dict:
    """Run a read-only SQL query. Returns rows as list of dicts."""
    _check_readonly(sql)
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch(sql, *(params or []))
        return {"rows": [dict(r) for r in rows], "count": len(rows)}
    finally:
        await conn.close()


@mcp.tool()
async def list_tables() -> list[str]:
    """List all user tables in the public schema."""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )
        return [r["tablename"] for r in rows]
    finally:
        await conn.close()


@mcp.tool()
async def describe_table(table_name: str) -> list[dict]:
    """Return column names and types for a table."""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = $1 AND table_schema = 'public'
            ORDER BY ordinal_position
            """,
            table_name,
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


if __name__ == "__main__":
    mcp.run()
