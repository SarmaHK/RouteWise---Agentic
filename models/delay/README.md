# models/delay/ — RouteWise Agentic

> ⚠️ **Owner:** Workstream B — Transit Intelligence & ML. **OUT OF SCOPE for the current phase.**
> **Layer:** ML model — **delay prediction (LSTM)**.

## Purpose (future)

- Training code, feature pipeline, and exported model for delay prediction, served to the agent
  through the `get_delay_prediction` tool.

## Boundaries

- **Do not implement during Workstream A / A1.** Model binaries (`.h5`, `.pt`, `.onnx`, …) are
  gitignored. B replaces the A mock behind the **same tool signature**
  ([`API_CONTRACTS.md` §6](../../docs/API_CONTRACTS.md)) — so agent code does not change.
