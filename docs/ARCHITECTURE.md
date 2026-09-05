# ARCHITECTURE.md — RouteWise Agentic

> Source of truth #2. The **complete system architecture** across all three workstreams.
> Read after [`PROJECT.md`](PROJECT.md). This document supersedes the earlier
> frontend-only architecture note and covers the **whole system**: frontend → backend →
> agent → tools → transit intelligence/ML → automation → data/external services.
>
> **Status:** **A1 (foundation), A2 (request understanding), A3 (agent orchestration & decision),
> A4 (tool system & capability execution), A5 (multi-step Qwen tool-calling orchestrator), A6
> (constraint-aware decision-engine refinement), A7 (mock intelligence integration &
> end-to-end agent validation), A8 (agent-experience UI) and A9 (agent & API stabilization,
> observability & integration readiness) are implemented.** A FastAPI backend (config, logging,
> CORS, `GET /health`, structured errors) now runs
> a real agent layer: `POST /api/route/plan` extracts a validated `TravelRequest` (A2 — Qwen or a
> deterministic mock), then `app/agent/` drives the canonical state machine and `app/agent/decision.py`
> scores **mock** candidates from `app/tools/` into a recommendation, alternatives, concise reasons,
> and an `agent_actions[]` trace. **A4** turned `app/tools/` into a clean capability-execution system —
> a structured `ToolResult`, Pydantic input validation, an explicit availability model, and a safe
> `ToolExecutor` (timeout + exception/malformed guards) behind the registry — with `search_routes`
> `AVAILABLE` on a deterministic mock provider and the fare/delay/availability/booking tools honest
> `NOT_IMPLEMENTED` stubs. **A5** connects the model to that seam: `app/services/ai/agent.py` is a
> Qwen **tool-calling adapter** (real + deterministic mock) and `app/agent/orchestrator.py` runs a
> **bounded multi-step loop** — Qwen selects each available tool, the app validates + executes it via
> the registry/executor and feeds the structured result back, repeating until a final answer or
> `MAX_AGENT_ITERATIONS` (default 8), with duplicate-call protection and a decision **grounded** in the
> A3 engine. **A6 refines that decision engine itself** (`app/agent/decision.py` + additive
> `schemas/route.py` fields): a deterministic prepare → hard-constraint filter (structured
> `constraint_violations[]`) → min–max normalize → preference-weighted score (delay risk **and** known
> delay minutes) → deterministic rank → grounded explanation pipeline, with impossible candidate values
> treated as unknown and recorded in `assumptions`. It consumes A5's `context.candidates` unchanged —
> **no** orchestrator or tool-seam change. **A7 fills that seam with a complete deterministic mock
> world** (`app/tools/intelligence.py` — one shared `MockRouteIntelligence`): `get_fare_estimate`,
> `get_delay_prediction` and `get_route_details` join `search_routes` as `AVAILABLE` **mock** tools,
> an unknown route id becomes a structured `ROUTE_NOT_FOUND` failure instead of invented data, the
> `MockAgentPlanner` now exercises a real multi-step scenario (`model: mock-qwen`), and observed tool
> results are merged **conservatively** into the agent context (candidate authoritative, conflicts
> reported) — which populates `PlanResponse.legs`. The agent, the decision engine and the mock dataset
> stay strictly layered (**agent → tools → mock providers → decision engine**), so
> `intelligence.py` is the single Workstream-B replacement point. The React + Vite + TypeScript frontend (app shell + a
> centralized `services/api` client)
> shows the parsed request, the agent-progress timeline (per-tool status/source, and — A5 — any
> `error_code`), and the mock decision — and, since **A6**, each route card's `rank` / `valid` /
> `strengths` / structured violations, using the existing design tokens
> (`frontend/src/styles/`) as the visual
> source of truth. **A8** turned that skeleton into the polished two-column agent-experience UI
> (`features/route-planner/` + the registered `components/{ui,agent,travel}`), and **A9 stabilized
> the whole pipeline for integration**: a per-request `request_id` (`X-Request-Id` header +
> `PlanResponse.request_id`), structured `event=…` observability logs on the existing logging
> foundation, a machine-readable `kind` on every `AgentAction`, honest planner provenance
> (`data_source`/`model` from the planner, not hard-coded), a typed retryable `503` when the live
> model is unreachable, and capped tool-error detail — all additive, no new states, tools,
> endpoints or dependencies. Everything else here (real tools, ML, automation, execution)
> remains the **agreed plan** for A10+/B/C. All route data is **mock**. Keep it **suitable for a hackathon
> MVP** — simple, demonstrable, mock-backed.

