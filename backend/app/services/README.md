# backend/app/services/ — RouteWise Agentic

> **Owner:** Workstream A (shared). · **Layer:** domain services.
> Reusable domain logic shared by the agent and the API routers.

## What goes here

- **`ai/` (A1 ✅)** — the AI service abstraction isolated behind a clean interface: base
  contract, `qwen_client` (Alibaba Cloud Model Studio / Qwen), `mock_client` fallback, and a
  factory that picks between them based on config. No agent decision logic lives here yet.
- **Domain services (A2+ ⏳)** — cross-cutting logic that is neither HTTP nor agent-state —
  e.g., request normalization, plan/route assembly, explanation formatting, mock-data loading.

## Boundaries

- No HTTP handling (that lives in [`../api/`](../api/README.md)) and no agent decision loop
  (that lives in [`../agent/`](../agent/README.md)).
- Keeps business logic **out of routers and out of the UI**.
