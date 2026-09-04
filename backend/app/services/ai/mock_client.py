"""Safe mock AI client for local development without credentials (Workstream A, Phase A1).

Returned when ``MODEL_STUDIO_API_KEY`` is empty. It performs NO network call and clearly
labels its output as mock, so the system never pretends to have real Qwen connectivity
(A1 brief §8; docs/AGENT_SPEC.md §15 — honesty).
"""

from __future__ import annotations

from typing import Any

from app.services.ai.base import AIResponse, AIClient, ConnectivityResult

_MOCK_MODEL = "mock-qwen"


class MockAIClient(AIClient):
    """Offline stand-in for Qwen so the app runs with zero credentials."""

    def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> AIResponse:
        last_user = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        return AIResponse(
            text=(
                "[MOCK AI RESPONSE - no Model Studio credentials configured. "
                f"Echo of last user message: {last_user!r}]"
            ),
            model=_MOCK_MODEL,
            data_source="mock",
            usage={},
            raw=None,
        )

    def check_connectivity(self) -> ConnectivityResult:
        return ConnectivityResult(
            ok=False,
            mode="mock",
            model=_MOCK_MODEL,
            detail=(
                "MODEL_STUDIO_API_KEY not set - using the local mock client. "
                "Real Qwen connectivity is NOT verified."
            ),
            latency_ms=0.0,
        )
