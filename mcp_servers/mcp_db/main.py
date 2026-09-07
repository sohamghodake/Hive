import os
import re

import asyncpg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

DATABASE_URL = os.getenv("DATABASE_URL", "").replace("+asyncpg", "")

app = FastAPI(title="mcp-db")

_BLOCKED = {
    "drop", "truncate", "delete", "insert", "update", "alter", "create",
    "grant", "revoke", "copy", "call", "do", "merge", "vacuum", "refresh",
}


def _check_readonly(sql: str) -> None:
    """Reject anything that is not a plain read.

    Checking only the leading keyword is not enough: `WITH t AS (...) DELETE ...`
    starts with WITH, and a trailing `; DROP ...` hides behind a valid SELECT.
    """
    stripped = re.sub(r"--[^\n]*|/\*.*?\*/", " ", sql, flags=re.DOTALL)

    if ";" in stripped.rstrip().rstrip(";"):
        raise HTTPException(400, "Multiple statements are not permitted")

    first = stripped.strip().split()[0].lower() if stripped.strip() else ""
    if first not in {"select", "with", "show", "explain", "table"}:
        raise HTTPException(400, f"Only read queries are permitted, got: {first.upper()}")

    for word in re.findall(r"\b[a-z]+\b", stripped.lower()):
        if word in _BLOCKED:
            raise HTTPException(400, f"Write operation not permitted: {word.upper()}")


class Params(BaseModel):
    params: dict


@app.post("/tools/query")
async def query(body: Params):
    sql = body.params["sql"]
    params = body.params.get("params", [])
    _check_readonly(sql)
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch(sql, *params)
        return {"rows": [dict(r) for r in rows], "count": len(rows)}
    finally:
        await conn.close()


@app.post("/tools/list_tables")
async def list_tables(body: Params):
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        )
        return {"tables": [r["tablename"] for r in rows]}
    finally:
        await conn.close()


@app.post("/tools/describe_table")
async def describe_table(body: Params):
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch(
            """SELECT column_name, data_type, is_nullable
               FROM information_schema.columns
               WHERE table_name=$1 AND table_schema='public'
               ORDER BY ordinal_position""",
            body.params["table_name"],
        )
        return {"columns": [dict(r) for r in rows]}
    finally:
        await conn.close()


@app.get("/health")
def health():
    return {"status": "ok"}
