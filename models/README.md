# models/ — RouteWise Agentic

> ⚠️ **Workstream B — Transit Intelligence & ML. OUT OF SCOPE for the current work.**
> Read [`../AI_CONTEXT.md`](../AI_CONTEXT.md) and
> [`../docs/PROJECT.md`](../docs/PROJECT.md) (§7–8 workstreams & scope) first.

## Purpose (future)

Will hold **machine-learning artifacts and training code** for transit intelligence:

- **XGBoost** — fare prediction
- **LSTM** — delay prediction
- Related feature pipelines and model exports

## Status — DO NOT IMPLEMENT YET

**This folder is a placeholder.** No models, training scripts, or ML dependencies are created
during Workstream A / the current phases.

Per the project rules, **do not build XGBoost, LSTM, or any ML pipeline now.** Workstream A
consumes fare/delay values through **mock tool interfaces**
([`../docs/API_CONTRACTS.md`](../docs/API_CONTRACTS.md) §6: `get_fare_estimate`,
`get_delay_prediction`). Workstream B will later replace those mocks with real models behind
the **same interfaces** — so the agent code does not change.

## Boundaries

- **Owner:** Workstream B (future).
- Model binaries (`.pkl`, `.joblib`, `.h5`, `.pt`, `.onnx`, …) are excluded from git via
  `.gitignore`.
