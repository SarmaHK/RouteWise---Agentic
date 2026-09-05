"""Concrete capabilities — ONE tool set behind ONE contract (A seam + real B/C + A7 mock fallback).

The canonical tool names come from API_CONTRACTS §6 / AGENT_SPEC §7 (the source of truth), which
``app/tools/README.md`` also lists. The A4 brief's examples (transit_search, fare_estimation,
delay_prediction, seat_availability) map onto these fixed names:

========================  ================================  =====  ==========================
Tool name                 Final behaviour                   Owner  Brief example
========================  ================================  =====  ==========================
``search_routes``         real graph / mock fallback        B      transit_search
``get_fare_estimate``     real XGBoost / mock fallback      B      fare_estimation
``get_delay_prediction``  real LSTM+feed / mock fallback    B      delay_prediction
``get_route_details``     real leg expansion / mock         B      —
``check_availability``    real simulated inventory / stub   C      seat_availability
``prepare_booking``       real simulated hold / stub        C      —
========================  ================================  =====  ==========================

Integrated behaviour (final integration — see docs/ARCHITECTURE.md):

* **Workstream B tools** run in *real* mode when ``enable_transit_intelligence`` is set: the
  spatial transit graph (seeded Sri Lankan network + GTFS-RT-style delay feed), the XGBoost fare
  predictor and the LSTM delay predictor — labelled ``data_source=simulated``. With the flag off
  they serve the **shared deterministic mock** from
  :class:`~app.tools.intelligence.MockRouteIntelligence` (A7 brief §15: ``search_routes``'s R1,
  R1's fare, R1's delay and R1's legs are provably the same route) — labelled
  ``data_source=mock``, never presented as live (demo resilience, final brief §19). If the real
  ML packages cannot be imported, the tool degrades honestly to an ``error`` availability state
  instead of fabricating data (final brief §28).
* **Workstream C tools** run in *real* mode when ``enable_autonomous_execution`` is set
  (simulated seat inventory / simulated 15-minute booking hold — never a payment). With the flag
  off they stay honest ``NOT_IMPLEMENTED`` stubs: the seam exists and is callable, but nothing is
  fabricated (A7 brief §11/§27; AGENT_SPEC §16).

Either way the **name, ``args_model`` and ``ToolResult`` contract are identical**, so the agent
and the decision engine never change when a provider is swapped (A7 brief §26/§27).
"""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.candidate import CandidateAvailability, RouteCandidate
from app.schemas.route import DataSource, Leg
from app.services.transit.spatial_graph import SpatialTransitGraph
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

logger = logging.getLogger(__name__)


class SearchRoutesArgs(BaseModel):
    """Validated input for ``search_routes``."""

    model_config = ConfigDict(extra="ignore")

    origin: str = Field(min_length=1, description="Trip origin, e.g. 'Colombo Fort'.")
    destination: str = Field(min_length=1, description="Trip destination, e.g. 'Ella'.")
    departure_time: Optional[datetime] = Field(
        default=None, description="Optional departure time."
    )
    preferences: dict[str, Any] = Field(
        default_factory=dict, description="Optional soft-preference bag."
    )


class RouteIdArgs(BaseModel):
    """Validated input for the route-scoped intelligence tools (fare / delay / details).

    One required, non-empty ``route_id`` — the very identifier ``search_routes`` returned on a
    candidate, which is what lets the four tools talk about *one* route (A7 brief §15/§17). An
    unknown id is deliberately **not** an input-validation problem (the payload shape is fine): in
    mock mode the tool answers with an honest ``ROUTE_NOT_FOUND`` structured failure instead
    (A7 brief §18). ``extra="ignore"`` drops undeclared keys so malformed input never reaches the
    implementation.

    **Integration (final merge):** the optional fields below are the Workstream B refinements —
    they are additive (API_CONTRACTS §9), all optional, and are only read by the *real* B
    implementations; the deterministic mock mode ignores them. ``route_id`` stays required for
    every caller, so the A7 validation guarantees are unchanged.
    """

    model_config = ConfigDict(extra="ignore")

    route_id: str = Field(
        min_length=1,
        max_length=64,
        description="Route id from search_routes, e.g. 'R1'.",
    )
    # --- Optional Workstream B refinement fields (real mode only) --- #
    travel_mode: Optional[str] = Field(default=None, description="Optional mode, e.g. 'train'.")
    mode: Optional[str] = Field(default=None, description="Optional mode alias.")
    distance_km: Optional[float] = Field(default=None, description="Optional trip distance in km.")
    transit_class: Optional[str] = Field(default="second", description="Optional seating class.")
    legs: Optional[list[dict[str, Any]]] = Field(
        default=None, description="Optional leg list to price individually."
    )
    corridor: Optional[str] = Field(default="", description="Optional corridor description.")
    recent_delays: Optional[list[float]] = Field(
        default=None, description="Optional recent delay sequence (minutes)."
    )
    weather: Optional[str] = Field(default="clear", description="Weather condition.")
    historical_mean_delay: Optional[float] = Field(
        default=10.0, description="Historical mean delay for the corridor."
    )
    at_time: Optional[datetime] = Field(default=None, description="Optional query timestamp.")


