# frontend/src/features/ — RouteWise Agentic

> **Owner:** Workstream A (UI). · **Layer:** feature slices (the heart of the app).
> **Feature-oriented** organization: each slice owns one behavior end-to-end.

## Slices

- `route-planner/` 🟩 (built in A8) — the whole plan flow: capture & submit the trip request, the
  agent activity rail, and the recommendation / alternatives / timeline results.
- A8 shipped **one** cohesive slice rather than the earlier three-slice sketch (`travel-request`,
  `agent-activity`, `route-results`): all three derive from **one** `POST /api/route/plan` response
  and share **one** state machine, so splitting them would fragment that state and create near-empty
  folders. See [`ARCHITECTURE.md` §3.1](../../../docs/ARCHITECTURE.md). It can be split later if the
  flow grows genuinely independent sub-behaviors.
- Shared building blocks live in [`../components/`](../components/README.md), not in the slice.

## Boundaries

- A feature exposes a clean `index.ts` and **never reaches into another feature's internals**.
- Do not pre-create empty slice folders — create a slice when you build it (see
  [`DEVELOPMENT_RULES.md`](../../../docs/DEVELOPMENT_RULES.md)).
