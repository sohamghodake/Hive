"""mcp-file — Model Context Protocol server for a sandboxed workspace.

Speaks MCP over streamable HTTP at /mcp (initialize, tools/list, tools/call), so
any MCP client can use it, not just Hive's orchestrator.
"""
import os
from pathlib import Path

import aiofiles
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from starlette.responses import JSONResponse

WORKSPACE = Path(os.getenv("WORKSPACE_PATH", "/workspace")).resolve()

mcp = FastMCP("mcp-file", instructions="Read, write, list and delete files in a sandboxed workspace.")


def _safe_path(relative: str) -> Path:
    resolved = (WORKSPACE / relative).resolve()
    # Compare path components, not strings: a string prefix check accepts the
    # sibling "/workspace_evil" because it starts with "/workspace".
    if not resolved.is_relative_to(WORKSPACE):
        raise ToolError(f"Path escapes workspace: {relative}")
    return resolved


@mcp.tool
async def read_file(path: str) -> str:
    """Read a text file from the workspace. `path` is relative to the workspace root."""
    p = _safe_path(path)
    if not p.is_file():
        raise ToolError(f"{path} not found")
    async with aiofiles.open(p) as f:
        return await f.read()


@mcp.tool
async def write_file(path: str, content: str) -> str:
    """Create or overwrite a text file in the workspace, creating parent directories."""
    p = _safe_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(p, "w") as f:
        await f.write(content)
    return f"Wrote {len(content)} characters to {path}"


@mcp.tool
async def list_files(directory: str = "") -> list[dict]:
    """List entries in a workspace directory with their size in bytes."""
    p = _safe_path(directory)
    if not p.is_dir():
        raise ToolError(f"Not a directory: {directory or '/'}")
    return [
        {
            "path": str(c.relative_to(WORKSPACE)),
            "is_dir": c.is_dir(),
            "size": None if c.is_dir() else c.stat().st_size,
        }
        for c in sorted(p.iterdir())
    ]


@mcp.tool
async def delete_file(path: str) -> str:
    """Delete a file from the workspace."""
    p = _safe_path(path)
    if not p.is_file():
        raise ToolError(f"{path} not found")
    p.unlink()
    return f"Deleted {path}"


@mcp.custom_route("/health", methods=["GET"])
async def health(_request):
    return JSONResponse({"status": "ok"})


app = mcp.http_app()
