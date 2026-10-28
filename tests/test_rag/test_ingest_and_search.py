"""The retrieval path end to end: upload through the API, chunk and embed with the
real model, then search through mcp-db's tool over MCP — against hive_test.

The embedding model is baked into the API image, so these need no network.
"""
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from sqlalchemy.ext.asyncio import async_sessionmaker

from api.services import ingest
from tests.conftest import TEST_DB_URL
from tests.test_mcp._load import load_server

CONTRACT = """MASTER SERVICES AGREEMENT

1. Term. This Agreement starts on the Effective Date and renews automatically for
successive one-year terms unless either party gives ninety (90) days' written notice.

2. Fees. Customer shall pay all invoices within thirty (30) days of receipt.

3. Limitation of Liability. Provider's total liability shall not exceed the fees paid
by Customer in the twelve (12) months preceding the claim.

4. Governing Law. This Agreement is governed by the laws of the State of Delaware.
"""


@pytest.fixture
def mcp_db(engine, monkeypatch):
    server = load_server("mcp_db")
    monkeypatch.setattr(server, "DATABASE_URL", TEST_DB_URL.replace("+asyncpg", ""))
    monkeypatch.setattr(server, "_pool", None)
    monkeypatch.setattr(ingest, "_session_factory", async_sessionmaker(engine, expire_on_commit=False))
    return server


async def upload(client, name, body: bytes, content_type="text/plain"):
    r = await client.post("/api/documents", files={"file": (name, body, content_type)})
    return r


async def test_upload_indexes_and_search_finds_the_clause(client, mcp_db):
    r = await upload(client, "msa.txt", CONTRACT.encode())
    assert r.status_code == 201
    doc_id = r.json()["id"]

    # The background indexing task has run by the time the ASGI call returns.
    assert (await client.get(f"/api/documents/{doc_id}")).json()["embedded"] is True

    async with Client(mcp_db.mcp) as c:
        hits = (await c.call_tool("search_documents", {"query": "how much notice to stop auto-renewal", "k": 1})).data
        page = (await c.call_tool("read_document", {"document_id": doc_id, "max_chars": 200})).data
        listed = (await c.call_tool("list_documents", {})).data

    assert "ninety (90) days" in hits[0]["chunk_text"]
    assert 0 < hits[0]["score"] <= 1
    assert page["next_offset"] == 200 and page["total_chars"] == len(CONTRACT)
    assert [d["name"] for d in listed] == ["msa.txt"]


async def test_reindex_rebuilds_the_same_chunks(client, mcp_db):
    doc_id = (await upload(client, "msa.txt", CONTRACT.encode())).json()["id"]

    r = await client.post(f"/api/documents/{doc_id}/reindex")

    assert r.status_code == 200 and r.json()["chunks"] >= 1
    assert (await client.get(f"/api/documents/{doc_id}/content")).json()["content"] == CONTRACT


async def test_empty_upload_is_rejected(client, mcp_db):
    r = await upload(client, "blank.txt", b"   \n  ")
    assert r.status_code == 422


async def test_search_with_nothing_indexed_says_so(mcp_db):
    async with Client(mcp_db.mcp) as c:
        with pytest.raises(ToolError, match="No indexed documents"):
            await c.call_tool("search_documents", {"query": "anything"})


async def test_read_only_transaction_stops_a_write_the_keyword_filter_misses(mcp_db):
    """lo_create() writes (it creates a large object) but contains no blocked
    keyword as a whole word, so only Postgres' READ ONLY transaction stops it."""
    mcp_db._check_readonly("SELECT lo_create(0)")  # the filter lets it through

    async with Client(mcp_db.mcp) as c:
        with pytest.raises(ToolError, match="read-only transaction"):
            await c.call_tool("query", {"sql": "SELECT lo_create(0)"})
        rows = (await c.call_tool("query", {"sql": "SELECT 1 AS one"})).data

    assert rows == {"rows": [{"one": 1}], "count": 1, "truncated": False}
