"""Pydantic schemas mirroring docs/API_CONTRACTS.md (Phase A1 foundation).

Import from here so routers/services share one source of typed shapes. Field names are
``snake_case`` and enums are ``UPPER_SNAKE_CASE`` per API_CONTRACTS §8.
"""

from app.schemas.common import ErrorDetail, ErrorResponse, HealthResponse
from app.schemas.route import (
    AgentAction,
    AgentState,
    DataSource,
    Leg,
    PlanRequest,
    PlanResponse,
    Recommendation,
    ToolCall,
)

__all__ = [
    "ErrorDetail",
    "ErrorResponse",
    "HealthResponse",
    "AgentAction",
    "AgentState",
    "DataSource",
    "Leg",
    "PlanRequest",
    "PlanResponse",
    "Recommendation",
    "ToolCall",
]
