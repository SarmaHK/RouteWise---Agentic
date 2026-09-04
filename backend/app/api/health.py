"""Health-check endpoint (A1 foundation).

``GET /health`` → ``{"status": "ok", ...}``. The contracted field is ``status``; ``service``
and ``phase`` are additive metadata (API_CONTRACTS §9). Mounted at the ROOT path (not under
``/api``) by convention for liveness probes and cloud load balancers — see
docs/ARCHITECTURE.md §11 (cloud-ready / 12-factor). Never exposes secrets.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
def health() -> HealthResponse:
    """Return a simple liveness response confirming the backend is running."""
    return HealthResponse(
        status="ok", service="routewise-agentic-backend", phase="A1-foundation"
    )
