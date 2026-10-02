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
    fastmcp==4.0.10 \
    fastembed==0.8.1 \
    pypdf \
    httpx \
    aiofiles \
    python-dotenv \
    python-multipart \
    pgvector \
    sse-starlette

ENV FASTEMBED_CACHE_PATH=/models
COPY rag/ ./rag/
# Bake the embedding model into the image so document indexing works offline
# and the first upload does not block on a ~130 MB download.
RUN PYTHONPATH=/app python -c "from rag.embeddings import embed_passages; embed_passages(['warmup'])"

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
