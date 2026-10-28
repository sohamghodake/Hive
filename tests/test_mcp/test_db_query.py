"""mcp-db's query tool against a real Postgres: the row cap, the statement timeout
and the role's privileges only mean something if the database enforces them."""
import os
import time

import pytest
import pytest_asyncio
from fastmcp import Client
from fastmcp.exceptions import ToolError

from tests.conftest import TEST_DB_URL
from tests.test_mcp._load import load_server

# A database migrated to head (so hive_reader exists), reached as hive_reader.
READER_URL = os.getenv("TEST_READER_DATABASE_URL", "")


async def _server(url: str):
    server = load_server("mcp_db")
    server.DATABASE_URL = url.replace("+asyncpg", "")
    return server


@pytest_asyncio.fixture
async def mcp_db():
    server = await _server(TEST_DB_URL)
    try:
        yield server
    finally:
        if server._pool is not None:
            await server._pool.close()


async def _query(server, sql: str) -> dict:
    async with Client(server.mcp) as client:
        return (await client.call_tool("query", {"sql": sql})).data


async def test_row_cap_is_applied_by_the_database(mcp_db):
    out = await _query(mcp_db, "SELECT g FROM generate_series(1, 1000000) AS g")
    assert out["count"] == mcp_db.MAX_ROWS
    assert out["truncated"] is True
    assert out["rows"][-1] == {"g": mcp_db.MAX_ROWS}


async def test_small_result_is_returned_whole(mcp_db):
    out = await _query(mcp_db, "SELECT g FROM generate_series(1, 3) AS g")
    assert out == {"rows": [{"g": 1}, {"g": 2}, {"g": 3}], "count": 3, "truncated": False}


@pytest.mark.parametrize("sql", ["SHOW TIMEZONE", "EXPLAIN SELECT 1", "TABLE pg_namespace"])
async def test_other_read_statements_work_through_the_cursor(mcp_db, sql):
    assert (await _query(mcp_db, sql))["count"] >= 1


async def test_slow_query_is_cancelled(mcp_db):
    mcp_db.STATEMENT_TIMEOUT_MS = 200
    started = time.monotonic()
    with pytest.raises(ToolError, match="statement timeout"):
        await _query(mcp_db, "SELECT pg_sleep(5)")
    assert time.monotonic() - started < 3


@pytest.mark.skipif(not READER_URL, reason="set TEST_READER_DATABASE_URL to a migrated database")
async def test_reader_role_cannot_read_server_files():
    """As the `hive` superuser this returned the file; READ ONLY does not stop reads."""
    server = await _server(READER_URL)
    try:
        with pytest.raises(ToolError, match="permission denied"):
            await _query(server, "SELECT pg_read_file('/etc/hostname')")
        with pytest.raises(ToolError, match="permission denied"):
            await _query(server, "SELECT * FROM pg_ls_dir('.')")
        # ...while the application tables stay readable.
        assert (await _query(server, "SELECT count(*) AS n FROM runs"))["count"] == 1
    finally:
        if server._pool is not None:
            await server._pool.close()
