# backend/app/tools/ — RouteWise Agentic

> **Owner:** Workstream A (interfaces + mocks) → **B/C** (real implementations). · **Layer:** tool seam.
> The **stable boundary** through which the agent consumes transit intelligence (B) and execution (C).

## What goes here (A4: tool contract + execution; A7: mock intelligence; real providers later in B/C)

- `search_routes`, `get_fare_estimate`, `get_delay_prediction`, `get_route_details` → **B**.
- `check_availability`, `prepare_booking` → **C**.
- Every result carries `data_source` (`mock` / `simulated` / `live`).
- **A7 availability:** the four Workstream-A data tools above are `AVAILABLE` on deterministic
  **mock** data (`data_source=mock`, `status=mock_data`); `check_availability` and `prepare_booking`
  remain honest `NOT_IMPLEMENTED` stubs. The executor gates every one of them, so no tool can ever
  fabricate a result — an unknown route id is a structured `ROUTE_NOT_FOUND` failure, not data.

## A4/A7 modules (capability-execution system)

- `base.py` — the contract: `Tool` ABC, `ToolResult` (`success` / `tool_name` / `data_source` /
  `data` / `error`), `ToolError` + `ToolErrorCode` (**A7 adds `ROUTE_NOT_FOUND`**), `ToolStatus`,
  `ToolAvailability`.
- `executor.py` — `ToolExecutor`: availability gate → Pydantic input validation → bounded execution
  (timeout) → exception/malformed guards. Always returns a structured result; never raises.
- `registry.py` — `ToolRegistry`: `register` (rejects duplicates) / `get` / `names` /
  `list_available` / `status` / `describe` / `execute`; plus `build_tools` / `get_tools` DI.
  `_default_tools()` constructs **one** `MockRouteIntelligence` and shares it with all four data
  tools, which is what makes them provably consistent about the same route.
- `intelligence.py` — **A7**: `MockRouteIntelligence` + `MockRoute`, the single source of mock route
  truth (7 routes / 3 corridors, route-level figures **and** leg detail that sums to those figures).
  Four honest views of one dataset: `candidates_for` (search), `fare_estimate`, `delay_prediction`,
  `route_details`. Deterministic, side-effect free, `None` for an unknown id. **This is the
  Workstream-B replacement point** — B supplies real data behind these same accessors and the same
  tool signatures, and nothing above this layer changes.
- `capabilities.py` — the concrete tools: `MockRouteSearchTool` (+ `SearchRoutesArgs`) and the three
  A7 intelligence tools (+ the shared `RouteIdArgs`), plus the two `NOT_IMPLEMENTED` C stubs. Each is
  an independent `Tool` subclass — there is deliberately **no** second tool base class, executor,
  registry or result class.
- `candidates.py` — `MockCandidateProvider`, a thin A3-compatible **facade** over `intelligence.py`
  (the corridor fixtures were moved there in A7, not duplicated).

Flow (A4 brief §11): **Agent → `ToolRegistry` → `ToolExecutor` → `Tool` → structured `ToolResult`.**

## Boundaries

- Signatures are fixed in [`API_CONTRACTS.md` §6](../../../docs/API_CONTRACTS.md); B/C replace the
  mocks later with **no signature change**, so agent code does not change.
- **Layering (A7 brief §3):** the agent and the decision engine never import `intelligence.py` —
  only the tools do. Agents decide what they need, tools expose capabilities, mock providers supply
  deterministic data, and the A6 engine makes the decision.
- `prepare_booking` **only prepares** — it never commits an irreversible action (that belongs to C,
  gated by explicit user confirmation).
