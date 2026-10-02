# Built from the repo root (see docker-compose.yml) so it can share rag/ with the
# api image — query and passage embeddings must come from the same model.
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastmcp==4.0.10 "uvicorn[standard]" asyncpg fastembed==0.8.1

ENV FASTEMBED_CACHE_PATH=/models PYTHONUNBUFFERED=1 PYTHONPATH=/app
COPY rag/ ./rag/
# Download the embedding model at build time; otherwise the first search after
# every container start blocks on a ~130 MB download.
RUN python -c "from rag.embeddings import embed_query; embed_query('warmup')"

COPY mcp_servers/mcp_db/main.py .
EXPOSE 8002
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
