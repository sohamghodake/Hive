from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph

from orchestrator.nodes import act, finalize, should_continue, think
from orchestrator.state import AgentState

logger = logging.getLogger(__name__)


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("think", think)
    g.add_node("act", act)
    g.add_node("finalize", finalize)
    g.set_entry_point("think")
    g.add_conditional_edges("think", should_continue, {"act": "act", "finalize": "finalize"})
    g.add_edge("act", "think")
    g.add_edge("finalize", END)
    return g.compile()


_graph = build_graph()

_DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://hive:hivepass@postgres:5432/hive"
)


async def run_agent(run_id: str) -> None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from api.models.agent import Agent
    from api.models.run import Run, RunStep, ToolCall

    engine = create_async_engine(_DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with factory() as db:
            run = await db.get(Run, uuid.UUID(run_id))
            if not run:
                logger.error("run not found: %s", run_id)
                return
            agent = await db.get(Agent, run.agent_id) if run.agent_id else None
            system_prompt = agent.system_prompt if agent else "You are a helpful assistant."
            user_input = run.input.get("message", str(run.input))

            run.status = "running"
            run.started_at = datetime.now(timezone.utc)
            await db.commit()

        initial: AgentState = {
            "run_id": run_id,
            "agent_id": str(run.agent_id),
            "messages": [HumanMessage(content=user_input)],
            "steps_completed": 0,
            "tool_results": [],
            "final_output": None,
            "error": None,
        }

        final_state: AgentState = await _graph.ainvoke(initial)

        async with factory() as db:
            run = await db.get(Run, uuid.UUID(run_id))
            run.status = "completed"
            run.output = final_state["final_output"]
            run.finished_at = datetime.now(timezone.utc)

            # Write one step per think→act cycle
            for i, tool_result in enumerate(final_state["tool_results"]):
                step = RunStep(
                    run_id=run.id,
                    sequence=i + 1,
                    node="act",
                    status="completed",
                    input={"tool": tool_result["tool"], "args": tool_result["input"]},
                    output={"result": tool_result["output"]},
                    started_at=datetime.fromisoformat(tool_result["ts"]),
                    finished_at=datetime.now(timezone.utc),
                )
                db.add(step)
                await db.flush()

                db.add(ToolCall(
                    run_id=run.id,
                    step_id=step.id,
                    tool_name=tool_result["tool"],
                    input=tool_result["input"],
                    output={"result": tool_result["output"]} if not tool_result["error"] else None,
                    error=tool_result["output"] if tool_result["error"] else None,
                ))

            # Final step
            db.add(RunStep(
                run_id=run.id,
                sequence=len(final_state["tool_results"]) + 1,
                node="finalize",
                status="completed",
                output=final_state["final_output"],
                started_at=run.finished_at,
                finished_at=run.finished_at,
            ))

            await db.commit()
            logger.info("run completed: %s", run_id)

    except Exception as exc:
        logger.exception("run failed: %s", run_id)
        try:
            async with factory() as db:
                run = await db.get(Run, uuid.UUID(run_id))
                if run:
                    run.status = "failed"
                    run.error = str(exc)
                    run.finished_at = datetime.now(timezone.utc)
                    await db.commit()
        except Exception:
            logger.exception("failed to write error state for run: %s", run_id)
    finally:
        await engine.dispose()
