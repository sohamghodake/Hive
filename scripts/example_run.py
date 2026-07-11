"""End-to-end smoke test: create an agent, trigger a run, poll until done.

Usage:
    python scripts/example_run.py
"""
import asyncio
import os
import time

import httpx

BASE_URL = os.getenv("HIVE_API_URL", "http://localhost:8000")


async def main():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=120.0) as client:
        # 1. Health check
        r = await client.get("/health")
        r.raise_for_status()
        print("✓ API healthy")

        # 2. Create (or reuse) agent
        r = await client.post("/api/agents", json={
            "name": "example-agent",
            "system_prompt": (
                "You are a concise assistant. When asked a question, "
                "answer it directly without using any tools unless necessary."
            ),
            "model": "kimi-k2.7-code:cloud",
            "tools": ["web_search"],
        })
        if r.status_code == 201:
            agent = r.json()
            print(f"✓ Created agent {agent['id']}")
        else:
            agents = (await client.get("/api/agents")).json()
            agent = next((a for a in agents if a["name"] == "example-agent"), agents[0])
            print(f"✓ Reusing agent {agent['id']}")

        # 3. Create a run
        r = await client.post("/api/runs", json={
            "agent_id": agent["id"],
            "input": {"message": "What is 2 + 2? Answer in one sentence."},
        })
        r.raise_for_status()
        run = r.json()
        print(f"✓ Run created: {run['id']} (status={run['status']})")

        # 4. Poll until terminal
        run_id = run["id"]
        for _ in range(60):
            await asyncio.sleep(2)
            r = await client.get(f"/api/runs/{run_id}")
            run = r.json()
            print(f"  status={run['status']}")
            if run["status"] in ("completed", "failed"):
                break

        if run["status"] == "completed":
            print(f"\n✓ Run completed. Output:\n{run['output']}")
        else:
            print(f"\n✗ Run failed. Error:\n{run.get('error')}")


asyncio.run(main())
