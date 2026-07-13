FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .

RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    pydantic \
    pydantic-settings \
    "sqlalchemy[asyncio]" \
    asyncpg \
    alembic \
    langchain-openai \
    langchain-groq \
    langgraph \
    mcp \
    fastmcp \
    httpx \
    aiofiles \
    python-dotenv \
    python-multipart \
    pgvector \
    sse-starlette

COPY api/ ./api/
COPY orchestrator/ ./orchestrator/
COPY db/ ./db/
COPY migrations/ ./migrations/
COPY scripts/ ./scripts/
COPY alembic.ini .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port 8000"]
