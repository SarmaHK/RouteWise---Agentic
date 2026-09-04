# frontend/src/hooks/ — RouteWise Agentic

> **Owner:** Workstream A (UI). · **Layer:** cross-feature hooks.
> Reusable behavior/state hooks shared across features.

## What goes here (built in phase A8)

- `useAgentStream` (hides the delivery mechanism — embedded vs streamed), `useMediaQuery`,
  `useApi`, and shared form hooks.

## Boundaries

- Hooks encapsulate **behavior**; they do not render UI. Feature-local hooks stay inside that
  feature's own `hooks/`.
