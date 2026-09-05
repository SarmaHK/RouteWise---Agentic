# backend/app/api/ — RouteWise Agentic

> **Owner:** Workstream A. · **Layer:** HTTP API (routers).
> Thin FastAPI routers that expose the contract endpoints — **no business logic here**.

## What goes here

- **A1 ✅:** `health.py` (`GET /health`), `route.py` (`POST /api/route/plan` **foundation
  stub** — honest `IDLE`, no fabricated route), and `router.py` (the `/api` aggregate).
- **A9 ✅:** `route.py` runs the full stabilized agent (extraction → bounded tool loop → decision)
  with per-request `request_id` correlation and typed error mapping (`502`/`503`). The agent
  status/stream routers were **decided against** — delivery stays single-shot (API_CONTRACTS §7).
- Request validation, response shaping, and the structured error envelope — all per
  [`API_CONTRACTS.md`](../../../docs/API_CONTRACTS.md).

## Boundaries

- Routers **call** the agent/services; they never implement scoring, decisions, or tool logic.
- Routers exist in A1 (health + a plan **stub**); the real planning endpoint is built in **A9**.
