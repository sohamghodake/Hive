"""The mcp-db read-only guard is the only thing standing between an LLM-authored
SQL string and the production tables, so its bypasses are worth pinning down."""
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mcp_servers" / "mcp_db"))

from main import _check_readonly  # noqa: E402


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "select name from agents limit 5",
        "WITH t AS (SELECT 1) SELECT * FROM t",
        "EXPLAIN SELECT 1",
        "SHOW TIMEZONE",
    ],
)
def test_allows_reads(sql):
    _check_readonly(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE agents",
        "DELETE FROM agents",
        "INSERT INTO agents (name) VALUES ('x')",
        "UPDATE agents SET name = 'x'",
        # Leading keyword is SELECT/WITH but the statement still writes.
        "WITH t AS (SELECT 1) DELETE FROM agents",
        "SELECT 1; DROP TABLE agents",
        "SELECT 1; -- harmless\n; TRUNCATE agents",
    ],
)
def test_blocks_writes(sql):
    with pytest.raises(HTTPException):
        _check_readonly(sql)
