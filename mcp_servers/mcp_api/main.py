"""mcp-api — Model Context Protocol server for outbound HTTP, with SSRF protection."""
import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from starlette.responses import JSONResponse

mcp = FastMCP("mcp-api", instructions="Fetch public URLs over HTTP. Internal and private addresses are refused.")

MAX_REDIRECTS = 5
MAX_BODY_BYTES = 1_000_000


async def _assert_public(url: str) -> None:
    """Reject URLs that resolve to anything but the public internet.

    The LLM chooses these URLs, so without this check http_get reaches whatever
    this container can: postgres:5432, the sibling tool servers, and cloud
    metadata at 169.254.169.254. Checking every resolved address (not just the
    first) stops a hostname with one public and one private record.

    Residual risk: DNS rebinding between this check and httpx's own lookup.
    Closing that needs connecting to the vetted IP directly.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise ToolError(f"Scheme not allowed: {parts.scheme or '(none)'}")
    if not parts.hostname:
        raise ToolError("URL has no host")

    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            parts.hostname, parts.port or (443 if parts.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror:
        raise ToolError(f"Cannot resolve host: {parts.hostname}")

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if not ip.is_global:
            raise ToolError(f"Destination not allowed: {parts.hostname} ({ip})")


async def _request(method: str, url: str, **kwargs) -> dict:
    # Redirects are followed by hand so each hop is re-validated; letting httpx
    # follow them would let a public URL bounce the request to an internal one.
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            await _assert_public(url)
            r = await client.request(method, url, **kwargs)
            if r.is_redirect and "location" in r.headers:
                url = urljoin(url, r.headers["location"])
                method, kwargs = "GET", {"headers": kwargs.get("headers", {})}
                continue
            body = r.content[:MAX_BODY_BYTES].decode(r.encoding or "utf-8", errors="replace")
            return {"status_code": r.status_code, "body": body}
    raise ToolError(f"Too many redirects (>{MAX_REDIRECTS})")


@mcp.tool
async def http_get(url: str, headers: dict[str, str] | None = None) -> dict:
    """GET a public URL. Returns status_code and the body as text (capped at 1 MB)."""
    return await _request("GET", url, headers=headers or {})


@mcp.tool
async def http_post(url: str, payload: dict | None = None, headers: dict[str, str] | None = None) -> dict:
    """POST JSON to a public URL. Returns status_code and the body as text."""
    return await _request("POST", url, json=payload or {}, headers=headers or {})


@mcp.custom_route("/health", methods=["GET"])
async def health(_request):
    return JSONResponse({"status": "ok"})


app = mcp.http_app()
