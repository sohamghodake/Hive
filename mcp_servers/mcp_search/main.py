import os

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

app = FastAPI(title="mcp-search")


class Params(BaseModel):
    params: dict


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


@app.post("/tools/search")
async def search(body: Params):
    query = body.params["query"]
    n = body.params.get("num_results", 5)
    if TAVILY_API_KEY:
        results = await _tavily(query, n)
    elif BRAVE_API_KEY:
        results = await _brave(query, n)
    else:
        results = []
    return {"results": results}


@app.get("/health")
def health():
    return {"status": "ok"}
