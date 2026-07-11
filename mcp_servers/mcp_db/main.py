import os

import asyncpg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

DATABASE_URL = os.getenv("DATABASE_URL", "").replace("+asyncpg", "")

app = FastAPI(title="mcp-db")

_BLOCKED = {"drop", "truncate", "delete", "insert", "update", "alter", "create", "grant", "revoke"}


def _check_readonly(sql: str) -> None:
    first = sql.strip().split()[0].lower()
    if first in _BLOCKED:
        raise HTTPException(400, f"Write operation not permitted: {first.upper()}")


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
