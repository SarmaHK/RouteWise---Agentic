# backend/app/services/ — RouteWise Agentic

> **Owner:** Workstream A (shared). · **Layer:** domain services.
> Reusable domain logic shared by the agent and the API routers.

## What goes here

- **`ai/` (A1 ✅ + A2 ✅)** — the AI service abstraction isolated behind a clean interface: base
  contract, `qwen_client` (Alibaba Cloud Model Studio / Qwen), `mock_client` fallback, and a
  factory that picks between them based on config. A2 adds **`extraction.py`** — the
  `TravelRequestExtractor` (a Qwen extractor wrapping the existing client + a deterministic mock
  extractor) and its own factory; natural-language → validated `TravelRequest`. No route/agent
  decision logic lives here yet (A3+).
- **Domain services (A3+ ⏳)** — further cross-cutting logic that is neither HTTP nor agent-state —
  e.g., plan/route assembly, explanation formatting, mock-data loading. (Request
  understanding/normalization itself is A2, implemented in `ai/extraction.py`.)

## Boundaries

- No HTTP handling (that lives in [`../api/`](../api/README.md)) and no agent decision loop
  (that lives in [`../agent/`](../agent/README.md)).
- Keeps business logic **out of routers and out of the UI**.
