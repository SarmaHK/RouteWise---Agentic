"""AI client factory (Workstream A, Phase A1).

Chooses the real Qwen client when credentials exist, otherwise the safe mock. Exposed both as
an explicit builder (test-friendly) and a cached accessor (for app code / FastAPI dependency).
"""

from __future__ import annotations

from functools import lru_cache

from app.config import Settings, get_settings
from app.services.ai.base import AIClient
from app.services.ai.mock_client import MockAIClient
from app.services.ai.qwen_client import QwenClient


def build_ai_client(settings: Settings) -> AIClient:
    """Return ``QwenClient`` if an API key is configured, else ``MockAIClient``."""
    if settings.ai_enabled:
        return QwenClient(settings)
    return MockAIClient()


@lru_cache
def get_ai_client() -> AIClient:
    """Cached accessor for application code (uses the cached ``Settings``)."""
    return build_ai_client(get_settings())
