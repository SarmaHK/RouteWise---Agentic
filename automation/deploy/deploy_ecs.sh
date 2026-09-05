#!/usr/bin/env bash
# ==============================================================================
# RouteWise Agentic — Automated Alibaba Cloud ECS Deployment Script
# Workstream C: Autonomous Execution & Cloud
# ==============================================================================

set -euo pipefail

echo "================================================================"
echo " RouteWise Agentic — Deploying to Alibaba Cloud ECS"
echo "================================================================"

# 1. Verify Docker & Docker Compose installation
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker is not installed. Please install docker before proceeding."
    exit 1
fi

DOCKER_COMPOSE_CMD=""
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
else
    echo "[ERROR] Neither 'docker compose' nor 'docker-compose' found."
    exit 1
fi

echo "[INFO] Using: $DOCKER_COMPOSE_CMD"

# 2. Check environment file
if [ ! -f "backend/.env" ]; then
    echo "[WARN] backend/.env not found! Creating from backend/.env.example..."
    cp backend/.env.example backend/.env
    echo "[INFO] Please review backend/.env to configure your MODEL_STUDIO_API_KEY."
fi

# 3. Pull & Build Containers
echo "[INFO] Building and starting containerized services (db, backend, frontend)..."
$DOCKER_COMPOSE_CMD down --remove-orphans || true
$DOCKER_COMPOSE_CMD up -d --build

# 4. Wait for database and backend health checks
echo "[INFO] Waiting for backend service to become healthy..."
MAX_ATTEMPTS=20
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    ATTEMPT=$((ATTEMPT + 1))
    if curl -s -f http://localhost:8000/api/health > /dev/null 2>&1; then
        echo "[SUCCESS] Backend is healthy and responding!"
        break
    fi
    echo "  Attempt $ATTEMPT/$MAX_ATTEMPTS: Backend starting up... sleeping 3s"
    sleep 3
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo "[ERROR] Backend service failed to become healthy within timeout."
    $DOCKER_COMPOSE_CMD logs backend
    exit 1
fi

# 5. Output operational endpoints
PUBLIC_IP=$(curl -s ifconfig.me || echo "localhost")

echo "================================================================"
echo " ROUTEWISE AGENTIC DEPLOYMENT COMPLETED SUCCESSFULLY"
echo "================================================================"
echo "  Frontend Web UI:       http://$PUBLIC_IP/"
echo "  Backend API Root:      http://$PUBLIC_IP:8000/"
echo "  API OpenAPI Docs:      http://$PUBLIC_IP:8000/docs"
echo "  Health Check:          http://$PUBLIC_IP:8000/api/health"
echo "  GTFS-RT Monitor:       http://$PUBLIC_IP:8000/api/route/disruption/status"
echo "================================================================"
