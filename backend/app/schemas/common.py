"""Shared response schemas (Phase A1 foundation).

Mirrors docs/API_CONTRACTS.md §5 (structured error envelope) and the health check
(A1 brief §12). Additive metadata is allowed (API_CONTRACTS §9); the contracted fields are
``status`` (health) and ``status``/``error`` (errors).
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """GET /health response — proves the backend is alive (A1 foundation)."""

    status: str = Field(default="ok", description="Liveness flag; 'ok' when healthy.")
    service: str = Field(default="routewise-agentic-backend")
    phase: str = Field(default="A1-foundation")


class ErrorDetail(BaseModel):
    """The ``error`` object of the structured error envelope (API_CONTRACTS §5)."""

    code: str = Field(description="Stable machine string clients may branch on.")
    message: str = Field(description="Human-readable and safe to show.")
    details: Optional[dict[str, Any]] = Field(default=None)
    retryable: bool = Field(default=False)


class ErrorResponse(BaseModel):
    """Structured error envelope returned for all error responses (API_CONTRACTS §5)."""

    status: str = Field(default="ERROR")
    error: ErrorDetail
