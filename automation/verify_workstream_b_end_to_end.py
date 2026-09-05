"""Comprehensive end-to-end verification script for Workstream B.

Tests:
1. Full stack Golden Demo run (Colombo Fort -> Ella, LKR 2000 budget, heavy bag, min walk).
2. Verification of PlanResponse: recommendation, legs, fares, delay risks, reasoning.
3. Contract schema compliance (ToolResult, Leg, RouteCandidate, timestamps with +05:30).
4. Generalization across Sri Lankan transit corridors and graceful empty handling.
5. GTFS-RT disruption injection test (delay spike shifts delay_risk to 'high').
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add backend and project root to Python path
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "backend"))
sys.path.insert(0, str(_REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.config import Settings
from app.schemas.route import AgentState, DataSource, PlanRequest, PlanResponse
from app.agent.orchestrator import build_agent
from app.services.ai.extraction import get_extractor
from app.api.route import plan_route
from app.tools.registry import build_tools
from models.delay.predictor import get_delay_predictor
from models.fare.predictor import get_fare_predictor

GOLDEN_QUERY = (
    "I am at Colombo Fort and need to reach Ella under a budget of LKR 2,000, "
    "but I have a heavy bag and don't want to walk."
)


def verify_golden_demo(settings: Settings) -> PlanResponse:
    print("\n--- 1. Testing Golden Demo End-to-End ---")
    agent = build_agent(settings)
    extractor = get_extractor()
    req = PlanRequest(raw_text=GOLDEN_QUERY)

    response = plan_route(req, extractor=extractor, agent=agent, settings=settings)

    print(f"Status: {response.status}")
    assert response.status == AgentState.COMPLETED, f"Expected COMPLETED, got {response.status}"

    rec = response.recommendation
    assert rec is not None, "Recommendation must not be null!"
    print(f"Recommended Route: {rec.id} — {rec.summary}")
    print(f"Total Fare: LKR {rec.total_fare_lkr:,.0f} (Budget: LKR 2,000)")
    assert rec.total_fare_lkr <= 2000.0, f"Fare exceeds budget: {rec.total_fare_lkr}"

    print(f"Delay Risk: {rec.delay_risk}")
    assert rec.delay_risk in ("none", "low", "moderate", "high"), f"Invalid delay risk: {rec.delay_risk}"

    print(f"Reasoning: {response.reasoning}")
    assert response.reasoning and len(response.reasoning) > 0, "Reasoning must not be empty!"

    legs = response.legs
    print(f"Number of transit legs: {len(legs)}")
    assert len(legs) > 0, "CRITICAL ERROR: PlanResponse.legs is empty!"

    allowed_modes = {"walk", "tuk", "bus", "train", "taxi", "ferry"}
    allowed_risks = {"none", "low", "moderate", "high"}

    for i, leg in enumerate(legs, start=1):
        print(f"  Leg {i}: [{leg.mode}] {leg.origin} -> {leg.destination} | {leg.duration_min} min | LKR {leg.fare_lkr} | risk: {leg.delay_risk}")
        assert leg.mode.lower() in allowed_modes, f"Invalid mode: {leg.mode}"
        if leg.delay_risk:
            assert leg.delay_risk.lower() in allowed_risks, f"Invalid risk: {leg.delay_risk}"
        if leg.departure_time:
            iso_str = leg.departure_time.isoformat()
            assert "+05:30" in iso_str or iso_str.endswith("Z"), f"Timestamp missing timezone: {iso_str}"

    print("[PASS] Golden Demo verification succeeded.")
    return response


def verify_network_generalization(tools):
    print("\n--- 2. Testing Network Generalization (Non-Hardcoded Corridors) ---")
    corridors = [
        ("Colombo Fort", "Kandy"),
        ("Galle", "Matara"),
        ("Kandy", "Ella"),
        ("Colombo Fort", "Galle"),
    ]

    for orig, dest in corridors:
        res = tools.execute("search_routes", {"origin": orig, "destination": dest})
        print(f"Route '{orig}' -> '{dest}': {len(res.data)} candidate(s) found.")
        assert res.success is True, f"Search failed for {orig} -> {dest}"
        assert len(res.data) >= 1, f"Expected candidates for {orig} -> {dest}"

    # Test unreachable / invalid corridor
    res_unreachable = tools.execute("search_routes", {"origin": "Jaffna", "destination": "NowhereLand"})
    print(f"Unreachable search result count: {len(res_unreachable.data)} (success: {res_unreachable.success})")
    assert res_unreachable.success is True
    assert len(res_unreachable.data) == 0, "Unreachable corridor must return empty list!"
    print("[PASS] Generalization & graceful degradation succeeded.")


def verify_gtfs_rt_disruption(tools):
    print("\n--- 3. Testing GTFS-RT Disruption Injection ---")
    feed_path = Path(__file__).resolve().parents[1] / "data" / "mock-realtime" / "delay_feed.json"
    assert feed_path.exists(), f"Feed file not found: {feed_path}"

    with open(feed_path, "r", encoding="utf-8") as f:
        original_feed = json.load(f)

    try:
        # Check baseline delay for R1
        res_baseline = tools.execute("get_delay_prediction", {"route_id": "R1"})
        print(f"Baseline R1 Delay: {res_baseline.data.get('delay_min_estimate')} min (Risk: {res_baseline.data.get('delay_risk')})")

        # Inject landslide disruption on Main Line train 1005 (R1)
        disrupted_feed = json.loads(json.dumps(original_feed))
        for ent in disrupted_feed.get("entity", []):
            trip_up = ent.get("trip_update", {})
            if "1005" in trip_up.get("trip", {}).get("trip_id", ""):
                trip_up["delay_minutes"] = 55.0
                trip_up["delay_risk"] = "high"

        with open(feed_path, "w", encoding="utf-8") as f:
            json.dump(disrupted_feed, f, indent=2)

        # Force delay predictor reload
        delay_predictor = get_delay_predictor()
        delay_predictor._feed_cache = delay_predictor._load_feed()

        # Re-query delay prediction for R1
        res_disrupted = tools.execute("get_delay_prediction", {"route_id": "R1"})
        disrupted_risk = res_disrupted.data.get("delay_risk") or res_disrupted.data.get("delay_category")
        disrupted_min = res_disrupted.data.get("delay_min_estimate") or res_disrupted.data.get("predicted_delay_minutes")

        print(f"Disrupted R1 Delay: {disrupted_min} min (Risk: {disrupted_risk})")
        assert disrupted_risk == "high", f"Expected 'high' delay risk under disruption, got {disrupted_risk}"
        assert disrupted_min >= 35.0, f"Expected >= 35 min delay under disruption, got {disrupted_min}"
        print("[PASS] GTFS-RT disruption injection successfully shifted delay risk upward to HIGH.")

    finally:
        # Restore original feed
        with open(feed_path, "w", encoding="utf-8") as f:
            json.dump(original_feed, f, indent=2)
        delay_predictor = get_delay_predictor()
        delay_predictor._feed_cache = delay_predictor._load_feed()
        print("Restored original delay feed.")


if __name__ == "__main__":
    b_settings = Settings(enable_transit_intelligence=True)
    tools = build_tools(b_settings)

    verify_golden_demo(b_settings)
    verify_network_generalization(tools)
    verify_gtfs_rt_disruption(tools)
    print("\nALL WORKSTREAM B VERIFICATION CHECKS PASSED.")
