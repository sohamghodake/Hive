import pytest
from unittest.mock import AsyncMock, patch
from langchain_core.messages import AIMessage, HumanMessage

from orchestrator.state import AgentState
from orchestrator.nodes import should_continue


def test_should_continue_routes_to_act_when_tool_calls_present():
    tc = [{"id": "tc1", "name": "read_file", "args": {"path": "test.txt"}}]
    msg = AIMessage(content="", tool_calls=tc)
    state = AgentState(run_id="r1", agent_id="a1", messages=[msg])
    assert should_continue(state) == "act"


def test_should_continue_routes_to_finalize_when_no_tool_calls():
    msg = AIMessage(content="All done.")
    state = AgentState(run_id="r1", agent_id="a1", messages=[msg])
    assert should_continue(state) == "finalize"
