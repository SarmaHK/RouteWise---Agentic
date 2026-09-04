"""Concrete A3 capabilities (Workstream A, Phase A3) — one mock, the rest honest stubs.

The canonical tool names below come from API_CONTRACTS §6 / AGENT_SPEC §7 (the source of truth),
which ``app/tools/README.md`` also lists. The A3 brief's examples (transit_search,
fare_estimation, delay_prediction, seat_availability) map onto these fixed names:

========================  ====================  =========  ==========================
Tool name                 A3 status             Owner      Brief example
========================  ====================  =========  ==========================
``search_routes``         mock data             B (future) transit_search
``get_fare_estimate``     not implemented       B          fare_estimation
``get_delay_prediction``  not implemented       B          delay_prediction
``get_route_details``     not implemented       B          —
``check_availability``    not implemented       C          seat_availability
``prepare_booking``       not implemented       C          —
========================  ====================  =========  ==========================

Only ``search_routes`` returns data in A3, and that data is explicitly mock (from
:class:`~app.tools.candidates.MockCandidateProvider`). Every other capability returns an honest
``not_implemented`` result — the seam exists and is callable, but nothing is fabricated
(A3 brief §6/§17; AGENT_SPEC §16). B/C replace these with real implementations later with no
signature change (API_CONTRACTS §6/§9).
"""

from __future__ import annotations

from typing import Any, Optional

from app.schemas.route import DataSource
from app.tools.base import (
    Tool,
    ToolAvailability,
    ToolResult,
    ToolStatus,
    not_implemented_result,
)
from app.tools.candidates import MockCandidateProvider


class MockRouteSearchTool(Tool):
    """``search_routes`` — return deterministic mock candidates for a corridor.

    This is the one capability that produces data in A3. The data is mock and labelled as such;
    Workstream B later supplies real candidates through the same signature.
    """

    name = "search_routes"
    description = "Find candidate multi-modal routes between an origin and a destination."
    input_schema = {
        "origin": "str (required)",
        "destination": "str (required)",
    }
    output_schema = {"candidates": "list[RouteCandidate]"}
    availability = ToolAvailability.mock
    owner = "B"

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
                    f"No mock candidate data for '{origin}' → '{destination}' in Phase A3."
                ),
                meta={"corridor_known": False},
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
        )


class _NotImplementedTool(Tool):
    """Base for A3 stub capabilities: honest 'not built yet' with a fixed signature."""

    availability = ToolAvailability.not_implemented

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
    """``get_route_details`` — stub; leg-by-leg detail is Workstream B (A4+/A6)."""

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
