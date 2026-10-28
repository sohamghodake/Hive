import pytest
from httpx import AsyncClient

from api.config import settings


@pytest.mark.asyncio
async def test_create_and_list_agent(client: AsyncClient):
    payload = {
        "name": "test-agent",
        "system_prompt": "You are a helpful assistant.",
        "model": "openai/gpt-oss-20b",
        "tools": ["read_file", "web_search"],
    }
    r = await client.post("/api/agents", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "test-agent"
    assert data["model"] == "openai/gpt-oss-20b"
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
    r = await client.post("/api/agents", json={"name": "delete-me", "system_prompt": "temp"})
    assert r.status_code == 201
    agent_id = r.json()["id"]

    r = await client.delete(f"/api/agents/{agent_id}")
    assert r.status_code == 204

    r = await client.get(f"/api/agents/{agent_id}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_model_defaults_to_configured_llm_model(client: AsyncClient):
    """The schema once defaulted to a model Groq does not serve, so an agent
    created without one failed on its first run."""
    r = await client.post("/api/agents", json={"name": "no-model", "system_prompt": "x"})
    assert r.status_code == 201
    assert r.json()["model"] == settings.llm_model


@pytest.mark.asyncio
async def test_duplicate_name_is_a_conflict_not_a_500(client: AsyncClient):
    body = {"name": "twice", "system_prompt": "x"}
    assert (await client.post("/api/agents", json=body)).status_code == 201

    r = await client.post("/api/agents", json=body)

    assert r.status_code == 409
    assert "already exists" in r.json()["detail"]
    # The session was rolled back, so the API still works afterwards.
    assert (await client.get("/api/agents")).status_code == 200


@pytest.mark.asyncio
async def test_unknown_tool_is_rejected(client: AsyncClient):
    r = await client.post(
        "/api/agents", json={"name": "typo", "system_prompt": "x", "tools": ["read_flie"]}
    )
    assert r.status_code == 422
    assert "read_flie" in r.text


@pytest.mark.asyncio
async def test_update_rejects_unknown_tool(client: AsyncClient):
    agent_id = (await client.post("/api/agents", json={"name": "upd", "system_prompt": "x"})).json()["id"]

    r = await client.patch(f"/api/agents/{agent_id}", json={"tools": ["rm_rf"]})
    assert r.status_code == 422

    r = await client.patch(f"/api/agents/{agent_id}", json={"tools": ["list_files"]})
    assert r.status_code == 200
    assert r.json()["tools"] == ["list_files"]
