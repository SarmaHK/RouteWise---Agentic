# frontend/src/types/ — RouteWise Agentic

> **Owner:** Workstream A (UI). · **Layer:** schemas / types.
> Shared domain types that mirror the API contracts.

## What goes here

- **A1 ✅ foundation subset** (`api.ts`) — `HealthResponse`, `PlanRequest`, `PlanResponse`,
  `AgentAction`, the `AgentState` union (the **9 canonical agent states**), and `DataSource`.
- **A8 ⏳** — the full route/leg/recommendation shapes as the interface is built out; types are
  tightened as contracts mature.

## Boundaries

- Must stay in sync with [`API_CONTRACTS.md`](../../../docs/API_CONTRACTS.md) and the backend
  [`schemas/`](../../../backend/app/schemas/README.md). **Contract first, types second** —
  TypeScript catches drift early.
