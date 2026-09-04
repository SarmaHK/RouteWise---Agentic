# backend/app/schemas/ — RouteWise Agentic

> **Owner:** Workstream A. · **Layer:** schemas / types.
> Pydantic models that mirror the API contracts **exactly**.

## What goes here

- **A1 ✅ (contract shapes defined):** `route.py` — `PlanRequest`/`PlanResponse`, the
  route/leg/recommendation shapes, `AgentAction`/`AgentState`, `DataSource`; `common.py` —
  `HealthResponse` and the structured error envelope. These mirror the contract now so the
  frontend `types/` and the backend stay aligned; they are **populated with real data from
  A2/A9**.

## Boundaries

- Must match [`API_CONTRACTS.md`](../../../docs/API_CONTRACTS.md): `snake_case`, LKR money,
  ISO 8601 `+05:30`, and the canonical agent states.
- The **contract is changed in the doc first**, then reflected here. Frontend `types/` mirrors
  these shapes.
