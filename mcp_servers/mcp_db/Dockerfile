FROM python:3.12-slim
WORKDIR /app
RUN pip install fastmcp asyncpg
COPY main.py .
ENV PYTHONUNBUFFERED=1
EXPOSE 8002
CMD ["python", "main.py"]
