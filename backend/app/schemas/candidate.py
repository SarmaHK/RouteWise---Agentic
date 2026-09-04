"""Route-candidate schema (Workstream A, Phase A3 — Agent Orchestration & Decision).

A :class:`RouteCandidate` is one *possible* journey the agent can evaluate. In A3 these come
ONLY from a small deterministic mock provider (``app.tools.candidates``); Workstream B will
later supply real candidates through the same shape with **no signature change**
(API_CONTRACTS §6, §9 — additive only).

Honesty is built into the model (AGENT_SPEC §15–§16):

* every candidate carries ``data_source`` (``mock`` in A3 — never presented as live), and
* ``availability`` defaults to ``unknown`` because A3 does **not** check seats/availability
  (that is a future Workstream C tool). The agent must never claim real availability.

Field names are ``snake_case`` per API_CONTRACTS §8.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.route import DataSource


class CandidateAvailability(str, Enum):
    """Seat/availability status of a candidate.

    A3 does not verify availability, so ``unknown`` is the honest default. The other members
    exist so Workstream C's future ``check_availability`` tool can populate them later with no
    schema change (API_CONTRACTS §6/§9).
    """

    unknown = "unknown"
    available = "available"
    limited = "limited"
    unavailable = "unavailable"


class RouteCandidate(BaseModel):
    """One candidate journey the decision engine can score (API_CONTRACTS §3 shape).

    All travel-specific numbers are optional: a candidate only carries what the (mock) source
    actually knows, so the engine never reasons over invented values (AGENT_SPEC §16).
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str = Field(description="Stable identifier for this candidate, e.g. 'R1'.")
    origin: str
    destination: str
    summary: str = Field(description="Short human-readable description of the journey.")
    modes: list[str] = Field(
        default_factory=list,
        description="Ordered transport modes, e.g. ['walk', 'tuk', 'train'].",
    )

    total_duration_min: Optional[float] = Field(
        default=None, description="Estimated door-to-door minutes (soft signal)."
    )
    total_fare_lkr: Optional[float] = Field(
        default=None, description="Estimated total fare in LKR (hard budget signal)."
    )
    transfers: Optional[int] = Field(
        default=None, description="Number of transfers/changes (soft comfort signal)."
    )
    walking_km: Optional[float] = Field(
        default=None, description="Total walking distance in km (soft signal, luggage-aware)."
    )
    delay_risk: Optional[str] = Field(
        default=None, description="none | low | moderate | high (penalized in scoring)."
    )
    delay_min_estimate: Optional[float] = Field(
        default=None, description="Estimated delay in minutes (used for the deadline check)."
    )

    availability: CandidateAvailability = Field(
        default=CandidateAvailability.unknown,
        description="Seat/availability status; 'unknown' in A3 (never claimed as real).",
    )
    notes: Optional[str] = Field(
        default=None, description="Optional provenance/mock note surfaced to the user."
    )
    data_source: DataSource = Field(
        default=DataSource.mock, description="Honesty flag; 'mock' throughout A3."
    )
