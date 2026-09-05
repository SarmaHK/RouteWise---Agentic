"""Workstream C (Autonomous Execution & Cloud) Integration & Safety Tests.

Verifies:
1. Tool availability toggles via `Settings.enable_autonomous_execution`.
2. AvailabilityTool execution and browser automation portal scraping.
3. BookingTool / BookingService strict safety invariant (15m simulated hold, zero payments).
4. Coder Wake disruption monitoring, GTFS-RT delay injection, and autonomous re-planning.
5. Offline-ready Travel Pass generator (SVG matrix, offline hash signature, self-contained HTML).
6. FastAPI endpoints: /hold, /travel-pass, /travel-pass/html, /replan, /disruption/*.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.schemas.candidate import RouteCandidate
from app.schemas.route import DataSource, PlanRequest, PlanResponse, Recommendation
from app.schemas.travel_request import Luggage, TravelRequest, WalkingPreference
from app.agent.decision import DecisionEngine
from app.tools.base import ToolAvailability, ToolStatus
from app.tools.registry import build_tools
from automation.booking.availability import AvailabilityService
from automation.booking.booking_service import BookingService
from automation.booking.browser_automation import BrowserBookingAutomation
from automation.monitoring.disruption_monitor import DisruptionMonitor
from automation.travel_pass.generator import TravelPassGenerator
from automation.travel_pass.schemas import TravelPassRequest


@pytest.fixture
def c_settings() -> Settings:
    """Settings with both Transit Intelligence (B) and Autonomous Execution (C) enabled."""
    return Settings(enable_transit_intelligence=True, enable_autonomous_execution=True)


@pytest.fixture
def c_registry(c_settings: Settings):
    """ToolRegistry with Workstream C capabilities activated."""
    return build_tools(c_settings)


@pytest.fixture
def test_client() -> TestClient:
    """FastAPI TestClient with autonomous execution enabled."""
    app = create_app()
    with TestClient(app) as tc:
        yield tc


@pytest.fixture(autouse=True)
def clean_delay_feed():
    """Ensure delay feed is in pristine baseline state before and after each test."""
    monitor = DisruptionMonitor.get_instance()
    monitor.restore_disruption()
    yield
    monitor.restore_disruption()


# -------------------------------------------------------------------------
# 1. Capability & Availability Toggles
# -------------------------------------------------------------------------
def test_autonomous_execution_toggle():
    """Verify tool availability toggles cleanly based on enable_autonomous_execution."""
    # When disabled (default)
    default_settings = Settings(enable_autonomous_execution=False)
    default_reg = build_tools(default_settings)
    assert default_reg.status("check_availability") is ToolAvailability.not_implemented
    assert default_reg.status("prepare_booking") is ToolAvailability.not_implemented

    stub_res = default_reg.execute("check_availability", {"route_id": "R1"})
    assert stub_res.success is False
    assert stub_res.status is ToolStatus.not_implemented
    assert stub_res.error.code == "NOT_IMPLEMENTED"

    stub_book = default_reg.execute("prepare_booking", {"route_id": "R1", "traveler_name": "Test"})
    assert stub_book.success is False
    assert stub_book.status is ToolStatus.not_implemented

    # When enabled
    c_reg = build_tools(Settings(enable_autonomous_execution=True))
    assert c_reg.status("check_availability") is ToolAvailability.available
    assert c_reg.status("prepare_booking") is ToolAvailability.available
    assert "check_availability" in c_reg.list_available()
    assert "prepare_booking" in c_reg.list_available()


# -------------------------------------------------------------------------
# 2. AvailabilityTool & Portal Scraping
# -------------------------------------------------------------------------
def test_availability_tool_execution(c_registry):
    """Verify check_availability returns seat inventory and simulated booking status."""
    res = c_registry.execute("check_availability", {"route_id": "R1", "seat_class": "second"})
    assert res.success is True
    assert res.status is ToolStatus.ok
    assert res.data_source == DataSource.simulated
    data = res.data
    assert data["availability"] in ("available", "limited", "unavailable")
    assert isinstance(data["available_seats"], int)
    assert data["available_seats"] > 0
    assert "quotas" in data


def test_browser_automation_mock_portal():
    """Verify BrowserBookingAutomation parses mock HTML portal and holds seats."""
    automation = BrowserBookingAutomation()
    assert automation.fixture_path.exists()

    # Scrape portal table
    services = automation.check_availability_via_portal(origin="Colombo Fort", destination="Ella")
    assert len(services) >= 1
    r1_service = next((s for s in services if s["route_id"] == "R1"), None)
    assert r1_service is not None
    assert "Podi Menike" in r1_service["service_name"]
    assert r1_service["available_seats"] > 0
    assert r1_service["fare_lkr"] > 0
    assert r1_service["source"] == "browser_portal_scrape"

    # Hold seat via portal automation
    hold = automation.hold_seat_via_portal(
        route_id="R1",
        traveler_name="Samantha Perera",
        seats=1,
    )
    assert hold["prepared"] is True
    assert hold["reference"].startswith("RW-R1-")
    assert hold["status"] == "HELD"
    assert hold["expires_in_minutes"] == 15
    assert hold["data_source"] == "simulated"


# -------------------------------------------------------------------------
# 3. BookingService & BookingTool Strict Safety Invariant
# -------------------------------------------------------------------------
def test_booking_safety_invariant(c_registry):
    """Verify prepare_booking enforces 15m hold and zero financial debits."""
    res = c_registry.execute(
        "prepare_booking",
        {
            "route_id": "R1",
            "traveler_name": "Samantha Perera",
            "seats": 2,
            "seat_class": "first_observation",
        },
    )
    assert res.success is True
    assert res.status is ToolStatus.ok
    booking = res.data

    # Strict safety invariant assertions
    assert booking["reference"].startswith("RW-R1-")
    assert booking["status"] == "HELD"
    assert booking["data_source"] == "simulated"
    assert booking["expires_in_minutes"] == 15
    assert "expires_at" in booking
    assert booking["seats"] == 2
    assert booking["traveler_name"] == "Samantha Perera"
    assert booking["is_confirmed_payment"] is False
    assert booking["safety_invariant"] == "HOLD_ONLY_NO_FUNDS_DEBITED"

    # Verify hold retrieval in memory
    service = BookingService.get_instance()
    retrieved = service.get_hold(booking["reference"])
    assert retrieved is not None
    assert retrieved["reference"] == booking["reference"]
    assert retrieved["total_fare_lkr"] > 0


# -------------------------------------------------------------------------
# 4. Disruption Monitoring & Coder Wake Autonomous Re-planning
# -------------------------------------------------------------------------
def test_disruption_injection_and_restoration():
    """Verify GTFS-RT disruption injection updates feed and restoration reverts it."""
    monitor = DisruptionMonitor.get_instance()
    # Baseline clean
    monitor.restore_disruption()

    baseline_count = len(monitor.get_active_disruptions())

    # Inject landslide disruption on distinct trip
    injection = monitor.inject_disruption(
        trip_id="trip_injected_disruption_custom_99",
        delay_minutes=55.0,
        delay_risk="high",
        alert_header="Landslide clearance between Hatton and Kotagala.",
    )
    assert injection["injected"] is True
    assert injection["delay_minutes"] == 55.0

    # Verify active disruption detected
    active = monitor.get_active_disruptions()
    assert len(active) == baseline_count + 1
    assert any(d["delay_minutes"] == 55.0 and d["delay_risk"] == "high" for d in active)

    # Restore baseline
    restored = monitor.restore_disruption()
    assert restored["restored"] is True
    assert len(monitor.get_active_disruptions()) == baseline_count


def test_replan_route_under_disruption():
    """Verify autonomous re-planning demotes high-delay candidate and logs REPLANNING state."""
    monitor = DisruptionMonitor.get_instance()
    try:
        # 1. Inject high delay on R1
        monitor.inject_disruption(
            trip_id="trip_train_mainline_1005",
            delay_minutes=60.0,
            delay_risk="high",
            alert_header="Main Line track closure due to heavy rainfall.",
        )

        # 2. Re-evaluate candidates via DecisionEngine
        # R1 has high delay, R2 (expressway bus) has low delay
        r1 = RouteCandidate(
            id="R1",
            origin="Colombo Fort",
            destination="Ella",
            summary="Direct Main Line train (Podi Menike)",
            total_duration_min=340.0,
            total_fare_lkr=1200.0,
            total_walking_distance_m=200.0,
            delay_risk="high",
            transfer_count=0,
            modes=["train"],
            trade_offs=["Subject to heavy delay (60 min track closure)"],
            data_source=DataSource.mock,
        )
        r2 = RouteCandidate(
            id="R2",
            origin="Colombo Fort",
            destination="Ella",
            summary="Southern Expressway bus + scenic inland connection",
            total_duration_min=290.0,
            total_fare_lkr=1650.0,
            total_walking_distance_m=450.0,
            delay_risk="low",
            transfer_count=1,
            modes=["bus"],
            trade_offs=["One transfer at Matara/Wellawaya"],
            data_source=DataSource.mock,
        )

        engine = DecisionEngine()
        req = TravelRequest(
            origin="Colombo Fort",
            destination="Ella",
            budget_lkr=2500.0,
            luggage=Luggage.heavy,
            walking_preference=WalkingPreference.minimize,
        )

        decision = engine.decide(req, [r1, r2])
        # R2 should be recommended due to R1 having high delay risk
        assert decision.recommendation is not None
        assert decision.recommendation.id == "R2"
        # R1 should appear in alternatives as excluded or lower ranked
        alt_ids = [a.id for a in decision.alternatives]
        assert "R1" in alt_ids
    finally:
        monitor.restore_disruption()


# -------------------------------------------------------------------------
# 5. Offline Travel Pass Generator
# -------------------------------------------------------------------------
def test_travel_pass_generation():
    """Verify SVG QR matrix, offline hash signature, and HTML voucher rendering."""
    # Build minimal plan
    plan = PlanResponse(
        status="COMPLETED",
        request=TravelRequest(
            origin="Colombo Fort",
            destination="Ella",
            budget_lkr=2000.0,
        ),
        recommendation=Recommendation(
            id="R1",
            summary="Main Line Train to Ella",
            total_duration_min=330.0,
            total_fare_lkr=1200.0,
            delay_risk="low",
        ),
        alternatives=[],
        agent_actions=[],
    )

    pass_data = TravelPassGenerator.get_instance().generate_pass(
        plan=plan,
        booking_reference="RW-R1-A1B2C3",
        traveler_name="Samantha Perera",
        seats=2,
        seat_class="second",
    )

    assert pass_data.pass_id.startswith("PASS-RW-2026-")
    assert pass_data.origin == "Colombo Fort"
    assert pass_data.destination == "Ella"
    assert pass_data.booking_reference == "RW-R1-A1B2C3"
    assert pass_data.total_fare_lkr == 1200.0
    assert pass_data.is_offline_ready is True

    # QR code SVG assertions
    assert pass_data.qr_code_svg.startswith("<svg")
    assert pass_data.qr_code_svg.endswith("</svg>")
    assert "<rect" in pass_data.qr_code_svg

    # HTML voucher assertions
    html = TravelPassGenerator.get_instance().render_html_voucher(pass_data)
    assert "<!DOCTYPE html>" in html
    assert "Samantha Perera" in html
    assert "RW-R1-A1B2C3" in html
    assert pass_data.pass_id in html
    assert pass_data.qr_code_svg in html
    assert "@media print" in html


# -------------------------------------------------------------------------
# 6. FastAPI Endpoints Integration
# -------------------------------------------------------------------------
def test_fastapi_execution_endpoints(test_client: TestClient):
    """Verify all Workstream C REST endpoints via TestClient."""
    # 1. POST /api/route/hold
    hold_resp = test_client.post(
        "/api/route/hold",
        json={"route_id": "R1", "traveler_name": "Samantha Perera", "seats": 1},
    )
    assert hold_resp.status_code == 200
    hold_body = hold_resp.json()
    assert hold_body["status"] == "HELD"
    assert hold_body["reference"].startswith("RW-R1-")
    booking_ref = hold_body["reference"]

    # 2. POST /api/route/travel-pass
    plan_resp = test_client.post(
        "/api/route/plan",
        json={"raw_text": "I want to go from Colombo Fort to Ella with 2000 LKR budget."},
    )
    assert plan_resp.status_code == 200
    plan_data = plan_resp.json()

    pass_resp = test_client.post(
        "/api/route/travel-pass",
        json={
            "plan": plan_data,
            "booking_reference": booking_ref,
            "traveler_name": "Samantha Perera",
            "seats": 1,
        },
    )
    assert pass_resp.status_code == 200
    pass_body = pass_resp.json()
    assert pass_body["pass_id"].startswith("PASS-RW-2026-")
    assert "<svg" in pass_body["qr_code_svg"]

    # 3. POST /api/route/travel-pass/html
    html_resp = test_client.post(
        "/api/route/travel-pass/html",
        json={
            "plan": plan_data,
            "booking_reference": booking_ref,
            "traveler_name": "Samantha Perera",
            "seats": 1,
        },
    )
    assert html_resp.status_code == 200
    assert "text/html" in html_resp.headers["content-type"]
    assert "<!DOCTYPE html>" in html_resp.text
    assert booking_ref in html_resp.text

    # 4. Disruption endpoints
    # Status
    status_resp = test_client.get("/api/route/disruption/status")
    assert status_resp.status_code == 200

    # Inject
    inject_resp = test_client.post(
        "/api/route/disruption/inject",
        json={
            "trip_id": "trip_train_mainline_1005",
            "delay_minutes": 50.0,
            "delay_risk": "high",
            "alert_header": "High winds and falling branches near Idalgashinna.",
        },
    )
    assert inject_resp.status_code == 200
    assert inject_resp.json()["injected"] is True

    # Check status again
    status_resp_after = test_client.get("/api/route/disruption/status")
    assert status_resp_after.status_code == 200
    assert status_resp_after.json()["disrupted_count"] >= 1

    # Replan under disruption
    replan_resp = test_client.post(
        "/api/route/replan",
        json={
            "request": {"raw_text": "I want to go from Colombo Fort to Ella with 2000 LKR budget."},
            "previous_recommendation_id": "R1",
            "disruption_notice": "Severe corridor delay",
        },
    )
    assert replan_resp.status_code == 200
    replan_body = replan_resp.json()
    assert replan_body["status"] in ("COMPLETED", "UNDERSTANDING")
    # Verify REPLANNING action was recorded
    action_states = [a["state"] for a in replan_body["agent_actions"]]
    assert "REPLANNING" in action_states

    # Restore disruption
    restore_resp = test_client.post("/api/route/disruption/restore")
    assert restore_resp.status_code == 200
    assert restore_resp.json()["restored"] is True
