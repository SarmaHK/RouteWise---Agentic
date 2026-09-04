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
| **Implementation sequencing** | Workstream A built first (phases A1–A2 done); B & C documented, built to the same interfaces |

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
- **No route-planning features yet (by design).** No orchestration, tool calling, route
  scoring/decision engine, ML, database, GTFS, automation, or real UI components are built during
  A2 — those belong to A3+ / Workstream B / Workstream C.
- **Honesty:** real Qwen connectivity is **not** claimed unless a key is configured; with no key the
  backend uses the mock extractor/client (see [`AGENT_SPEC.md` §15](AGENT_SPEC.md)).
- **Next (when instructed):** Workstream A phase **A3 — Agent Architecture**; B and C proceed
  against the agreed interfaces.

---

## 14. Development phases (Workstream A sequencing)

| Phase | Name | Focus |
|-------|------|-------|
| **A1** | **Project Foundation** ✅ | Docs, design system, tokens, architecture, contracts **+ a working foundation scaffold (FastAPI app + React shell + AI-service abstraction + tests)**. |
| **A2** | **Travel Request Understanding** ✅ | NLU: request → validated `TravelRequest` + constraints (extraction only; no route planning). |
| A3 | Agent Architecture | Agent state model, orchestration skeleton. |
| A4 | Agent Tool System | Tool definitions + mock implementations. |
| A5 | Tool-Calling Orchestrator | Qwen tool-calling loop (decide → call → observe). |
| A6 | Route Decision Engine | Candidate evaluation, scoring, selection, explanation. |
| A7 | Mock Intelligence Integration | Wire in mock fares/delays (B boundary). |
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
