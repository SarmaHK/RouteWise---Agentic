# ==============================================================================
# RouteWise Agentic Backend — Production Container
# Compatible with Alibaba Cloud Elastic Compute Service (ECS) and Container Registry (ACR)
# ==============================================================================

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app:/app/backend"

WORKDIR /app

# Install minimal OS packages for build and health check
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy backend, trained ML models, GTFS-RT data, and automation suites
COPY backend /app/backend
COPY models /app/models
COPY data /app/data
COPY automation /app/automation

WORKDIR /app/backend

EXPOSE 8000

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
