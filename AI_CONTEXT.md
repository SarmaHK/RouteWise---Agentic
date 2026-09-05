# AI_CONTEXT.md — RouteWise Agentic

> **STOP. READ THIS FIRST.**
>
> You are an AI coding agent working inside the **RouteWise Agentic** repository.
> Before you read code, write code, refactor, or "improve" anything, read this file
> completely and then follow the **Required Reading Order** below.
>
> This repository is worked on by **multiple human developers and multiple AI agents**
> (Qoder IDE, Antigravity, and others). The **documentation is the single source of truth**.
> Your job is to stay consistent with it — not to reinvent it.

---

## 1. What this project is (30-second summary)

**RouteWise Agentic** is an **Autonomous Multi-Modal Travel & Transit Coordinator for
Tourism in Sri Lanka**, built for the **AI Buildathon 2026** (Hospitality & Tourism track).

It is an **Agentic AI** system. It does not just show directions — it *understands* a
natural-language travel request, *reasons* over constraints and transit data, *acts*
through tools, *adapts* to disruptions, and *delivers* an offline-ready Travel Pass.

Core agentic loop:

```
UNDERSTAND → REASON → ACT → ADAPT → DELIVER
```

Full detail: [`docs/PROJECT.md`](docs/PROJECT.md).

---

## 2. Required reading order

The documentation is a curated **8-document system** (consolidated — no duplicate docs). Read
these in order. Do not skip ahead to code until you understand the docs that apply to the area
you are touching.

