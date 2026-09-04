"""Aggregate API router mounted under the ``/api`` prefix (docs/API_CONTRACTS.md §1.6).

Health is mounted separately at the root (see ``app.api.health``) because liveness probes are
infrastructure, not part of the versioned application API.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api import route

api_router = APIRouter()
api_router.include_router(route.router, prefix="/route")