---

## 1. System overview (layered flow)

```
Frontend (React)
      ↓  REST / JSON  (see API_CONTRACTS.md)
FastAPI Backend (Python)
      ↓
AI Agent / Qwen  (Workstream A — Decision Engine)
      ↓  tool calls (stable interfaces)
Tools  ──────────────┬───────────────────────────┐
      ↓              ↓                            ↓
Transit Intelligence / ML     Automation / Execution     Data / External Services
(Workstream B)                (Workstream C)             (mock now → real later)
  PostgreSQL/PostGIS            Coder Work browser          GTFS / GTFS-RT
  GTFS / mock GTFS-RT           automation, booking         simulated delay/congestion
  XGBoost fares                 Coder Wake monitoring       Alibaba Cloud services
  LSTM delays                   rerouting, Travel Pass
                                delivery, cloud deploy
```

The **agent** (A) is the brain: it understands a request, plans, calls **tools**, evaluates
results, decides, explains, and adapts. Tools are the **stable seam** through which A consumes
B (transit intelligence/ML) and C (execution/automation). In the MVP every tool is backed by a
**mock**; B and C later replace the mocks behind the **same interfaces**, so agent code and the
frontend do not change.

> **A7 layering rule (enforced, not aspirational).** The flow above is strictly
> **AGENT → TOOLS → MOCK PROVIDERS → DECISION ENGINE**. The agent and the decision engine
> **never** import a mock dataset; they only ever see intelligence as a structured `ToolResult`
> returned through the registry/executor. All four mock data tools share **one**
> `MockRouteIntelligence` instance (`backend/app/tools/intelligence.py`), which is why they cannot
> disagree about a route — and why Workstream B can replace that single module with real
> GTFS/PostGIS/XGBoost/LSTM data without touching a line above the tool layer.

---

## 2. Workstream boundaries (A ↔ B ↔ C)

Each workstream owns a layer and communicates **only through documented interfaces**
([`API_CONTRACTS.md`](API_CONTRACTS.md)). Full responsibilities in
[`WORKSTREAMS.md`](WORKSTREAMS.md).

### A ↔ B  (Agent ⇄ Transit Intelligence/ML)

- **A calls B** through the transit tools: `search_routes`, `get_fare_estimate`,
  `get_delay_prediction`, `get_route_details`.
- **B provides A** structured route candidates, fare estimates (XGBoost), delay predictions
  (LSTM), and geographic/transit-graph results — each tagged with `data_source`
  (`mock`/`simulated`/`live`).
- **Boundary rule:** A never queries the database or runs models directly; it only calls the
  tool interfaces. B never makes decisions; it only returns data/predictions.
- **MVP:** these tools are **mocked** (owned by A until B implements them — see
  [`WORKSTREAMS.md`](WORKSTREAMS.md) and A10 handover).
- **A7:** all four are now `AVAILABLE` on **deterministic mock** data (`data_source: mock`,
  `status: mock_data`) served by the shared `MockRouteIntelligence` — 7 routes over 3 corridors
  (Colombo Fort↔Ella, Kandy↔Ella, Colombo Fort↔Kandy), route-level figures **and** leg detail that
  provably sums to them. An id outside that dataset returns `ROUTE_NOT_FOUND`, never invented data.
  **A7 informs; A6 still decides** — no scoring or constraint logic lives in the mock providers.

### A ↔ C  (Agent ⇄ Autonomous Execution/Cloud)

- **A calls C** through the execution tools: `check_availability`, `prepare_booking`
  (and later re-routing/monitoring hooks).
- **C provides A** availability status, prepared (unconfirmed) bookings, disruption signals
  (from Coder Wake), and Travel Pass delivery.
- **Boundary rule:** **irreversible actions belong to C and require explicit user
  confirmation.** A may *prepare/plan* an action but must not *commit* money/bookings.
  `prepare_booking` only prepares.
- **MVP:** execution tools are **simulated** and labeled as such. **A7 leaves them as honest
  `NOT_IMPLEMENTED` stubs** — no browser automation, booking, monitoring, Travel Pass, or cloud
  deploy was built; the executor's availability gate means they can never fabricate a success.

### B ↔ C  (Transit Intelligence/ML ⇄ Execution/Cloud)

- **C consumes B**: real-time disruption/availability signals and delay predictions feed
  autonomous rerouting and Coder Wake monitoring.
