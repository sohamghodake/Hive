FROM python:3.12-slim
WORKDIR /app
RUN pip install fastmcp httpx
COPY main.py .
ENV PYTHONUNBUFFERED=1
EXPOSE 8003
CMD ["python", "main.py"]
