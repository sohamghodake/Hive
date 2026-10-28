FROM python:3.12-slim
WORKDIR /app
# Exported from uv.lock (`make lock`): every package pinned and hash-checked.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
ENV PYTHONUNBUFFERED=1
EXPOSE 8003
# Serves MCP over streamable HTTP at /mcp, plus GET /health.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
