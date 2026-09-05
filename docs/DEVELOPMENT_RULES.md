# DEVELOPMENT_RULES.md — RouteWise Agentic

> Source of truth #7. **These rules are specifically for AI coding agents** (and the humans
> working alongside them). They are binding. When in conflict with your instincts or a
> shortcut, **the rules win.**
>
> Start every task from [`AI_CONTEXT.md`](../AI_CONTEXT.md).

---

## The 20 rules

### 1. Read `AI_CONTEXT.md` first.
Every session, before touching anything. It tells you the reading order, current phase, and
active workstream.

### 2. Read relevant documentation before coding.
Only the docs relevant to the area you're changing — but actually read them. UI work →
`DESIGN_SYSTEM.md` (tokens + §12 usage + §13 component registry). API work →
`API_CONTRACTS.md`. Agent work → `AGENT_SPEC.md`. System/architecture → `ARCHITECTURE.md`.
Team/scope → `WORKSTREAMS.md`. Demo → `DEMO.md`.

### 3. Inspect the existing repository first.
Never assume a file/folder is empty or that something doesn't exist. Look before you create
or change. Preserve what's already there.

### 4. Reuse existing code where appropriate.
If a util, hook, service, or pattern already solves the problem, use it. Don't reimplement.

### 5. Reuse existing components.
Check the component registry ([`DESIGN_SYSTEM.md` §13](DESIGN_SYSTEM.md)) before creating any
component. Extend with props/variants rather than forking.

