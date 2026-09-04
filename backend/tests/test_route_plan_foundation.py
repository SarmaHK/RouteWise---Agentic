"""POST /api/route/plan pipe regression (A1 §11), updated for the A3 agent decision."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_plan_pipe_returns_decision(client: TestClient) -> None:
    payload = {"origin": "Colombo Fort", "destination": "Ella", "budget": 2000}
    response = client.post("/api/route/plan", json=payload)
    assert response.status_code == 200
    body = response.json()
    # A3 runs the full agent: status COMPLETED, a mock recommendation, alternatives, and an
    # ordered action trace. With NO luggage/walking preferences the cheaper/faster R2 wins; the
    # golden heavy-bag + minimize-walking request instead selects R1 (see the A3 tests).
    assert body["status"] == "COMPLETED"
    assert body["recommendation"] is not None
    assert body["recommendation"]["id"] == "R2"
    assert body["recommendation"]["data_source"] == "mock"
    assert body["legs"] == []
    assert body["alternatives"]
    assert len(body["agent_actions"]) == 5
    assert body["agent_actions"][0]["data_source"] == "mock"
    # The normalized TravelRequest is returned so the UI can confirm the contract end-to-end.
    assert body["request"]["origin"] == "Colombo Fort"
    assert body["request"]["destination"] == "Ella"


def test_plan_rejects_empty_request(client: TestClient) -> None:
    # A2 accepts raw_text OR origin OR destination; a totally empty body is still invalid.
    response = client.post("/api/route/plan", json={})
    assert response.status_code == 422
    body = response.json()
    # Errors use the structured envelope (docs/API_CONTRACTS.md §5).
    assert body["status"] == "ERROR"
    assert body["error"]["code"] == "validation_error"
