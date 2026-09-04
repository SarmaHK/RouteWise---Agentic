# frontend/ — RouteWise Agentic (React)

> **Workstream A UI + the design-system source of truth.**
> Read [`../AI_CONTEXT.md`](../AI_CONTEXT.md) and
> [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) first.

## Status — phase A1 (Project Foundation) ✅ implemented

The **A1 foundation is scaffolded and verified** — the React app boots, builds, and talks to the
backend. What exists now:

```
frontend/
├── index.html                 ✅ Vite entry (loads src/main.tsx)
├── package.json               ✅ scripts + deps (React 18 · Vite 5 · TypeScript 5)
├── vite.config.ts             ✅ dev server on :5173 (backend on :8000 is CORS-enabled for it)
├── tsconfig.json              ✅ strict TS config
├── .env.example               ✅ VITE_API_BASE_URL template (no secrets — Vite exposes VITE_* only)
└── src/
    ├── main.tsx               ✅ bootstrap: mounts <App/>, imports tokens.css + globals.css
    ├── App.tsx / App.css      ✅ A1 foundation shell (backend health + pipe test; tokens only)
    ├── config/env.ts          ✅ runtime config (API base URL)
    ├── types/api.ts           ✅ domain types mirroring API_CONTRACTS.md
    ├── services/api/          ✅ the ONLY backend caller (client · health · routePlan · index)
    └── styles/
        ├── tokens.css         ✅ design tokens (CSS custom properties) — SOURCE OF TRUTH
        └── globals.css        ✅ reset + base element styles (consumes tokens.css)
```

- `tokens.css` **implements** the values documented in
  [`../docs/DESIGN_SYSTEM.md`](../docs/DESIGN_SYSTEM.md). The Markdown explains the rules;
  this CSS enforces them. **Keep both in sync in the same change.**
- `globals.css` sets base document styles (background, text, headings, links, focus,
  reduced-motion, scrollbars) using tokens only.
- `App.tsx` is the **foundation shell**, not a product screen: it only proves the wiring
  (frontend → `services/api` → FastAPI → response) and renders all four interface states
  (loading / error / empty / success).
- **Still deferred (build in A8):** the real UI — pages, feature slices, and the registered
  components in [`../docs/DESIGN_SYSTEM.md` §13](../docs/DESIGN_SYSTEM.md) (TripForm, RouteCard,
  AgentActivity, …). The `components/`, `features/`, `pages/`, `hooks/`, and `state/` folders
  still hold only their README stubs — **do not build product UI during A1.**

## Run it

```bash
npm install
npm run dev        # http://localhost:5173 (start the backend on :8000 first — see ../backend/README.md)
npm run build      # tsc --noEmit (type-check) + vite build (production bundle in dist/)
npm run preview    # preview the production build
```

The shell checks `GET /health` on load and can exercise `POST /api/route/plan` (an honest A1
foundation stub). If the backend is down, the shell shows a clear offline/error state.

## Planned structure (do not create empty folders until you build the thing inside)

See [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) for the full
feature-oriented layout: `pages/`, `features/`, `components/` (`ui` / `agent` / `travel`),
`hooks/`, `services/` (`api` / `mock` / `formatters`), `state/`, `types/`, `config/`,
`assets/`, `utils/`. Shared components are registered in
[`../docs/DESIGN_SYSTEM.md` §13](../docs/DESIGN_SYSTEM.md).

## Tooling (decided in A1)

Final choices for the foundation (also recorded in
[`../docs/ARCHITECTURE.md` §3.5](../docs/ARCHITECTURE.md)):

- **Vite 5 + React 18 + TypeScript 5** — ✅ installed and used now.
- **ESLint + Prettier** — ⏳ not added in A1 (kept dependency-light per
  [`../docs/DEVELOPMENT_RULES.md`](../docs/DEVELOPMENT_RULES.md) rule 9); add when real UI work
  begins in A8.
- **Vitest + React Testing Library** — ⏳ deferred to A8 alongside the first real components.

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
