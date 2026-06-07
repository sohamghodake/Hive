import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_agent(client: AsyncClient):
    payload = {
        "name": "test-agent",
        "system_prompt": "You are a helpful assistant.",
        "model": "claude-sonnet-4-20250514",
        "tools": ["read_file", "web_search"],
    }
    r = await client.post("/api/agents", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "test-agent"
    agent_id = data["id"]

    r = await client.get("/api/agents")
    assert r.status_code == 200
    ids = [a["id"] for a in r.json()]
    assert agent_id in ids


@pytest.mark.asyncio
async def test_get_agent_not_found(client: AsyncClient):
    r = await client.get("/api/agents/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_agent(client: AsyncClient):
    r = await client.post(
        "/api/agents",
        json={"name": "delete-me", "system_prompt": "temp", "model": "claude-sonnet-4-20250514"},
    )
    assert r.status_code == 201
    agent_id = r.json()["id"]

    r = await client.delete(f"/api/agents/{agent_id}")
    assert r.status_code == 204

    r = await client.get(f"/api/agents/{agent_id}")
    assert r.status_code == 404
