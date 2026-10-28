import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from api.dependencies import get_db
from api.routers import runs as runs_router

MISSING = "00000000-0000-0000-0000-000000000001"


async def test_run_for_unknown_agent_is_404_not_500(client: AsyncClient):
    r = await client.post("/api/runs", json={"agent_id": MISSING, "input": {"task": "x"}})
    assert r.status_code == 404
    assert r.json()["detail"] == "Agent not found"


@pytest.mark.parametrize("query", ["limit=-1", "limit=0", "limit=201", "offset=-1"])
async def test_list_runs_rejects_out_of_range_paging(client: AsyncClient, query):
    assert (await client.get(f"/api/runs?{query}")).status_code == 422


async def test_list_runs_accepts_max_page(client: AsyncClient):
    assert (await client.get("/api/runs?limit=200")).status_code == 200


async def test_stream_for_unknown_run_is_404(client: AsyncClient, engine, monkeypatch):
    monkeypatch.setattr(runs_router, "session_factory", async_sessionmaker(engine))
    assert (await client.get(f"/api/runs/{MISSING}/stream")).status_code == 404


def test_stream_does_not_hold_a_request_scoped_session():
    """FastAPI closes a yield dependency only after the response has finished.
    For this endpoint that is the end of the stream, up to 10 minutes later, and
    the session's open transaction pinned a PgBouncer server connection for all
    of it. The stream must open its own short sessions instead."""
    route = next(r for r in runs_router.router.routes if r.path == "/{run_id}/stream")
    assert get_db not in [d.call for d in route.dependant.dependencies]
    # Sanity check that the assertion can fail: the detail route does take it.
    detail = next(r for r in runs_router.router.routes if r.path == "/{run_id}" and "GET" in r.methods)
    assert get_db in [d.call for d in detail.dependant.dependencies]
