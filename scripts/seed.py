"""Seed the database with a starter set of agents for local development.

Idempotent: agents already present by name are left untouched, so this is safe
to re-run against an existing database.
"""
import asyncio
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.models.agent import Agent

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://hive:hivepass@localhost:5432/hive"
)

# Only models with tool-calling support belong here; see README "Choosing a model".
DEFAULT_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")

SEED_AGENTS = [
    {
        "name": "research-agent",
        "description": "General-purpose research and summarisation agent",
        "system_prompt": (
            "You are a research assistant. Use web_search to gather information and "
            "write_file to save notes or reports to the workspace. Cite the sources "
            "you used. Produce clear, structured summaries and keep them concise."
        ),
        "tools": ["web_search", "read_file", "write_file"],
    },
    {
        "name": "market-researcher",
        "description": "Researches topics, fetches web data, and writes structured reports",
        "system_prompt": (
            "You are a market research analyst. Given a topic: search the web for "
            "current information, fetch relevant pages when you need detail, then "
            "write a structured report to the workspace as a markdown file. "
            "Lead with the key findings."
        ),
        "tools": ["web_search", "http_get", "write_file", "read_file"],
    },
    {
        "name": "file-manager",
        "description": "Reads, writes, and organises files in the workspace",
        "system_prompt": (
            "You are a file management assistant with access to a sandboxed "
            "workspace. You can read files, write new ones, and list directory "
            "contents. Confirm what you changed after each operation."
        ),
        "tools": ["read_file", "write_file", "list_files"],
    },
    {
        "name": "data-analyst",
        "description": "Queries the database and analyses data to answer questions",
        "system_prompt": (
            "You are a senior data analyst with SQL expertise. Use query_database to "
            "run read-only SQL against the Hive database rather than guessing at "
            "numbers. Present findings clearly, highlighting the key insight first."
        ),
        "tools": ["query_database", "write_file"],
    },
    {
        "name": "knowledge-assistant",
        "description": "Answers questions from documents uploaded to the knowledge base",
        "system_prompt": (
            "You answer questions using the document knowledge base. Call "
            "list_documents to see what is available, then read_document to pull the "
            "full text of the ones you need. Ground every answer in those documents "
            "and say so plainly when they do not cover the question."
        ),
        "tools": ["list_documents", "read_document", "write_file"],
    },
]


async def main():
    engine = create_async_engine(DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    created = 0
    async with factory() as db:
        for spec in SEED_AGENTS:
            existing = await db.execute(select(Agent).where(Agent.name == spec["name"]))
            if existing.scalar_one_or_none():
                print(f"· {spec['name']} already exists, skipping")
                continue
            db.add(Agent(model=DEFAULT_MODEL, config={"max_steps": 8}, **spec))
            created += 1
            print(f"✓ created {spec['name']}")
        await db.commit()

    await engine.dispose()
    print(f"\nSeeded {created} new agent(s) using model {DEFAULT_MODEL}.")


if __name__ == "__main__":
    asyncio.run(main())
