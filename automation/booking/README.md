# automation/booking/ — RouteWise Agentic

> ⚠️ **Owner:** Workstream C — Autonomous Execution & Cloud. **OUT OF SCOPE for the current phase.**
> **Layer:** execution — booking & availability.

## Purpose (future)

- Alibaba Cloud **Coder Work** browser automation and external adapters behind the
  `check_availability` and `prepare_booking` tools.

## Boundaries

- **Simulated only** during the MVP. **Irreversible actions require explicit user confirmation**;
  `prepare_booking` only prepares/holds — it never commits. Do not implement during A1
  (see [`AGENT_SPEC.md` §14](../../docs/AGENT_SPEC.md)).
