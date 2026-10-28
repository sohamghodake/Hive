from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    run_id: str
    agent_id: str
    messages: Annotated[list[Any], add_messages]
    steps_completed: int
    tool_results: list[dict]
    final_output: dict | None
    error: str | None
    # Timing and retries of the latest model call, set by `think`.
    call_stats: dict | None

    # Per-agent configuration, resolved from the Agent row at run start.
    model: str
    tool_names: list[str]
    max_steps: int
