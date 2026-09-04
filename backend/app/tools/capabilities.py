"""Concrete A4 capabilities (Workstream A, Phase A4) — one mock, the rest honest stubs.

The canonical tool names below come from API_CONTRACTS §6 / AGENT_SPEC §7 (the source of truth),
which ``app/tools/README.md`` also lists. The A4 brief's examples (transit_search, fare_estimation,
delay_prediction, seat_availability) map onto these fixed names:

========================  ====================  =========  ==========================
Tool name                 A4 availability       Owner      Brief example
========================  ====================  =========  ==========================
``search_routes``         available (mock)      B (future) transit_search
``get_fare_estimate``     not_implemented       B          fare_estimation
``get_delay_prediction``  not_implemented       B          delay_prediction
``get_route_details``     not_implemented       B          —
``check_availability``    not_implemented       C          seat_availability
``prepare_booking``       not_implemented       C          —
========================  ====================  =========  ==========================

Only ``search_routes`` returns data in A4 — ``availability=available`` with ``data_source=mock``
(from :class:`~app.tools.candidates.MockCandidateProvider`), so it exercises the full clean tool
contract (validate → execute → structured result). Every other capability returns an honest
``NOT_IMPLEMENTED`` result — the seam exists and is callable, but nothing is fabricated
(A4 brief §10/§21; AGENT_SPEC §16). B/C replace these with real implementations later with **no
signature change** (API_CONTRACTS §6/§9): they flip ``availability`` to ``available`` and implement
``execute`` behind the same ``args_model`` / ``ToolResult`` contract.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.route import DataSource
from app.tools.base import (
    Tool,
    ToolAvailability,
    ToolResult,
    ToolStatus,
    not_implemented_result,
)
from app.tools.candidates import MockCandidateProvider


class SearchRoutesArgs(BaseModel):
    """Validated input for ``search_routes`` (A4 brief §6; signature per API_CONTRACTS §6).

    ``origin``/``destination`` are required and non-empty; ``departure_time``/``preferences`` are
    optional and forward-compatible (the mock provider ignores them, a real B provider may not).
    ``extra="ignore"`` drops undeclared keys so malformed input never reaches the implementation.
    """

    model_config = ConfigDict(extra="ignore")

    origin: str = Field(min_length=1, description="Trip origin, e.g. 'Colombo Fort'.")
    destination: str = Field(min_length=1, description="Trip destination, e.g. 'Ella'.")
    departure_time: Optional[datetime] = Field(
        default=None, description="Optional departure time (forward-compatible; unused by mock)."
    )
    preferences: dict[str, Any] = Field(
        default_factory=dict, description="Optional soft-preference bag (forward-compatible)."
    )


class MockRouteSearchTool(Tool):
    """``search_routes`` — return deterministic mock candidates for a corridor.

    This is the one capability that produces data in A4. The data is mock and labelled as such
    (``data_source=mock``); the tool itself is ``available`` so it runs the full contract. Workstream
    B later supplies real candidates through the same signature and ``args_model``.
    """

    name = "search_routes"
    description = "Find candidate multi-modal routes between an origin and a destination."
    input_schema = {
        "origin": "str (required)",
        "destination": "str (required)",
        "departure_time": "datetime (optional)",
        "preferences": "dict (optional)",
    }
    output_schema = {"candidates": "list[RouteCandidate]"}
    availability = ToolAvailability.available
    data_source = DataSource.mock
    owner = "B"
    args_model = SearchRoutesArgs

    def __init__(self, provider: Optional[MockCandidateProvider] = None) -> None:
        self._provider = provider or MockCandidateProvider()

    def execute(self, **kwargs: Any) -> ToolResult:
        origin = kwargs.get("origin")
        destination = kwargs.get("destination")
        candidates = self._provider.candidates_for(origin, destination)
        if not candidates:
            return ToolResult(
                status=ToolStatus.mock_data,
                data_source=DataSource.mock,
                data=[],
                message=(
                    f"No mock candidate data for '{origin}' → '{destination}' yet."
                ),
                meta={"corridor_known": False},
                tool_name=self.name,
            )
        return ToolResult(
            status=ToolStatus.mock_data,
            data_source=DataSource.mock,
            data=candidates,
            message=(
                f"Returned {len(candidates)} mock candidate route(s) for "
                f"'{origin}' → '{destination}'."
            ),
            meta={"corridor_known": True},
            tool_name=self.name,
        )


class _NotImplementedTool(Tool):
    """Base for A4 stub capabilities: honest 'not built yet' with a fixed signature.

    ``availability`` stays ``not_implemented``, so the executor's availability gate returns the
    honest result without ever running ``execute`` (A4 brief §8/§21). ``execute`` is kept as a
    defensive fallback for a direct call and to satisfy the :class:`Tool` ABC.
    """

    availability = ToolAvailability.not_implemented
    data_source = DataSource.mock

    def execute(self, **kwargs: Any) -> ToolResult:
        return not_implemented_result(self.name, self.owner)


class FareEstimationTool(_NotImplementedTool):
    """``get_fare_estimate`` — stub; real implementation is Workstream B (XGBoost)."""

    name = "get_fare_estimate"
    description = "Estimate fare(s) for a route or its legs."
    input_schema = {"route_id": "str", "legs": "list[dict] (optional)"}
    output_schema = {"total_fare_lkr": "float", "currency": "str"}
    owner = "B"


class DelayPredictionTool(_NotImplementedTool):
    """``get_delay_prediction`` — stub; real implementation is Workstream B (LSTM)."""

    name = "get_delay_prediction"
    description = "Predict delay risk and estimated delay minutes for a route."
    input_schema = {"route_id": "str"}
    output_schema = {"delay_risk": "str", "delay_min_estimate": "float"}
    owner = "B"


class RouteDetailsTool(_NotImplementedTool):
    """``get_route_details`` — stub; leg-by-leg detail is Workstream B (A6+)."""

    name = "get_route_details"
    description = "Return full leg-by-leg detail for a chosen route."
    input_schema = {"route_id": "str"}
    output_schema = {"legs": "list[Leg]"}
    owner = "B"


class AvailabilityTool(_NotImplementedTool):
    """``check_availability`` — stub; simulated availability is Workstream C."""

    name = "check_availability"
    description = "Check seat/availability status for a route (simulated)."
    input_schema = {"route_id": "str"}
    output_schema = {"availability": "str"}
    owner = "C"


class BookingTool(_NotImplementedTool):
    """``prepare_booking`` — stub; only ever *prepares* (never commits) — Workstream C."""

    name = "prepare_booking"
    description = "Prepare (never commit) a booking/hold for a chosen route."
    input_schema = {"route_id": "str"}
    output_schema = {"prepared": "bool", "reference": "str | None"}
    owner = "C"
