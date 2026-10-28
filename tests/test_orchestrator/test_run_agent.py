"""run_agent end to end: the real graph, real persistence (hive_test) and the real
mcp-file server over fastmcp's in-memory transport. Only the model is scripted.

These pin what the unit tests cannot: that every step, tool call, token count and
rate-limit wait actually lands in the database, and that the tool boundaries
hold when the request comes from the model inside a run.
"""
import uuid

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

import db.session
from api.models.agent import Agent
from api.models.run import Run, RunStep, ToolCall
from api.routers import runs as runs_router
from orchestrator import mcp_client, nodes
from orchestrator.graph import run_agent
from tests.test_mcp._load import load_server

USAGE = {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}


class ScriptedLLM:
    """Returns (or raises) one scripted turn per model call."""

    def __init__(self, *turns):
        self.turns = list(turns)
        self.calls = 0

    def bind(self, **_kwargs):
        return self

    async def ainvoke(self, _messages):
        self.calls += 1
        turn = self.turns.pop(0)
        if isinstance(turn, Exception):
            raise turn
        return turn


def call(name, **args):
    tc = {"id": f"call_{uuid.uuid4().hex[:8]}", "name": name, "args": args}
    return AIMessage(content="", tool_calls=[tc], usage_metadata=USAGE)


def answer(text):
    return AIMessage(content=text, usage_metadata=USAGE, response_metadata={"finish_reason": "stop"})


@pytest.fixture
def factory(engine, monkeypatch):
    f = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db.session, "_session_factory", f)
    monkeypatch.setattr(runs_router, "session_factory", f)
    return f


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    root.mkdir()
    server = load_server("mcp_file")
    monkeypatch.setattr(server, "WORKSPACE", root.resolve())
    servers = {"mcp-file": server.mcp, "mcp-api": load_server("mcp_api").mcp}
    # Client() accepts a server object and connects in-memory, so call_tool runs
    # unchanged against the real tool implementation.
    monkeypatch.setattr(mcp_client, "endpoint", lambda name: servers[name])
    return root


def script(monkeypatch, *turns) -> ScriptedLLM:
    llm = ScriptedLLM(*turns)
    monkeypatch.setattr(nodes, "_get_llm", lambda model, tools: llm)
    monkeypatch.setattr(nodes.random, "uniform", lambda a, b: 0.0)
    return llm


async def start(factory, tools, max_steps=8) -> str:
    async with factory() as s:
        agent = Agent(name=f"t-{uuid.uuid4().hex[:6]}", system_prompt="test", model="stub",
                      tools=tools, config={"max_steps": max_steps})
        s.add(agent)
        await s.flush()
        run = Run(agent_id=agent.id, input={"task": "do it"})
        s.add(run)
        await s.commit()
        run_id = str(run.id)
    await run_agent(run_id)
    return run_id


async def load(factory, run_id):
    async with factory() as s:
        run = await s.get(Run, uuid.UUID(run_id))
        steps = (await s.execute(
            select(RunStep).where(RunStep.run_id == run.id).order_by(RunStep.sequence)
        )).scalars().all()
        calls = (await s.execute(select(ToolCall).where(ToolCall.run_id == run.id))).scalars().all()
    return run, steps, calls


async def test_run_persists_steps_tool_calls_usage_and_structured_output(factory, workspace, monkeypatch):
    script(monkeypatch,
           call("write_file", path="reports/a.md", content="hello"),
           answer('Done.\n```json\n{"ok": true}\n```'))

    run, steps, calls = await load(factory, await start(factory, ["write_file"]))

    assert run.status == "completed"
    assert run.output["data"] == {"ok": True}
    assert [s.node for s in steps] == ["think", "act", "think", "finalize"]
    think = steps[0].output
    assert think["usage"]["total_tokens"] == 120
    assert think["retries"] == 0 and think["rate_limit_wait_s"] == 0
    assert think["llm_ms"] >= 0 and think["max_tokens"] >= nodes.MIN_OUTPUT_TOKENS
    assert [(c.tool_name, c.mcp_server, c.error) for c in calls] == [("write_file", "mcp-file", None)]
    assert calls[0].duration_ms is not None
    assert (workspace / "reports/a.md").read_text() == "hello"


