# backend/ — RouteWise Agentic (Python / FastAPI)

> **Workstream A — AI Agent & Decision Engine lives here.**
> Read [`../AI_CONTEXT.md`](../AI_CONTEXT.md), [`../docs/PROJECT.md`](../docs/PROJECT.md),
> [`../docs/API_CONTRACTS.md`](../docs/API_CONTRACTS.md), and
> [`../docs/AGENT_SPEC.md`](../docs/AGENT_SPEC.md) first.

## Status — phase A1 (Project Foundation) ✅ implemented

The **A1 foundation is built and verified**: a FastAPI app with env-backed configuration
([`app/config.py`](app/config.py)), logging ([`app/logging_config.py`](app/logging_config.py)),
CORS for local dev, `GET /health`, a contract-shaped `POST /api/route/plan` **foundation stub**
(honest `IDLE`, no fabricated route), the structured error envelope
([`../docs/API_CONTRACTS.md`](../docs/API_CONTRACTS.md) §5), an isolated **AI service
abstraction** for Qwen / Model Studio with a mock fallback
([`app/services/ai/`](app/services/ai)), and tests ([`tests/`](tests)). Frontend ↔ backend
communication is verified end to end.

**Still deferred — do NOT build in A1:** the Qwen-powered agent, travel-request understanding,
tool calling, orchestration, route scoring, and the decision engine. Those are **A2–A9**; the
real `POST /api/route/plan` implementation lands in **A9** (today it is an honest stub).

## Run it

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell (bash: source .venv/bin/activate)
pip install -r requirements.txt
uvicorn app.main:app --reload     # http://localhost:8000 · /docs · /health
pytest                            # foundation tests (Qwen connectivity test skips without a key)
```

Configuration is env-based; copy `.env.example` to `.env` **only** to enable real Qwen.
**Never commit `.env` or any API key**
(see [`../docs/DEVELOPMENT_RULES.md`](../docs/DEVELOPMENT_RULES.md) → Environment & secrets).

## Stack (per project direction)

- **Python** · **FastAPI**
- **Qwen** via Alibaba Cloud Model Studio (reasoning engine) — later phase
- Mock data / mock tools for the MVP (real transit intelligence is Workstream B; real
  automation/booking is Workstream C)

## Current structure (A1 foundation)

```
backend/
├── app/
│   ├── main.py              # ✅ FastAPI entrypoint: CORS, routers, error handlers
│   ├── config.py            # ✅ env-backed settings (secrets via env only)
│   ├── logging_config.py    # ✅ logging foundation
│   ├── api/                 # ✅ health.py · route.py (plan stub) · router.py
│   ├── schemas/             # ✅ Pydantic models mirroring API_CONTRACTS.md
│   ├── services/ai/         # ✅ AI service abstraction (base · qwen_client · mock_client · factory)
│   ├── agent/               # ⏳ A2+ — understanding, orchestration, decision engine
│   └── tools/               # ⏳ A4+ — tool interfaces + MOCK implementations (API_CONTRACTS §6)
├── tests/                   # ✅ foundation tests (health · config · route stub · AI mock)
├── requirements.txt         # ✅ dependencies (requirements.txt chosen over pyproject.toml)
├── .env.example             # ✅ config template (copy to .env; never commit .env)
└── README.md
```

## Contract reminders

- The reserved primary endpoint is **`POST /api/route/plan`** — an honest **foundation stub** in
  A1; fully implemented in **A9**.
- Field names are **`snake_case`**; money is **LKR**; time is **ISO 8601 (+05:30)**.
- The `status` field is always one of the **canonical Agent states**
  ([`../docs/AGENT_SPEC.md`](../docs/AGENT_SPEC.md)).
- Tool interfaces (`search_routes`, `get_fare_estimate`, `get_delay_prediction`,
  `get_route_details`, `check_availability`, `prepare_booking`) are **mocked** behind stable
  signatures so Workstreams B/C can replace them later without breaking the agent.
- Every result carries `data_source` (`mock`/`simulated`/`live`) — never present mock data as
  real-time (see [`../docs/AGENT_SPEC.md`](../docs/AGENT_SPEC.md)).

## Boundaries

- **Workstream A owns this backend** (agent + API contracts).
- Transit intelligence / ML (Workstream B) and autonomous execution / cloud (Workstream C)
  are **out of scope now** — only clean interfaces/mocks are allowed where A needs a boundary.
