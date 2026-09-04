# backend/app/tools/ — RouteWise Agentic

> **Owner:** Workstream A (interfaces + mocks) → **B/C** (real implementations). · **Layer:** tool seam.
> The **stable boundary** through which the agent consumes transit intelligence (B) and execution (C).

## What goes here (interfaces in A4; mocks in A4/A7)

- `search_routes`, `get_fare_estimate`, `get_delay_prediction`, `get_route_details` → **B**.
- `check_availability`, `prepare_booking` → **C**.
- Every result carries `data_source` (`mock` / `simulated` / `live`).

## Boundaries

- Signatures are fixed in [`API_CONTRACTS.md` §6](../../../docs/API_CONTRACTS.md); B/C replace the
  mocks later with **no signature change**, so agent code does not change.
- `prepare_booking` **only prepares** — it never commits an irreversible action (that belongs to C,
  gated by explicit user confirmation).
