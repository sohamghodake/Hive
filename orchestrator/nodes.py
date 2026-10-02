from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import time
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, ToolMessage
from langchain_groq import ChatGroq

from orchestrator.state import AgentState
from orchestrator.tools import TOOL_MAP, TOOL_SERVERS

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")

# Groq's free tier allows 8000 tokens/minute, and `max_tokens` is *reserved*
# against that budget on every call: prompt + max_tokens must fit, or the request
# fails with 413 before the model runs. A fixed max_tokens is wrong both ways —
# too high and long conversations 413, too low and answers are cut off (gpt-oss
# spends part of it on hidden reasoning). So each call asks for whatever the
# budget has left after the prompt, between a floor and a cap.
TPM_BUDGET = int(os.getenv("LLM_TPM_BUDGET", "8000"))
MAX_OUTPUT_TOKENS = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "4096"))
MIN_OUTPUT_TOKENS = 512
REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "low")

# Tool results are appended verbatim to the message history and re-sent on every
# subsequent `think`. Unbounded output blows the token budget within two turns.
MAX_TOOL_CHARS = int(os.getenv("MAX_TOOL_OUTPUT_CHARS", "6000"))

MAX_LLM_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "6"))
MAX_RETRY_WAIT = 65.0  # the TPM window is one minute; never wait longer than that

# Groq states the wait it wants in the error text: "Please try again in 7.52s"
# or "in 1m2.5s". Honouring it beats guessing with exponential backoff, which
# gave up after ~15s while the per-minute window needed up to 60s to clear.
_RETRY_AFTER = re.compile(r"try again in (?:(\d+)m)?([\d.]+)s", re.IGNORECASE)


def _suggested_wait(exc: Exception) -> float | None:
    m = _RETRY_AFTER.search(str(exc))
    if not m:
        return None
    return int(m.group(1) or 0) * 60 + float(m.group(2))

# Cache one bound client per (model, tools) combination.
_llm_cache: dict[tuple[str, tuple[str, ...]], object] = {}


def _get_llm(model: str, tool_names: tuple[str, ...]):
    key = (model, tool_names)
    if key not in _llm_cache:
        extra = {}
        # gpt-oss reasons before answering, and those tokens come out of the
        # same max_tokens. "low" keeps tool-calling quality while leaving room
        # for the visible answer. Other models reject the parameter.
        if model.startswith("openai/gpt-oss") and REASONING_EFFORT:
            extra["reasoning_effort"] = REASONING_EFFORT
        client = ChatGroq(
            model=model,
            api_key=os.getenv("LLM_API_KEY", ""),
            max_tokens=MAX_OUTPUT_TOKENS,
            **extra,
        )
        # Bind only the tools this agent is configured for. Binding the full
        # registry would let any agent call any tool regardless of its config.
        selected = [TOOL_MAP[n] for n in tool_names if n in TOOL_MAP]
        if selected:
            client = client.bind_tools(selected)
        _llm_cache[key] = client
    return _llm_cache[key]


def _is_rate_limit(exc: Exception) -> bool:
    text = str(exc).lower()
    return "rate_limit" in text or "429" in text or "too many requests" in text


def _is_request_too_large(exc: Exception) -> bool:
    text = str(exc).lower()
    return "413" in text or "request too large" in text


async def _invoke_with_retry(llm, messages):
    """Call the model, backing off on transient rate limits.

    Groq distinguishes two failures that both surface as quota errors: 429 means
    the per-minute budget is momentarily exhausted and retrying works, while 413
    means this single request can never fit and retrying is pointless.
    """
    last_exc: Exception | None = None
    for attempt in range(MAX_LLM_RETRIES):
        try:
            return await llm.ainvoke(messages)
        except Exception as exc:
            last_exc = exc
            if _is_request_too_large(exc):
                raise RuntimeError(
                    "The request exceeds the model's per-minute token budget. "
                    "Shorten the agent's system prompt, reduce the task size, or "
                    "lower LLM_MAX_OUTPUT_TOKENS."
                ) from exc
            if not _is_rate_limit(exc) or attempt == MAX_LLM_RETRIES - 1:
                raise
            delay = min(_suggested_wait(exc) or 2**attempt, MAX_RETRY_WAIT) + random.uniform(0.2, 1.0)
            logger.warning(
                "rate limited, retrying in %.1fs (attempt %d/%d)",
                delay, attempt + 1, MAX_LLM_RETRIES,
            )
            await asyncio.sleep(delay)
    raise last_exc  # pragma: no cover - loop always returns or raises


