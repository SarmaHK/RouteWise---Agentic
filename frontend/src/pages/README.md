# frontend/src/pages/ — RouteWise Agentic

> **Owner:** Workstream A (UI). · **Layer:** pages (screens).
> Thin screens that map a URL to a composed view — **no business logic**.

## What goes here (built in phase A8)

- `Landing`, `PlanTrip`, `NotFound` — each composes features and handles page-level
  loading/error/empty/success states.

## Boundaries

- Pages compose [`../features/`](../features/README.md); they never call the API directly (use
  [`../services/`](../services/README.md)) or hold domain logic. See
  [`ARCHITECTURE.md` §3](../../../docs/ARCHITECTURE.md).
