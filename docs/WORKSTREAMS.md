# WORKSTREAMS.md — RouteWise Agentic

> Source of truth #6. The **shared team coordination document**. It defines all **three**
> workstreams equally — their purpose, responsibilities, inputs/outputs, dependencies,
> integration points, deliverables, and Definition of Done — plus exactly what each workstream
> provides to the others.
>
> This is **not** A-only. All three members use this as the shared source of truth. Read with
> [`ARCHITECTURE.md`](ARCHITECTURE.md) (boundaries) and [`API_CONTRACTS.md`](API_CONTRACTS.md)
> (the interfaces that connect the workstreams).

---

## 0. Team model & ground rules

- **3 members, 3 workstreams.** Each member **owns a feature/system workstream end-to-end**
  (design → implementation → integration → testing → UI). This is **not** a simplistic
  "frontend dev / backend dev / ML dev" split.
- **Everyone contributes to integration, testing, and UI where appropriate** — workstream
  ownership is about accountability, not silos. Each workstream ships **its own related UI**.
- **Interfaces first.** Workstreams connect **only** through the documented contracts in
  [`API_CONTRACTS.md`](API_CONTRACTS.md). Agree the interface, then build independently.
- **Mock until real.** A workstream may proceed against **mocks** of another's output; the mock
  is replaced later behind the **same interface** (no caller rewrites).
- **Coordinate before crossing boundaries.** Do not modify another workstream's layer without
  coordination (see [`DEVELOPMENT_RULES.md`](DEVELOPMENT_RULES.md)).
- **Current implementation sequencing:** Workstream **A is built first** (its phases A1–A10);
  B and C are **fully documented here** and implemented after/alongside via the agreed
  interfaces. Documentation covers all three; implementation is sequenced. **A1 (foundation) is
  implemented** — the FastAPI + React scaffold, contracts, `GET /health`, the
  `POST /api/route/plan` foundation stub, and the AI-service abstraction — but **no application
  *features*** (no agent logic, planning, tools, ML, database, or automation) are built until
  A2+ / Workstreams B & C.

### Workstream map

| Workstream | Name | Layer | Primary owner |
|------------|------|-------|---------------|
| **A** | AI Agent & Decision Engine | Backend agent + API + agent UI | Member 1 |
| **B** | Transit Intelligence & ML | Data + transit graph + ML + transit APIs/UI | Member 2 |
| **C** | Autonomous Execution & Cloud | Automation + booking + monitoring + delivery + cloud + UI | Member 3 |

---

## 1. WORKSTREAM A — AI Agent & Decision Engine

### Purpose
The **brain** of RouteWise: understand a natural-language travel request, reason over
constraints and tool results, decide on the best multi-modal route, explain it, and adapt when
conditions change. Owns the Qwen-powered agent, the tool-calling orchestration, the route
decision engine, the stable public API, and the agent-activity experience.

### Responsibilities
- Qwen integration (Alibaba Cloud Model Studio).
- Natural-language travel understanding; travel-request parsing; constraint extraction.
- Agent state model + orchestration (the 9 canonical states — see
  [`AGENT_SPEC.md`](AGENT_SPEC.md)).
- Tool calling (decide → call → observe → reason).
- Route candidate evaluation, **route scoring**, decision-making, AI explanations.
- **Mock tool integration** (mocks for B/C outputs until they are real).
- Agent activity/status **UI**.
- **Stable API contracts** (`POST /api/route/plan`, agent status/stream).
- **Handover to Workstream B** (contracts + mocks ready to be replaced).

### Inputs
- Travel request from the frontend (text + structured fields).
- Tool results from B (routes/fares/delays/details) and C (availability/booking-prep) — **mock**
  in the MVP.
- Disruption signals from C (future) that trigger re-planning.

### Outputs
- Plan response: `status`, normalized `request`, `recommendation`, `legs[]`, `alternatives[]`,
  `agent_actions[]` (see [`API_CONTRACTS.md`](API_CONTRACTS.md)).
- Tool **calls** to B and C (structured args).
- Agent states/steps for the UI.

