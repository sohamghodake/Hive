import httpx
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="mcp-api")


class Params(BaseModel):
    params: dict


@app.post("/tools/http_get")
async def http_get(body: Params):
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(body.params["url"], headers=body.params.get("headers", {}))
        return {"status_code": r.status_code, "body": r.text}


@app.post("/tools/http_post")
async def http_post(body: Params):
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            body.params["url"],
            json=body.params.get("payload", {}),
            headers=body.params.get("headers", {}),
        )
        return {"status_code": r.status_code, "body": r.text}


@app.get("/health")
def health():
    return {"status": "ok"}
