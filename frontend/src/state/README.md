# frontend/src/state/ — RouteWise Agentic

> **Owner:** Workstream A (UI). · **Layer:** shared client state.
> Small, boring client state shared across features.

## What goes here (built in phase A8)

- A lightweight store + slices for agent state, latest plan, selected route, and the trip-form
  draft.

## Boundaries

- **Server data** (plan, agent steps, routes) is fetched from the API — do not re-derive business
  rules client-side. **Never store secrets here.** No heavyweight state library without a
  documented decision.
