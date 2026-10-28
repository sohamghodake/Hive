"""Record/replay cache for model calls (Tier 1).

Wraps the client the think node gets, keyed by model + tools + the exact message
history. On a hit the stored response is returned and no tokens are spent; the
step then records no usage (the original is kept under
response_metadata.cached_usage), so the database stays an honest ledger of
tokens actually spent.

Modes:
  record  always call the model, and store what comes back
  replay  serve hits from the cache, call the model on a miss (default)
  only    serve hits, fail on a miss: a zero-token regression run

A replay is exact only while tool outputs are unchanged too: the first differing
tool result changes the history, and every later call misses.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.messages import AIMessage, ToolMessage, messages_from_dict, messages_to_dict

from evals._util import ROOT

CACHE_DIR = ROOT / "cache"


class CacheMiss(RuntimeError):
    pass


@dataclass
class CallStats:
    live_calls: int = 0
    cache_hits: int = 0
    live_tokens: int = 0
    keys: list[str] = field(default_factory=list)


def _message_key(m) -> dict:
    out = {"type": m.type, "content": m.content}
    if isinstance(m, AIMessage) and m.tool_calls:
        out["tool_calls"] = [{"name": tc["name"], "args": tc["args"], "id": tc["id"]} for tc in m.tool_calls]
    if isinstance(m, ToolMessage):
        out["tool_call_id"] = m.tool_call_id
    return out


def cache_key(model: str, tool_names, messages) -> str:
    blob = json.dumps(
        {"model": model, "tools": sorted(tool_names), "messages": [_message_key(m) for m in messages]},
        sort_keys=True, default=str,
    )
    return hashlib.sha256(blob.encode()).hexdigest()


def _path(model: str, key: str) -> Path:
    return CACHE_DIR / model.replace("/", "__") / f"{key}.json"


class CachingLLM:
    """Stands in for the bound chat model: same .bind() / .ainvoke() surface."""

    def __init__(self, inner, model: str, tool_names, mode: str, stats: CallStats):
        self.inner, self.model, self.tool_names, self.mode, self.stats = inner, model, tuple(tool_names), mode, stats

    def bind(self, **kwargs):
        return CachingLLM(self.inner.bind(**kwargs), self.model, self.tool_names, self.mode, self.stats)

    async def ainvoke(self, messages):
        key = cache_key(self.model, self.tool_names, messages)
        path = _path(self.model, key)
        self.stats.keys.append(key)
        if self.mode in ("replay", "only") and path.exists():
            msg = messages_from_dict(json.loads(path.read_text()))[0]
            msg.response_metadata = {
                **(msg.response_metadata or {}), "cache_hit": True, "cached_usage": msg.usage_metadata,
            }
            msg.usage_metadata = None
            self.stats.cache_hits += 1
            return msg
        if self.mode == "only":
            raise CacheMiss(f"no cached response for call {len(self.stats.keys)} ({key[:12]})")

        response = await self.inner.ainvoke(messages)
        self.stats.live_calls += 1
        self.stats.live_tokens += (response.usage_metadata or {}).get("total_tokens", 0)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(messages_to_dict([response])))
        return response
