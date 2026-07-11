import os
from pathlib import Path

import aiofiles
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

WORKSPACE = Path(os.getenv("WORKSPACE_PATH", "/workspace")).resolve()

app = FastAPI(title="mcp-file")


def _safe_path(relative: str) -> Path:
    resolved = (WORKSPACE / relative).resolve()
    if not str(resolved).startswith(str(WORKSPACE)):
        raise HTTPException(400, f"Path escapes workspace: {relative}")
    return resolved


class Params(BaseModel):
    params: dict


@app.post("/tools/read_file")
async def read_file(body: Params):
    p = _safe_path(body.params["path"])
    if not p.exists():
        raise HTTPException(404, f"{body.params['path']} not found")
    async with aiofiles.open(p) as f:
        return {"content": await f.read()}


@app.post("/tools/write_file")
async def write_file(body: Params):
    p = _safe_path(body.params["path"])
    p.parent.mkdir(parents=True, exist_ok=True)
    content = body.params["content"]
    async with aiofiles.open(p, "w") as f:
        await f.write(content)
    return {"result": f"Written {len(content)} bytes to {body.params['path']}"}


@app.post("/tools/list_files")
async def list_files(body: Params):
    p = _safe_path(body.params.get("directory", ""))
    if not p.is_dir():
        raise HTTPException(400, "Not a directory")
    return {"files": [str(c.relative_to(WORKSPACE)) for c in p.iterdir()]}


@app.post("/tools/delete_file")
async def delete_file(body: Params):
    p = _safe_path(body.params["path"])
    p.unlink(missing_ok=True)
    return {"result": f"Deleted {body.params['path']}"}


@app.get("/health")
def health():
    return {"status": "ok"}
