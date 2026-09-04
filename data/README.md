# data/ — RouteWise Agentic

> Read [`../AI_CONTEXT.md`](../AI_CONTEXT.md) and
> [`../docs/PROJECT.md`](../docs/PROJECT.md) (§10 MVP / mock-data strategy) first.

## Purpose

Holds the project's **data assets**: mock and static transit fixtures used to make the MVP
demo reliable, plus (later) real GTFS/static data.

## Status — phase A1 (Project Foundation)

**Empty by design.** No data files are created during the foundation phase. Mock fixtures
are added when the tools that consume them are built (Workstream A: **A4/A7**; real transit
data: Workstream B, later).

## Ownership & boundaries

- **Shared folder.** Small, curated **mock** fixtures that Workstream A needs for its tools
  may live here (e.g., `mock/`), clearly labeled as simulated.
- **Real GTFS / GTFS-RT / PostGIS-backed transit data is Workstream B** — **out of scope now.**
  Do not build a GTFS ingestion pipeline or database here during A1.

## Planned structure (create when needed)

```
data/
├── mock/          # small curated mock fixtures for the MVP (labeled simulated)
├── static/        # static reference data (e.g., place gazetteer) if needed
├── raw/           # (gitignored) bulky/raw source data — Workstream B
└── gtfs/          # (gitignored) GTFS feeds — Workstream B
```

> Bulky/raw/GTFS data is excluded from git via `.gitignore`. Commit only small, intentional
> mock fixtures. Never present mock data as real-time
> (see [`../docs/AGENT_SPEC.md`](../docs/AGENT_SPEC.md)).
