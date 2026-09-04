# automation/ — RouteWise Agentic

> ⚠️ **Workstream C — Autonomous Execution & Cloud. OUT OF SCOPE for the current work.**
> Read [`../AI_CONTEXT.md`](../AI_CONTEXT.md) and
> [`../docs/PROJECT.md`](../docs/PROJECT.md) (§7–8 workstreams & scope) first.

## Purpose (future)

Will hold **autonomous execution and cloud/automation** assets:

- **Alibaba Cloud Coder Work** browser automation
- Booking / availability workflows and external tool adapters
- **Coder Wake** monitoring, autonomous disruption handling & rerouting
- Travel Pass execution / delivery
- Alibaba Cloud deployment / infrastructure-as-code

## Status — DO NOT IMPLEMENT YET

**This folder is a placeholder.** No browser automation, booking logic, monitoring, or
deployment scripts are created during Workstream A / the current phases.

Per the project rules, **do not build real booking automation, Coder Wake monitoring, or the
final Travel Pass implementation now.** Workstream A interacts with execution through **mock
tool interfaces** ([`../docs/API_CONTRACTS.md`](../docs/API_CONTRACTS.md) §6:
`check_availability`, `prepare_booking`). Those mocks **only prepare/simulate** — they never
commit an irreversible action. Real execution (with explicit user confirmation) is
Workstream C.

## Boundaries

- **Owner:** Workstream C (future).
- Irreversible actions require explicit confirmation
  (see [`../docs/AGENT_SPEC.md`](../docs/AGENT_SPEC.md)).
- Keep secrets/credentials out of the repo (see `.gitignore`).
