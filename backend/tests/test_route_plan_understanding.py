"""POST /api/route/plan A2 behaviour — request UNDERSTANDING only (A2 brief §7, §9).

Verifies the endpoint extracts a TravelRequest, returns status UNDERSTANDING, plans no route,
surfaces clarification honestly, keeps the mock data source clear, and follows the error
contract. Runs offline (no MODEL_STUDIO_API_KEY => deterministic mock extractor).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

GOLDEN = (
    "I am at Colombo Fort and need to reach Ella under a budget of LKR 2,000, "
    "but I have a heavy bag and don't want to walk."
)


def test_plan_understands_natural_language(client: TestClient) -> None:
    response = client.post("/api/route/plan", json={"raw_text": GOLDEN})
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "UNDERSTANDING"
    # A2 plans NO route.
    assert body["recommendation"] is None
    assert body["legs"] == []
    assert body["alternatives"] == []

    req = body["request"]
    assert req["origin"] == "Colombo Fort"
    assert req["destination"] == "Ella"
    assert req["budget"] == 2000
    assert req["currency"] == "LKR"
    assert req["luggage"] == "heavy"
    assert req["walking_preference"] == "minimize"
    assert req["clarification_required"] is False
    # Data source is honestly labelled mock (no API key configured in tests).
    assert req["extraction_source"] == "mock"
    assert req["raw_text"] == GOLDEN


def test_plan_agent_action_is_understanding_and_mock(client: TestClient) -> None:
    response = client.post("/api/route/plan", json={"raw_text": GOLDEN})
    body = response.json()
    assert len(body["agent_actions"]) == 1
    action = body["agent_actions"][0]
    assert action["state"] == "UNDERSTANDING"
    assert action["data_source"] == "mock"
    assert action["label"]


def test_plan_flags_clarification_when_origin_missing(client: TestClient) -> None:
    response = client.post("/api/route/plan", json={"raw_text": "I need to reach Ella."})
    assert response.status_code == 200
    req = response.json()["request"]
    assert req["destination"] == "Ella"
    assert req["origin"] is None
    assert req["clarification_required"] is True
    assert "origin" in req["missing_fields"]
    assert req["clarification_questions"]  # a human-readable question is offered


def test_plan_accepts_structured_fields_without_raw_text(client: TestClient) -> None:
    response = client.post(
        "/api/route/plan",
        json={"origin": "Kandy", "destination": "Ella", "budget": 1500},
    )
    assert response.status_code == 200
    req = response.json()["request"]
    assert req["origin"] == "Kandy"
    assert req["destination"] == "Ella"
    assert req["budget"] == 1500
    assert req["clarification_required"] is False


def test_plan_rejects_empty_body_with_contract_envelope(client: TestClient) -> None:
    response = client.post("/api/route/plan", json={})
    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "ERROR"
    assert body["error"]["code"] == "validation_error"
