# frontend/src/components/ — RouteWise Agentic

> **Owner:** Workstream A (UI). · **Layer:** shared UI / design system.
> Reusable, presentational, **registered** components that consume design tokens.

## Groups (built in A8)

- `ui/` 🟩 — Button, Badge, Card, StatusIndicator, Alert. (Input, Select, Modal, Tooltip still 🟥 planned.)
- `agent/` 🟩 — AgentActivity, AgentStep, AgentStatus, ReasoningSummary.
- `travel/` 🟩 — TripForm, RouteCard, RouteTimeline, TransportLeg, FareDisplay, DelayBadge, ModeIcon,
  TravelRequestSummary. (TravelPass 🟥 stays a Workstream-C contract.)

Each group is **flat files** (`Component.tsx` + `Component.css`, tokens only) with one `index.ts`
barrel. **No test runner was added in A8**, so there are no `.test.tsx` files yet — see
[`DESIGN_SYSTEM.md` §13.2](../../../docs/DESIGN_SYSTEM.md).

## Boundaries

- **Check the registry first** — [`DESIGN_SYSTEM.md` §13](../../../docs/DESIGN_SYSTEM.md); no
  duplicate components.
- Components **render only**: no data fetching, no domain logic, no hard-coded styles (tokens only).
