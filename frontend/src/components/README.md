# frontend/src/components/ — RouteWise Agentic

> **Owner:** Workstream A (UI). · **Layer:** shared UI / design system.
> Reusable, presentational, **registered** components that consume design tokens.

## Planned groups (created when built)

- `ui/` — Button, Input, Select, Card, Badge, Modal, Tooltip, StatusIndicator.
- `agent/` — AgentActivity, AgentStep, AgentStatus, ReasoningSummary.
- `travel/` — TripForm, RouteCard, RouteTimeline, TransportLeg, FareDisplay, DelayBadge, TravelPass.

## Boundaries

- **Check the registry first** — [`DESIGN_SYSTEM.md` §13](../../../docs/DESIGN_SYSTEM.md); no
  duplicate components.
- Components **render only**: no data fetching, no domain logic, no hard-coded styles (tokens only).
