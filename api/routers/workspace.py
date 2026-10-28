from fastapi import APIRouter, HTTPException
from fastmcp.exceptions import ToolError
from pydantic import BaseModel

from orchestrator.mcp_client import call_tool

router = APIRouter()


async def _file_tool(tool: str, args: dict):
    """Call mcp-file over MCP, mapping its tool errors onto HTTP statuses."""
    try:
        return await call_tool("mcp-file", tool, args)
    except ToolError as exc:
        msg = str(exc)
        raise HTTPException(404 if "not found" in msg.lower() else 400, msg) from exc


class FileEntry(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int | None = None


@router.get("/files", response_model=list[FileEntry])
async def list_files(directory: str = "") -> list[FileEntry]:
    entries = await _file_tool("list_files", {"directory": directory})
    return [
        FileEntry(name=e["path"].split("/")[-1], path=e["path"], is_dir=e["is_dir"], size=e["size"])
        for e in entries
    ]


@router.get("/files/content")
async def read_file(path: str) -> dict:
    return {"path": path, "content": await _file_tool("read_file", {"path": path})}


@router.delete("/files")
async def delete_file(path: str) -> dict:
    await _file_tool("delete_file", {"path": path})
    return {"deleted": path}
