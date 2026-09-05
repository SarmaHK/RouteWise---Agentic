"""Workstream B (Transit Intelligence & ML) Integration & Golden Demo Tests.

Verifies the integration of:
1. SpatialTransitGraph + search_routes candidate generation
2. FarePredictor (XGBoost) + get_fare_estimate tool
3. DelayPredictor (LSTM) + get_delay_prediction tool
4. RouteDetailsTool (ordered Leg expansion conforming to Pydantic schema)
5. End-to-end Golden Demo (Colombo Fort -> Ella, LKR 2000 budget, heavy luggage, min walking)
6. Disruption scenario (weather/landslide delay shifting route ranking)
7. PlanResponse API contract with dynamically populated legs
"""

from __future__ import annotations

import pytest
from app.config import Settings
from app.schemas.candidate import RouteCandidate
from app.schemas.route import DataSource, PlanRequest, PlanResponse
from app.schemas.travel_request import Luggage, TravelRequest, WalkingPreference
from app.agent.decision import DecisionEngine
from app.agent.orchestrator import RouteAgent
from app.tools.base import ToolAvailability, ToolStatus
from app.tools.registry import build_tools
from models.fare.predictor import get_fare_predictor
from models.delay.predictor import get_delay_predictor
from app.services.transit.spatial_graph import get_transit_graph


@pytest.fixture
def b_settings() -> Settings:
    """Settings with Workstream B Transit Intelligence enabled."""
    return Settings(enable_transit_intelligence=True)


@pytest.fixture
def b_registry(b_settings: Settings):
    """ToolRegistry with Workstream B capabilities activated."""
    return build_tools(b_settings)


# -------------------------------------------------------------------------
# 1. Capability & Availability Tests
# -------------------------------------------------------------------------
def test_workstream_b_tools_available(b_registry):
    """Verify all Workstream B tools report available status when enabled."""
    available = b_registry.list_available()
    assert "search_routes" in available
    assert "get_fare_estimate" in available
    assert "get_delay_prediction" in available
    assert "get_route_details" in available

    assert b_registry.status("get_fare_estimate") is ToolAvailability.available
    assert b_registry.status("get_delay_prediction") is ToolAvailability.available
    assert b_registry.status("get_route_details") is ToolAvailability.available


# -------------------------------------------------------------------------
# 2. Fare Model (XGBoost) Tests
# -------------------------------------------------------------------------
def test_fare_predictor_and_tool(b_registry):
    """Verify XGBoost fare prediction outputs single non-negative float in LKR."""
    predictor = get_fare_predictor()
    fare = predictor.predict_fare("train", 270.0, transit_class="second")
    assert isinstance(fare, float)
    assert 500.0 <= fare <= 2500.0

    # Tool invocation
    res = b_registry.execute(
        "get_fare_estimate",
        {"route_id": "R1", "travel_mode": "train", "distance_km": 270.0, "transit_class": "second"},
    )
    assert res.success is True
    assert res.status is ToolStatus.ok
    assert isinstance(res.data["estimated_fare_lkr"], float)
    assert res.data["currency"] == "LKR"
    assert res.data["confidence"] > 0.8
    assert res.data["estimated_fare_lkr"] > 0


# -------------------------------------------------------------------------
# 3. Delay Model (LSTM) Tests
# -------------------------------------------------------------------------
def test_delay_predictor_and_tool(b_registry):
    """Verify LSTM delay prediction outputs non-negative float and exact category."""
    predictor = get_delay_predictor()
    pred = predictor.predict(
        route_id="R1",
        corridor="Colombo Fort to Ella",
        recent_delays=[35.0, 40.0, 42.0, 45.0, 48.0, 50.0],
        weather="heavy_rain",
        historical_mean_delay=20.0,
    )
    assert isinstance(pred.predicted_delay_minutes, float)
    assert pred.predicted_delay_minutes >= 0.0
    assert pred.delay_category in ["none", "low", "moderate", "high"]
    assert pred.predicted_delay_minutes >= 35.0
    assert pred.delay_category == "high"

    # Tool invocation
    res = b_registry.execute(
        "get_delay_prediction",
        {
            "route_id": "R1",
            "corridor": "Colombo Fort to Ella",
            "recent_delays": [5.0, 5.0, 8.0],
            "weather": "clear",
        },
    )
    assert res.success is True
    assert res.status is ToolStatus.ok
    assert isinstance(res.data["predicted_delay_minutes"], float)
    assert res.data["delay_category"] in ["none", "low", "moderate", "high"]


