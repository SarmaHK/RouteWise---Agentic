# frontend/src/services/ — RouteWise Agentic

> **Owner:** Workstream A (UI). · **Layer:** data / services.
> The frontend data layer — the **only** place that talks to the backend.

## Groups

- `api/` — **A1 ✅** the single backend client: `client.ts` (the only `fetch` caller — headers,
  timeouts, error normalization), `health.ts` (`GET /health`), `routePlan.ts`
  (`POST /api/route/plan`), and `index.ts` (barrel export).
- `mock/` — ⏳ A8 clearly-labeled fallback fixtures for demo resilience (backend unreachable mid-demo).
- `formatters/` — ⏳ A8 LKR currency, durations, times, distances.

## Boundaries

- Components never call `fetch` directly; they go through `services/api`. Shapes mirror
  [`API_CONTRACTS.md`](../../../docs/API_CONTRACTS.md). Mock data is **never** presented as
  real-time (see [`AGENT_SPEC.md` §15](../../../docs/AGENT_SPEC.md)).
