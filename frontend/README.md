# frontend/ — RouteWise Agentic (React)

> **Workstream A UI + the design-system source of truth.**
> Read [`../AI_CONTEXT.md`](../AI_CONTEXT.md) and
> [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) first.

## Status — phase A8 (Agent Experience / UI) ✅ implemented · A9 (stabilization) ✅

The **A8 product UI is built and verified** — the React app boots, builds (`tsc --noEmit` strict +
`vite build`), and talks to the backend through `services/api`. The A1 foundation is now the base for
a two-column agent-experience UI. **A9 kept the UI unchanged except consistency fixes**: a new request
now clears the previous run's state (no stale trace/stepper during "Working…"), the `request_id` /
`kind` additive contract fields are mirrored in `types/api.ts`, and the header badge reads "Phase
A9". What exists now:

```
frontend/
├── index.html                 ✅ Vite entry (loads src/main.tsx)
├── package.json               ✅ scripts + deps (React 18 · Vite 5 · TypeScript 5 — no new deps in A8)
├── vite.config.ts             ✅ dev server on :5173 (backend on :8000 is CORS-enabled for it)
├── tsconfig.json              ✅ strict TS config
├── .env.example               ✅ VITE_API_BASE_URL template (no secrets — Vite exposes VITE_* only)
└── src/
    ├── main.tsx               ✅ bootstrap: mounts <App/>, imports tokens.css + globals.css
    ├── App.tsx / App.css      ✅ A8 shell only (header + connection StatusIndicator + <RoutePlanner> + footer)
    ├── features/route-planner/ ✅ A8 the plan flow (request → agent activity rail → results)
    ├── components/ui·agent·travel/ ✅ A8 registered shared components (docs/DESIGN_SYSTEM.md §13)
    ├── config/env.ts          ✅ runtime config (API base URL)
    ├── types/api.ts           ✅ domain types mirroring API_CONTRACTS.md
    ├── services/api/          ✅ the ONLY backend caller (client · health · routePlan · index)
    ├── services/format.ts     ✅ A8 presentation formatters (LKR · durations · distances · describeError)
    ├── services/agentState.ts ✅ A8 agent-state labels + canonical order + visited-state helper
    └── styles/
        ├── tokens.css         ✅ design tokens (CSS custom properties) — SOURCE OF TRUTH
        └── globals.css        ✅ reset + base element styles + .skeleton (consumes tokens.css)
```

- `tokens.css` **implements** the values documented in
  [`../docs/DESIGN_SYSTEM.md`](../docs/DESIGN_SYSTEM.md). The Markdown explains the rules;
  this CSS enforces them. **Keep both in sync in the same change.**
- `globals.css` sets base document styles (background, text, headings, links, focus,
  reduced-motion, scrollbars) + the shared `.skeleton` loading primitive, using tokens only.
- `App.tsx` is the **shell** (header + connection indicator + footer) and mounts the one feature
  slice `features/route-planner/`, which owns the plan state machine and renders all four interface
  states (loading / error / empty / success). Components call the backend only through
  `services/api`; formatters/agent-state maps live in `services/format.ts` / `services/agentState.ts`.
- **Built in A8:** the registered components in
  [`../docs/DESIGN_SYSTEM.md` §13](../docs/DESIGN_SYSTEM.md) (`ui/`, `agent/`, `travel/`) and the
  `features/route-planner/` slice. **Still deferred:** `pages/`, `hooks/`, `state/`, `utils/`,
  `assets/`, and `services/mock/` still hold only their README stubs — create them when you build the
  thing inside (no empty leaf folders).

## Run it

```bash
npm install
npm run dev        # http://localhost:5173 (start the backend on :8000 first — see ../backend/README.md)
npm run build      # tsc --noEmit (type-check) + vite build (production bundle in dist/)
npm run preview    # preview the production build
```

The shell checks `GET /health` on load (the header connection indicator); `features/route-planner/`
exercises `POST /api/route/plan` (the full A3–A7 agent run). If the backend is down, the shell shows a
clear offline state with a re-check action.

## Planned structure (do not create empty folders until you build the thing inside)

See [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) for the full
feature-oriented layout: `pages/`, `features/`, `components/` (`ui` / `agent` / `travel`),
`hooks/`, `services/` (`api` / `mock` / `formatters`), `state/`, `types/`, `config/`,
`assets/`, `utils/`. Shared components are registered in
[`../docs/DESIGN_SYSTEM.md` §13](../docs/DESIGN_SYSTEM.md).

## Tooling (decided in A1, unchanged in A8)

Final choices (also recorded in
[`../docs/ARCHITECTURE.md` §3.5](../docs/ARCHITECTURE.md)):

- **Vite 5 + React 18 + TypeScript 5** — ✅ installed and used now.
- **ESLint + Prettier** — ⏳ still not added (kept dependency-light per
  [`../docs/DEVELOPMENT_RULES.md`](../docs/DEVELOPMENT_RULES.md) rule 9 and the A8 "no new
  dependencies" constraint).
- **Vitest + React Testing Library** — ⏳ **not added in A8.** A8 shipped the first real components
  without a runner, so the UI behaviors are verified by `tsc --noEmit` (strict) + `vite build` + the
  backend suite + manual DOM checks; add a runner when the team accepts the dependency.

## Using the tokens

Import once in the app bootstrap (`src/main.*`):

```ts
import './styles/tokens.css';
import './styles/globals.css';
```

Then, in any component style, reference tokens — **never** hard-code values:

```css
.route-card {
  background: var(--card-bg);
  border: var(--card-border);
  border-radius: var(--card-radius);
  padding: var(--card-padding);
  box-shadow: var(--card-shadow);
}
```

If a token you need does not exist, **add it to `../docs/DESIGN_SYSTEM.md` and `tokens.css`
first**, then use it. See [`../docs/DEVELOPMENT_RULES.md`](../docs/DEVELOPMENT_RULES.md)
rules 6–7.
