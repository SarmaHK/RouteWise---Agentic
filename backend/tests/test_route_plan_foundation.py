"""Foundation POST /api/route/plan tests (A1 brief §11 — verify the pipe, not planning)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_plan_returns_foundation_stub(client: TestClient) -> None:
    payload = {"origin": "Colombo Fort", "destination": "Ella", "budget": 2000}
    response = client.post("/api/route/plan", json=payload)
    assert response.status_code == 200
    body = response.json()
    # Honest A1 stub: IDLE, no fabricated route, one explanatory (mock-labelled) action.
    assert body["status"] == "IDLE"
    assert body["recommendation"] is None
    assert body["legs"] == []
    assert body["alternatives"] == []
    assert len(body["agent_actions"]) == 1
    assert body["agent_actions"][0]["data_source"] == "mock"
    # Request is echoed back so the UI can confirm the contract end-to-end.
    assert body["request"]["origin"] == "Colombo Fort"
    assert body["request"]["destination"] == "Ella"


def test_plan_validates_required_fields(client: TestClient) -> None:
    response = client.post("/api/route/plan", json={"origin": "Colombo Fort"})
    assert response.status_code == 422
    body = response.json()
    # Errors use the structured envelope (docs/API_CONTRACTS.md §5).
    assert body["status"] == "ERROR"
    assert body["error"]["code"] == "validation_error"
