FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastmcp==4.0.10 "uvicorn[standard]" aiofiles
COPY main.py .
ENV PYTHONUNBUFFERED=1
EXPOSE 8001
# Serves MCP over streamable HTTP at /mcp, plus GET /health.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
