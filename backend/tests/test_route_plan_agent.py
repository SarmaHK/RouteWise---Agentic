"""A3 API tests (brief §15, tests 19–20) — POST /api/route/plan end to end.

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
    assert [a["state"] for a in body["agent_actions"]] == [
        "UNDERSTANDING",
        "PLANNING",
        "SEARCHING",
        "EVALUATING",
        "COMPLETED",
    ]

    # A3 leaves legs empty (get_route_details is a future Workstream B tool) — no fabricated
    # leg-by-leg schedules (AGENT_SPEC §16).
    assert body["legs"] == []

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
