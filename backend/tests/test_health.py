"""Health endpoint tests (A1 brief §12, §14)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    # The contracted field is `status`; service/phase are additive metadata.
    assert body["status"] == "ok"
    assert body["service"] == "routewise-agentic-backend"


def test_root_index_points_to_health(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["health"] == "/health"
