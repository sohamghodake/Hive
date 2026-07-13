import httpx
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from api.config import settings

router = APIRouter()


async def _mcp(tool: str, params: dict) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{settings.mcp_file_url}/tools/{tool}",
            json={"params": params},
        )
        if resp.status_code == 404:
            raise HTTPException(404, resp.json().get("detail", "Not found"))
        if resp.status_code == 400:
            raise HTTPException(400, resp.json().get("detail", "Bad request"))
        resp.raise_for_status()
        return resp.json()


class FileEntry(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int | None = None


@router.get("/files")
async def list_files(directory: str = "") -> list[dict]:
    result = await _mcp("list_files", {"directory": directory})
    files = result.get("files", [])
    # Enrich with minimal metadata
    entries = []
    for f in sorted(files):
        entries.append({"name": f.split("/")[-1], "path": f, "is_dir": False})
    return entries


@router.get("/files/content")
async def read_file(path: str) -> dict:
    result = await _mcp("read_file", {"path": path})
    return {"path": path, "content": result.get("content", "")}


@router.delete("/files")
async def delete_file(path: str) -> dict:
    await _mcp("delete_file", {"path": path})
    return {"deleted": path}
