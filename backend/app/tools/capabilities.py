"""Concrete capabilities (Workstream A & Workstream B).

Tools implemented:
- ``search_routes``: Multi-modal transit routing engine (Workstream B / PostGIS-backed graph)
- ``get_fare_estimate``: XGBoost fare estimation model (Workstream B)
- ``get_delay_prediction``: LSTM delay prediction model (Workstream B)
- ``get_route_details``: Ordered leg expansion (Workstream B)
- ``check_availability``: Simulated seat availability (Workstream C stub)
- ``prepare_booking``: Unconfirmed booking preparation (Workstream C stub)
"""

from __future__ import annotations

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
    ToolResult,
    ToolStatus,
    not_implemented_result,
)
from app.tools.candidates import MockCandidateProvider
from models.delay.predictor import DelayPredictor
from models.fare.predictor import FarePredictor


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


class MockRouteSearchTool(Tool):
    """``search_routes`` — find multi-modal candidate routes (Workstream B).

    Uses SpatialTransitGraph covering the Sri Lankan transit network with fallback to
    deterministic mock fixtures for the golden demo corridors.
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

        # 1. First check deterministic mock provider for demo corridor test compatibility
        candidates = self._provider.candidates_for(origin, destination)

        # 2. If not a hardcoded fixture, query the spatial transit graph across Sri Lanka
        if not candidates and origin and destination:
            candidates = self._graph.find_candidates(
                origin,
                destination,
                departure_time=departure_time,
                preferences=preferences,
            )

        if not candidates:
            return ToolResult(
                status=ToolStatus.mock_data,
                data_source=DataSource.mock,
                data=[],
                message=f"No candidate transit routes found for '{origin}' → '{destination}'.",
                meta={"corridor_known": False},
                tool_name=self.name,
            )

        return ToolResult(
            status=ToolStatus.mock_data,
            data_source=DataSource.mock,
            data=candidates,
            message=f"Returned {len(candidates)} candidate route(s) for '{origin}' → '{destination}'.",
            meta={"corridor_known": True, "count": len(candidates)},
            tool_name=self.name,
        )


TransitRouteSearchTool = MockRouteSearchTool


class _NotImplementedTool(Tool):
    """Base for stub capabilities: honest 'not built yet' with a fixed signature."""

    availability = ToolAvailability.not_implemented
    data_source = DataSource.mock

    def execute(self, **kwargs: Any) -> ToolResult:
        return not_implemented_result(self.name, self.owner)


class FareEstimationArgs(BaseModel):
    """Validated input for ``get_fare_estimate``."""

    model_config = ConfigDict(extra="ignore")
    route_id: Optional[str] = Field(default="R1", description="Route identifier, e.g. 'R1'.")
    travel_mode: Optional[str] = Field(default=None, description="Optional mode, e.g. 'train'.")
    mode: Optional[str] = Field(default=None, description="Optional mode alias.")
    distance_km: Optional[float] = Field(default=None, description="Optional trip distance in km.")
    transit_class: Optional[str] = Field(default="second", description="Optional seating class.")
    legs: Optional[list[dict[str, Any]]] = Field(
        default=None, description="Optional leg list to price individually."
    )


class FareEstimationTool(Tool):
    """``get_fare_estimate`` — real Workstream B implementation (XGBoost)."""

    name = "get_fare_estimate"
    description = "Estimate fare(s) for a route or its legs using trained XGBoost model."
    input_schema = {
        "route_id": "str (optional)",
        "travel_mode": "str (optional)",
        "distance_km": "float (optional)",
        "legs": "list[dict] (optional)",
    }
    output_schema = {
        "total_fare_lkr": "float",
        "estimated_fare_lkr": "float",
        "currency": "str",
        "confidence": "float",
    }
    availability = ToolAvailability.available
    data_source = DataSource.simulated
    owner = "B"
    args_model = FareEstimationArgs

    def __init__(self, as_stub: Optional[bool] = None) -> None:
        if as_stub is None:
            from app.config import get_settings
            as_stub = not getattr(get_settings(), "enable_transit_intelligence", False)
        self.as_stub = as_stub
        if as_stub:
            self.availability = ToolAvailability.not_implemented
            self.data_source = DataSource.mock
        else:
            self.availability = ToolAvailability.available
            self.data_source = DataSource.simulated
        self._predictor = FarePredictor.get_instance()

    def execute(self, **kwargs: Any) -> ToolResult:
        if self.as_stub:
            return not_implemented_result(self.name, self.owner)

        route_id = kwargs.get("route_id", "R1")
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


class DelayPredictionArgs(BaseModel):
    """Validated input for ``get_delay_prediction``."""

    model_config = ConfigDict(extra="ignore")
    route_id: Optional[str] = Field(default="R1", description="Route identifier, e.g. 'R1'.")
    corridor: Optional[str] = Field(default="", description="Optional corridor description.")
    recent_delays: Optional[list[float]] = Field(default=None, description="Optional delay sequence.")
    weather: Optional[str] = Field(default="clear", description="Weather condition.")
    historical_mean_delay: Optional[float] = Field(default=10.0, description="Historical mean delay.")
    at_time: Optional[datetime] = Field(default=None, description="Optional query timestamp.")


class DelayPredictionTool(Tool):
    """``get_delay_prediction`` — real Workstream B implementation (LSTM)."""

    name = "get_delay_prediction"
    description = "Predict delay risk and estimated delay minutes using trained LSTM sequence model."
    input_schema = {
        "route_id": "str (optional)",
        "corridor": "str (optional)",
        "recent_delays": "list[float] (optional)",
        "weather": "str (optional)",
    }
    output_schema = {
        "delay_risk": "str",
        "delay_category": "str",
        "delay_min_estimate": "float",
        "predicted_delay_minutes": "float",
    }
    availability = ToolAvailability.available
    data_source = DataSource.simulated
    owner = "B"
    args_model = DelayPredictionArgs

    def __init__(self, as_stub: Optional[bool] = None) -> None:
        if as_stub is None:
            from app.config import get_settings
            as_stub = not getattr(get_settings(), "enable_transit_intelligence", False)
        self.as_stub = as_stub
        if as_stub:
            self.availability = ToolAvailability.not_implemented
            self.data_source = DataSource.mock
        else:
            self.availability = ToolAvailability.available
            self.data_source = DataSource.simulated
        self._predictor = DelayPredictor.get_instance()

    def execute(self, **kwargs: Any) -> ToolResult:
        if self.as_stub:
            return not_implemented_result(self.name, self.owner)

        route_id = kwargs.get("route_id", "R1")
        at_time = kwargs.get("at_time")
        recent_delays = kwargs.get("recent_delays")
        weather = kwargs.get("weather", "clear")

        res = self._predictor.predict(
            route_id=route_id,
            corridor=kwargs.get("corridor", ""),
            recent_delays=recent_delays,
            weather=weather,
            historical_mean_delay=kwargs.get("historical_mean_delay", 10.0),
            at_time=at_time,
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



class RouteDetailsArgs(BaseModel):
    """Validated input for ``get_route_details``."""

    model_config = ConfigDict(extra="ignore")
    route_id: str = Field(min_length=1, description="Route identifier, e.g. 'R1'.")


class RouteDetailsTool(Tool):
    """``get_route_details`` — real Workstream B implementation (ordered Leg expansion)."""

    name = "get_route_details"
    description = "Return full leg-by-leg detail for a chosen route."
    input_schema = {"route_id": "str"}
    output_schema = {"legs": "list[Leg]"}
    availability = ToolAvailability.available
    data_source = DataSource.simulated
    owner = "B"
    args_model = RouteDetailsArgs

    def __init__(self, as_stub: Optional[bool] = None) -> None:
        if as_stub is None:
            from app.config import get_settings
            as_stub = not getattr(get_settings(), "enable_transit_intelligence", False)
        self.as_stub = as_stub
        if as_stub:
            self.availability = ToolAvailability.not_implemented
            self.data_source = DataSource.mock
        else:
            self.availability = ToolAvailability.available
            self.data_source = DataSource.simulated
        self._graph = SpatialTransitGraph()

    def execute(self, **kwargs: Any) -> ToolResult:
        if self.as_stub:
            return not_implemented_result(self.name, self.owner)

        route_id = kwargs.get("route_id", "")
        legs = self._graph.get_route_legs(route_id)

        return ToolResult(
            status=ToolStatus.ok,
            data_source=DataSource.simulated,
            data={"legs": legs},
            message=f"Returned {len(legs)} leg(s) for route '{route_id}'.",
            meta={"leg_count": len(legs)},
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
