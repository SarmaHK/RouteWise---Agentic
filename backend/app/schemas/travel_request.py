"""Normalized travel-request schema (Workstream A, Phase A2 — Request Understanding).

This is the structured output of ``NATURAL LANGUAGE -> Qwen extraction -> Pydantic
validation``. It captures everything the agent understood about a trip WITHOUT solving the
route (A2 brief §2). Every travel-specific field is optional on purpose: the extractor must
never invent values it did not see (A2 brief §3; AGENT_SPEC §15-§16 — honesty, no
hallucination). Missing hard constraints are surfaced honestly through
``clarification_required`` / ``missing_fields`` / ``clarification_questions`` rather than
fabricated.

Field names are ``snake_case`` and enums use ``UPPER_SNAKE_CASE`` members per
docs/API_CONTRACTS.md §8.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

# Fields the agent cannot proceed to planning without (AGENT_SPEC §9 — hard constraints).
# A2 only UNDERSTANDS the request, so these drive honest clarification, not route solving.
_REQUIRED_FOR_PLANNING: tuple[str, ...] = ("origin", "destination")

# Plain-language question asked when a required field is missing (A2 brief §6).
_CLARIFICATION_PROMPTS: dict[str, str] = {
    "origin": "Where are you starting from?",
    "destination": "Where do you want to go?",
}


class Luggage(str, Enum):
    """How much the traveller is carrying (API_CONTRACTS §2; soft-to-moderate constraint)."""

    none = "none"
    light = "light"
    heavy = "heavy"


class WalkingPreference(str, Enum):
    """Willingness to walk (API_CONTRACTS §2; soft preference)."""

    minimize = "minimize"
    normal = "normal"
    ok = "ok"


class ExtractionSource(str, Enum):
    """Provenance of the extraction so the system never pretends to use real Qwen.

    ``mock`` = deterministic offline extractor (no MODEL_STUDIO_API_KEY).
    ``qwen`` = real Alibaba Cloud Model Studio extraction (A2 brief §5).
    """

    mock = "mock"
    qwen = "qwen"


class TravelRequest(BaseModel):
    """A validated, normalized understanding of one travel request (A2 output)."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    origin: Optional[str] = Field(
        default=None, description='Starting point, e.g. "Colombo Fort".'
    )
    destination: Optional[str] = Field(
        default=None, description='End point, e.g. "Ella".'
    )
    budget: Optional[float] = Field(
        default=None,
        description="Maximum total fare (a ceiling, per API_CONTRACTS §2). None = unstated.",
    )
    currency: str = Field(
        default="LKR", description="ISO-style currency for ``budget``; LKR by default."
    )
    luggage: Optional[Luggage] = Field(
        default=None, description="Luggage condition when stated."
    )
    walking_preference: Optional[WalkingPreference] = Field(
        default=None, description="Walking preference when stated."
    )
    departure_time: Optional[datetime] = Field(
        default=None, description="When the traveller wants to leave (ISO 8601)."
    )
    arrival_deadline: Optional[datetime] = Field(
        default=None, description="Must-arrive-by deadline when stated (ISO 8601)."
    )
    preferences: dict[str, Any] = Field(
        default_factory=dict,
        description="Other soft preferences/constraints preserved from the request.",
    )
    raw_text: Optional[str] = Field(
        default=None, description="The original natural-language request, if provided."
    )

    # --- Clarification state (A2 brief §6) — honest, minimal, not a chat agent ---
    clarification_required: bool = Field(
        default=False, description="True when a hard constraint is missing."
    )
    missing_fields: list[str] = Field(
        default_factory=list, description="Names of required fields that are absent."
    )
    clarification_questions: list[str] = Field(
        default_factory=list, description="Human-readable questions for missing fields."
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions the extractor recorded (AGENT_SPEC §4).",
    )
    extraction_source: Optional[ExtractionSource] = Field(
        default=None, description="Provenance of this extraction (mock | qwen)."
    )

    def refresh_clarification(self) -> "TravelRequest":
        """Recompute clarification state from the currently-present required fields.

        Returns ``self`` so it can be chained. Does NOT invent values — it only records what
        is missing and asks for it (A2 brief §6).
        """
        missing = [f for f in _REQUIRED_FOR_PLANNING if getattr(self, f) in (None, "")]
        self.missing_fields = missing
        self.clarification_questions = [
            _CLARIFICATION_PROMPTS[f] for f in missing if f in _CLARIFICATION_PROMPTS
        ]
        self.clarification_required = bool(missing)
        return self