- **B consumes C (indirectly)**: outcomes of executed actions (e.g., confirmed bookings,
  observed delays) can enrich future data — **out of MVP scope**, noted as future.
- **Boundary rule:** B and C do **not** call each other's internals; they exchange through the
  shared tool/data contracts and the backend. Keep them decoupled.

> **Coordination rule:** do not modify another workstream's layer without coordination
> (see [`DEVELOPMENT_RULES.md`](DEVELOPMENT_RULES.md)). Interface changes are agreed in
> [`API_CONTRACTS.md`](API_CONTRACTS.md) first.

---

## 3. Frontend architecture (React)

**Feature-oriented.** Grouped by feature/domain, not by file type. `App` only wires providers,
routing, and the shell — **no business logic** in components.

### 3.1 Directory structure (target layout; layer skeleton established in A1)

```
frontend/
├── index.html
├── package.json                 # added at scaffold time (not in A1)
├── vite.config.*                # build config decided at scaffold time
├── README.md
└── src/
    ├── main.*                   # bootstrap: mounts <App/>, imports globals.css + tokens.css
    ├── App.*                    # shell: providers + routing + layout ONLY
    ├── pages/                   # thin screens: Landing, PlanTrip, NotFound
    ├── features/                # feature slices (heart of the app)
    │   └── route-planner/       # 🟩 A8: the whole plan flow — request → agent rail → results
    │       └── (RoutePlanner.tsx · RoutePlanner.css · index.ts)
    ├── components/              # 🟩 SHARED, registered components (see DESIGN_SYSTEM.md §13)
    │   ├── ui/                  # Button, Badge, Card, StatusIndicator, Alert (Input/Select/Modal/Tooltip still planned)
    │   ├── agent/               # AgentActivity, AgentStep, AgentStatus, ReasoningSummary
    │   └── travel/              # TripForm, RouteCard, RouteTimeline, TransportLeg, FareDisplay, DelayBadge, ModeIcon, TravelRequestSummary (TravelPass = Workstream C)
    ├── hooks/                   # cross-feature hooks (useMediaQuery, useAgentStream, useApi…)
    ├── services/
    │   ├── api/                 # 🟩 THE only place that calls the backend (client, health, routePlan)
    │   ├── format.ts            # 🟩 A8: formatters (LKR, durations, distances) + describeError
    │   ├── agentState.ts        # 🟩 A8: agent-state labels, canonical order, visited-state helper
    │   └── mock/                # ⏳ frontend fallback fixtures (demo resilience; deferred — not built in A8)
    ├── state/                   # shared client state (store + slices: agent, trip, route)
    ├── types/                   # shared domain types mirroring API_CONTRACTS.md
    ├── config/                  # env/config (API base URL, feature flags)
    ├── styles/
    │   ├── tokens.css           # ✅ DESIGN TOKENS — exists now
    │   └── globals.css          # ✅ reset + base styles — exists now
    ├── assets/                  # icons, transport-mode icon set, images
    └── utils/                   # tiny pure helpers (cn/classnames, guards)
```

> **A1 established the layer skeleton** — these folders exist, each with a `README.md` stating
> its purpose + owner (no empty folders): `src/pages`, `src/features`, `src/components`,
> `src/hooks`, `src/services`, `src/state`, `src/types`, and `src/styles` (real tokens).
> **A1 also built the foundation app files** — `main.tsx`, `App.tsx`/`App.css`, `package.json`,
> `index.html`, `vite.config.ts`, `tsconfig.json`, `config/env.ts`, `types/api.ts`, and
> `services/api/` (the single backend client).
> **A8 built the product UI on that skeleton:** the shared **component groups**
> (`components/{ui,agent,travel}`), the presentation **services** (`services/format.ts` +
> `services/agentState.ts`), and the first **feature slice** (`features/route-planner/`). `App.tsx`
> is now **shell-only** (header + connection `StatusIndicator` + `<RoutePlanner>`); all plan state
> lives in the slice, and components call the backend only through `services/api`.
>
> **Deviation from the three-slice sketch (documented, per rule 5).** The A1 outline named three
> slices (`travel-request`, `agent-activity`, `route-results`). All three derive from **one**
> `POST /api/route/plan` response and share **one** state machine, so splitting them would fragment
> that state across folders and create near-empty leaf dirs (which
> [`DEVELOPMENT_RULES.md`](DEVELOPMENT_RULES.md) forbids pre-creating). A8 therefore ships **one
> cohesive slice**, `features/route-planner/`, composing the shared components; it can be split
> later if the flow grows genuinely independent sub-behaviors.
>
> Still **created when you build them**: `services/mock/` (demo-resilience fallback), `state/`,
> `utils/`, `assets/`, and `pages/` — do not pre-create empty leaf folders (see
> [`DEVELOPMENT_RULES.md`](DEVELOPMENT_RULES.md)).

