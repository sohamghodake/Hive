import pytest
from langchain_core.messages import AIMessage

from orchestrator.nodes import act, should_continue
from orchestrator.state import AgentState


def _state(**over) -> AgentState:
    base = {
        "run_id": "r1",
        "agent_id": "a1",
        "messages": [],
        "steps_completed": 0,
        "tool_results": [],
        "final_output": None,
        "error": None,
        "model": "openai/gpt-oss-120b",
        "tool_names": [],
        "max_steps": 8,
    }
    base.update(over)
    return base  # type: ignore[return-value]


def test_should_continue_routes_to_act_when_tool_calls_present():
    tc = [{"id": "tc1", "name": "read_file", "args": {"path": "test.txt"}}]
    msg = AIMessage(content="", tool_calls=tc)
    assert should_continue(_state(messages=[msg])) == "act"


def test_should_continue_routes_to_finalize_when_no_tool_calls():
    msg = AIMessage(content="All done.")
    assert should_continue(_state(messages=[msg])) == "finalize"


def test_should_continue_finalizes_at_step_budget():
    """Without this the graph runs until LangGraph's recursion limit throws."""
    tc = [{"id": "tc1", "name": "read_file", "args": {"path": "test.txt"}}]
    msg = AIMessage(content="", tool_calls=tc)
    state = _state(messages=[msg], steps_completed=8, max_steps=8)
    assert should_continue(state) == "finalize"


@pytest.mark.asyncio
async def test_act_refuses_tool_not_granted_to_agent():
    """The agent's `tools` list is a boundary, not a hint: a model that asks for
    an ungranted tool must be refused rather than silently served."""
    tc = [{"id": "tc1", "name": "web_search", "args": {"query": "x"}}]
    msg = AIMessage(content="", tool_calls=tc)
    state = _state(messages=[msg], tool_names=["read_file"])

    result = await act(state)

    assert result["tool_results"][0]["error"] is True
    assert "not enabled" in result["tool_results"][0]["output"]


@pytest.mark.asyncio
async def test_act_reports_unknown_tool():
    tc = [{"id": "tc1", "name": "no_such_tool", "args": {}}]
    msg = AIMessage(content="", tool_calls=tc)
    state = _state(messages=[msg], tool_names=["no_such_tool"])

    result = await act(state)

    assert result["tool_results"][0]["error"] is True
    assert "Unknown tool" in result["tool_results"][0]["output"]