| # | Document | Read it when you need to know… |
|---|----------|--------------------------------|
| 1 | [`docs/PROJECT.md`](docs/PROJECT.md) | The product, problem, target users, capabilities, stack, workstreams, MVP strategy, golden demo, status. |
| 2 | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Full-stack design: layers, A↔B/A↔C/B↔C boundaries, frontend structure, data/API/tool flow. |
| 3 | [`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md) | **Every** token (color, type, spacing, radius, shadow, motion — §1–11), how to apply them (§12), and the component registry (§13). |
| 4 | [`docs/API_CONTRACTS.md`](docs/API_CONTRACTS.md) | Endpoint shapes, request/response contracts, tool interfaces, current-vs-future status, workstream communication map. |
| 5 | [`docs/AGENT_SPEC.md`](docs/AGENT_SPEC.md) | What the Agent must / must not do: I/O, canonical **states**, planning, tool calling, scoring, hard vs soft constraints, safety, honesty. |
| 6 | [`docs/WORKSTREAMS.md`](docs/WORKSTREAMS.md) | Team coordination: A/B/C responsibilities, dependencies, pairwise exchanges, boundary rules. |
| 7 | [`docs/DEVELOPMENT_RULES.md`](docs/DEVELOPMENT_RULES.md) | The 20 engineering rules + git collaboration + environment/secrets. |
| 8 | [`docs/DEMO.md`](docs/DEMO.md) | The golden demo walkthrough and the mock scenarios (normal / delayed / unavailable / replanning). |

---

## 3. The Prime Directive: documentation is the source of truth

When documentation and your own instinct disagree, **the documentation wins.**

You must **NOT** independently invent any of the following when it is already defined
in the docs:

- UI colors, typography, spacing, radii, shadows, motion
- Components (names, structure, variants)
- Architecture and folder structure
- API structures and contracts
- Agent states and their meaning
- Naming conventions
- Business rules and constraint handling

If you believe a documented decision is wrong or blocking, **do not silently change it.**
Surface it (PR description, comment, or to the team lead) and let a human decide.

---

## 4. Non-negotiable working rules (summary)

The full list is [`docs/DEVELOPMENT_RULES.md`](docs/DEVELOPMENT_RULES.md). The essentials:

1. **Read `AI_CONTEXT.md` first**, then the relevant docs, before touching code.
2. **Inspect the existing repository before changing it.** Never assume a file/folder is empty.
3. **Reuse** existing components, hooks, services, and **design tokens**. Never duplicate.
4. **Never invent arbitrary UI values.** Every color/size/space comes from a token.
5. **Do not silently change API contracts or architecture.** Flag it instead.
6. **Do not modify unrelated functionality.** Keep the change surface minimal.
7. **Keep business logic out of UI components.** Logic lives in services/hooks/state.
8. **Handle loading, error, empty, and success states** in every feature.
9. **Test your changes** before declaring completion. Never claim something works unverified.
10. **Do not implement future workstreams or phases** unless explicitly instructed.

---

## 5. Workstream boundaries — respect them

The project is split into three feature/system workstreams owned by a 3-member team.
Each owns a workstream end-to-end (not a "frontend dev / backend dev / ML dev" split).
**The documentation covers all three** as the shared team source of truth — this is not an
A-only project. Full detail: [`docs/WORKSTREAMS.md`](docs/WORKSTREAMS.md).

- **Workstream A — AI Agent & Decision Engine** ← **built first** (active build workstream)
- **Workstream B — Transit Intelligence & ML** (PostgreSQL/PostGIS, GTFS, XGBoost, LSTM)
- **Workstream C — Autonomous Execution & Cloud** (Coder Work automation, booking, Coder Wake, deployment)

**Implementation is sequenced A-first.** Do NOT implement real Workstream B or C functionality
yet — they are built later by their owners **to the same interfaces**. You may create clean
*interfaces / mocks / contracts* where a workstream needs a boundary. Mantra: **A decides,
B informs, C acts.** See [`docs/PROJECT.md`](docs/PROJECT.md) for exact scope.

---

## 6. Development phases — know where you are

Workstream A proceeds through phases **A1 → A10**.

```
A1 Project Foundation             ✅ implemented
A2 Travel Request Understanding   ✅ implemented
A3 Agent Architecture             ✅ implemented / orchestration + decision
A4 Agent Tool System              ✅ implemented / tool contract + registry + executor
A5 Tool-Calling Orchestrator      ✅ implemented / bounded multi-step Qwen tool loop
A6 Route Decision Engine          ← current / refined deterministic decision engine
A7 Mock Intelligence Integration
A8 Agent Experience / UI
A9 Final API & Agent State
A10 Workstream B Handover
```

**CURRENT PHASE: A6 — Route Decision Engine (decision refinement & constraint-aware route
optimization).**

Do **not** auto-advance into A7 or any later phase. Wait for an explicit human instruction. A6
**refines and strengthens** the A3 `DecisionEngine` (`backend/app/agent/decision.py`) — it does not
replace the A3/A4/A5 architecture, and the public contract `decide(request, candidates) -> Decision`
is unchanged (no orchestrator, tool, endpoint, or candidate-schema change was needed). The pipeline
is explicit: candidate **preparation/sanitization** → **hard-constraint validation** → **feature
normalization** → **preference-weighted scoring** → **deterministic ranking** → recommendation +
alternatives + concise explanation.

- **Hard constraints** (origin, destination, budget ceiling, arrival deadline, and an explicitly
  `unavailable` service) are checked deterministically and **every** violation is reported as a
  structured `ConstraintViolation` (`type` + grounded `message`) in a fixed precedence order — an
  excluded candidate is never silently discarded.
- **Soft preferences** (`walking_preference`, `luggage`) only re-rank candidates that already passed
  the hard filter; they adjust fixed weights (never LLM-generated) which are renormalized to sum to 1.
- **Delay** data is *consumed* when present (`delay_risk` plus a small, capped `delay_min_estimate`
  penalty) but never *predicted* — that stays Workstream B, behind the same fields.
- **Impossible values** (negative / `NaN` / infinite), malformed candidates and duplicate ids are
  treated as **unknown** and recorded as assumptions — never silently accepted, never invented.
- Each route card now carries the additive fields `rank` / `valid` / `strengths` /
  `constraint_violations` (mirrored in `frontend/src/types/api.ts`), and `alternatives[]` is ordered
  valid runners-up first, then clearly-marked exclusions.

The engine remains **deterministic**: Qwen selects tools (A5) but never chooses the winner, and the
golden Colombo Fort → Ella demo still resolves by reasoning over the data (heavy bag + minimize
walking → R1; the same candidates with no preferences → R2). All route data is still **mock**. Do not
start real Workstream B/C work (ML models, PostGIS, GTFS ingestion, browser automation, booking,
Travel Pass generation) or A7+ logic — those are later phases.

---

## 7. Repository map

```
RouteWise - Agentic/
├── AI_CONTEXT.md          ← you are here; the agent entry point
├── README.md              ← human-facing project overview
├── .gitignore
├── docs/                  ← SOURCE OF TRUTH (8 consolidated docs — read these)
│   ├── PROJECT.md
│   ├── ARCHITECTURE.md
│   ├── DESIGN_SYSTEM.md
│   ├── API_CONTRACTS.md
│   ├── AGENT_SPEC.md
│   ├── WORKSTREAMS.md
│   ├── DEVELOPMENT_RULES.md
│   └── DEMO.md
├── frontend/              ← React + Vite + TS app (Workstream A UI + design tokens)
│   ├── README.md
│   ├── src/main.tsx · App.tsx                 ← app shell (request input → agent progress timeline → mock decision); A5 renders the multi-step tool trace; A6 renders the structured route comparison (strengths · trade-offs · constraint violations)
│   ├── src/services/api/                      ← the ONLY backend caller (client · health · routePlan)
│   ├── src/config/env.ts · src/types/api.ts   ← runtime config + contract-mirroring types (A5: ToolCall.error_code · A6: Recommendation rank/valid/strengths/constraint_violations)
│   └── src/styles/tokens.css · globals.css    ← CSS source of truth for the design system
├── backend/               ← FastAPI (Workstream A agent + API) — A1 foundation + A2 understanding + A3 agent + A4 tools + A5 tool loop + A6 decision refinement
│   ├── README.md
│   └── app/ (main · config · logging_config · api/ · schemas/ · agent/ · tools/ · services/ai/ incl. extraction + agent tool-calling planner) · tests/
├── data/                  ← mock/static data (shared; real GTFS is Workstream B)
│   └── README.md
├── models/                ← ML artifacts (Workstream B — DO NOT implement yet)
│   └── README.md
└── automation/            ← Coder Work/Wake automation (Workstream C — DO NOT implement yet)
    └── README.md
```

The Markdown design system **explains** the rules; `frontend/src/styles/tokens.css`
**implements** them as the machine-readable source of truth. Keep the two in sync.

---

## 8. Before you finish any task — self-check

- [ ] I read `AI_CONTEXT.md` and the docs relevant to what I changed.
- [ ] I inspected the existing code before editing (I did not assume it was empty).
- [ ] I reused existing components/tokens/services — I did not duplicate.
- [ ] Every visual value I used comes from a **design token** (no magic numbers/colors).
- [ ] I did **not** change any API contract or architecture silently.
- [ ] I did **not** touch unrelated features.
- [ ] I stayed inside **Workstream A** and the **current phase**.
- [ ] Loading / error / empty / success states are handled (if UI work).
- [ ] I tested my change and can state honestly what I verified.
- [ ] I updated the docs if (and only if) I was instructed to change architecture.
- [ ] My final report clearly lists files created/modified and any decisions needed.

---

## 9. Golden rule

> **Optimize for a working, demonstrable hackathon MVP — not for impressive-looking
> abstractions. Small, consistent, documented, and working beats large, clever, and
> inconsistent every time.**

When in doubt, **stop and ask** rather than invent.
