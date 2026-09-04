# ARCHITECTURE.md — RouteWise Agentic

> Source of truth #2. The **complete system architecture** across all three workstreams.
> Read after [`PROJECT.md`](PROJECT.md). This document supersedes the earlier
> frontend-only architecture note and covers the **whole system**: frontend → backend →
> agent → tools → transit intelligence/ML → automation → data/external services.
>
> **Status:** **A1 (foundation), A2 (request understanding), and A3 (agent orchestration &
> decision) are implemented.** A FastAPI backend (config, logging, CORS, `GET /health`,
> structured errors) now runs a real agent layer: `POST /api/route/plan` extracts a validated
> `TravelRequest` (A2 — Qwen or a deterministic mock), then `app/agent/` drives the canonical state
> machine and `app/agent/decision.py` scores **mock** candidates from `app/tools/` (a deterministic
> mock candidate provider + honest `not_implemented` tool stubs) into a recommendation,
> alternatives, concise reasons, and an `agent_actions[]` trace. The React + Vite + TypeScript
> frontend (app shell + a centralized `services/api` client) shows the parsed request, the
> agent-progress timeline, and the mock decision, with the design tokens (`frontend/src/styles/`)
> as the visual source of truth. Everything else here (real tools, ML, automation, execution, the
> full component UI) remains the **agreed plan** for A4+. All route data is **mock**. Keep it
> **suitable for a hackathon MVP** — simple, demonstrable, mock-backed.

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

### A ↔ C  (Agent ⇄ Autonomous Execution/Cloud)

- **A calls C** through the execution tools: `check_availability`, `prepare_booking`
  (and later re-routing/monitoring hooks).
- **C provides A** availability status, prepared (unconfirmed) bookings, disruption signals
  (from Coder Wake), and Travel Pass delivery.
- **Boundary rule:** **irreversible actions belong to C and require explicit user
  confirmation.** A may *prepare/plan* an action but must not *commit* money/bookings.
  `prepare_booking` only prepares.
