# backend/tests/ — RouteWise Agentic

> **Owner:** Workstream A (backend). · **Layer:** tests.
> Pytest suite for the backend: agent behavior, tools, schemas, and API contracts.

## What goes here

- **A1 ✅ foundation tests** — app starts and `GET /health` works (`test_health.py`), config
  loads safely with no secrets leaked (`test_config.py`), the `POST /api/route/plan` foundation
  stub honors the contract (`test_route_plan_foundation.py`), the AI service factory selects the
  right client (`test_ai_service.py`), and real Qwen connectivity is exercised only when
  `MODEL_STUDIO_API_KEY` is present (`test_ai_connectivity.py`, skipped otherwise). Shared
  fixtures live in `conftest.py`.
- **A2 ✅ request understanding** — `test_travel_request_extraction.py`,
  `test_route_plan_understanding.py` (NL → validated `TravelRequest`, honest clarification).
- **A3 ✅ agent + decision** — `test_agent_state_machine.py`, `test_decision_engine.py`,
  `test_route_agent.py`, `test_route_plan_agent.py` (canonical states, deterministic scoring, the
  observable `agent_actions[]` trace).
- **A4 ✅ tool seam** — `test_tool_contract.py`, `test_tool_registry.py`, `test_tool_execution.py`,
  `test_tool_stubs.py`, `test_agent_tool_integration.py` (`ToolResult`, availability model,
  registry, executor gates; honest `NOT_IMPLEMENTED` stubs).
- **A5 ✅ tool-calling loop** — `test_qwen_tool_calling.py`, `test_agent_loop.py` (derived tool
  definitions, bounded multi-step loop, duplicate-call guard, sanitized args; the live-Qwen tests
  skip without a key).
- **A6 ✅ decision engine** — `test_decision_engine_a6.py` (structured violations, defensive
  candidates, normalization, preference weights, delay penalty, ranking, grounded explanations).
- **A7 ✅ mock intelligence** — `test_mock_intelligence_a7.py` (the 31 required scenarios: shared
  provider consistency, fare/delay/details payloads, `ROUTE_NOT_FOUND`, registry/executor behavior,
  the multi-step agent loop, and A6-engine integration — plus the golden trace, the not-hard-coded
  sequence proof, the `mock-qwen` labelling proof, the failure-mode matrix, and an API end-to-end run).
- **Contract tests** — endpoint shapes match [`API_CONTRACTS.md`](../../docs/API_CONTRACTS.md).
- **Determinism checks** — same input + same mock data ⇒ same recommendation (critical for a
  reliable demo). **A7 makes this end-to-end:** the shared mock dataset has no randomness, so the
  golden Colombo Fort → Ella run always yields the same trace and the same decision.

Run with `pytest` from `backend/`. The whole A1–A7 suite passes with **zero failures and zero
errors**; only the live-Qwen connectivity tests skip (no `MODEL_STUDIO_API_KEY` in this environment).

## Boundaries

- Frontend tests live with the frontend (created at scaffold time). Backend tests target
  `backend/app/`. **A7 tests the tool seam and the agent only — no Workstream B/C behavior
  (ML, GTFS, database, booking, automation) is exercised, because none is implemented.**
