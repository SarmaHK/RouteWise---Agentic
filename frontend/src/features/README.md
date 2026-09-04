# frontend/src/features/ — RouteWise Agentic

> **Owner:** Workstream A (UI). · **Layer:** feature slices (the heart of the app).
> **Feature-oriented** organization: each slice owns one behavior end-to-end.

## Planned slices (created when built — phase A8)

- `travel-request/` — capture & submit the trip request.
- `agent-activity/` — agent steps/status/reasoning visualization.
- `route-results/` — recommendation, alternatives, timeline, Travel Pass view.
- Each slice holds its own `components/ hooks/ services/ state/ types.ts index.ts`.

## Boundaries

- A feature exposes a clean `index.ts` and **never reaches into another feature's internals**.
- Do not pre-create empty slice folders — create a slice when you build it (see
  [`DEVELOPMENT_RULES.md`](../../../docs/DEVELOPMENT_RULES.md)).
