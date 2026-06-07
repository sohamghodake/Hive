"""MCP server for sandboxed file I/O using FastMCP."""
import os
from pathlib import Path

import aiofiles
from fastmcp import FastMCP

WORKSPACE = Path(os.getenv("WORKSPACE_PATH", "/workspace")).resolve()

mcp = FastMCP("mcp-file", port=8001)


def _safe_path(relative: str) -> Path:
    resolved = (WORKSPACE / relative).resolve()
    if not str(resolved).startswith(str(WORKSPACE)):
        raise ValueError(f"Path escapes workspace: {relative}")
    return resolved


@mcp.tool()
async def read_file(path: str) -> str:
    """Read a file from the sandboxed workspace."""
    p = _safe_path(path)
    if not p.exists():
        raise FileNotFoundError(f"{path} not found in workspace")
    async with aiofiles.open(p) as f:
        return await f.read()


@mcp.tool()
async def write_file(path: str, content: str) -> str:
    """Write content to a file in the sandboxed workspace."""
    p = _safe_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(p, "w") as f:
        await f.write(content)
    return f"Written {len(content)} bytes to {path}"


@mcp.tool()
async def list_files(directory: str = "") -> list[str]:
    """List files in a workspace directory."""
    p = _safe_path(directory)
    if not p.is_dir():
        raise NotADirectoryError(f"{directory} is not a directory")
    return [str(child.relative_to(WORKSPACE)) for child in p.iterdir()]


@mcp.tool()
async def delete_file(path: str) -> str:
    """Delete a file from the sandboxed workspace."""
    p = _safe_path(path)
    p.unlink(missing_ok=True)
    return f"Deleted {path}"


if __name__ == "__main__":
    mcp.run()
