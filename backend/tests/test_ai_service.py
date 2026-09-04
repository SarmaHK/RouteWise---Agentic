"""AI service abstraction tests (A1 brief §7, §8, §14) — always run, no network."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.services.ai import MockAIClient, QwenClient
from app.services.ai.factory import build_ai_client


def test_factory_returns_mock_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MODEL_STUDIO_API_KEY", raising=False)
    client = build_ai_client(Settings(_env_file=None))
    assert isinstance(client, MockAIClient)


def test_factory_returns_qwen_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_STUDIO_API_KEY", "test-key")
    client = build_ai_client(Settings(_env_file=None))
    assert isinstance(client, QwenClient)


def test_mock_complete_is_labeled_and_offline() -> None:
    result = MockAIClient().complete([{"role": "user", "content": "hello"}])
    assert result.data_source == "mock"
    assert "MOCK" in result.text


def test_mock_connectivity_is_honest_not_verified() -> None:
    result = MockAIClient().check_connectivity()
    assert result.ok is False
    assert result.mode == "mock"
    assert "NOT verified" in result.detail
