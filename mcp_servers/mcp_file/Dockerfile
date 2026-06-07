FROM python:3.12-slim
WORKDIR /app
RUN pip install fastmcp aiofiles
COPY main.py .
ENV PYTHONUNBUFFERED=1
EXPOSE 8001
CMD ["python", "main.py"]