### Dependencies
- **On B:** route candidates, fare estimates, delay predictions, route details (via tools).
- **On C:** availability, booking preparation, disruption signals, Travel Pass delivery (via
  tools).
- **On Qwen/Model Studio:** reasoning (Alibaba Cloud).
- All are **mocked** by A until B/C deliver, so A is never blocked. **Since A7** the four B-facing
  data tools (`search_routes`, `get_fare_estimate`, `get_delay_prediction`, `get_route_details`) are
  `AVAILABLE` on **one shared deterministic mock dataset**; the two C-facing tools are still honest
  `NOT_IMPLEMENTED` stubs.

### Integration points
- Frontend ⇄ A: `POST /api/route/plan` (+ optional agent status/stream).
- A ⇄ B: transit tool interfaces.
- A ⇄ C: execution tool interfaces + disruption/replan hook.

### Deliverables
- Working agent (understand → plan → call tools → score → decide → explain → re-plan).
- Public API + schemas mirroring the contracts.
- Mock tool layer (replaceable by B/C). **A7 made the replacement point concrete:**
  `backend/app/tools/intelligence.py` — B swaps that module's data source, keeps the accessors and the
  four tool signatures, and nothing above the tool layer changes.
- Agent-activity UI (states, steps, reasoning summary).

### Definition of Done (A)
- The **golden demo** ([`DEMO.md`](DEMO.md)) runs end-to-end on mocks: request understood,
  constraints extracted, routes evaluated, budget/luggage/walking respected, decision explained,
  alternatives shown, a disruption triggers re-planning.
  **A7 status:** everything except the disruption/re-planning leg is demonstrated end-to-end over a
  multi-tool mock run (search → fare → delay → details → decision → legs). Re-planning needs C's
  disruption signal (A8+).
- All 9 states render correctly in the UI; `status` matches the contract.
- Deterministic on fixed mock data; honest `data_source` labeling; no hallucinated values.
  **A7:** the shared mock dataset has no randomness and is internally consistent (leg figures sum to
  route totals), so the golden run reproduces exactly.
- API contracts stable + documented; mocks behind exact B/C signatures; tests pass.

### Phases (A)
`A1 Foundation → A2 Travel Request Understanding → A3 Agent Architecture → A4 Agent Tool System
→ A5 Tool-Calling Orchestrator → A6 Route Decision Engine → A7 Mock Intelligence Integration →
A8 Agent Experience/UI → A9 Final API & Agent State → A10 Workstream B Handover.`
**Current: A9 (Agent & API Stabilization, Observability & Integration Readiness) — A1–A9 are
implemented.** Do not auto-advance into A10.

---

## 2. WORKSTREAM B — Transit Intelligence & ML

### Purpose
Provide the **transit truth**: routes, schedules, geography, fares, and delay risk. Turn
GTFS/static + simulated real-time data into a transit graph and ML predictions the agent can
consume through tools.

### Responsibilities
- **PostgreSQL / PostGIS** storage and geographic calculations.
- **GTFS** ingestion (static) and **mock GTFS-RT** (real-time simulation).
- Transit **graph/data** model.
- **XGBoost** fare prediction.
- **LSTM** delay prediction.
- **Transit intelligence APIs** implementing A's tool interfaces (`search_routes`,
  `get_fare_estimate`, `get_delay_prediction`, `get_route_details`).
- Related **UI** (e.g., transit/map/data views, delay & fare visualizations).

### Inputs
- Tool calls from A (origin/destination/time/preferences; route/leg ids).
- GTFS/static feeds + simulated delay/congestion data (real-time feeds later).
- (Future) observed outcomes from C to enrich data.

### Outputs
- Candidate routes (multi-modal, with legs, times, distances).
- Fare estimates (+ confidence), delay predictions (+ risk level), route details.
- All tagged `data_source` (`mock`/`simulated`/`live`).

### Dependencies
- **On A:** the tool **interface contracts** to implement (provided by A; A mocks them first).
- **On data:** GTFS/static + simulated feeds.
- **On C (future):** real-time disruption/availability signals to refine predictions.

