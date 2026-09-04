"""Configuration tests (A1 brief §6, §14, §17 — safety).

Verify settings load with safe defaults and that the secret API key is never exposed in the
loggable view.
"""

from __future__ import annotations

import pytest

from app.config import Settings


@pytest.fixture()
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for var in ("MODEL_STUDIO_API_KEY", "ENVIRONMENT"):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def test_defaults_are_safe_without_env(clean_env) -> None:
    settings = Settings(_env_file=None)
    assert settings.environment == "development"
    assert settings.ai_enabled is False
    assert settings.model_name  # a default model id is present
    assert "http://localhost:5173" in settings.cors_origins


def test_public_view_never_exposes_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_STUDIO_API_KEY", "super-secret-value")
    settings = Settings(_env_file=None)
    view = settings.public_view()
    assert settings.ai_enabled is True
    # The secret must not appear anywhere in the loggable/serializable view.
    assert "super-secret-value" not in str(view)
    assert "model_studio_api_key" not in view


def test_cors_origins_parses_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", "http://a.dev, http://b.dev")
    settings = Settings(_env_file=None)
    assert settings.cors_origins == ["http://a.dev", "http://b.dev"]
