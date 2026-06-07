"""Build and run the LangGraph agent graph, persisting state to PostgreSQL."""
from __future__ import annotations

import logging
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


async def run_agent(run_id: str) -> None:
    """Background task: load the run, execute the graph, persist results."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from api.config import settings
    from api.models.agent import Agent
    from api.models.run import Run, RunStep, ToolCall

    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        run = await db.get(Run, uuid.UUID(run_id))
        if not run:
            logger.error('"msg": "run not found", "run_id": "%s"', run_id)
            return

        agent = await db.get(Agent, run.agent_id)
        system_prompt = agent.system_prompt if agent else "You are a helpful assistant."

        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        await db.commit()

    try:
        user_input = run.input.get("message", str(run.input))
        initial_state = AgentState(
            run_id=run_id,
            agent_id=str(run.agent_id),
            messages=[HumanMessage(content=user_input)],
        )

        final_state: AgentState = await _graph.ainvoke(initial_state)

        async with factory() as db:
            run = await db.get(Run, uuid.UUID(run_id))
            run.status = "completed"
            run.output = final_state.final_output
            run.finished_at = datetime.now(timezone.utc)

            for i, tool_result in enumerate(final_state.tool_results):
                db.add(ToolCall(
                    run_id=run.id,
                    tool_name=tool_result["tool"],
                    input=tool_result["input"],
                    output={"result": tool_result["output"]} if not tool_result["error"] else None,
                    error=tool_result["output"] if tool_result["error"] else None,
                ))

            await db.commit()

    except Exception as exc:
        logger.exception('"msg": "agent run failed", "run_id": "%s"', run_id)
        async with factory() as db:
            run = await db.get(Run, uuid.UUID(run_id))
            if run:
                run.status = "failed"
                run.error = str(exc)
                run.finished_at = datetime.now(timezone.utc)
                await db.commit()
    finally:
        await engine.dispose()