- **MVP:** execution tools are **simulated** and labeled as such.

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
    │   ├── travel-request/      # capture & submit the trip request
    │   ├── agent-activity/      # agent steps/status/reasoning visualization
    │   └── route-results/       # recommended route, alternatives, timeline, pass
    │       └── (each: components/ hooks/ services/ state/ types.ts index.ts)
    ├── components/              # SHARED, registered components (see DESIGN_SYSTEM.md §13)
    │   ├── ui/                  # Button, Input, Select, Card, Badge, Modal, Tooltip, StatusIndicator
    │   ├── agent/               # AgentActivity, AgentStep, AgentStatus, ReasoningSummary
    │   └── travel/              # TripForm, RouteCard, RouteTimeline, TransportLeg, FareDisplay, DelayBadge, TravelPass
    ├── hooks/                   # cross-feature hooks (useMediaQuery, useAgentStream, useApi…)
    ├── services/
    │   ├── api/                 # THE only place that calls the backend (client, routePlan, agentState)
    │   ├── mock/                # frontend fallback fixtures (demo resilience; labeled simulated)
    │   └── formatters/          # LKR currency, durations, times, distances
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
> `services/api/` (the single backend client). Still **created when you build them** (A8): the
> **feature slices** (`features/*`), **component groups** (`components/{ui,agent,travel}`), the
> remaining **service groups** (`services/{mock,formatters}`), `state/`, `utils/`, and `assets/`
> — do not pre-create empty leaf folders (see
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
`types/` mirroring the contracts and catches drift early. **Deferred to A8** (kept
dependency-light per [`DEVELOPMENT_RULES.md`](DEVELOPMENT_RULES.md) rule 9): **ESLint + Prettier**
and **Vitest + React Testing Library** — added with the first real components. Final choices are
recorded here and in `frontend/README.md`.

---

## 4. Backend architecture (Python / FastAPI)

**Workstream A owns the backend** (agent + API). Structure below — **A1 implemented the
foundation files**, **A2 added request understanding** (`schemas/travel_request.py`,
`services/ai/extraction.py`), and **A3 added the agent + tools** (`agent/`, `tools/`,
`schemas/candidate.py`) (✅):

```
backend/
├── app/
│   ├── main.py            # ✅ FastAPI entrypoint, CORS, router registration, error handlers
│   ├── config.py          # ✅ settings/env (API keys via env only — never committed)
│   ├── logging_config.py  # ✅ logging foundation
│   ├── api/               # ✅ health.py · route.py (A3: extraction → agent → decision) · router.py  (agent status/stream: A5/A8/A9)
│   ├── schemas/           # ✅ Pydantic models mirroring API_CONTRACTS.md (A2 travel_request.py · A3 candidate.py)
│   ├── services/ai/       # ✅ AI abstraction (base · qwen_client · mock_client · factory) + A2 extraction.py
│   ├── agent/             # ✅ A3: state.py (state machine + execution context) · decision.py (scoring) · orchestrator.py
│   └── tools/             # ✅ A3: base.py (Tool ABC) · candidates.py (mock provider) · capabilities.py · registry.py (A→B/C seam)
├── tests/                 # ✅ foundation + A2 extraction + A3 state/decision/agent/API tests
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
- **CORS** enabled for the dev frontend origin.
- **Secrets via environment only** (see [`DEVELOPMENT_RULES.md`](DEVELOPMENT_RULES.md)).

---

## 5. Agent architecture (Workstream A)

The agent is the **decision engine**. Full behavior in [`AGENT_SPEC.md`](AGENT_SPEC.md); the
loop is:

```
UNDERSTAND → REASON → ACT → ADAPT → DELIVER
```

Conceptual internal pipeline (built in phases A2–A7; **[Understanding] ✅ A2**, and
**[Planning]/[Tool calling]/[Evaluation]/[Decision] ✅ A3 — deterministic, over mock data**):

```
Travel request (text + structured fields)
   → [Understanding]  ✅ A2: parse → TravelRequest + constraints (hard/soft) + missing-info detection
   → [Planning]       ✅ A3: choose the candidate provider + scoring pass (deterministic, not an LLM)
   → [Tool calling]   ✅ A3: search_routes (mock provider); fare/delay stubs → A4+
   → [Evaluation]     ✅ A3: filter hard constraints → score soft prefs → rank (agent/decision.py)
   → [Decision]       ✅ A3: recommendation + alternatives + concise reasons
   → [Adaptation]     on disruption → REPLANNING loop back to searching (A4+)
   → [Delivery]       recommendation + explanation + agent_actions (+ Travel Pass data)
```

- **Reasoning engine:** **Qwen** via Alibaba Cloud Model Studio. **A2** wires Qwen for request
  **extraction** (understanding) behind the existing AI abstraction. **A3's route decision is
  deterministic** (`agent/decision.py` transparent scoring) — Qwen is **not** called for route
  selection; an LLM tool-calling loop is A5+.
- **State:** the agent reports one of the **9 canonical states** (see
  [`AGENT_SPEC.md`](AGENT_SPEC.md)); these drive the UI and the `status` field.
- **Determinism:** same inputs + same mock data ⇒ same recommendation (critical for a reliable
  demo).
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

> **A3 scope:** steps **1–7 and 9–10** are implemented over **mock** candidates (extraction →
> planning → deterministic scoring → decision → `agent_actions[]` → frontend). Step **8
> (EXECUTING)** and step **11 (REPLANNING)** are **not** exercised — `prepare_booking` /
> `check_availability` and disruption handling are honest `not_implemented` stubs (A4+); the agent
> goes **EVALUATING → COMPLETED**.

Agent steps/states are surfaced to the UI as `agent_actions[]` (embedded) and/or streamed —
the frontend abstracts the mechanism (see §3.3).

---

## 7. API flow

- Frontend calls **`POST /api/route/plan`** (the reserved primary endpoint; an honest
  **foundation stub** in A1, a real **mock agent decision** in **A3**, live-data planning in **A9**).
- Response carries `status` (canonical agent state), `request` (normalized), `recommendation`,
  `legs[]`, `alternatives[]`, `agent_actions[]`, and `reasoning`. In A3 `legs[]` is empty and all
  route figures are **mock**; `recommendation`/`alternatives`/`agent_actions` are populated.
- Optional (later) **`GET /api/agent/status`** and **`GET /api/agent/stream`** for live agent
  activity — mechanism **TBD** in A5/A8/A9.
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

---

## 9. ML integration (Workstream B — future)

- **XGBoost** → fare prediction, exposed via `get_fare_estimate`.
- **LSTM** → delay prediction, exposed via `get_delay_prediction`.
- **PostgreSQL/PostGIS** → transit graph + geographic calculations, exposed via
  `search_routes` / `get_route_details`.
- **GTFS / mock GTFS-RT** → static schedules + simulated real-time feeds.
- **Integration point:** B implements the **same tool interfaces** A already calls. Model
  artifacts live in `models/` (gitignored binaries); training/feature code in B's area.
- **MVP:** none of this is implemented — A uses mocks. See
  [`WORKSTREAMS.md`](WORKSTREAMS.md) and A7/A10.

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
