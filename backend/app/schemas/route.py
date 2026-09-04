"""Route-planning schemas (Phase A1 foundation).

These Pydantic models mirror docs/API_CONTRACTS.md §2–§4 so the frontend types and the
backend stay aligned. In A1 the ``POST /api/route/plan`` endpoint returns an HONEST
foundation stub (status IDLE, no fabricated route) — the real planning/decision logic is
built in A2–A9. Defining the contract shapes now is foundational; implementing them is not.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AgentState(str, Enum):
    """The 9 canonical agent states (API_CONTRACTS §2; AGENT_SPEC §5)."""

    IDLE = "IDLE"
    UNDERSTANDING = "UNDERSTANDING"
    PLANNING = "PLANNING"
    SEARCHING = "SEARCHING"
    EVALUATING = "EVALUATING"
    EXECUTING = "EXECUTING"
    REPLANNING = "REPLANNING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class DataSource(str, Enum):
    """Honesty flag carried by every tool/route result (API_CONTRACTS §3)."""

    mock = "mock"
    simulated = "simulated"
    live = "live"


class PlanRequest(BaseModel):
    """Request body for ``POST /api/route/plan`` (API_CONTRACTS §2)."""

    origin: str = Field(description='e.g. "Colombo Fort".')
    destination: str = Field(description='e.g. "Ella".')
    budget: Optional[float] = Field(
        default=None, description="Max total fare in LKR (hard constraint when present)."
    )
    luggage: Optional[str] = Field(
        default=None, description='e.g. "none" | "light" | "heavy".'
    )
    walking_preference: Optional[str] = Field(
        default=None, description='e.g. "minimize" | "normal" | "ok" (soft preference).'
    )
    departure_time: Optional[datetime] = None
    arrival_deadline: Optional[datetime] = Field(
        default=None, description="Must-arrive-by (hard constraint when present)."
    )
    preferences: dict[str, Any] = Field(
        default_factory=dict, description="Open bag for extra soft preferences."
    )
    raw_text: Optional[str] = Field(
        default=None,
        description="Optional original natural-language request (normalized in A2).",
    )


class ToolCall(BaseModel):
    """A tool invocation recorded in an agent action (API_CONTRACTS §4)."""

    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    status: str = "done"  # pending | running | done | error
    result_summary: Optional[str] = None


class AgentAction(BaseModel):
    """One entry of the ordered agent-activity log (API_CONTRACTS §4)."""

    seq: int
    state: AgentState
    label: str
    detail: Optional[str] = None
    tool_call: Optional[ToolCall] = None
    status: str = "done"  # pending | active | done | error
    timestamp: Optional[datetime] = None
    data_source: Optional[DataSource] = None


class Leg(BaseModel):
    """A single leg of a route (API_CONTRACTS §3). Foundation shape; populated from A6+."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    mode: str  # walk | tuk | bus | train | taxi | ferry
    origin: str = Field(alias="from")
    destination: str = Field(alias="to")
    departure_time: Optional[datetime] = None
    arrival_time: Optional[datetime] = None
    duration_min: Optional[float] = None
    fare_lkr: Optional[float] = None
    walking_km: Optional[float] = None
    delay_risk: Optional[str] = None  # none | low | moderate | high
    delay_min_estimate: Optional[float] = None
    notes: Optional[str] = None
    data_source: DataSource = DataSource.mock


class Recommendation(BaseModel):
    """A recommended (or alternative) route (API_CONTRACTS §3). Foundation shape."""

    id: str
    summary: str
    total_duration_min: Optional[float] = None
    total_fare_lkr: Optional[float] = None
    transfers: Optional[int] = None
    walking_km: Optional[float] = None
    within_budget: Optional[bool] = None
    delay_risk: Optional[str] = None
    score: Optional[float] = None
    rationale: Optional[str] = None
    trade_offs: list[str] = Field(default_factory=list)
    is_recommended: bool = False
    data_source: DataSource = DataSource.mock


class PlanResponse(BaseModel):
    """Response for ``POST /api/route/plan`` (API_CONTRACTS §2)."""

    status: AgentState
    request: Optional[PlanRequest] = Field(
        default=None, description="The normalized request the agent understood."
    )
    recommendation: Optional[Recommendation] = None
    legs: list[Leg] = Field(default_factory=list)
    alternatives: list[Recommendation] = Field(default_factory=list)
    agent_actions: list[AgentAction] = Field(default_factory=list)
