# RouteWise Agentic

**Autonomous Multi-Modal Travel & Transit Coordinator for Tourism in Sri Lanka**

- **Competition:** AI Buildathon 2026
- **Track:** Hospitality & Tourism
- **Current phase:** A1 — Project Foundation ✅ (docs consolidated into an 8-doc system; **working foundation scaffold implemented** — FastAPI backend + React shell + AI-service abstraction)
- **Build sequencing:** Workstream A first; B & C documented now, built later to the same interfaces

> 🤖 **AI agents: read [`AI_CONTEXT.md`](AI_CONTEXT.md) before doing anything.**
> The `docs/` folder is the single source of truth for this project.

---

## What is RouteWise Agentic?

RouteWise is an **Agentic AI** travel coordinator. It goes beyond passive
map/navigation apps: instead of only drawing a line from A to B, it *understands* a
traveler's natural-language request, *reasons* over budget, luggage, walking
preference, timing and transit conditions, *acts* through tools, *adapts* when
something changes, and *delivers* a clear recommendation plus an offline-ready
Travel Pass.

The agentic loop:

```
UNDERSTAND → REASON → ACT → ADAPT → DELIVER
```

### Golden demo scenario

> *"I am at Colombo Fort and need to reach Ella under a budget of LKR 2,000, but I
> have a heavy bag and don't want to walk."*

The agent must understand the request, extract constraints (budget, heavy luggage,
minimal walking), evaluate multi-modal routes, weigh delays, compare alternatives,
explain its decision, and produce the final travel information — reasoning over data
and tools, **not** a hard-coded answer.

---

## Architecture (high level)

```
┌──────────────────────────────────────────────────────────────┐
│  Frontend (React)  — travel request UI, agent activity, routes │
└───────────────▲───────────────────────────────┬──────────────┘
                │ REST / JSON contracts          │
┌───────────────┴───────────────────────────────▼──────────────┐
│  Backend (Python / FastAPI)                                    │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Workstream A — AI Agent & Decision Engine (Qwen)         │ │
│  │  understand → plan → call tools → score routes → explain  │ │
│  └───────────────┬───────────────────────────┬──────────────┘ │
└──────────────────┼───────────────────────────┼────────────────┘
                   │ (mock now)                 │ (mock now)
     ┌─────────────▼──────────────┐  ┌──────────▼─────────────────┐
     │ Workstream B (future)       │  │ Workstream C (future)       │
     │ Transit Intelligence & ML   │  │ Autonomous Execution & Cloud│
     │ PostgreSQL/PostGIS, GTFS,   │  │ Coder Work automation,      │
     │ XGBoost fares, LSTM delays  │  │ booking, Coder Wake, deploy │
     └─────────────────────────────┘  └─────────────────────────────┘
```

**Primary reasoning engine:** Qwen (Alibaba Cloud Model Studio).
**Automation/dev ecosystem:** Alibaba Cloud Coder Work / IDE / Wake.
**MVP strategy:** mock data everywhere so the demo is reliable. Real integrations come later.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| AI | Alibaba Cloud Model Studio · **Qwen 3.8 Max** |
| Agent / Automation | Alibaba Cloud **Coder Work · Coder IDE · Coder Wake** |
| Backend | **Python · FastAPI** |
| Frontend | **React.js** |
| Database | **PostgreSQL · PostGIS** |
| Machine Learning | **XGBoost** (fares) · **LSTM** (delays) |
| Cloud | **Alibaba Cloud** |
| Data | GTFS/static transit · mock GTFS-RT · simulated delay/congestion · future real integrations |

---

## Team workstreams

Each of the 3 members owns a **feature/system workstream** end-to-end (integration,
testing and UI included) — not a simplistic frontend/backend/ML split.

- **Workstream A — AI Agent & Decision Engine** *(built first)*
  Qwen integration, travel-request understanding, constraint extraction, agent state &
  orchestration, tool calling, route candidate evaluation & scoring, decision-making,
  AI explanations, mock tools, agent activity/status UI, stable API contracts, handover to B.
- **Workstream B — Transit Intelligence & ML** *(built later)*
  PostgreSQL/PostGIS, GTFS, mock GTFS-RT, transit graph, geographic calculations,
  XGBoost fare prediction, LSTM delay prediction, transit APIs, related UI.
- **Workstream C — Autonomous Execution & Cloud** *(built later)*
  Coder Work browser automation, booking/availability, external tool adapters,
  Coder Wake monitoring, disruption handling & rerouting, Travel Pass execution/delivery,
  Alibaba Cloud deployment, related UI.

**Documentation covers all three workstreams; implementation is sequenced A-first.** B and C
are built later by their owners to the same interfaces (clean interfaces/mocks are allowed
where a boundary is needed now). Mantra: **A decides, B informs, C acts.**

---

## Development phases (Workstream A)

