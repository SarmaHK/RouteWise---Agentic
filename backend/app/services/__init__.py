"""Domain services (Workstream A, shared).

Reusable domain logic used by the API routers and (from A2+) the agent — kept out of routers
and out of the UI (docs/ARCHITECTURE.md §4). In A1 this holds the AI (Qwen / Alibaba Cloud
Model Studio) client abstraction under ``ai/``.
"""
