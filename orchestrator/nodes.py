from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, ToolMessage
from langchain_openai import ChatOpenAI

from orchestrator.state import AgentState
from orchestrator.tools import ALL_TOOLS, TOOL_MAP

logger = logging.getLogger(__name__)

_llm_instance = None


def _get_llm():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
            base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
            api_key=os.getenv("LLM_API_KEY", ""),
            max_tokens=8096,
        ).bind_tools(ALL_TOOLS)
    return _llm_instance


async def think(state: AgentState) -> AgentState:
    logger.info("node=think run_id=%s", state["run_id"])
    response: AIMessage = await _get_llm().ainvoke(state["messages"])
    return {
        **state,
        "messages": [response],
        "steps_completed": state["steps_completed"] + 1,
    }


async def act(state: AgentState) -> AgentState:
    last = state["messages"][-1]
    if not isinstance(last, AIMessage) or not last.tool_calls:
        return state

    tool_results = list(state["tool_results"])
    new_messages: list = []

    for tc in last.tool_calls:
        tool_name = tc["name"]
        tool_input = tc["args"]
        logger.info("node=act tool=%s run_id=%s", tool_name, state["run_id"])

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

    return {**state, "messages": new_messages, "tool_results": tool_results}


async def finalize(state: AgentState) -> AgentState:
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            return {**state, "final_output": {"text": str(msg.content)}}
    return {**state, "final_output": {"text": "No output produced."}}


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "act"
    return "finalize"
