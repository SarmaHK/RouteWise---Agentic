# PROJECT.md — RouteWise Agentic

> Source of truth #1. Read after [`../AI_CONTEXT.md`](../AI_CONTEXT.md). This document defines
> **what** the project is and **why**. It must stay aligned with the official project proposal.
> **Do not invent features** that are not part of the documented direction.
>
> This is the **shared** project overview for **all three workstreams** — not A-only. Detailed
> workstream coordination lives in [`WORKSTREAMS.md`](WORKSTREAMS.md); system design in
> [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 1. Identity

| Field | Value |
|-------|-------|
| **Project** | RouteWise Agentic |
| **Full name** | Autonomous Multi-Modal Travel & Transit Coordinator for Tourism in Sri Lanka |
| **Competition** | AI Buildathon 2026 |
| **Track** | Hospitality & Tourism |
| **Team size** | 3 members (3 workstreams) |
| **Reasoning engine** | Qwen (Alibaba Cloud Model Studio) |
| **Implementation sequencing** | Workstream A built first (phases A1–A7 done); B & C documented, built to the same interfaces |

---

## 2. Problem

Tourists in Sri Lanka face a fragmented, hard-to-navigate travel experience:

- **Multi-modal complexity.** One journey can combine walking, tuk-tuk, bus, and train (e.g.,
  Colombo → Ella). No single app plans all legs coherently.
- **Opaque costs & timing.** Fares are hard to predict; delays and congestion are common and
  rarely communicated in advance.
- **Real traveler constraints are ignored.** Passive map apps optimize for distance/time only —
  they ignore **budget ceilings**, **heavy luggage**, **low walking tolerance**, **arrival
  deadlines**, and **comfort**.
- **No adaptation.** When a bus is late or a connection is missed, the traveler is on their own;
  nothing re-plans proactively.
- **Connectivity gaps.** Tourists lose signal in transit; paper tickets and online-only tools are
  fragile offline.

**Result:** travelers waste time, overspend, over-walk with heavy bags, and miss the experiences
they came for.

---

## 3. Solution

RouteWise Agentic is an **agentic** travel coordinator that moves **beyond passive navigation**.
Instead of only drawing a line from A to B, it:

- **Understands** a natural-language travel request.
- **Extracts** constraints and preferences (budget, luggage, walking, timing).
- **Plans** a multi-modal journey and **evaluates** candidate routes.
- Uses **transit intelligence** to **predict fares and delays**.
- **Acts** autonomously through tools (availability, booking preparation).
- **Adapts** to disruptions by **re-planning**.
- **Delivers** a justified recommendation and an **offline-ready Travel Pass**.

---

## 4. Target users

- **Tourists / independent travelers** in Sri Lanka planning multi-modal trips under a budget.
- **Luggage-burdened travelers** who want to minimize walking and transfers.
- **Time-constrained travelers** with arrival deadlines (flights, check-ins, tours).
- **Hospitality & tourism operators** (hotels, tour desks) advising guests on reliable routes.
- (Secondary) **Budget-conscious backpackers** optimizing cost vs comfort vs time.

---

## 5. Core Agentic concept

The system is built around a five-stage agentic loop. Every major feature maps onto a stage.

```
UNDERSTAND  →  REASON  →  ACT  →  ADAPT  →  DELIVER
```

| Stage | What happens | Primary workstream |
|-------|--------------|--------------------|
| **UNDERSTAND** | Parse natural-language request → structured intent + constraints. | A |
| **REASON** | Generate/evaluate candidate routes; score vs hard constraints & soft preferences. | A |
| **ACT** | Call tools (fares, delays, availability, booking prep). | A (mock) → B/C (real) |
| **ADAPT** | Detect disruption; re-plan/reroute autonomously. | A (logic) + C (signals) |
| **DELIVER** | Recommendation, explanation, and offline Travel Pass. | A (data) → C (delivery) |

Full agent behavior: [`AGENT_SPEC.md`](AGENT_SPEC.md).

---

## 6. Main capabilities

1. **Natural-language travel understanding** with constraint extraction.
2. **Multi-modal route planning** (walk, tuk-tuk, bus, train, taxi, ferry).
3. **Budget-aware optimization** (hard budget ceiling enforcement).
4. **Luggage- & walking-aware** comfort optimization.
5. **Transit intelligence**: fare prediction (XGBoost) + delay prediction (LSTM).
6. **Route comparison** with honest trade-offs and alternatives.
7. **Autonomous actions** (simulated → real): availability checks, booking preparation.
8. **Disruption handling & autonomous re-planning**.
9. **Explainable decisions** referencing the user's own constraints.
10. **Offline-ready Travel Pass** delivery.
11. **Transparent agent activity** — the reasoning is visible in the UI.

---

## 7. Technology stack

Use this direction unless a documented project decision later changes it.

| Layer | Technology |
|-------|------------|
| **AI** | Alibaba Cloud Model Studio · **Qwen 3.8 Max** |
| **Agent / Automation** | Alibaba Cloud **Coder Work** · **Coder IDE** · **Coder Wake** |
| **Backend** | **Python** · **FastAPI** |
| **Frontend** | **React.js** |
| **Database** | **PostgreSQL** · **PostGIS** |
| **Machine Learning** | **XGBoost** (fare prediction) · **LSTM** (delay prediction) |
| **Cloud** | **Alibaba Cloud** |
| **Data** | GTFS / static transit · mock GTFS-RT · simulated delay/congestion · future real integrations |

System design & data flow: [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 8. Overall architecture (summary)

```
Frontend (React) → FastAPI Backend (Python) → AI Agent / Qwen (A)
      → Tools (stable interfaces)
          → Transit Intelligence / ML (B): PostGIS, GTFS, XGBoost, LSTM
          → Autonomous Execution / Cloud (C): Coder Work/Wake, booking, Travel Pass, deploy
          → Data / External Services (mock now → real later)
```

**Boundary rule:** workstreams connect **only** through documented interfaces
([`API_CONTRACTS.md`](API_CONTRACTS.md)). A "decides", B "informs", C "acts". In the MVP the
B/C-facing tools are **mocked** by A, then replaced later behind the **same signatures**. Full
detail: [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 9. The three workstreams (summary)

Each of the 3 members **owns a workstream end-to-end** and contributes to integration, testing,
and UI. Full detail (purpose, responsibilities, I/O, dependencies, deliverables, DoD, and
pairwise exchanges) is in [`WORKSTREAMS.md`](WORKSTREAMS.md).

- **Workstream A — AI Agent & Decision Engine.** Qwen integration, NLU, constraint extraction,
  agent state & orchestration, tool calling, route evaluation & scoring, decisions, explanations,
  mock tools, agent-activity UI, stable API contracts, handover to B.
- **Workstream B — Transit Intelligence & ML.** PostgreSQL/PostGIS, GTFS + mock GTFS-RT, transit
  graph, geographic calculations, XGBoost fares, LSTM delays, transit APIs, related UI.
- **Workstream C — Autonomous Execution & Cloud.** Coder Work automation, booking/availability,
  external tool adapters, Coder Wake monitoring, disruption handling & rerouting, Travel Pass
  delivery, Alibaba Cloud deployment, related UI.

---

## 10. MVP & mock-data strategy

The hackathon MVP must be **demonstrably reliable**:

- **Mock data everywhere** for transit, fares, delays, availability — **realistic** (Sri Lankan
  routes, plausible LKR fares, believable delays) but clearly **not real-time**.
- Every mock sits **behind the same interface** the real service will use, so B/C swap in without
  changing A or the frontend.
- **One shared source of mock truth (A7).** All mock route intelligence lives in a single module
  (`backend/app/tools/intelligence.py`) that every data tool reads — routes are **not** duplicated
  inside each tool, and there are **no random values**, so the same input always gives the same
  result and the tools can never contradict each other about a route. That module is the
  **Workstream-B replacement point**: B supplies real data behind the same accessors and the same
  tool signatures, and nothing above the tool layer changes.
- The Agent **reasons over** the mock data and tools — the golden scenario's answer is **never
  hard-coded**.
- The Agent must **never pretend mock data is real-time** (see
  [`AGENT_SPEC.md` §15–16](AGENT_SPEC.md)); mock/simulated results are labeled `data_source`.

Demo plan & mock scenarios: [`DEMO.md`](DEMO.md).

---

## 11. Golden demo scenario

> **"I am at Colombo Fort and need to reach Ella under a budget of LKR 2,000, but I have a heavy
> bag and don't want to walk."**

The Agent must: understand the request; extract constraints (origin, destination, budget,
luggage, walking); find/evaluate multi-modal routes; respect the **LKR 2,000 budget** (hard) and
**heavy luggage** / **minimal walking** (soft); consider delays; compare alternatives; take
(simulated) autonomous actions; **explain** the decision; and produce the final travel info /
**Travel Pass**. **Do not hard-code the result** — the Agent reasons over data and tools.

Full walkthrough + scripted scenarios: [`DEMO.md`](DEMO.md).

---

## 12. Constraints model (summary)

- **Hard constraints** (must be satisfied): origin, destination, budget ceiling, required arrival
  time.
- **Soft preferences** (optimize, may trade off): less walking, less waiting, faster, fewer
  transfers, more comfort.

Full definitions + scoring model: [`AGENT_SPEC.md` §8–10](AGENT_SPEC.md).

---

## 13. Current project status

- **Phase A1 — Project Foundation: COMPLETE.** The shared documentation system (this doc set),
  the centralized design system + CSS tokens, the repository skeleton, **and a working foundation
  scaffold** are established:
  - **Backend (FastAPI):** configuration, logging, CORS for local dev, `GET /health`, a
    contract-shaped `POST /api/route/plan` **foundation stub** (honest `IDLE`, no fabricated
    route), and the structured error envelope; plus backend tests.
  - **AI service abstraction:** an isolated Qwen / Alibaba Cloud Model Studio client behind a
    clean interface, configurable via env, with a **mock fallback** when no API key is present.
  - **Frontend (React + Vite + TypeScript):** app shell, design tokens/global styles, and a
    centralized `services/api` client (the only backend caller).
  - Frontend ↔ backend communication is **verified end to end** (health + the plan stub).
- **Phase A2 — Travel Request Understanding: COMPLETE.** `POST /api/route/plan` now **understands**
  a natural-language request:
  - **Extraction:** NL → Qwen structured extraction → Pydantic validation → a normalized
    **`TravelRequest`** (origin, destination, budget+currency, luggage, walking, times,
    preferences), reusing the existing AI abstraction (no second Qwen client).
  - **Mock fallback:** with no API key a **deterministic offline extractor** runs and is honestly
    labelled `extraction_source: "mock"`; with a key, real Qwen is used and malformed output is
    rejected safely (`502`), never silently accepted.
  - **Clarification:** missing hard constraints (origin/destination) set `clarification_required`
    with a question — never fabricated.
  - **Scope:** understanding **only** — status `UNDERSTANDING`, no route/search/score (those are A3+).
  - **Frontend:** a minimal travel-request input + parsed-`TravelRequest` display + clarification
    state, using design tokens only. Backend tests cover the 15 required scenarios.
- **Phase A3 — Agent Orchestration & Decision Engine: COMPLETE.** `POST /api/route/plan` now runs a
  real (mock-backed) agent decision:
  - **State machine + execution context:** the 9 canonical `AgentState`s drive an observable
    `agent_actions[]` trace (UNDERSTANDING → PLANNING → SEARCHING → EVALUATING → COMPLETED).
  - **Tool/capability abstraction:** a `Tool` ABC + registry (the A→B/C seam) with a deterministic
    **mock** candidate provider and honest `not_implemented` stubs for fare/delay/booking.
  - **Decision engine:** transparent **deterministic** scoring — hard constraints filter, soft
    preferences score (luggage/walking-aware) — producing a recommendation, alternatives, concise
    **reasons**, and a `reasoning` summary. Qwen is **not** used for route selection.
  - **Frontend:** an agent-progress timeline, the recommended route (marked **MOCK**), concise
    reasons, alternatives with trade-offs, and an honest no-route state — design tokens only.
  - **Scope:** mock data only; no execution/replanning, ML, database, GTFS, or Travel Pass (A4+).
- **Phase A4 — Tool System & Capability Execution: COMPLETE.** The A3 tool seam is now a clean,
  safe capability-execution system (`backend/app/tools/`):
  - **Tool contract + structured result:** every tool declares its metadata + a Pydantic
    `args_model` and returns a `ToolResult` (`success` / `tool_name` / `data_source` / `data` /
    `error{code,message}`) — never an arbitrary dict.
  - **Availability model:** `AVAILABLE` / `NOT_IMPLEMENTED` / `DISABLED` / `ERROR` separates "the
    tool exists" from "it can return data"; provenance stays on `data_source`.
  - **Registry + executor:** `ToolRegistry` (register/get/list/status/execute, rejects duplicates)
    delegates to a `ToolExecutor` that gates availability, validates input, bounds execution with a
    timeout, and turns any exception/malformed return into a structured failure — the agent never
    crashes and a stub can never fabricate success.
  - **Tools:** `search_routes` is `AVAILABLE` on the deterministic **mock** provider; the
    fare/delay/route-details/availability/booking tools remain honest `NOT_IMPLEMENTED` stubs (B/C).
  - **Agent + API:** the orchestrator routes `search_routes` through the seam (resolve → validate →
    execute → structured result → decide); invocation stays orchestrator-controlled (the Qwen loop is
    A5). `ToolCall` gained two **additive** fields (`availability`, `data_source`), shown as small
    status/source tags in the existing timeline — no new UI, response contract otherwise unchanged.
  - **Scope:** no real B/C providers; all data still **mock** (the Qwen tool-calling loop is A5, below).
- **Phase A5 — Tool-Calling Orchestrator: COMPLETE.** `POST /api/route/plan` now runs an autonomous,
  **bounded multi-step Qwen tool-calling loop** on the A4 tool seam:
  - **Qwen tool-calling adapter** (`services/ai/agent.py`): exposes only `AVAILABLE` tools as function
    definitions, parses/validates the model's `tool_calls`, and works with **real Qwen** (when
    `MODEL_STUDIO_API_KEY` is set) or a **deterministic mock** planner (no key) — reusing the existing
    AI abstraction (no second Qwen client).
  - **Multi-step loop** (`agent/orchestrator.py`): the model **selects** each tool (the sequence is not
    hard-coded); the app validates + executes it through the A4 `ToolRegistry` → `ToolExecutor` and
    feeds the structured `ToolResult` (success **or** failure) back, repeating until a final answer.
  - **Safety bounds:** `MAX_AGENT_ITERATIONS` (configurable, default **8**) stops a runaway loop and
    preserves the observed actions; duplicate/loop detection suppresses repeated identical calls; tool
    calls are represented as agent actions under the **existing 9 states** (no new `TOOL_CALLING`
    state), with a `can_advance` guard for non-canonical transitions.
  - **Grounded decision:** the final recommendation is computed by the A3 `DecisionEngine` over the
    tool-gathered **mock** candidates — Qwen never invents candidate facts, and on the iteration limit
    the agent returns no recommendation rather than fabricating one.
  - **API + frontend:** the endpoint contract is preserved; the only change is the **additive**
    `ToolCall.error_code`, surfaced as a small tag in the existing timeline. The whole loop runs
    **in-request** (no streaming/SSE/WebSocket).
  - **Scope:** no real B/C providers, no replanning/execution; all route data still **mock**. Real
    Qwen tool-calling is **MOCK ONLY / NOT VERIFIED** here (no API key in this environment; the two
    live tests skip honestly).
- **Phase A6 — Route Decision Engine (decision refinement & constraint-aware route optimization):
  COMPLETE.** The A3 `DecisionEngine` is refined into a focused, deterministic pipeline — the A5
  tool-calling loop and the A4 tool seam are **unchanged**:
  - **Hard constraints, structured:** `validate_constraints` returns **every** violation as a
    `ConstraintViolation` (`type` + grounded `message`) in a fixed precedence (origin → destination →
    budget → arrival deadline → availability); the first still drives the A3 single-string `constraint`,
    so a violating candidate is **never** selected **and never silently dropped** — it appears as a
    clearly-marked `valid: false` alternative.
  - **Defensive candidates:** malformed objects and duplicate ids are skipped, and impossible values
    (negative / `NaN` / infinite fare, duration, walking, transfers, delay) are treated as **unknown**
    and recorded in `assumptions` — never accepted, never invented.
  - **Robust normalization + weights:** min–max across survivors with defined degenerate cases (single
    candidate or all-identical → 1.0; missing → 0.0); base weights adjusted by `walking_preference` and
    `luggage`, then renormalized. Weights are **never** LLM-generated.
  - **Delay consumed, not predicted:** `delay_risk` **and** a known `delay_min_estimate` are penalized
    (0.001/min, capped at 60) — the only scoring change vs A3. No ML, no LSTM.
  - **Deterministic ranking + grounded explanation:** rank by score, tie-broken by lower fare → fewer
    transfers → stable id; every card carries `rank`, `valid`, `strengths`, `trade_offs` and
    `constraint_violations` drawn only from real values. 0 valid ⇒ no recommendation; 1 valid ⇒ no
    fabricated alternatives.
  - **API + frontend:** `POST /api/route/plan` preserved; the schema change is **additive**
    (`ConstraintViolation` + four `Recommendation` fields), mirrored in `frontend/src/types/api.ts` and
    rendered inside the existing route cards using the current design system only.
  - **Scope:** no real B/C data, no replanning/execution, no Travel Pass; all route data still **mock**.
- **Phase A7 — Mock Intelligence Integration & End-to-End Agent Validation: COMPLETE.** The agent now
  runs a **full, realistic multi-step workflow** against a complete deterministic mock environment —
  the A4 seam, the A5 loop, the A6 engine and the nine canonical states are all **unchanged**:
  - **One shared source of mock route truth** (`backend/app/tools/intelligence.py` —
    `MockRouteIntelligence`): 7 routes across 3 corridors (Colombo Fort↔Ella, Kandy↔Ella,
    Colombo Fort↔Kandy), each with route-level figures **and** leg detail that provably sums to them
    (`Σ leg duration/fare/walking == route totals`; `vehicle legs − 1 == transfers`). No randomness;
    no per-tool duplication of R1/R2/R3. `candidates.py` is now a thin facade over it.
  - **Three new tools through the A4 seam** — `get_fare_estimate`, `get_delay_prediction`,
    `get_route_details` — ordinary `Tool` subclasses registered in the existing `ToolRegistry` and run
    by the existing `ToolExecutor`. **No** second executor, registry, result class or tool base class.
    With `search_routes` that makes **four `AVAILABLE` mock data tools** (`data_source=mock`,
    `status=mock_data`); `check_availability` / `prepare_booking` stay honest `NOT_IMPLEMENTED` stubs.
  - **Honest unknowns:** `ToolErrorCode.ROUTE_NOT_FOUND` (additive) — an id outside the dataset (e.g.
    `R999`) returns `success: false` + `data_source: mock`, never fabricated numbers.
  - **Tool definitions stay derived:** the Qwen function schema is built from
    `registry.list_available()`, so the three new tools joined it automatically — the tool list is not
    hard-coded a second time.
  - **Model-driven multi-step planning:** `MockAgentPlanner` was upgraded to a realistic scenario
    (search the corridor → fare/delay/details for each observed route → finalize), labelled
    `model: mock-qwen` + `data_source: mock`. `PlannerContext` gained **additive** evidence fields
    (`called_tools`, `route_ids`). The scenario lives **only** in the mock planner — the production
    agent hard-codes neither the sequence nor the winner, and adapts when a tool or corridor is absent.
  - **Conservative merging:** observed results are associated **per route id** with the structured
    candidates; the **candidate stays authoritative** (a missing field may be filled, a contradiction
    is reported and the candidate value kept, unassociated intelligence is reported and ignored).
    `PlanResponse.legs` is now populated for the recommended route. **A7 informs; A6 decides** — no
    decision logic moved into the mock providers, and the golden outcome is unchanged (R1 0.472 >
    R2 0.408, R3 excluded on budget).
  - **Golden trace:** UNDERSTANDING → PLANNING → SEARCHING (`search_routes` → R1/R2/R3, then fare ×3,
    then delay ×3, then details ×3) → EVALUATING → COMPLETED — **14 actions (10 tool calls) over the
    existing five states**, no new `TOOL_CALLING` state.
  - **Frontend (minimal):** a per-leg list on the recommended route card and a ✓/✗ glyph on each
    timeline tool line (derived from the call's real `status`) — existing design system only, **no new
    CSS, no new components**.
  - **Scope:** strictly Workstream A. No XGBoost/LSTM, no PostgreSQL/PostGIS, no GTFS/GTFS-RT, no live
    transit APIs, no browser/railway automation, no booking, no Coder Work/Wake, no Travel Pass, no
    monitoring, no cloud deploy. All route data is still **mock**.
- **No route-planning features beyond A7's end-to-end mock agent run (by design).** No
  execution/booking, disruption replanning, ML, database, GTFS, automation, or Travel Pass are
  built yet — those belong to A8+ / Workstream B / Workstream C. All A7 route data is **mock**.
- **Honesty:** real Qwen connectivity is **not** claimed unless a key is configured; with no key the
  backend uses the mock extractor/client **and the mock tool-calling planner** (see
  [`AGENT_SPEC.md` §15](AGENT_SPEC.md)).
- **Next (when instructed):** Workstream A phase **A8 — Agent Experience / UI** (agent-activity UI and
  route presentation); B and C proceed against
  the agreed interfaces.

---

## 14. Development phases (Workstream A sequencing)

| Phase | Name | Focus |
|-------|------|-------|
| **A1** | **Project Foundation** ✅ | Docs, design system, tokens, architecture, contracts **+ a working foundation scaffold (FastAPI app + React shell + AI-service abstraction + tests)**. |
| **A2** | **Travel Request Understanding** ✅ | NLU: request → validated `TravelRequest` + constraints (extraction only; no route planning). |
| **A3** | **Agent Architecture** ✅ | Agent state model + execution context, orchestration, deterministic decision/scoring over mock candidates. |
| **A4** | **Agent Tool System** ✅ | Tool contract + structured result, availability model, registry + safe executor; `search_routes` (mock) available, other capabilities honest `NOT_IMPLEMENTED` stubs. |
| **A5** | **Tool-Calling Orchestrator** ✅ | Bounded multi-step Qwen tool-calling loop (decide → call → observe): adapter (real + deterministic mock), iteration limit + duplicate/loop detection, decision grounded in the A3 engine. |
| **A6** | **Route Decision Engine** ✅ | Constraint-aware candidate evaluation: structured hard-constraint violations, defensive/malformed-candidate handling, robust normalization, preference-weighted + delay-aware scoring, deterministic ranking, grounded reasons/strengths/trade-offs. |
| **A7** | **Mock Intelligence Integration** ✅ | Complete deterministic mock environment behind the B boundary: one shared mock route-truth module, `get_fare_estimate` / `get_delay_prediction` / `get_route_details` as `AVAILABLE` mock tools, `ROUTE_NOT_FOUND`, a multi-step `MockAgentPlanner` (`mock-qwen`), conservative per-route result merging + populated `legs`, and an end-to-end agent validation (golden trace). |
| A8 | Agent Experience / UI | Agent-activity UI, route presentation. |
| A9 | Final API & Agent State | Stable `POST /api/route/plan`, agent status API. |
| A10 | Workstream B Handover | Contracts + mocks ready for B to replace. |

**Do not automatically continue past the current phase.** Wait for instruction.

---

## 15. Future scope

- **Real transit integrations:** live GTFS/GTFS-RT feeds replacing simulated data (B).
- **Live ML:** production XGBoost/LSTM retraining on real fare/delay data (B).
- **Real autonomous execution:** live booking/availability via Coder Work; Coder Wake
  monitoring-driven autonomous rerouting; real Travel Pass issuance (C).
- **Cloud deployment:** full Alibaba Cloud deployment + infra-as-code (C).
- **More regions/modes**, multi-traveler planning, payments, accessibility/localization
  (Sinhala/Tamil/English), and offline-first mobile packaging.

> Future scope is **documented, not implemented**. Do not build it without explicit instruction.

---

## 16. Documentation map (source of truth)

| # | Document | Purpose |
|---|----------|---------|
| 1 | [`PROJECT.md`](PROJECT.md) | This overview: problem, solution, users, capabilities, stack, status. |
| 2 | [`ARCHITECTURE.md`](ARCHITECTURE.md) | Full-stack architecture, boundaries, data/API/tool flow. |
| 3 | [`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md) | Centralized UI tokens + usage guidelines + component registry. |
| 4 | [`API_CONTRACTS.md`](API_CONTRACTS.md) | Endpoint & tool interface contracts (current vs future). |
| 5 | [`AGENT_SPEC.md`](AGENT_SPEC.md) | Agent purpose, I/O, states, tools, scoring, safety, must-nots. |
| 6 | [`WORKSTREAMS.md`](WORKSTREAMS.md) | Team coordination: A/B/C responsibilities & exchanges. |
| 7 | [`DEVELOPMENT_RULES.md`](DEVELOPMENT_RULES.md) | Engineering rules, git collaboration, secrets. |
| 8 | [`DEMO.md`](DEMO.md) | Hackathon demo script + mock scenarios. |

Entry point for AI agents: [`../AI_CONTEXT.md`](../AI_CONTEXT.md).

---

## 17. Change policy

This file reflects the **approved project direction**. If you believe something here is wrong or
needs to change, **do not silently edit it** — raise it with the team lead. Update it only when
there is a documented project decision to do so.
