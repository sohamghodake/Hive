"""Concurrency load test for the run pipeline.

Runs N agent runs at once through the real stack — LangGraph, MCP tool calls to
mcp-file, and per-step persistence through whatever DATABASE_URL points at —
with only the LLM stubbed (fixed latency, one tool call, then an answer).
Stubbing the model is deliberate: real concurrent runs would measure Groq's
rate limiter, not this system.

While it runs, a separate direct connection samples pg_stat_activity, so the
report shows how many real Postgres backends the load needed.

    # through PgBouncer (the compose default)
    docker compose exec api python scripts/load_test.py --runs 100 --concurrency 50

    # same load straight to Postgres, for comparison
    docker compose exec -e DATABASE_URL=postgresql+asyncpg://hive:hivepass@postgres:5432/hive \\
        api python scripts/load_test.py --runs 100 --concurrency 50
"""
from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import time
import uuid
from urllib.parse import urlsplit

import asyncpg
from langchain_core.messages import AIMessage, ToolMessage
from sqlalchemy import delete, select

import orchestrator.nodes as nodes
from api.models.agent import Agent
from api.models.run import Run
from db.session import _DATABASE_URL, _session_factory, engine
from orchestrator.graph import run_agent

DIRECT_URL = os.getenv(
    "MIGRATION_DATABASE_URL", "postgresql+asyncpg://hive:hivepass@postgres:5432/hive"
).replace("+asyncpg", "")


class StubLLM:
    """First turn requests list_files; once a tool result is present, answers."""

    def __init__(self, latency: float):
        self.latency = latency

    def bind(self, **_kwargs):  # the think node binds a per-call max_tokens
        return self

    async def ainvoke(self, messages):
        await asyncio.sleep(self.latency)
        if not any(isinstance(m, ToolMessage) for m in messages):
            return AIMessage(
                content="",
                tool_calls=[{"id": f"call_{uuid.uuid4().hex[:12]}", "name": "list_files", "args": {"directory": ""}}],
            )
        return AIMessage(content='Listed the workspace.\n```json\n{"ok": true}\n```')


async def sample_backends(stop: asyncio.Event, peaks: dict) -> None:
    conn = await asyncpg.connect(DIRECT_URL)
    try:
        while not stop.is_set():
            row = await conn.fetchrow(
                """SELECT count(*) AS total, count(*) FILTER (WHERE state = 'active') AS active
                   FROM pg_stat_activity
                   WHERE datname = current_database() AND backend_type = 'client backend'
                     AND pid <> pg_backend_pid()"""
            )
            peaks["total"] = max(peaks["total"], row["total"])
            peaks["active"] = max(peaks["active"], row["active"])
            await asyncio.sleep(0.05)
    finally:
        await conn.close()


def pct(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(p / 100 * (len(ordered) - 1))))]


async def main(runs: int, concurrency: int, latency: float) -> None:
    stub = StubLLM(latency)
    nodes._get_llm = lambda model, tools: stub

    async with _session_factory() as db:
        agent = Agent(
            name=f"loadtest-{uuid.uuid4().hex[:8]}",
            system_prompt="load test",
            model="stub",
            tools=["list_files"],
            config={"max_steps": 4},
        )
        db.add(agent)
        await db.flush()
        run_ids = []
        for i in range(runs):
            r = Run(agent_id=agent.id, input={"task": f"load test {i}"}, run_metadata={"load_test": True})
            db.add(r)
            await db.flush()
            run_ids.append(str(r.id))
        await db.commit()
        agent_id = agent.id

    stop = asyncio.Event()
    peaks = {"total": 0, "active": 0}
    sampler = asyncio.create_task(sample_backends(stop, peaks))
    await asyncio.sleep(0.3)  # baseline sample before load
    baseline = dict(peaks)

    sem = asyncio.Semaphore(concurrency)
    latencies: list[float] = []

    async def one(run_id: str):
        async with sem:
            t = time.perf_counter()
            await run_agent(run_id)
            latencies.append(time.perf_counter() - t)

    started = time.perf_counter()
    await asyncio.gather(*(one(rid) for rid in run_ids))
    wall = time.perf_counter() - started
    stop.set()
    await sampler

    async with _session_factory() as db:
        statuses = (
            await db.execute(select(Run.status, Run.output).where(Run.agent_id == agent_id))
        ).all()
        completed = sum(1 for s, _ in statuses if s == "completed")
        structured = sum(1 for s, o in statuses if s == "completed" and o and o.get("data"))
        errors = [
            r.error for r in (await db.execute(select(Run).where(Run.agent_id == agent_id, Run.status == "failed"))).scalars()
        ]
        # Clean up: steps and tool_calls cascade from runs.
        await db.execute(delete(Run).where(Run.agent_id == agent_id))
        await db.execute(delete(Agent).where(Agent.id == agent_id))
        await db.commit()
    await engine.dispose()

    target = urlsplit(_DATABASE_URL)
    via = "PgBouncer" if target.port == 6432 else "Postgres (direct)"
    print(f"""
Hive run-pipeline load test
  database path      : {via}  ({target.hostname}:{target.port})
  runs / concurrency : {runs} / {concurrency}   (stub LLM latency {latency * 1000:.0f} ms/turn)

  completed          : {completed}/{runs}  ({completed / runs:.0%}),  structured output on {structured}
  wall time          : {wall:.2f} s   →  {runs / wall:.1f} runs/s
  run latency        : p50 {pct(latencies, 50):.2f} s · p95 {pct(latencies, 95):.2f} s · max {max(latencies):.2f} s
  postgres backends  : peak {peaks['total']} open, {peaks['active']} active  (baseline {baseline['total']})
""")
    if errors:
        print("  first errors:", *sorted(set(e[:160] for e in errors if e))[:3], sep="\n    ")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=int, default=100)
    ap.add_argument("--concurrency", type=int, default=50)
    ap.add_argument("--llm-latency", type=float, default=0.4, help="seconds per stubbed model turn")
    a = ap.parse_args()
    asyncio.run(main(a.runs, a.concurrency, a.llm_latency))
