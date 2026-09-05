"""Concrete capabilities (Workstream A; A4 seam, A7 mock intelligence).

The canonical tool names below come from API_CONTRACTS §6 / AGENT_SPEC §7 (the source of truth),
which ``app/tools/README.md`` also lists. The A4 brief's examples (transit_search, fare_estimation,
delay_prediction, seat_availability) map onto these fixed names:

========================  ====================  =========  ==========================
Tool name                 A7 availability       Owner      Brief example
========================  ====================  =========  ==========================
``search_routes``         available (mock)      B (future) transit_search
``get_fare_estimate``     available (mock)      B (future) fare_estimation
``get_delay_prediction``  available (mock)      B (future) delay_prediction
``get_route_details``     available (mock)      B (future) —
``check_availability``    not_implemented       C          seat_availability
``prepare_booking``       not_implemented       C          —
========================  ====================  =========  ==========================

**A7** turns the three B-owned *information* capabilities into deterministic mocks so the agent can
demonstrate a realistic end-to-end workflow (A7 brief §4/§11). All four data tools are
``availability=available`` with ``data_source=mock`` and all four read the **one** shared dataset in
:class:`~app.tools.intelligence.MockRouteIntelligence`, so ``search_routes``'s R1, R1's fare, R1's
delay and R1's legs are provably the same route and can never contradict each other (A7 brief §15).

The two Workstream C capabilities stay honest ``NOT_IMPLEMENTED`` stubs — the seam exists and is
callable, but nothing is fabricated (A7 brief §11/§27; AGENT_SPEC §16). B/C replace any of these
with real implementations later with **no signature change** (API_CONTRACTS §6/§9): they swap the
provider behind the same ``args_model`` / ``ToolResult`` contract, and the agent does not change.

Nothing here touches a database, GTFS, ML models, or a booking system: the fare/delay figures are
deterministic mock values, never a real prediction and never presented as live (A7 brief §4/§24).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.route import DataSource
from app.tools.base import (
    Tool,
    ToolAvailability,
    ToolErrorCode,
    ToolResult,
    ToolStatus,
    not_implemented_result,
)
from app.tools.candidates import MockCandidateProvider
from app.tools.intelligence import MockRouteIntelligence


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


class RouteIdArgs(BaseModel):
    """Validated input for the A7 route-scoped intelligence tools (fare / delay / details).

    One required, non-empty ``route_id`` — the very identifier ``search_routes`` returned on a
    candidate, which is what lets the four tools talk about *one* route (A7 brief §15/§17). An
    unknown id is deliberately **not** an input-validation problem (the payload shape is fine): the
    tool answers with an honest ``ROUTE_NOT_FOUND`` structured failure instead (A7 brief §18).
    ``extra="ignore"`` drops undeclared keys so malformed input never reaches the implementation.
    """

    model_config = ConfigDict(extra="ignore")

    route_id: str = Field(
        min_length=1,
        max_length=64,
        description="Route id from search_routes, e.g. 'R1'.",
    )


class MockRouteSearchTool(Tool):
    """``search_routes`` — return deterministic mock candidates for a corridor.

    The data is mock and labelled as such (``data_source=mock``); the tool itself is ``available``
    so it runs the full contract. Since A7 it reads the **shared** mock route truth (through
    :class:`~app.tools.candidates.MockCandidateProvider`), which is the same dataset the fare,
    delay and route-details tools read — so a candidate it returns and the intelligence later
    fetched for that candidate's id cannot disagree (A7 brief §15). Workstream B supplies real
    candidates through the same signature and ``args_model``.
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
    """Base for capabilities that are honestly *not built yet* (A7: the two Workstream C tools).

    ``availability`` stays ``not_implemented``, so the executor's availability gate returns the
    honest result without ever running ``execute`` (A4 brief §8/§21; A7 brief §11/§27). ``execute``
    is kept as a defensive fallback for a direct call and to satisfy the :class:`Tool` ABC.
    """

    availability = ToolAvailability.not_implemented
    data_source = DataSource.mock

    def execute(self, **kwargs: Any) -> ToolResult:
        return not_implemented_result(self.name, self.owner)


def _route_not_found(
    tool_name: str, route_id: Any, provider: MockRouteIntelligence
) -> ToolResult:
    """Honest structured failure for an unknown route id (A7 brief §18).

    The mock provider is asked about a route it does not hold: the answer is
    ``success=False`` + ``error.code=ROUTE_NOT_FOUND`` + ``data_source=mock``, with **no** data —
    never a fabricated route and never a random value. The known ids are listed so the agent (or a
    real model) can recover by asking about a route that actually exists.
    """
    known = provider.route_ids()
    message = (
        f"No mock route '{route_id}' — '{tool_name}' will not invent data for a route the "
        f"deterministic mock dataset does not hold (known mock routes: {', '.join(known)})."
    )
    return ToolResult.failure(
        tool_name,
        ToolErrorCode.ROUTE_NOT_FOUND,
        message,
        status=ToolStatus.error,
        data_source=DataSource.mock,
        data=None,
        details={"route_id": str(route_id), "known_route_ids": known},
    )


