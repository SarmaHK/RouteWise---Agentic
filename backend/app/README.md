# backend/app/ — RouteWise Agentic

> **Owner:** Workstream A — AI Agent & Decision Engine. · **Layer:** FastAPI application root.
> The Python application package: HTTP layer, agent, tools, schemas, and services.

## Contents

**App root (A1 ✅):** `main.py` (FastAPI entrypoint: CORS, routers, error handlers) ·
`config.py` (env-backed settings) · `logging_config.py` (logging foundation).

**Subfolders:**

- `api/` — ✅ thin FastAPI routers (`health.py`, `route.py` plan stub, `router.py`).
- `schemas/` — ✅ Pydantic models mirroring [`API_CONTRACTS.md`](../../docs/API_CONTRACTS.md).
- `services/ai/` — ✅ AI service abstraction (Qwen/Model Studio client + mock fallback).
- `agent/` — ⏳ A2+ the decision engine: understand → plan → call tools → evaluate → decide → explain → adapt.
- `tools/` — ⏳ A4+ the A ↔ B/C seam: tool interfaces + mock implementations.

## Boundaries

- **A1 foundation is implemented** (app root + `api/` + `schemas/` + `services/ai/`); the agent
  decision loop and tools are **A2+**. Routers stay thin — no business logic in them.
- Secrets come from the environment only (see [`DEVELOPMENT_RULES.md`](../../docs/DEVELOPMENT_RULES.md)).