| Phase | Name | Status |
|-------|------|--------|
| **A1** | **Project Foundation** | ✅ **Current** |
| A2 | Travel Request Understanding | ⏳ Not started |
| A3 | Agent Architecture | ⏳ |
| A4 | Agent Tool System | ⏳ |
| A5 | Tool-Calling Orchestrator | ⏳ |
| A6 | Route Decision Engine | ⏳ |
| A7 | Mock Intelligence Integration | ⏳ |
| A8 | Agent Experience / UI | ⏳ |
| A9 | Final API & Agent State | ⏳ |
| A10 | Workstream B Handover | ⏳ |

Do not auto-advance past the current phase.

---

## Documentation system (source of truth)

All project knowledge lives in [`docs/`](docs). Start with [`AI_CONTEXT.md`](AI_CONTEXT.md).

| # | Document | Purpose |
|---|----------|---------|
| 1 | [`PROJECT.md`](docs/PROJECT.md) | Product, problem, users, capabilities, stack, workstreams, MVP, demo, status. |
| 2 | [`ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Full-stack architecture, A/B/C boundaries, data/API/tool flow, frontend structure. |
| 3 | [`DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md) | Centralized UI tokens + application guidelines + component registry. |
| 4 | [`API_CONTRACTS.md`](docs/API_CONTRACTS.md) | Endpoint & tool interface contracts (current vs future) + communication map. |
| 5 | [`AGENT_SPEC.md`](docs/AGENT_SPEC.md) | Agent I/O, canonical states, planning, tool calling, scoring, safety, must-nots. |
| 6 | [`WORKSTREAMS.md`](docs/WORKSTREAMS.md) | Team coordination: A/B/C responsibilities & pairwise exchanges. |
| 7 | [`DEVELOPMENT_RULES.md`](docs/DEVELOPMENT_RULES.md) | The 20 rules + git collaboration + environment/secrets. |
| 8 | [`DEMO.md`](docs/DEMO.md) | Golden demo walkthrough + mock scenarios. |

The **Markdown design system explains** the visual rules; **`frontend/src/styles/tokens.css`
implements** them as CSS custom properties. Keep both in sync.

---

## Repository layout

```
RouteWise - Agentic/
├── AI_CONTEXT.md      # AI agent entry point — read first
├── README.md          # this file
├── .gitignore
├── docs/              # source of truth
├── frontend/          # React + Vite + TS app shell + design tokens (Workstream A UI)
├── backend/           # FastAPI foundation (Workstream A): app, config, health, route/plan stub, AI service
├── data/              # mock/static data (shared)
├── models/            # ML artifacts (Workstream B — not implemented yet)
└── automation/        # Coder Work/Wake automation (Workstream C — not implemented yet)
```

---

## Local development (A1 foundation)

Prerequisites: a recent **Python 3.x** and **Node.js 18+** (this foundation was built and
verified on **Python 3.13** and **Node 25**).

**1. Backend** (from `backend/`):

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell (cmd: .venv\Scripts\activate.bat · bash: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env            # OPTIONAL — only to enable real Qwen; never commit .env
uvicorn app.main:app --reload     # http://localhost:8000 · docs at /docs · health at /health
```

**2. Frontend** (from `frontend/`, in a second terminal):

```bash
npm install
npm run dev                       # http://localhost:5173 (Vite; CORS-enabled against :8000)
```

Open http://localhost:5173 — the foundation shell checks backend health and can exercise
`POST /api/route/plan` (which returns an honest A1 **foundation stub**, not a real plan).

**Verify:**

- `pytest` from `backend/` — health, config, route-plan foundation, and the AI-service mock; the
  live Qwen connectivity test is **skipped** unless `MODEL_STUDIO_API_KEY` is set.
- `npm run build` from `frontend/` — type-checks (`tsc --noEmit`) then builds the production bundle.

> Configuration is via environment variables only. **Never commit `.env` or any API key**
> (see [`docs/DEVELOPMENT_RULES.md`](docs/DEVELOPMENT_RULES.md) → Environment & secrets).

---

## Status

**A1 — Project Foundation is complete.** The documentation is **consolidated into an 8-doc
system** covering all three workstreams (PROJECT, ARCHITECTURE, DESIGN_SYSTEM, API_CONTRACTS,
AGENT_SPEC, WORKSTREAMS, DEVELOPMENT_RULES, DEMO), the machine-readable design tokens live in
`frontend/src/styles/tokens.css`, **and a working foundation scaffold is in place**: a FastAPI
backend (config, logging, CORS, `GET /health`, a contract-shaped `POST /api/route/plan`
foundation stub, structured errors), an isolated **AI service abstraction** for Qwen/Model Studio
with a mock fallback, and a **React + Vite + TypeScript** frontend (app shell + a centralized
`services/api` client). Backend tests pass and frontend ↔ backend communication is verified
end to end.

**No application features are implemented yet** (by design): no agent logic, travel-request
understanding, tool calling, route scoring, ML, database, or automation — those are later phases
(A2+) and Workstreams B/C. **Qwen connectivity is not claimed** (with no API key configured the
backend uses the mock AI client).