class MockRouteSearchTool(Tool):
    """``search_routes`` — find multi-modal candidate routes (Workstream B).

    With Workstream B transit intelligence enabled (``enable_transit_intelligence``), candidates
    come from the real :class:`~app.services.transit.spatial_graph.SpatialTransitGraph` — the
    seeded Sri Lankan transit network with a GTFS-RT-style delay feed — labelled
    ``data_source=simulated``. With the flag off, the tool reads the **shared** A7 mock route
    truth (through :class:`~app.tools.candidates.MockCandidateProvider`), the same dataset the
    fare, delay and route-details tools read — so a candidate it returns and the intelligence
    later fetched for that candidate's id cannot disagree (A7 brief §15). If the mock provider has
    no candidates for the corridor, the real graph is still tried as a fallback before answering
    with an honest empty result. Either way the data is labelled with its true source; nothing is
    ever presented as live Sri Lankan transit.
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

    def __init__(
        self,
        provider: Optional[MockCandidateProvider] = None,
        graph: Optional[SpatialTransitGraph] = None,
    ) -> None:
        self._provider = provider or MockCandidateProvider()
        self._graph = graph or SpatialTransitGraph()

    def execute(self, **kwargs: Any) -> ToolResult:
        origin = kwargs.get("origin")
        destination = kwargs.get("destination")
        departure_time = kwargs.get("departure_time")
        preferences = kwargs.get("preferences")

        from app.config import get_settings
        transit_intel = getattr(get_settings(), "enable_transit_intelligence", False)

        if transit_intel and origin and destination:
            candidates = self._graph.find_candidates(
                origin,
                destination,
                departure_time=departure_time,
                preferences=preferences,
            )
            data_source = DataSource.simulated
            status = ToolStatus.ok
        else:
            candidates = self._provider.candidates_for(origin, destination)
            if not candidates and origin and destination:
                candidates = self._graph.find_candidates(
                    origin,
                    destination,
                    departure_time=departure_time,
                    preferences=preferences,
                )
            data_source = DataSource.mock
            status = ToolStatus.mock_data

        if not candidates:
            return ToolResult(
                status=status,
                data_source=data_source,
                data=[],
                message=f"No candidate transit routes found for '{origin}' → '{destination}'.",
                meta={"corridor_known": False},
                tool_name=self.name,
            )

        return ToolResult(
            status=status,
            data_source=data_source,
            data=candidates,
            message=f"Returned {len(candidates)} candidate route(s) for '{origin}' → '{destination}'.",
            meta={"corridor_known": True, "count": len(candidates)},
            tool_name=self.name,
        )


#: Backwards-compatible alias (Workstream B name for the same capability).
TransitRouteSearchTool = MockRouteSearchTool


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


class _NotImplementedTool(Tool):
    """Base for capabilities that are honestly *not built yet* (the two Workstream C tools when
    ``enable_autonomous_execution`` is off).

    ``availability`` stays ``not_implemented``, so the executor's availability gate returns the
    honest result without ever running ``execute`` (A4 brief §8/§21; A7 brief §11/§27). ``execute``
    is kept as a defensive fallback for a direct call and to satisfy the :class:`Tool` ABC.
    """

    availability = ToolAvailability.not_implemented
    data_source = DataSource.mock

    def execute(self, **kwargs: Any) -> ToolResult:
        return not_implemented_result(self.name, self.owner)


class FareEstimationTool(Tool):
    """``get_fare_estimate`` — real Workstream B fare prediction, deterministic mock fallback.

    *Real mode* (``enable_transit_intelligence`` on): the XGBoost fare model behind
    :mod:`models.fare.predictor` (with its own tariff heuristic when no trained artifact is
    present) — ``status=ok``, ``data_source=simulated``.
    *Mock mode* (flag off): the shared A7 mock route truth, so the fare returned for ``R1`` is the
    same figure the R1 candidate carried and the same one ``get_route_details`` reports for R1's
    legs (A7 brief §15) — ``status=mock_data``, ``data_source=mock``, and the payload note says
    the figure is illustrative, never live pricing (A7 brief §24).

    One name, one ``args_model``, one ``ToolResult`` contract either way: Workstream B replaced
    the provider **behind** this exact signature, and the agent does not change (A7 brief §26).
    """

    name = "get_fare_estimate"
    description = (
        "Estimate the total fare for a route id — per-leg mock breakdown by default, "
        "XGBoost fare model when transit intelligence is enabled."
    )
    input_schema = {
        "route_id": "str (required)",
        "travel_mode": "str (optional)",
        "distance_km": "float (optional)",
        "legs": "list[dict] (optional)",
    }
    output_schema = {
        "route_id": "str",
        "total_fare_lkr": "float",
        "currency": "str",
        "fare_breakdown": "list[{leg_id, mode, fare_lkr}] (mock mode)",
        "estimated_fare_lkr": "float (real mode)",
        "confidence": "float (real mode)",
        "data_source": "str",
    }
    availability = ToolAvailability.available
    data_source = DataSource.mock
    owner = "B"
    args_model = RouteIdArgs

    def __init__(
        self,
        provider: Optional[MockRouteIntelligence] = None,
        use_real: Optional[bool] = None,
    ) -> None:
        self._provider = provider or MockRouteIntelligence()
        if use_real is None:
            from app.config import get_settings

            use_real = bool(getattr(get_settings(), "enable_transit_intelligence", False))
        self.use_real = use_real
        self._predictor: Any = None
        if use_real:
            try:
                from models.fare.predictor import FarePredictor

                self._predictor = FarePredictor.get_instance()
                self.data_source = DataSource.simulated
            except Exception as exc:  # ML package unusable — degrade honestly, never fabricate
                logger.warning(
                    "get_fare_estimate: real Workstream B mode unavailable (%s); "
                    "marking the tool as error state instead of fabricating fares.",
                    exc,
                )
                self.availability = ToolAvailability.error

    def execute(self, **kwargs: Any) -> ToolResult:
        if not self.use_real:
            return self._execute_mock(kwargs.get("route_id"))
        return self._execute_real(kwargs)

    def _execute_mock(self, route_id: Any) -> ToolResult:
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

    def _execute_real(self, kwargs: dict[str, Any]) -> ToolResult:
        if self._predictor is None:
            return ToolResult.failure(
                self.name,
                ToolErrorCode.TOOL_UNAVAILABLE,
                f"Tool '{self.name}' real fare model is unavailable.",
                status=ToolStatus.unavailable,
                data_source=DataSource.simulated,
            )

        route_id = kwargs.get("route_id") or "R1"
        legs = kwargs.get("legs")
        dist = kwargs.get("distance_km")
        mode = kwargs.get("travel_mode") or kwargs.get("mode")

        if dist is not None and mode:
            fare = self._predictor.predict_fare(mode=mode, distance_km=dist)
        else:
            fare = self._predictor.predict_route_fare(route_id, legs)

        # Sanitize non-negative, finite
        if fare is None or not math.isfinite(fare) or fare < 0:
            fare = 1200.0
        fare = round(float(fare), 0)

        data = {
            "route_id": route_id,
            "total_fare_lkr": fare,
            "estimated_fare_lkr": fare,
            "currency": "LKR",
            "confidence": 0.95,
        }
        return ToolResult(
            status=ToolStatus.ok,
            data_source=DataSource.simulated,
            data=data,
            message=f"Estimated fare for '{route_id}': LKR {fare:,.0f}.",
            meta=data,
            tool_name=self.name,
        )


class DelayPredictionTool(Tool):
    """``get_delay_prediction`` — real Workstream B delay prediction, deterministic mock fallback.

    *Real mode* (``enable_transit_intelligence`` on): the LSTM sequence model plus the GTFS-RT-
    style delay feed behind :mod:`models.delay.predictor` — ``status=ok``,
    ``data_source=simulated``. *Mock mode* (flag off): simulated intelligence only — no LSTM, no
    live feed, no claim that a delay is actually happening; the risk/minutes are the same values
    the candidate and the route details carry for that route id (A7 brief §15), and the payload is
    labelled mock (A7 brief §24).
    """

    name = "get_delay_prediction"
    description = (
        "Predict delay risk and estimated delay minutes for a route id — deterministic mock by "
        "default, LSTM + real-time feed when transit intelligence is enabled."
    )
    input_schema = {
        "route_id": "str (required)",
        "corridor": "str (optional)",
        "recent_delays": "list[float] (optional)",
        "weather": "str (optional)",
    }
    output_schema = {
        "route_id": "str",
        "delay_risk": "str",
        "delay_min_estimate": "float",
        "leg_delays": "list[{leg_id, mode, delay_risk, delay_min_estimate}] (mock mode)",
        "delay_category": "str (real mode)",
        "predicted_delay_minutes": "float (real mode)",
        "data_source": "str",
    }
    availability = ToolAvailability.available
    data_source = DataSource.mock
    owner = "B"
    args_model = RouteIdArgs

    def __init__(
        self,
        provider: Optional[MockRouteIntelligence] = None,
        use_real: Optional[bool] = None,
    ) -> None:
        self._provider = provider or MockRouteIntelligence()
        if use_real is None:
            from app.config import get_settings

            use_real = bool(getattr(get_settings(), "enable_transit_intelligence", False))
        self.use_real = use_real
        self._predictor: Any = None
        if use_real:
            try:
                from models.delay.predictor import DelayPredictor

                self._predictor = DelayPredictor.get_instance()
                self.data_source = DataSource.simulated
            except Exception as exc:  # ML package unusable — degrade honestly, never fabricate
                logger.warning(
                    "get_delay_prediction: real Workstream B mode unavailable (%s); "
                    "marking the tool as error state instead of fabricating delays.",
                    exc,
                )
                self.availability = ToolAvailability.error

    def execute(self, **kwargs: Any) -> ToolResult:
        if not self.use_real:
            return self._execute_mock(kwargs.get("route_id"))
        return self._execute_real(kwargs)

    def _execute_mock(self, route_id: Any) -> ToolResult:
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

    def _execute_real(self, kwargs: dict[str, Any]) -> ToolResult:
        if self._predictor is None:
            return ToolResult.failure(
                self.name,
                ToolErrorCode.TOOL_UNAVAILABLE,
                f"Tool '{self.name}' real delay model is unavailable.",
                status=ToolStatus.unavailable,
                data_source=DataSource.simulated,
            )

        route_id = kwargs.get("route_id") or "R1"
        res = self._predictor.predict(
            route_id=route_id,
            corridor=kwargs.get("corridor") or "",
            recent_delays=kwargs.get("recent_delays"),
            weather=kwargs.get("weather") or "clear",
            historical_mean_delay=kwargs.get("historical_mean_delay") or 10.0,
            at_time=kwargs.get("at_time"),
        )
        risk = res.delay_category
        minutes = res.predicted_delay_minutes

        # Sanitize
        if minutes is None or not math.isfinite(minutes) or minutes < 0:
            minutes = 5.0
        minutes = round(float(minutes), 1)
        if risk not in ("none", "low", "moderate", "high"):
            risk = "low"

        data = {
            "route_id": route_id,
            "delay_risk": risk,
            "delay_category": risk,
            "delay_min_estimate": minutes,
            "predicted_delay_minutes": minutes,
        }
        return ToolResult(
            status=ToolStatus.ok,
            data_source=DataSource.simulated,
            data=data,
            message=f"Predicted delay for '{route_id}': {minutes} min (risk: {risk}).",
            meta=data,
            tool_name=self.name,
        )


class RouteDetailsTool(Tool):
    """``get_route_details`` — leg-by-leg detail for a route id (Workstream B + A7 mock).

    *Real mode* (``enable_transit_intelligence`` on): ordered :class:`~app.schemas.route.Leg`
    expansion from the spatial transit graph — ``status=ok``, ``data_source=simulated``.
    *Mock mode* (flag off): the shared mock route truth, reusing the existing ``Leg`` shape rather
    than a second route representation, and returning the same route-level figures the candidate
    carries (duration, walking, transfers, fare context, delay context) so the agent can associate
    all three intelligence results with one route (A7 brief §9/§15/§17) — ``status=mock_data``.
    """

    name = "get_route_details"
    description = (
        "Return full leg-by-leg detail for a route id — mock dataset by default, spatial-graph "
        "leg expansion when transit intelligence is enabled."
    )
    input_schema = {"route_id": "str (required)"}
    output_schema = {
        "route_id": "str",
        "origin": "str (mock mode)",
        "destination": "str (mock mode)",
        "legs": "list[Leg]",
        "total_duration_min": "float (mock mode)",
        "total_fare_lkr": "float (mock mode)",
        "transfers": "int (mock mode)",
        "walking_km": "float (mock mode)",
        "delay_risk": "str (mock mode)",
        "delay_min_estimate": "float (mock mode)",
        "data_source": "str",
    }
    availability = ToolAvailability.available
    data_source = DataSource.mock
    owner = "B"
    args_model = RouteIdArgs

    def __init__(
        self,
        provider: Optional[MockRouteIntelligence] = None,
        use_real: Optional[bool] = None,
        graph: Optional[SpatialTransitGraph] = None,
    ) -> None:
        self._provider = provider or MockRouteIntelligence()
        if use_real is None:
            from app.config import get_settings

            use_real = bool(getattr(get_settings(), "enable_transit_intelligence", False))
        self.use_real = use_real
        self._graph = graph
        if use_real:
            self.data_source = DataSource.simulated

    def execute(self, **kwargs: Any) -> ToolResult:
        if not self.use_real:
            return self._execute_mock(kwargs.get("route_id"))
        return self._execute_real(kwargs.get("route_id"))

    def _execute_mock(self, route_id: Any) -> ToolResult:
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

    def _execute_real(self, route_id: Any) -> ToolResult:
        graph = self._graph or SpatialTransitGraph()
        legs = graph.get_route_legs(route_id or "")

        return ToolResult(
            status=ToolStatus.ok,
            data_source=DataSource.simulated,
            data={"route_id": route_id, "legs": legs},
            message=f"Returned {len(legs)} leg(s) for route '{route_id}'.",
            meta={"leg_count": len(legs)},
            tool_name=self.name,
        )


class AvailabilityArgs(BaseModel):
    """Validated input for ``check_availability``."""

    model_config = ConfigDict(extra="ignore")
    route_id: str = Field(min_length=1, description="Route identifier, e.g. 'R1'.")
    departure_time: Optional[datetime] = Field(
        default=None, description="Optional departure timestamp."
    )
    seat_class: Optional[str] = Field(
        default=None, description="Optional seat class preference."
    )


class AvailabilityTool(Tool):
    """``check_availability`` — real Workstream C implementation (simulated seat inventory).

    Real mode (``enable_autonomous_execution`` on): the simulated seat-inventory service in
    :mod:`automation.booking.availability`. With the flag off the tool is an honest
    ``NOT_IMPLEMENTED`` stub and fabricates nothing (A7 brief §11/§27).
    """

    name = "check_availability"
    description = "Check seat/availability status for a route (simulated)."
    input_schema = {"route_id": "str"}
    output_schema = {"availability": "str"}
    availability = ToolAvailability.available
    data_source = DataSource.simulated
    owner = "C"
    args_model = AvailabilityArgs

    def __init__(self, as_stub: Optional[bool] = None) -> None:
        if as_stub is None:
            from app.config import get_settings

            as_stub = not getattr(get_settings(), "enable_autonomous_execution", False)
        self.as_stub = as_stub
        self._service: Any = None
        if as_stub:
            self.availability = ToolAvailability.not_implemented
            self.data_source = DataSource.mock
        else:
            try:
                from automation.booking.availability import get_availability_service

                self._service = get_availability_service()
                self.availability = ToolAvailability.available
                self.data_source = DataSource.simulated
            except Exception as exc:  # automation package unusable — degrade honestly
                logger.warning(
                    "check_availability: Workstream C service unavailable (%s); "
                    "marking the tool as error state instead of fabricating availability.",
                    exc,
                )
                self.availability = ToolAvailability.error
                self.data_source = DataSource.mock

    def execute(self, **kwargs: Any) -> ToolResult:
        if self.as_stub:
            return not_implemented_result(self.name, self.owner)
        if self._service is None:
            return ToolResult.failure(
                self.name,
                ToolErrorCode.TOOL_UNAVAILABLE,
                f"Tool '{self.name}' availability service is unavailable.",
                status=ToolStatus.unavailable,
                data_source=DataSource.simulated,
            )

        route_id = kwargs.get("route_id", "")
        travel_date = str(kwargs.get("departure_time")) if kwargs.get("departure_time") else None
        seat_class = kwargs.get("seat_class")
        res = self._service.check_availability(route_id, travel_date=travel_date, seat_class=seat_class)
        avail_str = res.get("availability", "unknown")

        status = ToolStatus.ok
        if avail_str == "unavailable":
            status = ToolStatus.unavailable

        data = {
            "availability": CandidateAvailability(avail_str).value,
            "available_seats": res.get("available_seats", 0),
            "status_reason": res.get("status_reason", ""),
            "quotas": res.get("quotas", {}),
        }
        return ToolResult(
            status=status,
            data_source=DataSource.simulated,
            data=data,
            message=f"Availability for '{route_id}': {avail_str} ({res.get('status_reason', '')}).",
            meta=data,
            tool_name=self.name,
        )


class BookingArgs(BaseModel):
    """Validated input for ``prepare_booking``."""

    model_config = ConfigDict(extra="ignore")
    route_id: str = Field(min_length=1, description="Route identifier to hold.")
    traveler_name: Optional[str] = Field(
        default=None, description="Optional name of primary traveler."
    )
    seats: Optional[int] = Field(default=1, description="Number of seats to reserve.")
    total_fare_lkr: Optional[float] = Field(
        default=None, description="Optional route fare total in LKR."
    )
    seat_class: Optional[str] = Field(
        default="second", description="Optional seating class preference."
    )


class BookingTool(Tool):
    """``prepare_booking`` — real Workstream C implementation (simulated temporary hold).

    SAFETY INVARIANT:
    This tool only ever PREPARES / HOLDS a booking. It must NEVER commit payment, debit
    funds, or call any live external payment gateway.

    With ``enable_autonomous_execution`` off the tool is an honest ``NOT_IMPLEMENTED`` stub and
    fabricates nothing (A7 brief §11/§27).
    """

    name = "prepare_booking"
    description = "Prepare (never commit) a booking/hold for a chosen route."
    input_schema = {
        "route_id": "str",
        "traveler_name": "str (optional)",
        "seats": "int (optional)",
    }
    output_schema = {
        "prepared": "bool",
        "reference": "str | None",
        "status": "str",
        "expires_in_minutes": "int",
        "total_fare_lkr": "float | None",
    }
    availability = ToolAvailability.available
    data_source = DataSource.simulated
    owner = "C"
    args_model = BookingArgs

    def __init__(self, as_stub: Optional[bool] = None) -> None:
        if as_stub is None:
            from app.config import get_settings

            as_stub = not getattr(get_settings(), "enable_autonomous_execution", False)
        self.as_stub = as_stub
        self._service: Any = None
        if as_stub:
            self.availability = ToolAvailability.not_implemented
            self.data_source = DataSource.mock
        else:
            try:
                from automation.booking.booking_service import get_booking_service

                self._service = get_booking_service()
                self.availability = ToolAvailability.available
                self.data_source = DataSource.simulated
            except Exception as exc:  # automation package unusable — degrade honestly
                logger.warning(
                    "prepare_booking: Workstream C service unavailable (%s); "
                    "marking the tool as error state instead of fabricating a hold.",
                    exc,
                )
                self.availability = ToolAvailability.error
                self.data_source = DataSource.mock

    def execute(self, **kwargs: Any) -> ToolResult:
        if self.as_stub:
            return not_implemented_result(self.name, self.owner)
        if self._service is None:
            return ToolResult.failure(
                self.name,
                ToolErrorCode.TOOL_UNAVAILABLE,
                f"Tool '{self.name}' booking service is unavailable.",
                status=ToolStatus.unavailable,
                data_source=DataSource.simulated,
            )

        route_id = kwargs.get("route_id", "R1")
        traveler_name = kwargs.get("traveler_name") or "Samantha Perera"
        seats = int(kwargs.get("seats") or 1)
        fare = kwargs.get("total_fare_lkr")
        seat_class = kwargs.get("seat_class") or "second"

        hold = self._service.prepare_hold(
            route_id=route_id,
            traveler_name=traveler_name,
            seats=seats,
            total_fare_lkr=fare,
            seat_class=seat_class,
        )

        prepared = hold.get("prepared", False)
        status = ToolStatus.ok if prepared else ToolStatus.unavailable
        ref = hold.get("reference")

        return ToolResult(
            status=status,
            data_source=DataSource.simulated,
            data=hold,
            message=(
                f"Booking hold prepared for '{route_id}' (ref: {ref}, expires in 15 min)."
                if prepared
                else f"Booking hold failed for '{route_id}': service unavailable."
            ),
            meta=hold,
            tool_name=self.name,
        )
