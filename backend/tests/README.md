# backend/tests/ — RouteWise Agentic

> **Owner:** Workstream A (backend). · **Layer:** tests.
> Pytest suite for the backend: agent behavior, tools, schemas, and API contracts.

## What goes here

- **A1 ✅ foundation tests** — app starts and `GET /health` works (`test_health.py`), config
  loads safely with no secrets leaked (`test_config.py`), the `POST /api/route/plan` foundation
  stub honors the contract (`test_route_plan_foundation.py`), the AI service factory selects the
  right client (`test_ai_service.py`), and real Qwen connectivity is exercised only when
  `MODEL_STUDIO_API_KEY` is present (`test_ai_connectivity.py`, skipped otherwise). Shared
  fixtures live in `conftest.py`.
- **Unit tests (A2+ ⏳)** — agent scoring/decision, constraint filtering, tool mocks.
- **Contract tests** — endpoint shapes match [`API_CONTRACTS.md`](../../docs/API_CONTRACTS.md).
- **Determinism checks** — same input + same mock data ⇒ same recommendation (critical for a
  reliable demo).

## Boundaries

- Frontend tests live with the frontend (created at scaffold time). Backend tests target
  `backend/app/`. **A1 added foundation tests only — no agent/tool feature tests yet.**
