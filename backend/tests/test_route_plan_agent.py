"""A3 API tests (brief §15, tests 19–20) — POST /api/route/plan end to end, updated for A7.

Run offline through the FastAPI ``TestClient`` (no MODEL_STUDIO_API_KEY ⇒ deterministic mock
extractor + mock candidates). Test 21 ("existing A1/A2 tests continue passing") is covered by
running the complete backend suite, including the updated understanding/foundation tests.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

GOLDEN = (
    "I am at Colombo Fort and need to reach Ella under a budget of LKR 2,000, "
    "but I have a heavy bag and don't want to walk."
)


# 19. The golden demo request produces a structured, explicitly-MOCK recommendation.
def test_golden_request_produces_structured_recommendation(client: TestClient) -> None:
    response = client.post("/api/route/plan", json={"raw_text": GOLDEN})
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "COMPLETED"

    recommendation = body["recommendation"]
    assert recommendation is not None
    assert recommendation["id"] == "R1"
    assert recommendation["is_recommended"] is True
    assert recommendation["within_budget"] is True
    assert recommendation["score"] is not None
    assert recommendation["rationale"]  # a concise reason is present
    # The full concise-reasons list is observable (brief §8/§14.6), not just the headline.
    reasons = recommendation["reasons"]
    assert isinstance(reasons, list) and reasons
    assert any("budget" in reason.lower() for reason in reasons)
    assert any("heavy luggage" in reason.lower() for reason in reasons)
    # Brief §16: the recommendation must be explicitly marked as MOCK data.
    assert recommendation["data_source"] == "mock"

    # Alternatives are returned and honest (brief §13/§14.7).
    assert isinstance(body["alternatives"], list) and body["alternatives"]

    # The observable action trace follows the canonical states (brief §11).
    # A7 (brief §20): several SEARCHING tool calls now sit between PLANNING and EVALUATING, but the
    # canonical order is unchanged and no new state was invented.
    states = [a["state"] for a in body["agent_actions"]]
    assert list(dict.fromkeys(states)) == [
        "UNDERSTANDING",
        "PLANNING",
        "SEARCHING",
        "EVALUATING",
        "COMPLETED",
    ]
    tools = [a["tool_call"]["name"] for a in body["agent_actions"] if a.get("tool_call")]
    assert tools[0] == "search_routes"
    assert {"get_fare_estimate", "get_delay_prediction", "get_route_details"} <= set(tools)
    assert all(a["tool_call"]["data_source"] == "mock" for a in body["agent_actions"] if a.get("tool_call"))

    # A7 (brief §9/§22): legs now carry the recommended route's leg detail from the mock
    # get_route_details tool — structured and explicitly mock, never a fabricated live schedule.
    assert [leg["id"] for leg in body["legs"]] == ["R1-L1", "R1-L2", "R1-L3"]
    assert all(leg["data_source"] == "mock" for leg in body["legs"])
    # The legs are internally consistent with the recommended totals (§15 data consistency).
    assert sum(leg["duration_min"] for leg in body["legs"]) == recommendation["total_duration_min"]
    assert sum(leg["fare_lkr"] for leg in body["legs"]) == recommendation["total_fare_lkr"]

    # A concise explanation is surfaced, and it is honest about being mock.
    assert body["reasoning"]
    assert "MOCK" in body["reasoning"]

    # The A2 request contract is intact.
    assert body["request"]["origin"] == "Colombo Fort"
    assert body["request"]["destination"] == "Ella"
    assert body["request"]["budget"] == 2000
    assert body["request"]["luggage"] == "heavy"
    assert body["request"]["walking_preference"] == "minimize"


# 20. An incomplete request still returns clarification and stops before the decision.
def test_incomplete_request_returns_clarification(client: TestClient) -> None:
    response = client.post("/api/route/plan", json={"raw_text": "I need to reach Ella."})
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "UNDERSTANDING"
    assert body["recommendation"] is None
    assert body["legs"] == []

    request = body["request"]
    assert request["destination"] == "Ella"
    assert request["origin"] is None
    assert request["clarification_required"] is True
    assert "origin" in request["missing_fields"]
    assert request["clarification_questions"]
