"""POST /api/route/plan request-UNDERSTANDING behaviour (A2), updated for A3 and A7.

A2 verified the endpoint extracts a TravelRequest and plans no route. In A3 the same endpoint now
also runs the agent and decides a route, so the happy-path assertions below reflect a COMPLETED
decision; the extraction, clarification, and error-contract guarantees are unchanged. A7 adds the
recommended route's mock leg detail to the same response — understanding itself is untouched. Runs
offline (no MODEL_STUDIO_API_KEY => deterministic mock extractor + mock candidates).
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

    # A3 decides a route: the golden request completes with an explicitly-mock recommendation.
    assert body["status"] == "COMPLETED"
    assert body["recommendation"] is not None
    assert body["recommendation"]["id"] == "R1"
    assert body["recommendation"]["data_source"] == "mock"
    # A7 (brief §9/§22): leg detail now comes from the mock get_route_details tool — simulated
    # structure for the RECOMMENDED route, never a live timetable or a real seat.
    assert [leg["id"] for leg in body["legs"]] == ["R1-L1", "R1-L2", "R1-L3"]
    assert [leg["mode"] for leg in body["legs"]] == ["walk", "tuk", "train"]
    assert all(leg["data_source"] == "mock" for leg in body["legs"])
    assert body["alternatives"]  # alternatives are returned

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


def test_plan_records_understanding_action_as_mock(client: TestClient) -> None:
    response = client.post("/api/route/plan", json={"raw_text": GOLDEN})
    body = response.json()
    actions = body["agent_actions"]
    # A3 records a full trace; the first action is still the (mock) understanding step.
    assert len(actions) >= 1
    first = actions[0]
    assert first["state"] == "UNDERSTANDING"
    assert first["data_source"] == "mock"
    assert first["label"]


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