### Integration points
- B ⇄ A: implements A's transit tool interfaces (drop-in replacement for A's mocks — **since A7 the
  single file to replace is `backend/app/tools/intelligence.py`**, behind unchanged tool signatures).
- B ⇄ C: provides delay/route intelligence that feeds C's rerouting/monitoring.
- B ⇄ DB: PostgreSQL/PostGIS.

### Deliverables
- Transit graph + geo calculations on PostGIS.
- GTFS ingestion + mock GTFS-RT.
- Trained XGBoost (fares) and LSTM (delays) models + serving path.
- Transit intelligence APIs behind A's tool contracts; related UI.

### Definition of Done (B)
- A's transit tools return **real** (or realistic simulated) data behind the **unchanged**
  signatures — A's code doesn't change when B replaces the mocks.
- Fare/delay predictions meet agreed accuracy targets on test data; results carry
  `data_source` + confidence.
- Golden-demo route (Colombo Fort → Ella) resolves from B's data with plausible LKR fares and
  delay risk; geographic calcs correct; tests pass.

> **Status:** not implemented during A1. Interface owned by A; B builds to it (A10 handover).

---

## 3. WORKSTREAM C — Autonomous Execution & Cloud

### Purpose
Make RouteWise **act** and **stay resilient**: execute booking/availability workflows, monitor
for disruptions, autonomously re-route, deliver the offline-ready Travel Pass, and run the whole
system on Alibaba Cloud.

