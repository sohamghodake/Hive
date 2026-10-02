"""mcp-search — Model Context Protocol server for web search (Tavily or Brave)."""
import os

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from starlette.responses import JSONResponse

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

mcp = FastMCP("mcp-search", instructions="Search the web and return titled, linked snippets.")


async def _brave(query: str, n: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": n},
            headers={"Accept": "application/json", "X-Subscription-Token": BRAVE_API_KEY},
        )
        r.raise_for_status()
        return [
            {"title": x.get("title"), "url": x.get("url"), "snippet": x.get("description")}
            for x in r.json().get("web", {}).get("results", [])
        ]


async def _tavily(query: str, n: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            "https://api.tavily.com/search",
            json={"query": query, "max_results": n, "api_key": TAVILY_API_KEY},
        )
        r.raise_for_status()
        return [
            {"title": x.get("title"), "url": x.get("url"), "snippet": x.get("content")}
            for x in r.json().get("results", [])
        ]


@mcp.tool
async def web_search(query: str, num_results: int = 5) -> list[dict]:
    """Search the web. Returns results with title, url and snippet."""
    n = max(1, min(num_results, 10))
    if TAVILY_API_KEY:
        return await _tavily(query, n)
    if BRAVE_API_KEY:
        return await _brave(query, n)
    # Previously this silently returned [], which agents read as "no results".
    raise ToolError("Web search is not configured: set TAVILY_API_KEY or BRAVE_API_KEY.")


@mcp.custom_route("/health", methods=["GET"])
async def health(_request):
    return JSONResponse({"status": "ok", "provider": "tavily" if TAVILY_API_KEY else "brave" if BRAVE_API_KEY else None})


app = mcp.http_app()
