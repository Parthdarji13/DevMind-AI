# DevMind AI — Backend Production Dockerfile
FROM python:3.12-slim

# Install system dependencies (git for repo cloning, curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application source
COPY app/ ./app/

# Create persistent storage directories
RUN mkdir -p /app/data/indices /app/data/temp_repos

# Set environment defaults
ENV FASTAPI_HOST=0.0.0.0 \
    FASTAPI_PORT=8000 \
    DATA_DIR=/app/data \
    INDICES_DIR=/app/data/indices \
    TEMP_STORAGE_DIR=/app/data/temp_repos \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Start FastAPI application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
