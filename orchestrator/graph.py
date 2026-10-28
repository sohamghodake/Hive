from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from langchain_core.messages import HumanMessage, SystemMessage
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
    from api.models.agent import Agent
    from api.models.run import Run, RunStep, ToolCall
    from db.session import _session_factory as factory

    try:
        async with factory() as db:
            run = await db.get(Run, uuid.UUID(run_id))
            if not run:
                logger.error("run not found: %s", run_id)
                return
            agent = await db.get(Agent, run.agent_id) if run.agent_id else None
            system_prompt = agent.system_prompt if agent else "You are a helpful assistant."
            user_input = (
                run.input.get("task")
                or run.input.get("message")
                or str(run.input)
            )

            # Resolve per-agent execution config. Falling back to the env model
            # keeps agent-less runs working.
            model = (agent.model if agent and agent.model else None) or os.getenv(
                "LLM_MODEL", "openai/gpt-oss-120b"
            )
            tool_names = list(agent.tools) if agent and agent.tools else []
            max_steps = int((agent.config or {}).get("max_steps", 8)) if agent else 8

            run.status = "running"
            run.started_at = datetime.now(timezone.utc)
            await db.commit()

        initial: AgentState = {
            "run_id": run_id,
            "agent_id": str(run.agent_id),
            "messages": [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_input),
            ],
            "steps_completed": 0,
            "tool_results": [],
            "final_output": None,
            "error": None,
            "call_stats": None,
            "model": model,
            "tool_names": tool_names,
            "max_steps": max_steps,
        }

        # Persist each node as it completes, committing every time, so the SSE
        # endpoint and the run page see progress while the run is still going.
        # (Writing everything after ainvoke returned made "live" traces arrive
        # all at once at the end.)
        run_uuid = uuid.UUID(run_id)
        sequence = 0
        persisted_tools = 0
        final_output = None
        mark = datetime.now(timezone.utc)

        # Each iteration runs think→act (2 nodes); leave room for finalize.
        async for chunk in _graph.astream(
            initial, {"recursion_limit": max_steps * 2 + 4}, stream_mode="updates"
        ):
            now = datetime.now(timezone.utc)
            async with factory() as db:
                for node, update in chunk.items():
                    if node == "think":
                        msg = update["messages"][-1]
                        calls = [tc["name"] for tc in getattr(msg, "tool_calls", None) or []]
                        sequence += 1
                        db.add(RunStep(
                            run_id=run_uuid, sequence=sequence, node="think",
                            status="completed",
                            output={
                                **({"tool_calls": calls} if calls else {"text": str(msg.content)[:500]}),
                                # Token usage per model call makes cost auditable per step.
                                "usage": getattr(msg, "usage_metadata", None),
                                "finish_reason": (msg.response_metadata or {}).get("finish_reason"),
                                **(update.get("call_stats") or {}),
                            },
                            started_at=mark, finished_at=now,
                        ))

                    elif node == "act":
                        for tr in update["tool_results"][persisted_tools:]:
                            ended = datetime.fromisoformat(tr["ts"])
                            started = ended - timedelta(milliseconds=tr.get("duration_ms") or 0)
                            result = {"result": tr["output"]}
                            if tr.get("truncated"):
                                result |= {"truncated": True, "full_chars": tr["full_chars"]}
                            sequence += 1
                            step = RunStep(
                                run_id=run_uuid, sequence=sequence, node="act",
                                status="failed" if tr["error"] else "completed",
                                input={"tool": tr["tool"], "args": tr["input"]},
                                output=result,
                                started_at=started, finished_at=ended,
                            )
                            db.add(step)
                            await db.flush()
                            db.add(ToolCall(
                                run_id=run_uuid,
                                step_id=step.id,
                                tool_name=tr["tool"],
                                mcp_server=tr.get("server"),
                                input=tr["input"],
                                output=None if tr["error"] else result,
                                error=tr["output"] if tr["error"] else None,
                                duration_ms=tr.get("duration_ms"),
                            ))
                        persisted_tools = len(update["tool_results"])

                    elif node == "finalize":
                        final_output = update["final_output"]
                        sequence += 1
                        db.add(RunStep(
                            run_id=run_uuid, sequence=sequence, node="finalize",
                            status="completed", output=final_output,
                            started_at=mark, finished_at=now,
                        ))
                await db.commit()
            mark = now

        async with factory() as db:
            run = await db.get(Run, run_uuid)
            run.status = "completed"
            run.output = final_output
            run.finished_at = datetime.now(timezone.utc)
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
