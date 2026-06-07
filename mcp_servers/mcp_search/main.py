"""MCP server for web search via Brave Search or Tavily."""
import os

import httpx
from fastmcp import FastMCP

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

mcp = FastMCP("mcp-search", port=8003)


async def _brave_search(query: str, num_results: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": num_results},
            headers={"Accept": "application/json", "X-Subscription-Token": BRAVE_API_KEY},
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {"title": r.get("title"), "url": r.get("url"), "snippet": r.get("description")}
            for r in data.get("web", {}).get("results", [])
        ]


async def _tavily_search(query: str, num_results: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={"query": query, "max_results": num_results, "api_key": TAVILY_API_KEY},
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {"title": r.get("title"), "url": r.get("url"), "snippet": r.get("content")}
            for r in data.get("results", [])
        ]


@mcp.tool()
async def search(query: str, num_results: int = 5) -> dict:
    """Search the web. Returns list of {title, url, snippet}."""
    if TAVILY_API_KEY:
        results = await _tavily_search(query, num_results)
    elif BRAVE_API_KEY:
        results = await _brave_search(query, num_results)
    else:
        return {"results": [], "error": "No search API key configured"}
    return {"results": results}


if __name__ == "__main__":
    mcp.run()
