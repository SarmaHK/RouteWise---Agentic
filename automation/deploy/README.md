# automation/deploy/ — RouteWise Agentic

> ⚠️ **Owner:** Workstream C — Autonomous Execution & Cloud. **OUT OF SCOPE for the current phase.**
> **Layer:** cloud deployment / infrastructure-as-code.

## Purpose (future)

- **Alibaba Cloud** deployment: infrastructure-as-code, CI/CD, and environment configuration for
  the backend (FastAPI) + frontend (React) + data/ML services.

## Boundaries

- Keep the app **12-factor-friendly** (config via env, stateless backend) so deployment is
  additive. **Secrets via environment only — never committed**
  (see [`DEVELOPMENT_RULES.md`](../../docs/DEVELOPMENT_RULES.md)). Do not implement during A1.