### 3.2 Layer responsibilities & dependency direction

One-way dependency: `pages → features → components/hooks/services/state → types/utils/styles`.
Lower layers never import from higher ones.

| Layer | Responsibility | Must NOT |
|-------|----------------|----------|
| **pages/** | Map URL → screen; compose features; page-level states. | Hold business logic or API calls. |
| **features/** | Own a behavior slice; expose a clean `index.ts`. | Reach into another feature's internals. |
| **components/** | Reusable presentational UI (registered). Consume tokens + props. | Fetch data, hold domain logic, hard-code styles. |
| **hooks/** | Encapsulate behavior/state (`useAgentStream`, `useTravelRequest`). | Render UI. |
| **services/api/** | The **only** caller of the backend; normalize errors. | Be bypassed by direct `fetch` in components. |
| **services/mock/** | Frontend fallback fixtures for demo resilience. | Be presented as real data. |
| **state/** | Shared client state (agent state, latest plan, selected route). | Duplicate server data; store secrets. |
| **types/** | Domain types mirroring the API contracts. | Diverge from [`API_CONTRACTS.md`](API_CONTRACTS.md). |

### 3.3 Frontend ↔ backend communication

- **Transport:** JSON over REST, matching [`API_CONTRACTS.md`](API_CONTRACTS.md) exactly.
- **Base URL** from `config/`/env (e.g., `VITE_API_BASE_URL`), default `http://localhost:8000`.
- **Single client** (`services/api/client`) sets headers/timeouts and normalizes errors.
- **Primary endpoint (MVP):** `POST /api/route/plan`.
- **Agent activity** arrives either **embedded** (`agent_actions[]` in the response) and/or
  **streamed** (SSE/WebSocket). The frontend hides this behind `useAgentStream()`/`agentSlice`
  so components don't care. (Mechanism decided in a later phase.)
- **States:** every call handles loading/error/empty/success (see
  [`DESIGN_SYSTEM.md` §12](DESIGN_SYSTEM.md)).
- **Mock resilience:** if the backend is unreachable mid-demo, `services/mock` supplies a
  clearly-labeled simulated response so the flow still runs end-to-end.

### 3.4 State strategy

- **Server state** (plan, agent steps, routes): fetched from the API; the backend/contracts are
  the source of truth — do not re-derive business rules client-side.
- **Client/UI state** (selected route, form draft, active panel): local or a `state/` slice.
- Keep the store **small and boring**; a lightweight approach (React state/context or a minimal
  store) is fine for the MVP. No heavyweight state library without a documented decision.

### 3.5 Tooling (decided in A1)

**Chosen and installed in A1:** **Vite 5 + React 18 + TypeScript 5** (strict). TypeScript keeps
`types/` mirroring the contracts and catches drift early. **Still deferred after A8** (kept
dependency-light per [`DEVELOPMENT_RULES.md`](DEVELOPMENT_RULES.md) rule 9 and the A8 "no new
dependencies" constraint): **ESLint + Prettier** and **Vitest + React Testing Library**. A8 shipped
the first real components **without** adding a runner — UI correctness is verified by `tsc --noEmit`
(strict) + the production build + the backend suite + manual DOM checks. Add the runner/linters when
the team accepts the dependency. Final choices are recorded here and in `frontend/README.md`.

---

## 4. Backend architecture (Python / FastAPI)

**Workstream A owns the backend** (agent + API). Structure below — **A1 implemented the
foundation files**, **A2 added request understanding** (`schemas/travel_request.py`,
`services/ai/extraction.py`), **A3 added the agent + tools** (`agent/`, `tools/`,
`schemas/candidate.py`), **A4 refined the tool seam into a capability-execution system**
(`tools/base.py`, `tools/executor.py`, `tools/registry.py`), **A5 added the Qwen tool-calling
adapter + multi-step loop** (`services/ai/agent.py`; `agent/orchestrator.py` now runs the bounded
loop; `config.py` gained `MAX_AGENT_ITERATIONS`; `schemas/route.py` gained `ToolCall.error_code`), and
**A6 refined the decision engine** (`agent/decision.py`; `schemas/route.py` gained `ConstraintViolation`
and the additive `Recommendation.rank` / `.valid` / `.strengths` / `.constraint_violations`), and
**A7 added the mock intelligence layer** (`tools/intelligence.py` — the shared source of mock route
truth; `tools/capabilities.py` gained the three intelligence tools; `tools/candidates.py` is now a thin
facade over it; `tools/base.py` gained `ToolErrorCode.ROUTE_NOT_FOUND`; `agent/orchestrator.py` merges
tool results and populates `PlanResponse.legs`) (✅):

```
backend/
├── app/
│   ├── main.py            # ✅ FastAPI entrypoint, CORS, router registration, error handlers
│   ├── config.py          # ✅ settings/env (API keys via env only — never committed)
│   ├── logging_config.py  # ✅ logging foundation + A9 request-id / structured-event helpers
│   ├── api/               # ✅ health.py · route.py (A3 extraction → A5 agent loop → decision; A9 request-id + 503 mapping) · router.py  (agent status/stream: reserved, decided against in A9)
│   ├── schemas/           # ✅ Pydantic models mirroring API_CONTRACTS.md (A2 travel_request.py · A3 candidate.py · A5 route.py: ToolCall.error_code · A6 route.py: ConstraintViolation + Recommendation.rank/valid/strengths/constraint_violations)
│   ├── services/ai/       # ✅ AI abstraction (base · qwen_client · mock_client · factory) + A2 extraction.py + A5 agent.py (Qwen tool-calling planner)
│   ├── agent/             # ✅ A3: state.py (state machine + execution context; A9 run metadata) · decision.py (scoring, refined in A6) · orchestrator.py (A5 bounded multi-step loop; A7 merges tool results + legs; A9 observability events + timing)
│   └── tools/             # ✅ A3/A4: base.py (Tool ABC + ToolResult) · executor.py (A4 safe execution) · registry.py (A→B/C seam) · capabilities.py (the concrete tools)
│       ├── intelligence.py # ✅ A7: MockRouteIntelligence — the ONE shared source of mock route truth (the Workstream-B replacement point)
│       └── candidates.py   # ✅ A3 mock provider, A7 thin facade over intelligence.py (kept for backwards compatibility)
├── tests/                 # ✅ foundation + A2 extraction + A3 state/decision/agent/API + A4 tool contract/registry/execution/stub/integration + A5 qwen-tool-calling/agent-loop + A6 decision-engine + A7 mock-intelligence (provider consistency / fare / delay / details / registry / agent loop / decision integration) + A9 stabilization (isolation / determinism / action contract / observability / error mapping) tests
├── requirements.txt       # ✅ dependencies (requirements.txt chosen over pyproject.toml)
├── .env.example           # ✅ config template (never commit .env)
└── README.md
```

Principles:

- **Routers are thin** — validate input, call the agent/services, shape the response per the
  contract. No business logic in routers.
- **Schemas mirror** [`API_CONTRACTS.md`](API_CONTRACTS.md) (`snake_case`, LKR money, ISO 8601
  `+05:30`, canonical agent states).
- **Tools are the seam** to B and C: stable signatures, mock-backed now, real later.
- **Mock data lives in exactly one place (A7).** `tools/intelligence.py` is the only module that
  knows the routes; tools read it, and nothing above the tool layer imports it.
- **CORS** enabled for the dev frontend origin.
- **Secrets via environment only** (see [`DEVELOPMENT_RULES.md`](DEVELOPMENT_RULES.md)).

---

## 5. Agent architecture (Workstream A)

The agent is the **decision engine**. Full behavior in [`AGENT_SPEC.md`](AGENT_SPEC.md); the
loop is:

```
UNDERSTAND → REASON → ACT → ADAPT → DELIVER
```

Conceptual internal pipeline (built in phases A2–A7 — **all seven stages now implemented**;
**[Understanding] ✅ A2**,
**[Planning]/[Tool calling]/[Evaluation]/[Decision] ✅ A3 — deterministic, over mock data**,
**[Tool calling] hardened in ✅ A4 — registry → executor → structured `ToolResult`**,
**[Planning]+[Tool calling] made model-driven in ✅ A5 — a bounded multi-step Qwen loop**,
**[Evaluation]+[Decision] refined in ✅ A6 — structured violations, robust normalization, delay-aware
scoring, deterministic ranking**, and
**[Tool calling]+[Evaluation] given a real multi-step mock world in ✅ A7 — four `AVAILABLE` mock
tools over one shared dataset, results merged per route**):

```
Travel request (text + structured fields)
   → [Understanding]  ✅ A2: parse → TravelRequest + constraints (hard/soft) + missing-info detection
   → [Planning]       ✅ A5: Qwen is given the TravelRequest + AVAILABLE tool defs and *selects* the
                        next tool (model-driven sequence, not hard-coded); bounded multi-step loop
   → [Tool calling]   ✅ A4/A5/A7: each selected call → registry → executor (validate + timeout + guards)
                        → structured ToolResult fed back to Qwen; search_routes + fare/delay/details
                        (all mock, all AVAILABLE, one shared dataset — A7);
                        availability/booking = NOT_IMPLEMENTED (never fabricated);
                        unknown route id = ROUTE_NOT_FOUND (never invented)
   → [Evaluation]     ✅ A3, refined ✅ A6, fed ✅ A7: observed tool results are merged per route id
                        (candidate stays authoritative, conflicts reported) → prepare/sanitize
                        defensively → filter hard constraints (all violations kept, structured)
                        → min–max normalize → weight by soft prefs
                        → subtract the delay penalty → deterministic rank (agent/decision.py)
   → [Decision]       ✅ A3, refined ✅ A6: recommendation + ranked alternatives, each with grounded
                        reasons / strengths / trade_offs / constraint_violations (never fabricated)
   → [Adaptation]     on disruption → REPLANNING loop back to searching (A10+/Workstream C)
   → [Delivery]       recommendation + explanation + agent_actions (+ Travel Pass data)
```

- **Reasoning engine:** **Qwen** via Alibaba Cloud Model Studio. **A2** wires Qwen for request
  **extraction** (understanding) behind the existing AI abstraction. **A5** wires Qwen for **tool
  calling** (`services/ai/agent.py`) — the model chooses which available tool to call next in a
  bounded loop; with no `MODEL_STUDIO_API_KEY` a deterministic **mock** planner drives the same loop.
  **The route decision itself stays deterministic** (`agent/decision.py` transparent scoring over the
  tool-gathered candidates) — Qwen selects tools but does **not** invent candidate facts or the final
  pick ([`AGENT_SPEC.md` §15–16](AGENT_SPEC.md)).
- **State:** the agent reports one of the **9 canonical states** (see
  [`AGENT_SPEC.md`](AGENT_SPEC.md)); these drive the UI and the `status` field.
- **Determinism:** same inputs + same mock data ⇒ same recommendation (critical for a reliable
  demo). **A7 makes this testable end-to-end:** the shared mock dataset has no randomness, so the
  golden Colombo Fort → Ella run always yields R1 (0.472) > R2 (0.408), R3 excluded — a computed
  outcome, never a hard-coded one.
- **Honesty:** every tool result carries `data_source`; mock is never presented as real-time.

---

## 6. Data flow (end-to-end)

```
1. User submits request (TripForm) ─────────────────────────────► POST /api/route/plan
2. Backend validates → hands to Agent
3. Agent UNDERSTANDING → extracts constraints → (echoed back to UI as chips)
4. Agent PLANNING → chooses tools
5. Agent SEARCHING → calls tools ──► (mock) transit/ML [B] & execution [C]
6. Tools return structured candidates/fares/delays (data_source-tagged)
7. Agent EVALUATING → filters hard constraints, scores soft prefs, ranks
8. Agent EXECUTING → prepare_booking / check_availability (simulated; no commit)
9. Agent COMPLETED → recommendation + alternatives + rationale + agent_actions[]
10. Response ─────────────────────────────────────────────────► Frontend renders
    (RouteCards, RouteTimeline, ReasoningSummary, Travel Pass view)
11. On disruption → Agent REPLANNING → repeat 5–9 → updated recommendation
```

> **A3–A7 scope:** steps **1–7 and 9–10** are implemented over **mock** candidates (extraction →
> planning → deterministic scoring → decision → `agent_actions[]` → frontend). **A5** makes step **5**
> a **model-driven, multi-step loop**: Qwen selects each tool call, which may revisit SEARCHING (and
> reach EXECUTING when it picks an action tool). **A6** refines steps **6–7** (evaluation → decision)
> without touching the loop: every candidate is validated against the hard constraints, normalized,
> weighted, scored, ranked and explained from its **real** values. **A7** makes steps **5–6** genuinely
> multi-step: one request now calls `search_routes` **and** fare/delay/details per returned route, all
> served from one shared mock dataset, and the observed results are merged into step **7** — which also
> fills the `legs[]` the UI renders in step **10**. Step **8 (EXECUTING)** and step
> **11 (REPLANNING)**
> are still **not** truly exercised — `prepare_booking` / `check_availability` and disruption handling
> remain honest `not_implemented` stubs (Workstream C, A10+); on the happy path the agent goes
> **EVALUATING → COMPLETED**. **A9** wraps the whole flow in correlation + observability: every run
> carries a `request_id` and emits structured `event=…` log lines with per-tool and total durations.

Agent steps/states are surfaced to the UI as `agent_actions[]` embedded in the single-shot
`POST /api/route/plan` response. **A9 decided the delivery mechanism:** single-shot only — **no**
streaming/SSE/WebSocket and no agent status endpoint (the reserved routes stay unbuilt).

---

## 7. API flow

- Frontend calls **`POST /api/route/plan`** (the reserved primary endpoint; an honest
  **foundation stub** in A1, a real **mock agent decision** in **A3**, a **model-driven multi-step
  tool loop** in **A5**, a **constraint-aware ranked decision** in **A6**, a **fully-populated mock
  intelligence run** in **A7**, live-data planning in **Workstream B**).
- Response carries `status` (canonical agent state), `request` (normalized), `recommendation`,
  `legs[]`, `alternatives[]`, `agent_actions[]`, and `reasoning`. All
  route figures are **mock**; `recommendation`/`alternatives`/`agent_actions` are populated from A3.
  **A6** adds
  four **additive** recommendation fields (`rank`, `valid`, `strengths`, `constraint_violations`) — no
  new endpoint, no breaking change. **A7** populates `legs[]` for the recommended route (it was empty
  before) and lengthens `agent_actions[]` to a multi-tool trace — again **additive**: same endpoint,
  same field names, same response keys. **A9** adds two more **additive, optional** fields —
  `AgentAction.kind` and `PlanResponse.request_id` (mirroring the `X-Request-Id` header) — and
  freezes the whole shape as the B/C integration baseline.
- Optional (later) **`GET /api/agent/status`** and **`GET /api/agent/stream`** for live agent
  activity — mechanism **decided in A9**: **single-shot only** (a single response
  with the full `agent_actions[]` trace, no streaming); both routes stay reserved and unbuilt.
- Errors use a structured envelope. Full shapes in
  [`API_CONTRACTS.md`](API_CONTRACTS.md).

---

## 8. Tool flow

- The agent calls tools by **name** with structured args; tools return structured results.
- Tools are **idempotent reads** except `prepare_booking` (prepares only; never commits).
- Each result includes `data_source` and (for predictions) a confidence/uncertainty signal.
- **MVP:** all tools mocked behind the signatures in
  [`API_CONTRACTS.md` §6](API_CONTRACTS.md). B/C replace mocks later with **no signature
  change**.
- **A7 mock tool flow.** Tool definitions exposed to the model are **derived from
  `registry.list_available()`** — there is no second, hand-maintained tool list, so a newly
  `AVAILABLE` tool joins the Qwen function schema automatically. Every call goes
  `registry → executor` (availability gate → Pydantic validation → bounded run → malformed guard), so
  a disabled/stubbed tool or a bad argument is a structured failure, never a crash and never a
  fabricated success. The four data tools read the **one** shared `MockRouteIntelligence`, which is
  what makes `get_fare_estimate("R1")` agree with the fare inside R1's `search_routes` candidate.

---

## 9. ML integration (Workstream B — future)

- **XGBoost** → fare prediction, exposed via `get_fare_estimate`.
- **LSTM** → delay prediction, exposed via `get_delay_prediction`.
- **PostgreSQL/PostGIS** → transit graph + geographic calculations, exposed via
  `search_routes` / `get_route_details`.
- **GTFS / mock GTFS-RT** → static schedules + simulated real-time feeds.
- **Integration point:** B implements the **same tool interfaces** A already calls. Model
  artifacts live in `models/` (gitignored binaries); training/feature code in B's area.
  **Since A7 the concrete replacement point is `backend/app/tools/intelligence.py`:** B supplies real
  data behind `MockRouteIntelligence`'s accessors (`candidates_for` / `fare_estimate` /
  `delay_prediction` / `route_details`) and the same four tool signatures, and nothing above the tool
  layer — agent, decision engine, schemas, API, frontend — has to change. Swap the data source,
  flip `data_source` to `live`, keep the contract.
- **MVP:** none of this is implemented — A uses mocks (**A7**: deterministic, internally consistent
  mocks, still labeled `mock`). See [`WORKSTREAMS.md`](WORKSTREAMS.md) and A10.

---

## 10. Automation integration (Workstream C — future)

- **Coder Work** browser automation → booking/availability workflows and external tool adapters
  behind `check_availability` / `prepare_booking`.
- **Coder Wake** monitoring → detects disruptions and triggers the agent's **REPLANNING** path.
- **Travel Pass** execution/delivery → offline-ready pass generation (A defines the data/visual
  contract; C implements delivery).
- **Integration point:** C implements the execution tools and the disruption signal that feeds
  the agent. **Irreversible actions require explicit user confirmation.**
- **MVP:** simulated only. See [`WORKSTREAMS.md`](WORKSTREAMS.md).

---

## 11. Cloud direction (Alibaba Cloud — future, Workstream C)

- **AI:** Alibaba Cloud **Model Studio** (Qwen) — reasoning engine.
- **Agent/automation ecosystem:** **Coder Work / Coder IDE / Coder Wake**.
- **Deployment:** backend (FastAPI) + frontend (React) + data/ML services on **Alibaba Cloud**.
  Infra-as-code lives in `automation/`.
- **MVP:** local/dev deployment; cloud deployment is a later C task. Keep the app
  **12-factor-friendly** (config via env, stateless backend) so cloud deploy is additive.

---

## 12. User experience flow (screens)

The screen journey (states in [`AGENT_SPEC.md`](AGENT_SPEC.md); demo script in
[`DEMO.md`](DEMO.md)):

```
LANDING → TRAVEL REQUEST → AI UNDERSTANDING → AGENT PLANNING → TRANSIT INTELLIGENCE
        → ROUTE EVALUATION → AUTONOMOUS EXECUTION → FINAL ROUTE → TRAVEL PASS
```

- **Desktop (≥ `lg` 1024px):** two-column — main content + persistent **Agent activity rail**.
- **Tablet (≥ `md`):** single column; agent activity collapsible.
- **Mobile (< `md`):** single column; agent activity in a bottom sheet / expandable card.
- The **agent activity rail** is a first-class part of the UX (it makes the agent's thinking
  legible), driven by the canonical agent states and their colors
  ([`DESIGN_SYSTEM.md` §11.5](DESIGN_SYSTEM.md)).

---

## 13. Repository layout

Established in **A1** as a **shared monorepo** — one repo, three workstreams, explicit ownership.
Every folder has a `README.md` naming its **owning workstream** and **layer**.

```
RouteWise - Agentic/
├── AI_CONTEXT.md          # agent entry point — read first
├── README.md              # human-facing overview
├── .gitignore
├── docs/                  # SOURCE OF TRUTH (8 docs) — shared
├── frontend/              # Workstream A (UI) + shared design system
│   └── src/               # pages · features · components · hooks · services · state · types
│       └── styles/        # tokens.css + globals.css — DESIGN TOKENS (real code)
├── backend/               # Workstream A (FastAPI + agent)
│   ├── app/               # api · agent · tools · schemas · services
│   └── tests/             # backend tests
├── data/                  # shared → B: mock/ · static/  (raw/ · gtfs/ are gitignored)
├── models/                # Workstream B: fare/ (XGBoost) · delay/ (LSTM) — not implemented
└── automation/            # Workstream C: booking/ · monitoring/ · travel_pass/ · deploy/
```

> Ownership boundaries are explicit **on disk** (folder READMEs) and in
> [`WORKSTREAMS.md`](WORKSTREAMS.md). Folder-creation rules:
> [`DEVELOPMENT_RULES.md`](DEVELOPMENT_RULES.md).

---

## 14. Architecture principles (MVP)

1. **Tools are the seam.** A ↔ B ↔ C interact only through documented tool/API interfaces, so
   mocks can be swapped for real services without rewriting callers.
2. **Contracts first.** Shapes are agreed in [`API_CONTRACTS.md`](API_CONTRACTS.md) before code.
3. **Business logic out of UI.** Frontend renders; backend/agent decide.
4. **Mock-backed but honest.** Everything simulated is labeled; never presented as real-time.
5. **Simple over clever.** Prefer the smallest architecture that demos reliably.
6. **Cloud-ready, cloud-deferred.** Env-based config and stateless backend keep deployment
   additive.

> Changing this architecture requires an explicit, communicated decision — not a silent
> refactor (see [`DEVELOPMENT_RULES.md`](DEVELOPMENT_RULES.md)).