def _output_budget(messages, n_tools: int) -> int:
    """Output tokens to request so prompt + output stays inside the TPM budget.

    The prompt size is estimated (≈3.5 chars/token for English and JSON, plus a
    per-tool allowance for the schemas sent with every call) rather than run
    through a tokenizer: the estimate only needs to be conservative, and the
    floor guarantees a usable answer even when it is not.
    """
    chars = 0
    for m in messages:
        chars += len(str(m.content))
        for tc in getattr(m, "tool_calls", None) or []:
            chars += len(json.dumps(tc.get("args", {}))) + 40
    prompt_tokens = int(chars / 3.5) + 120 * n_tools + 200
    return max(MIN_OUTPUT_TOKENS, min(MAX_OUTPUT_TOKENS, TPM_BUDGET - prompt_tokens - 300))


async def think(state: AgentState) -> AgentState:
    logger.info(
        "node=think run_id=%s step=%s", state["run_id"], state["steps_completed"]
    )
    llm = _get_llm(
        state.get("model") or DEFAULT_MODEL,
        tuple(state.get("tool_names") or ()),
    )
    budget = _output_budget(state["messages"], len(state.get("tool_names") or ()))
    response: AIMessage = await _invoke_with_retry(llm.bind(max_tokens=budget), state["messages"])
    return {
        **state,
        "messages": [response],
        "steps_completed": state["steps_completed"] + 1,
    }


def _truncate(text: str) -> str:
    """Cap tool output, cutting at a line boundary with an explicit marker.

    A raw character cut once sliced a diff mid-identifier ("sub_ctx" → "sub_"),
    and the model then reported the fragment as an undefined variable. Ending on
    a whole line and saying plainly that content is missing prevents that.
    """
    if len(text) <= MAX_TOOL_CHARS:
        return text
    cut = text.rfind("\n", int(MAX_TOOL_CHARS * 0.75), MAX_TOOL_CHARS)
    cut = cut if cut != -1 else MAX_TOOL_CHARS
    return (
        text[:cut]
        + f"\n\n[TOOL OUTPUT TRUNCATED: {len(text) - cut} more characters were not shown. "
        "The text above ends at a cut point, not at the real end of the content.]"
    )


async def act(state: AgentState) -> AgentState:
    last = state["messages"][-1]
    if not isinstance(last, AIMessage) or not last.tool_calls:
        return state

    allowed = set(state.get("tool_names") or ())
    tool_results = list(state["tool_results"])
    new_messages: list = []

    for tc in last.tool_calls:
        tool_name = tc["name"]
        tool_input = tc["args"]
        logger.info("node=act tool=%s run_id=%s", tool_name, state["run_id"])

        t = TOOL_MAP.get(tool_name)
        started = time.perf_counter()
        if tool_name not in allowed:
            content = f"Tool '{tool_name}' is not enabled for this agent."
            is_error = True
        elif t is None:
            content = f"Unknown tool: {tool_name}"
            is_error = True
        else:
            try:
                result = await t.ainvoke(tool_input)
                content = result if isinstance(result, str) else json.dumps(result)
                content = _truncate(content)
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
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "server": TOOL_SERVERS.get(tool_name),
        })
        new_messages.append(ToolMessage(content=content, tool_call_id=tc["id"]))

    return {**state, "messages": new_messages, "tool_results": tool_results}


_JSON_BLOCK = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _extract_structured(text: str):
    """Parse the last ```json block in the answer, if any.

    Agents whose prompts ask for structured findings end with such a block; it
    is stored as output.data (JSONB) so results can be queried in SQL, not just
    read. Malformed JSON is ignored rather than failing an otherwise good run.
    """
    blocks = _JSON_BLOCK.findall(text)
    if not blocks:
        return None
    try:
        return json.loads(blocks[-1])
    except json.JSONDecodeError:
        return None


async def finalize(state: AgentState) -> AgentState:
    # If the last message still requests tools, the step budget cut the run off.
    last = state["messages"][-1]
    stopped_early = isinstance(last, AIMessage) and bool(last.tool_calls)

    text = "No output produced."
    cut_off = False
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            text = str(msg.content)
            # The model ran out of output tokens mid-answer: say so rather than
            # presenting a truncated report as complete.
            cut_off = (getattr(msg, "response_metadata", None) or {}).get("finish_reason") == "length"
            break

    output: dict = {"text": text}
    if cut_off:
        output["truncated"] = True
    data = _extract_structured(text)
    if data is not None:
        output["data"] = data
    if stopped_early:
        output["stopped_early"] = True
    return {**state, "final_output": output}


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if not (isinstance(last, AIMessage) and last.tool_calls):
        return "finalize"
    # Stop cleanly at the step budget instead of letting LangGraph hit its
    # recursion limit, which would surface as an opaque crash.
    if state.get("steps_completed", 0) >= state.get("max_steps", 8):
        logger.warning(
            "run_id=%s hit max_steps=%s, finalizing early",
            state["run_id"], state.get("max_steps", 8),
        )
        return "finalize"
    return "act"