### Responsibilities
- **Coder Work** browser automation; booking/availability workflows; external tool adapters.
- **Coder Wake** monitoring (disruption detection).
- **Autonomous disruption handling** and **rerouting** (feeds A's `REPLANNING`).
- **Travel Pass** execution/delivery (offline-ready).
- **Alibaba Cloud** deployment/infrastructure.
- Related **UI** (execution status, confirmations, Travel Pass view, monitoring).

### Inputs
- Tool calls from A (`check_availability`, `prepare_booking`).
- Delay/route intelligence from B (to decide reroutes).
- Disruption signals (Coder Wake) → trigger A's re-planning.
- User **confirmation** for any irreversible action.

### Outputs
- Availability status; prepared (unconfirmed) bookings/holds + refs.
- Disruption signals to A; executed re-routes; delivered Travel Pass.
- Deployment/infra + monitoring status.

### Dependencies
- **On A:** execution tool contracts + the agent's replanning hook.
- **On B:** delay/route intelligence for rerouting decisions.
- **On Alibaba Cloud:** Coder Work/Wake, Model Studio, deployment target.
- **On user:** explicit confirmation before committing irreversible actions.

### Integration points
- C ⇄ A: implements A's execution tool interfaces; sends disruption → `REPLANNING`.
- C ⇄ B: consumes delay/route intelligence for autonomous rerouting.
- C ⇄ Cloud: deployment/monitoring.

### Deliverables
- Booking/availability automation (Coder Work) behind `check_availability`/`prepare_booking`.
- Coder Wake monitoring + autonomous rerouting wired to A's replanning.
- Travel Pass generation/delivery (offline-ready).
- Alibaba Cloud deployment (backend + frontend + services) + infra-as-code in `automation/`.

### Definition of Done (C)
- A's execution tools return real (or realistic simulated) results behind **unchanged**
  signatures; `prepare_booking` **never commits** without explicit confirmation.
- A injected disruption triggers monitoring → agent `REPLANNING` → updated recommendation and
  (if requested) Travel Pass — demonstrated live.
- Travel Pass is offline-ready and matches the visual/data contract
  ([`DESIGN_SYSTEM.md` §11.9](DESIGN_SYSTEM.md)); system deploys and runs on Alibaba Cloud.

> **Status:** not implemented during A1. Interface owned by A; C builds to it.

---

## 4. Cross-workstream exchange (who provides what)

Only **real** dependencies are listed. Each exchange happens through a documented interface in
[`API_CONTRACTS.md`](API_CONTRACTS.md) — never by reaching into another workstream's internals.

### What A provides to B
- The **transit tool interface contracts** (`search_routes`, `get_fare_estimate`,
  `get_delay_prediction`, `get_route_details`) — signatures, args, expected result shapes,
  `data_source`/confidence fields.
- **Mock implementations** of those tools (so B has a working reference + test harness). **A7
  delivered the real reference:** all four are `AVAILABLE` on one shared deterministic dataset
  (`backend/app/tools/intelligence.py` — 7 routes / 3 corridors, route totals **and** consistent leg
  detail), each returning `{ success, tool_name, data_source: mock, data | error{code,message} }` and a
  structured `ROUTE_NOT_FOUND` for an unknown id. B replaces the data source, not the contract.
- The **query shapes** the agent needs (origin/destination/time/preferences; route/leg ids).
- **Handover (A10):** contracts + mocks + example agent calls for B to replace.

### What B provides to A
- **Real route candidates**, **fare estimates** (XGBoost), **delay predictions** (LSTM), and
  **route details** — behind A's **unchanged** tool signatures.
- `data_source` + confidence on every result (so A stays honest).

### What A provides to C
- The **execution tool interface contracts** (`check_availability`, `prepare_booking`) —
  signatures, args, result shapes, and the **confirmation gate** rules.
- The **replanning hook**: how a disruption signal from C triggers A's `REPLANNING`.
- The **Travel Pass data/visual contract** (what data the pass needs; how it's styled).
- **Mock implementations** of the execution tools (so C has a reference + test harness). **A7
  deliberately left these as honest `NOT_IMPLEMENTED` stubs** — the contracts and the executor's
  availability gate are in place, but no simulated availability/booking behavior was built.

### What C provides to A
- **Availability status** and **prepared (unconfirmed) bookings** behind A's signatures.
- **Disruption signals** (Coder Wake) that trigger re-planning.
- **Travel Pass delivery** (offline-ready) matching A's data contract.

### What B provides to C
- **Delay predictions** and **route/transit intelligence** that C uses to decide **autonomous
  rerouting** and to interpret monitoring signals.
- Alternative route candidates for C's reroute execution.

### What C provides to B
- **(Future)** observed execution outcomes (confirmed bookings, realized delays) that can enrich
  B's data/models. **Out of MVP scope** — documented as a future feedback loop, not a current
  dependency.

### Exchange matrix (summary)

| Provider → Consumer | Interface | MVP status |
|---------------------|-----------|------------|
| A → B | transit tool contracts + mocks | A defines; B implements later |
| B → A | routes/fares/delays/details (real) | mock now |
| A → C | execution tool contracts + replan hook + pass contract | A defines; C implements later |
| C → A | availability/booking-prep/disruption/pass delivery | simulated now |
| B → C | delay/route intelligence for rerouting | future |
| C → B | observed outcomes (feedback) | future (out of MVP) |

---

## 5. Shared responsibilities (all members)

- **Integration:** each member integrates their workstream against the others' interfaces and
  helps wire end-to-end flows.
- **Testing:** each member tests their own workstream **and** the integration points they touch.
- **UI:** each workstream ships its **own related UI**, following the shared design system
  ([`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md)) so the product looks like **one** system.
- **Docs:** keep this file, [`ARCHITECTURE.md`](ARCHITECTURE.md), and
  [`API_CONTRACTS.md`](API_CONTRACTS.md) updated when an interface or boundary changes.
- **Demo:** all three contribute to the golden demo ([`DEMO.md`](DEMO.md)).

---

## 6. Boundary rules (quick reference)

- **A** decides; **B** informs; **C** acts. (Brain / truth / hands.)
- A never touches the DB or models directly — it calls B's tools.
- A never commits irreversible actions — it calls C's tools; C gates on confirmation.
- B never makes travel decisions — it returns data/predictions.
- C never invents routes/fares — it uses B's intelligence and A's plan.
- Interface changes are agreed in [`API_CONTRACTS.md`](API_CONTRACTS.md) **before** code.
