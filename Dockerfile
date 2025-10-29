# Dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y unixodbc && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/
COPY src /app/src

RUN pip install -e /app

CMD ["python", "-m", "mssql_mcp.cli"]