"""Route-planning schemas (Workstream A).

These Pydantic models mirror docs/API_CONTRACTS.md §2–§4 so the frontend types and the
backend stay aligned.

A1 defined the contract shapes with an honest foundation stub. A2 (Request Understanding)
makes ``PlanRequest`` accept free-form natural language: ``origin``/``destination`` are now
optional because they are extracted from ``raw_text``, and at least one of
``raw_text``/``origin``/``destination`` must be present. ``PlanResponse.request`` now carries
the normalized :class:`~app.schemas.travel_request.TravelRequest` the agent understood. No
route planning/scoring is implemented in A2 (that arrives in A3+).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.travel_request import TravelRequest


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
    """Request body for ``POST /api/route/plan`` (API_CONTRACTS §2).

    A2 accepts EITHER structured fields OR free-form ``raw_text``. ``origin``/``destination``
    are optional here because the extractor derives them from ``raw_text``; a request with
    none of the three is rejected by :meth:`_require_some_input` (422).
    """

    origin: Optional[str] = Field(
        default=None, description='e.g. "Colombo Fort". Optional in A2 (extracted).'
    )
    destination: Optional[str] = Field(
        default=None, description='e.g. "Ella". Optional in A2 (extracted).'
    )
    budget: Optional[float] = Field(
        default=None, description="Max total fare in LKR (hard constraint when present)."
    )
    currency: Optional[str] = Field(
        default=None, description='Currency for ``budget``; defaults to "LKR" downstream.'
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
        description="Original natural-language request; the A2 extraction input.",
    )

    @model_validator(mode="after")
    def _require_some_input(self) -> "PlanRequest":
        """Reject an empty request: need ``raw_text`` OR an ``origin`` OR a ``destination``."""
        has_text = bool(self.raw_text and self.raw_text.strip())
        if not (has_text or self.origin or self.destination):
            raise ValueError(
                "Provide at least one of: raw_text, origin, or destination."
            )
        return self


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
    """A recommended (or alternative) route (API_CONTRACTS §3).

    A3 populates this from the deterministic decision engine. ``rationale`` is the headline
    reason; ``reasons`` is the concise, observable list of decision factors (A3 brief §8/§14.6,
    additive per API_CONTRACTS §9) — never hidden chain-of-thought. ``trade_offs`` explains why an
    alternative ranked below the recommendation (AGENT_SPEC §11). Every figure is mock in A3.
    """

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
    reasons: list[str] = Field(default_factory=list)
    trade_offs: list[str] = Field(default_factory=list)
    is_recommended: bool = False
    data_source: DataSource = DataSource.mock


class PlanResponse(BaseModel):
    """Response for ``POST /api/route/plan`` (API_CONTRACTS §2).

    A3 adds one additive field, ``reasoning`` (API_CONTRACTS §9 permits additive changes): the
    concise, observable explanation of the decision (the ReasoningSummary shown at COMPLETED,
    DESIGN_SYSTEM §12.9). It never exposes hidden chain-of-thought — only structured factors.
    """

    status: AgentState
    request: Optional[TravelRequest] = Field(
        default=None, description="The normalized request the agent understood (A2)."
    )
    recommendation: Optional[Recommendation] = None
    legs: list[Leg] = Field(default_factory=list)
    alternatives: list[Recommendation] = Field(default_factory=list)
    agent_actions: list[AgentAction] = Field(default_factory=list)
    reasoning: Optional[str] = Field(
        default=None,
        description="Concise explanation of the decision / clarification (A3, additive).",
    )