### 6. Reuse design tokens.
Every color, font size, spacing, radius, shadow, and duration comes from
[`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md) / `frontend/src/styles/tokens.css`.

### 7. Never invent arbitrary UI values.
No stray `#hex`, `px`, `rgba`, or `rem` in components. If a token is missing, **add it to the
design system + tokens.css first**, then use it.

### 8. Do not create duplicate components.
No `Button2`, `FancyButton`, `RouteCardV2`, `NewCard`. One registered component per concept.

### 9. Do not introduce unnecessary dependencies.
Every new package needs a real justification and (ideally) a documented decision. Prefer the
standard library / existing deps. For the MVP, avoid heavyweight frameworks when a small one
will do. **The documentation-foundation step added none.** The **A1 implementation** step added
only the documented core tooling, each required by the A1 brief (a startable backend/frontend, a
health check, the AI-service abstraction, and a build): backend — `fastapi`, `uvicorn[standard]`,
`pydantic`, `pydantic-settings`, `httpx` (Qwen/Model Studio client + FastAPI `TestClient`),
`pytest`; frontend — `react`, `react-dom`, `vite`, `@vitejs/plugin-react`, `typescript`,
`@types/react`, `@types/react-dom`. Frontend linters/test tooling (ESLint/Prettier, Vitest) are
**deferred to A8**. Add anything further only with a documented decision.

### 10. Do not silently change architecture.
Folder structure, layering, and patterns are documented
([`ARCHITECTURE.md`](ARCHITECTURE.md)). Changing them requires an explicit,
communicated decision — not a quiet refactor.

### 11. Do not silently change API contracts.
[`API_CONTRACTS.md`](API_CONTRACTS.md) is the agreement between frontend/backend/workstreams.
Additive changes are fine (document them); breaking changes need a proposal + version bump +
consumer updates.

### 12. Do not modify unrelated functionality.
Keep the change surface minimal and focused on the task. No drive-by rewrites of code you
weren't asked to touch.

### 13. Keep business logic separate from UI.
Components render. Logic lives in hooks/services/state. A component should not fetch data or
implement scoring/decision rules.

### 14. Keep modules focused.
One module = one clear responsibility. Small, boring, understandable beats clever and dense.

### 15. Handle loading / error / empty states.
Every data-driven view designs all four states (loading, error, empty, success) — see
[`DESIGN_SYSTEM.md` §12.8](DESIGN_SYSTEM.md). No blank screens, no infinite spinners, no
unhandled promise rejections.

### 16. Test changes before declaring completion.
Run the relevant checks/tests. If you can't verify, **say so explicitly** — never claim it
works when you haven't checked.

### 17. Update documentation when architecture changes.
If you (with approval) change architecture, contracts, components, or the design system,
update the corresponding doc **in the same change**. Docs must never drift from reality.

### 18. Do not implement future phases unless explicitly instructed.
Stay in the **current phase** (see [`PROJECT.md` §13–14](PROJECT.md)). Don't auto-advance. The A6
**constraint-aware decision-engine refinement** is now built on the A3 engine (structured violations,
defensive candidates, robust normalization, delay-aware scoring, grounded explanations); don't start
A7+ mock-intelligence integration, replanning/execution, agent-activity UI, ML, PostGIS, GTFS,
automation, booking, or Travel Pass generation unless told to. Phase A6 also **must not** rewrite the
A5 tool-calling loop or the A4 tool seam.

### 19. Do not claim functionality works unless verified.
Honest reporting only. Distinguish "implemented and tested" from "written but not run" from
"planned". This is a hard rule — see also [`AGENT_SPEC.md` §15](AGENT_SPEC.md) (the
*product* agent has the same honesty requirement).

### 20. Optimize for a working hackathon MVP.
Prefer a demonstrable, reliable MVP over unnecessary enterprise abstraction. Ship the smallest
thing that works cleanly and is documented — not a speculative framework.

---

## Workstream & phase discipline (reminder)

- **Documentation covers all three workstreams** (A, B, C) as the shared team source of truth
  ([`WORKSTREAMS.md`](WORKSTREAMS.md)) — this is **not** an A-only project.
- **Implementation is sequenced A-first.** The active build workstream is **A — AI Agent &
  Decision Engine**; B and C are built later by their owners **to the same interfaces**.
- **Current phase: A6 — Route Decision Engine (decision refinement & constraint-aware route optimization).** Do not auto-continue into A7.
- You may create **clean interfaces / mocks / contracts** where a workstream needs a boundary —
  but **no real B/C functionality** until that workstream is explicitly started.

See [`PROJECT.md`](PROJECT.md) for exact scope and [`AI_CONTEXT.md`](../AI_CONTEXT.md) for the
phase list.

---

## Git collaboration & change safety

This repo is shared by **3 human developers and multiple AI agents**. Collaborate safely.

**Before modifying files:**

- Inspect the current repository; identify existing code, config, and dependencies.
- **Avoid destructive changes.** Never delete working functionality just to make structure
  "cleaner".
- If existing code conflicts with the proposed architecture, **explain the conflict first**
  and get a decision before any destructive change.

**Branching & commits:**

- Work on a **feature branch** per task/workstream (e.g., `a/A2-request-understanding`,
  `b/gtfs-ingest`, `c/booking-adapter`). Do not commit directly to `main`.
- Keep commits **small, scoped, and reviewable** — one logical change per commit.
- Write **clear commit messages**: what changed and why; reference the workstream/phase.
- **Never** rewrite shared history or **force-push** shared branches (`main`, or anyone else's
  active branch). Use `--force-with-lease` only on your own unshared branch, if unavoidable.

**Pull requests & review:**

- Open a **PR** for every change; another member (or the team lead) reviews before merge.
- A PR states: files changed, workstream/phase, contracts touched (if any), and what was
  tested. Cross-workstream contract changes need the affected owner's sign-off
  ([`API_CONTRACTS.md` §9](API_CONTRACTS.md)).
- Resolve conflicts by **merging/rebasing from `main`** locally; never clobber a teammate's
  work to win a conflict.
- Keep **docs in sync** in the same PR when architecture/contracts/components change (rule 17).

---

## Environment & secrets

- **Never commit secrets** — API keys (Alibaba Cloud / Model Studio / Qwen), DB credentials,
  tokens, or real `.env` files. These are excluded via `.gitignore`.
- Provide a committed **`.env.example`** with placeholder values and comments; each developer
  keeps real values in a local, gitignored `.env`.
- Read secrets from **environment variables** (e.g., via `backend/app/config.py`) — never
  hard-code them, and never log or echo them (including in agent tool traces or demo output).
- Do not paste real credentials into issues, PRs, chat, or the demo. If a secret is committed
  by accident, **rotate it immediately** and purge it from history.

---

## Definition of Done (for any task)

A task is done only when:

- [ ] You read `AI_CONTEXT.md` + relevant docs.
- [ ] You inspected existing code before changing it.
- [ ] You reused components/tokens/services; no duplication; no magic UI values.
- [ ] You stayed within the active workstream and current phase.
- [ ] Contracts/architecture unchanged (or explicitly approved + docs updated).
- [ ] Loading/error/empty/success handled (if UI).
- [ ] Business logic kept out of UI.
- [ ] You ran relevant checks/tests and can state honestly what you verified.
- [ ] You reported files created/modified, dependencies added, and any decisions needed.

---

## Reporting format (end of task)

Report clearly, using the structure the team lead requests. At minimum include:

- **Repository inspected** — what already existed.
- **Files created / modified** — exact paths.
- **Dependencies added** — or "None".
- **Validation** — what you ran and the results (be honest about what wasn't run).
- **Issues / decisions needed** — anything requiring a human decision.
- **Current phase** and **what's explicitly out of scope**.
