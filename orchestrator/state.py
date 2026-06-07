from __future__ import annotations

from typing import Annotated, Any

from langgraph.graph.message import add_messages
from pydantic import BaseModel


class AgentState(BaseModel):
    run_id: str
    agent_id: str
    messages: Annotated[list[Any], add_messages] = []
    steps_completed: int = 0
    tool_results: list[dict] = []
    final_output: dict | None = None
    error: str | None = None
