# backend/app/tools/ — RouteWise Agentic

> **Owner:** Workstream A (interfaces + mocks) → **B/C** (real implementations). · **Layer:** tool seam.
> The **stable boundary** through which the agent consumes transit intelligence (B) and execution (C).

## What goes here (A4: tool contract + execution; real providers later in B/C)

- `search_routes`, `get_fare_estimate`, `get_delay_prediction`, `get_route_details` → **B**.
- `check_availability`, `prepare_booking` → **C**.
- Every result carries `data_source` (`mock` / `simulated` / `live`).
- **A4 availability:** only `search_routes` is `AVAILABLE` (deterministic **mock** data); the other
  five are honest `NOT_IMPLEMENTED` stubs the executor gates so they never fabricate a result.

## A4 modules (capability-execution system)

- `base.py` — the contract: `Tool` ABC, `ToolResult` (`success` / `tool_name` / `data_source` /
  `data` / `error`), `ToolError` + `ToolErrorCode`, `ToolStatus`, `ToolAvailability`.
- `executor.py` — `ToolExecutor`: availability gate → Pydantic input validation → bounded execution
  (timeout) → exception/malformed guards. Always returns a structured result; never raises.
- `registry.py` — `ToolRegistry`: `register` (rejects duplicates) / `get` / `names` /
  `list_available` / `status` / `describe` / `execute`; plus `build_tools` / `get_tools` DI.
- `capabilities.py` — the concrete tools: `MockRouteSearchTool` (+ `SearchRoutesArgs`) and the five
  `NOT_IMPLEMENTED` stubs.
- `candidates.py` — `MockCandidateProvider`, the deterministic mock data behind `search_routes`.

Flow (A4 brief §11): **Agent → `ToolRegistry` → `ToolExecutor` → `Tool` → structured `ToolResult`.**

## Boundaries

- Signatures are fixed in [`API_CONTRACTS.md` §6](../../../docs/API_CONTRACTS.md); B/C replace the
  mocks later with **no signature change**, so agent code does not change.
- `prepare_booking` **only prepares** — it never commits an irreversible action (that belongs to C,
  gated by explicit user confirmation).