class FareEstimationTool(Tool):
    """``get_fare_estimate`` — deterministic **mock** fare for one known route id (A7 brief §7).

    Reads the shared mock route truth, so the fare returned for ``R1`` is the same figure the R1
    candidate carried and the same one ``get_route_details`` reports for R1's legs (A7 brief §15).
    This is *not* a fare-prediction model: no XGBoost, no live pricing, no randomness — the payload
    says ``data_source="mock"`` and carries a note saying the figure is illustrative. Workstream B
    replaces the provider behind this exact signature/``args_model`` (A7 brief §26).
    """

    name = "get_fare_estimate"
    description = "Estimate the total fare and per-leg fare breakdown for a known route id."
    input_schema = {"route_id": "str (required)"}
    output_schema = {
        "route_id": "str",
        "total_fare_lkr": "float",
        "currency": "str",
        "fare_breakdown": "list[{leg_id, mode, fare_lkr}]",
        "data_source": "str",
    }
    availability = ToolAvailability.available
    data_source = DataSource.mock
    owner = "B"
    args_model = RouteIdArgs

    def __init__(self, provider: Optional[MockRouteIntelligence] = None) -> None:
        self._provider = provider or MockRouteIntelligence()

    def execute(self, **kwargs: Any) -> ToolResult:
        route_id = kwargs.get("route_id")
        payload = self._provider.fare_estimate(route_id)
        if payload is None:
            return _route_not_found(self.name, route_id, self._provider)
        return ToolResult(
            status=ToolStatus.mock_data,
            data_source=DataSource.mock,
            data=payload,
            message=(
                f"Mock fare for {payload['route_id']}: "
                f"LKR {payload['total_fare_lkr']:,.0f} across "
                f"{len(payload['fare_breakdown'])} leg(s) — illustrative, not live pricing."
            ),
            meta={"route_id": payload["route_id"], "known_route": True},
            tool_name=self.name,
        )


class DelayPredictionTool(Tool):
    """``get_delay_prediction`` — deterministic **mock** delay for one known route id (A7 §8).

    Simulated intelligence only: no LSTM, no GTFS-RT feed, no real transit API, and no claim that a
    delay is actually happening. The risk/minutes are the same values the candidate and the route
    details carry for that route id (A7 brief §15), and the payload is labelled mock.
    """

    name = "get_delay_prediction"
    description = "Predict delay risk and estimated delay minutes for a known route id."
    input_schema = {"route_id": "str (required)"}
    output_schema = {
        "route_id": "str",
        "delay_risk": "str",
        "delay_min_estimate": "float",
        "leg_delays": "list[{leg_id, mode, delay_risk, delay_min_estimate}]",
        "data_source": "str",
    }
    availability = ToolAvailability.available
    data_source = DataSource.mock
    owner = "B"
    args_model = RouteIdArgs

    def __init__(self, provider: Optional[MockRouteIntelligence] = None) -> None:
        self._provider = provider or MockRouteIntelligence()

    def execute(self, **kwargs: Any) -> ToolResult:
        route_id = kwargs.get("route_id")
        payload = self._provider.delay_prediction(route_id)
        if payload is None:
            return _route_not_found(self.name, route_id, self._provider)
        return ToolResult(
            status=ToolStatus.mock_data,
            data_source=DataSource.mock,
            data=payload,
            message=(
                f"Mock delay for {payload['route_id']}: {payload['delay_risk']} risk, "
                f"~{payload['delay_min_estimate']:.0f} min — simulated, not a live delay."
            ),
            meta={"route_id": payload["route_id"], "known_route": True},
            tool_name=self.name,
        )


class RouteDetailsTool(Tool):
    """``get_route_details`` — deterministic **mock** leg-by-leg detail for a route id (A7 §9).

    Reuses the existing :class:`~app.schemas.route.Leg` shape rather than creating a second route
    representation, and returns the same route-level figures the candidate carries (duration,
    walking, transfers, fare context, delay context) so the agent can associate all three
    intelligence results with one route (A7 brief §9/§15/§17).
    """

    name = "get_route_details"
    description = "Return full leg-by-leg detail for a known route id."
    input_schema = {"route_id": "str (required)"}
    output_schema = {
        "route_id": "str",
        "origin": "str",
        "destination": "str",
        "legs": "list[Leg]",
        "total_duration_min": "float",
        "total_fare_lkr": "float",
        "transfers": "int",
        "walking_km": "float",
        "delay_risk": "str",
        "delay_min_estimate": "float",
        "data_source": "str",
    }
    availability = ToolAvailability.available
    data_source = DataSource.mock
    owner = "B"
    args_model = RouteIdArgs

    def __init__(self, provider: Optional[MockRouteIntelligence] = None) -> None:
        self._provider = provider or MockRouteIntelligence()

    def execute(self, **kwargs: Any) -> ToolResult:
        route_id = kwargs.get("route_id")
        payload = self._provider.route_details(route_id)
        if payload is None:
            return _route_not_found(self.name, route_id, self._provider)
        return ToolResult(
            status=ToolStatus.mock_data,
            data_source=DataSource.mock,
            data=payload,
            message=(
                f"Mock details for {payload['route_id']}: {len(payload['legs'])} leg(s), "
                f"{payload['total_duration_min']:.0f} min, {payload['transfers']} transfer(s), "
                f"{payload['walking_km']:.1f} km walking."
            ),
            meta={
                "route_id": payload["route_id"],
                "known_route": True,
                "leg_count": len(payload["legs"]),
            },
            tool_name=self.name,
        )


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
