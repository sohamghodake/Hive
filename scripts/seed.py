"""Seed the database with a default agent for local development."""
import asyncio
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.models.agent import Agent

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://hive:hivepass@localhost:5432/hive"
)


async def main():
    engine = create_async_engine(DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        result = await db.execute(select(Agent).where(Agent.name == "research-agent"))
        if result.scalar_one_or_none():
            print("Seed agent already exists.")
            await engine.dispose()
            return

        agent = Agent(
            name="research-agent",
            description="General-purpose research and summarisation agent",
            system_prompt=(
                "You are a research assistant. Use web_search to gather information, "
                "read_file and write_file to manage notes in the workspace, "
                "and query_database to look up internal data. "
                "Produce clear, structured summaries."
            ),
            model="kimi-k2.7-code:cloud",
            tools=["read_file", "write_file", "web_search", "query_database"],
        )
        db.add(agent)
        await db.commit()
        await db.refresh(agent)
        print(f"Created agent: {agent.id} ({agent.name})")

    await engine.dispose()


asyncio.run(main())
