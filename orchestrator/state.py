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