async def test_ungranted_tool_is_refused_inside_a_run(factory, workspace, monkeypatch):
    script(monkeypatch, call("write_file", path="x.txt", content="y"), answer("ok"))

    run, steps, calls = await load(factory, await start(factory, ["list_files"]))

    assert run.status == "completed"
    assert "not enabled" in calls[0].error
    assert steps[1].status == "failed"
    assert not (workspace / "x.txt").exists()


async def test_sandbox_escape_from_a_run_is_refused(factory, workspace, monkeypatch):
    script(monkeypatch, call("write_file", path="../escape.txt", content="y"), answer("ok"))

    run, steps, calls = await load(factory, await start(factory, ["write_file"]))

    assert "escapes workspace" in calls[0].error
    assert steps[1].status == "failed"
    assert not (workspace.parent / "escape.txt").exists()


async def test_internal_address_from_a_run_is_refused(factory, workspace, monkeypatch):
    """A model talked into fetching cloud metadata gets an error, not credentials."""
    script(monkeypatch, call("http_get", url="http://169.254.169.254/latest/meta-data/"), answer("ok"))

    _, steps, calls = await load(factory, await start(factory, ["http_get"]))

    assert (calls[0].mcp_server, steps[1].status) == ("mcp-api", "failed")
    assert "not allowed" in calls[0].error


async def test_step_budget_stops_the_run_and_flags_it(factory, workspace, monkeypatch):
    script(monkeypatch, call("list_files"), call("list_files"))

    run, steps, _ = await load(factory, await start(factory, ["list_files"], max_steps=2))

    assert run.status == "completed"
    assert run.output["stopped_early"] is True
    assert [s.node for s in steps].count("think") == 2


async def test_truncated_tool_output_is_flagged(factory, workspace, monkeypatch):
    monkeypatch.setattr(nodes, "MAX_TOOL_CHARS", 50)
    (workspace / "big.txt").write_text("\n".join(f"line {i}" for i in range(100)))
    script(monkeypatch, call("read_file", path="big.txt"), answer("ok"))

    _, steps, calls = await load(factory, await start(factory, ["read_file"]))

    assert calls[0].output["truncated"] is True
    assert calls[0].output["full_chars"] == len((workspace / "big.txt").read_text())
    assert steps[1].output["truncated"] is True


async def test_rate_limit_wait_is_recorded_on_the_step(factory, workspace, monkeypatch):
    llm = script(monkeypatch,
                 Exception("Error code: 429 rate_limit_exceeded (TPM). Please try again in 0.2s."),
                 answer("ok"))

    run, steps, _ = await load(factory, await start(factory, []))

    assert run.status == "completed"
    assert llm.calls == 2
    assert (steps[0].output["retries"], steps[0].output["rate_limit_wait_s"]) == (1, 0.2)


async def test_daily_limit_fails_the_run_without_retrying(factory, workspace, monkeypatch):
    llm = script(monkeypatch, Exception(
        "Error code: 429 rate_limit_exceeded on tokens per day (TPD): Limit 200000. "
        "Please try again in 1h2m58.272s."
    ))

    run, _, _ = await load(factory, await start(factory, []))

    assert run.status == "failed"
    assert run.error.startswith("Daily model quota exhausted")
    assert llm.calls == 1


async def test_stream_replays_steps_then_reports_done(client, factory, workspace, monkeypatch):
    script(monkeypatch, call("list_files"), answer("ok"))
    run_id = await start(factory, ["list_files"])

    r = await client.get(f"/api/runs/{run_id}/stream")

    events = [line.removeprefix("data: ") for line in r.text.splitlines() if line.startswith("data: ")]
    assert r.headers["content-type"].startswith("text/event-stream")
    assert len(events) == 5  # think, act, think, finalize, done
    assert '"tool": "list_files"' in events[1]
    assert events[-1] == '{"type": "done", "status": "completed"}'
