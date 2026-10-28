FROM python:3.12-slim

WORKDIR /app

# Install exactly what uv.lock pins, into /opt/venv. --locked fails the build if
# pyproject.toml has changed without the lock being regenerated (`make lock`).
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_PYTHON_DOWNLOADS=never UV_COMPILE_BYTECODE=1 \
    PATH=/opt/venv/bin:$PATH
COPY pyproject.toml uv.lock ./
RUN --mount=from=ghcr.io/astral-sh/uv:0.13.6,source=/uv,target=/bin/uv \
    uv sync --locked --no-dev --no-install-project --no-cache

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