# -------------------------------------------------------------------------
# 4. Route Graph & RouteDetailsTool (Leg Expansion)
# -------------------------------------------------------------------------
def test_route_details_leg_expansion(b_registry):
    """Verify get_route_details expands route into valid Pydantic Leg models."""
    res = b_registry.execute("get_route_details", {"route_id": "R1"})
    assert res.success is True
    assert res.status is ToolStatus.ok
    assert "legs" in res.data
    legs = res.data["legs"]
    assert len(legs) >= 1

    first_leg = legs[0]
    # Check Leg attributes
    assert hasattr(first_leg, "origin")
    assert hasattr(first_leg, "destination")
    assert hasattr(first_leg, "mode")
    assert hasattr(first_leg, "duration_min")
    assert first_leg.origin != ""
    assert first_leg.destination != ""
    assert first_leg.duration_min is not None and first_leg.duration_min > 0


# -------------------------------------------------------------------------
# 5. Golden Demo (Colombo Fort -> Ella, LKR 2000 budget, heavy luggage)
# -------------------------------------------------------------------------
def test_golden_demo_agent_run(b_settings):
    """Verify full agent run on Golden Demo with ML transit intelligence."""
    tools = build_tools(b_settings)
    engine = DecisionEngine()
    agent = RouteAgent(tools=tools, engine=engine)

    golden_request = TravelRequest(
        origin="Colombo Fort",
        destination="Ella",
        budget=2000.0,
        luggage=Luggage.heavy,
        walking_preference=WalkingPreference.minimize,
    )

    context = agent.run(golden_request)
    assert context.recommendation is not None
    assert len(context.candidates) >= 2

    rec = context.recommendation
    # Budget compliance
    assert rec.total_fare_lkr <= 2000.0
    # Mode compliance (train or bus, minimal walking)
    assert rec.walking_km is not None and rec.walking_km <= 1.0
    assert rec.data_source in [DataSource.simulated, DataSource.mock]


# -------------------------------------------------------------------------
# 6. Disruption Scenario Test
# -------------------------------------------------------------------------
def test_disruption_impacts_delay_category(b_registry):
    """Verify simulated corridor disruption triggers high delay warning."""
    # Under heavy monsoon and recent delay spikes on the Main Line
    res = b_registry.execute(
        "get_delay_prediction",
        {
            "route_id": "R1",
            "corridor": "Colombo Fort to Ella",
            "recent_delays": [30.0, 45.0, 50.0, 55.0, 60.0, 65.0],
            "weather": "heavy_rain",
            "historical_mean_delay": 35.0,
        },
    )
    assert res.success is True
    assert res.data["delay_category"] == "high"
    assert res.data["predicted_delay_minutes"] >= 35.0


# -------------------------------------------------------------------------
# 7. PlanResponse API Serialization with Legs
# -------------------------------------------------------------------------
def test_plan_response_with_expanded_legs(b_settings):
    """Verify PlanResponse correctly embeds populated Leg schema."""
    from app.api.route import plan_route
    from app.agent.orchestrator import build_agent
    from app.schemas.route import AgentState
    from app.services.ai.extraction import get_extractor

    plan_req = PlanRequest(
        origin="Colombo Fort",
        destination="Ella",
        budget=2000.0,
        luggage="heavy",
        walking_preference="minimize",
    )

    # Invoke plan_route with b_settings, extractor, and agent
    agent = build_agent(b_settings)
    extractor = get_extractor()
    response: PlanResponse = plan_route(
        plan_req, extractor=extractor, agent=agent, settings=b_settings
    )
    assert response.status == AgentState.COMPLETED
    assert response.recommendation is not None
    assert response.recommendation.total_fare_lkr <= 2000.0
    assert len(response.legs) > 0

    # Ensure serialized dict matches Pydantic aliases ("from" and "to")
    serialized = response.model_dump(by_alias=True)
    assert "legs" in serialized
    assert len(serialized["legs"]) > 0
    assert "from" in serialized["legs"][0]
    assert "to" in serialized["legs"][0]
    assert "mode" in serialized["legs"][0]
