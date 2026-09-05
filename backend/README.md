# backend/ — RouteWise Agentic (Python / FastAPI)

> **Workstream A — AI Agent & Decision Engine lives here.**
> Read [`../AI_CONTEXT.md`](../AI_CONTEXT.md), [`../docs/PROJECT.md`](../docs/PROJECT.md),
> [`../docs/API_CONTRACTS.md`](../docs/API_CONTRACTS.md), and
> [`../docs/AGENT_SPEC.md`](../docs/AGENT_SPEC.md) first.

## Status — phase A1 (Project Foundation) ✅ implemented  ·  **current phase: A7**

> The A1 description below is the **historical** foundation record. The authoritative current state
> lives in [`../AI_CONTEXT.md`](../AI_CONTEXT.md) §6 and [`../docs/PROJECT.md`](../docs/PROJECT.md) §13:
> **A1–A7 are implemented** — `POST /api/route/plan` now runs the full agent (A2 extraction → A3 state
> machine + decision engine → A4 tool seam → A5 bounded multi-step Qwen tool-calling loop → A6
> constraint-aware scoring → **A7 mock intelligence**: four `AVAILABLE` mock data tools over one shared
> deterministic dataset). Still **not** built: Workstream B/C real data, execution/booking,
> replanning, ML, database, GTFS, Travel Pass (A8+).

The **A1 foundation is built and verified**: a FastAPI app with env-backed configuration
([`app/config.py`](app/config.py)), logging ([`app/logging_config.py`](app/logging_config.py)),
CORS for local dev, `GET /health`, a contract-shaped `POST /api/route/plan` **foundation stub**
(honest `IDLE`, no fabricated route), the structured error envelope
([`../docs/API_CONTRACTS.md`](../docs/API_CONTRACTS.md) §5), an isolated **AI service
abstraction** for Qwen / Model Studio with a mock fallback
([`app/services/ai/`](app/services/ai)), and tests ([`tests/`](tests)). Frontend ↔ backend
communication is verified end to end.

**Still deferred at A1 (since built in A2–A7):** the Qwen-powered agent, travel-request understanding,
tool calling, orchestration, route scoring, and the decision engine. The endpoint's **live-data**
implementation still lands in **A9** (today it runs the full agent over **mock** intelligence).

## Run it

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell (bash: source .venv/bin/activate)
pip install -r requirements.txt
uvicorn app.main:app --reload     # http://localhost:8000 · /docs · /health
pytest                            # A1–A7 tests (Qwen connectivity tests skip without a key)
```

Configuration is env-based; copy `.env.example` to `.env` **only** to enable real Qwen.
**Never commit `.env` or any API key**
(see [`../docs/DEVELOPMENT_RULES.md`](../docs/DEVELOPMENT_RULES.md) → Environment & secrets).

## Stack (per project direction)

- **Python** · **FastAPI**
- **Qwen** via Alibaba Cloud Model Studio (reasoning engine) — later phase
- Mock data / mock tools for the MVP (real transit intelligence is Workstream B; real
  automation/booking is Workstream C)

## Structure (A1 foundation; ✅ marks what later phases added)

```
backend/
├── app/
│   ├── main.py              # ✅ FastAPI entrypoint: CORS, routers, error handlers
│   ├── config.py            # ✅ env-backed settings (secrets via env only) + A5 MAX_AGENT_ITERATIONS
│   ├── logging_config.py    # ✅ logging foundation
│   ├── api/                 # ✅ health.py · route.py (A1 stub → A2 extraction → A3–A7 agent loop) · router.py
│   ├── schemas/             # ✅ Pydantic models mirroring API_CONTRACTS.md (A2 travel_request · A3 candidate · A5/A6 route)
│   ├── services/ai/         # ✅ AI service abstraction (base · qwen_client · mock_client · factory) + A2 extraction + A5 agent (tool-calling planner)
│   ├── agent/               # ✅ A3 state.py (state machine + context) · decision.py (A6 engine) · orchestrator.py (A5 loop, A7 result merging)
│   └── tools/               # ✅ A4 seam (base · executor · registry · capabilities) + A7 intelligence.py — the ONE shared mock route truth
├── tests/                   # ✅ A1–A7 tests (foundation · extraction · state/decision/agent/API · tool seam · agent loop · decision engine · mock intelligence)
├── requirements.txt         # ✅ dependencies (requirements.txt chosen over pyproject.toml)
├── .env.example             # ✅ config template (copy to .env; never commit .env)
└── README.md
```

## Contract reminders

- The reserved primary endpoint is **`POST /api/route/plan`** — an honest **foundation stub** in
  A1, a real mock agent decision from **A3**, a multi-step mock-intelligence run from **A7**;
  live-data planning in **A9**.
- Field names are **`snake_case`**; money is **LKR**; time is **ISO 8601 (+05:30)**.
- The `status` field is always one of the **canonical Agent states**
  ([`../docs/AGENT_SPEC.md`](../docs/AGENT_SPEC.md)).
- Tool interfaces (`search_routes`, `get_fare_estimate`, `get_delay_prediction`,
  `get_route_details`, `check_availability`, `prepare_booking`) are **mocked** behind stable
  signatures so Workstreams B/C can replace them later without breaking the agent. **Since A7** the
  first four are `AVAILABLE` on deterministic **mock** data read from one shared provider
  ([`app/tools/intelligence.py`](app/tools/intelligence.py) — the Workstream-B replacement point);
  `check_availability` / `prepare_booking` stay honest `NOT_IMPLEMENTED` stubs, and an unknown route id
  is a structured `ROUTE_NOT_FOUND` failure, never invented data.
- Every result carries `data_source` (`mock`/`simulated`/`live`) — never present mock data as
  real-time (see [`../docs/AGENT_SPEC.md`](../docs/AGENT_SPEC.md)).

## Boundaries

- **Workstream A owns this backend** (agent + API contracts).
- Transit intelligence / ML (Workstream B) and autonomous execution / cloud (Workstream C)
  are **out of scope now** — only clean interfaces/mocks are allowed where A needs a boundary.
