"""LangGraph node functions — each receives and returns AgentState."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from api.config import settings
from orchestrator.state import AgentState
from orchestrator.tools import ALL_TOOLS, TOOL_MAP

logger = logging.getLogger(__name__)

_llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    api_key=settings.anthropic_api_key,
    max_tokens=8096,
).bind_tools(ALL_TOOLS)


async def think(state: AgentState) -> AgentState:
    """Call the LLM and get its next response (possibly with tool calls)."""
    logger.info('"node": "think", "run_id": "%s"', state.run_id)
    response: AIMessage = await _llm.ainvoke(state.messages)
    return state.model_copy(update={"messages": [response], "steps_completed": state.steps_completed + 1})


async def act(state: AgentState) -> AgentState:
    """Execute all tool calls present in the last AIMessage."""
    last = state.messages[-1]
    if not isinstance(last, AIMessage) or not last.tool_calls:
        return state

    tool_results = list(state.tool_results)
    new_messages: list = []

    for tc in last.tool_calls:
        tool_name = tc["name"]
        tool_input = tc["args"]
        logger.info('"node": "act", "tool": "%s", "run_id": "%s"', tool_name, state.run_id)

        t = TOOL_MAP.get(tool_name)
        if t is None:
            content = f"Unknown tool: {tool_name}"
            is_error = True
        else:
            try:
                result = await t.ainvoke(tool_input)
                content = json.dumps(result) if not isinstance(result, str) else result
                is_error = False
            except Exception as exc:
                content = f"Tool error: {exc}"
                is_error = True

        tool_results.append({
            "tool": tool_name,
            "input": tool_input,
            "output": content,
            "error": is_error,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        new_messages.append(ToolMessage(content=content, tool_call_id=tc["id"]))

    return state.model_copy(update={"messages": new_messages, "tool_results": tool_results})


async def finalize(state: AgentState) -> AgentState:
    """Extract final structured output from the last assistant message."""
    for msg in reversed(state.messages):
        if isinstance(msg, AIMessage) and msg.content:
            return state.model_copy(update={"final_output": {"text": str(msg.content)}})
    return state.model_copy(update={"final_output": {"text": "No output produced."}})


def should_continue(state: AgentState) -> str:
    """Routing function — decides next node after 'think'."""
    last = state.messages[-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "act"
    return "finalize"
