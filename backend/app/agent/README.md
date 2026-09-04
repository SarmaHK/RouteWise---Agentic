# backend/app/agent/ — RouteWise Agentic

> **Owner:** Workstream A — AI Agent & Decision Engine. · **Layer:** agent logic.
> The brain of RouteWise: `UNDERSTAND → REASON → ACT → ADAPT → DELIVER`.

## What goes here (built in phases A2–A7)

- Request understanding + constraint extraction (hard vs soft) and missing-info detection.
- Orchestration + the tool-calling loop (Qwen via Alibaba Cloud Model Studio).
- Route evaluation, scoring, decision, explanation, and replanning.

## Boundaries

- The agent reaches B/C **only** through [`../tools/`](../tools/README.md) interfaces — never the
  database or ML models directly.
- Behavior is fully specified in [`AGENT_SPEC.md`](../../../docs/AGENT_SPEC.md): the **9 canonical
  states**, honesty/`data_source`, safety, and the MUST-NOTs. No code during A1.
