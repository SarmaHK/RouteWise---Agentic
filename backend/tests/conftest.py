"""Shared pytest fixtures for the backend foundation tests (Phase A1)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture()
def client() -> TestClient:
    """A TestClient bound to a freshly created app (no shared state between tests)."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
