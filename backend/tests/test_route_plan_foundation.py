"""POST /api/route/plan pipe regression (A1 §11), updated for A2 request understanding."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_plan_pipe_returns_understanding(client: TestClient) -> None:
    payload = {"origin": "Colombo Fort", "destination": "Ella", "budget": 2000}
    response = client.post("/api/route/plan", json=payload)
    assert response.status_code == 200
    body = response.json()
    # A2 understands the request but plans NO route: status UNDERSTANDING, empty route,
    # one explanatory action labelled with its (mock) data source.
    assert body["status"] == "UNDERSTANDING"
    assert body["recommendation"] is None
    assert body["legs"] == []
    assert body["alternatives"] == []
    assert len(body["agent_actions"]) == 1
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
