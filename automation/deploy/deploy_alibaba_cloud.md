# RouteWise Agentic — Alibaba Cloud Deployment Runbook
**Workstream C: Autonomous Execution & Cloud Deployment**

This runbook guides zero-downtime containerized deployment of the complete RouteWise Agentic multi-modal travel platform to **Alibaba Cloud**.

---

## 1. Cloud Architecture Overview

```
                          [ Internet / Travelers ]
                                     │
                                     ▼
                     Alibaba Cloud Server Load Balancer (SLB)
                             [ Ports 80 / 443 SSL ]
                                     │
                     ┌───────────────┴───────────────┐
                     ▼                               ▼
       Alibaba Cloud ECS Instance       Alibaba Cloud ECS Instance
       (Frontend Nginx Container)        (FastAPI Agentic Backend)
             Port 80 / 5173                       Port 8000
                     │                               │
                     │                 ┌─────────────┴─────────────┐
                     │                 ▼                           ▼
                     │       PostgreSQL + PostGIS      Alibaba Cloud Model Studio
                     │     (ApsaraDB RDS or Docker)     (Qwen Max / DashScope API)
                     │                 │
                     └─────────────────┴─────────────► [ Travel Pass HTML & QR ]
```

- **Compute:** Alibaba Cloud Elastic Compute Service (ECS) — `ecs.g7.xlarge` (4 vCPU, 16 GiB) running Ubuntu 22.04 LTS or Alibaba Cloud Linux 3.
- **AI Engine:** Alibaba Cloud Model Studio (Qwen Max model tier via `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`).
- **Container Registry:** Alibaba Cloud Container Registry (ACR) enterprise/personal instance.
- **Database:** Containerized PostgreSQL 15 + PostGIS 3.3 (or Alibaba Cloud ApsaraDB for RDS PostgreSQL).
- **Execution & Monitoring:** Coder Work (Browser automation & booking hold) + Coder Wake (GTFS-RT disruption monitor).

---

## 2. Prerequisites & Security Group Configuration

### 2.1 Security Group Rules
Configure your ECS Security Group with the following inbound rules:

| Protocol | Port Range | Source | Purpose |
|---|---|---|---|
| SSH | `22` | Authorized IP / CIDR | Administrative SSH access |
| HTTP | `80` | `0.0.0.0/0` | Public Web UI & Reverse Proxy |
| HTTPS | `443` | `0.0.0.0/0` | Secure SSL traffic |
| Custom TCP | `8000` | VPC CIDR / `0.0.0.0/0` | RouteWise FastAPI backend API |
| Custom TCP | `5173` | VPC CIDR / `0.0.0.0/0` | Vite Development Preview (optional) |

### 2.2 Environment Secrets
Ensure the secret `MODEL_STUDIO_API_KEY` is provisioned into ECS environment variables or Alibaba Cloud Secrets Manager. **Never commit API keys to version control.**

---

## 3. Quickstart Deployment (Single-Command Docker Compose)

### Step 1: Clone and Configure Environment on ECS
```bash
git clone -b workstream-c/autonomous-execution-cloud https://github.com/SarmaHK/RouteWise---Agentic.git
cd RouteWise---Agentic

# Configure production environment
cp backend/.env.example backend/.env
```

Edit `backend/.env`:
```env
ENVIRONMENT=production
LOG_LEVEL=INFO
MODEL_STUDIO_API_KEY=your_real_dashscope_api_key_here
MODEL_STUDIO_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
MODEL_NAME=qwen-max
ENABLE_TRANSIT_INTELLIGENCE=true
ENABLE_AUTONOMOUS_EXECUTION=true
DATABASE_URL=postgresql://routewise:routewise_pass@db:5432/routewise_transit
BACKEND_CORS_ORIGINS=http://your-ecs-ip,http://your-domain.com
```

### Step 2: Launch Complete Multi-Container Stack
```bash
chmod +x automation/deploy/deploy_ecs.sh
./automation/deploy/deploy_ecs.sh
```

Or execute directly via Docker Compose:
```bash
docker compose up -d --build
```

---

## 4. Deploying via Alibaba Cloud Container Registry (ACR)

If building images in CI/CD (GitHub Actions / Alibaba Cloud CodePipeline) and deploying to multiple ECS instances:

```bash
# 1. Log in to Alibaba Cloud Container Registry
docker login --username=your_aliyun_username registry.ap-southeast-1.aliyuncs.com

# 2. Build and tag images
docker build -t registry.ap-southeast-1.aliyuncs.com/routewise/backend:v1.0 -f backend/Dockerfile .
docker build -t registry.ap-southeast-1.aliyuncs.com/routewise/frontend:v1.0 -f frontend/Dockerfile ./frontend

# 3. Push to ACR
docker push registry.ap-southeast-1.aliyuncs.com/routewise/backend:v1.0
docker push registry.ap-southeast-1.aliyuncs.com/routewise/frontend:v1.0

# 4. On ECS instance, pull and start
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

---

## 5. Verification & Live Demo Checks

### 5.1 System Health
```bash
curl -i http://localhost:8000/api/health
# Expected: HTTP/1.1 200 OK -> {"status":"ok","environment":"production"}
```

### 5.2 Plan Golden Demo Route (Colombo Fort -> Ella)
```bash
curl -X POST http://localhost:8000/api/route/plan \
  -H "Content-Type: application/json" \
  -d '{"raw_text": "I need to travel from Colombo Fort to Ella with heavy luggage, budget LKR 2000"}'
```

### 5.3 Test Disruption Injection & Autonomous Re-Planning
```bash
# 1. Inject high-delay landslide disruption on train R1
curl -X POST http://localhost:8000/api/route/disruption/inject \
  -H "Content-Type: application/json" \
  -d '{"trip_id": "trip_train_mainline_1005", "delay_minutes": 55.0, "delay_risk": "high"}'

# 2. Autonomous re-planning endpoint
curl -X POST http://localhost:8000/api/route/replan \
  -H "Content-Type: application/json" \
  -d '{"request": {"raw_text": "Colombo Fort to Ella with heavy luggage"}, "previous_recommendation_id": "R1"}'
# Expected: Status COMPLETED, R2 (Express Bus) recommended as optimal resilient route.

# 3. Restore feed
curl -X POST http://localhost:8000/api/route/disruption/restore
```

### 5.4 Test Offline Travel Pass Generation
```bash
# Get standalone offline HTML voucher
curl -X POST http://localhost:8000/api/route/travel-pass/html \
  -H "Content-Type: application/json" \
  -d '{
    "plan": { ... },
    "traveler_name": "Samantha Perera",
    "seats": 2
  }' > travel_pass_voucher.html
```

---

## 6. Disaster Recovery & Rollback

- **Feed Restoration:** In case of test feed corruption, execute `POST /api/route/disruption/restore` to revert GTFS-RT feed to pristine backup state.
- **Rollback Containers:**
  ```bash
  docker compose down
  git checkout <previous_stable_commit>
  docker compose up -d --build
  ```
