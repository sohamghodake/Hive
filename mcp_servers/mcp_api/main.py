"""MCP server for external API integrations (HTTP, email, webhooks)."""
import os

import httpx
from fastmcp import FastMCP

mcp = FastMCP("mcp-api", port=8004)


@mcp.tool()
async def http_get(url: str, headers: dict | None = None) -> dict:
    """Perform a GET request to an external URL."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=headers or {})
        return {
            "status_code": resp.status_code,
            "body": resp.text,
            "headers": dict(resp.headers),
        }


@mcp.tool()
async def http_post(url: str, payload: dict, headers: dict | None = None) -> dict:
    """Perform a POST request with a JSON payload to an external URL."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, headers=headers or {})
        return {
            "status_code": resp.status_code,
            "body": resp.text,
        }


if __name__ == "__main__":
    mcp.run()
