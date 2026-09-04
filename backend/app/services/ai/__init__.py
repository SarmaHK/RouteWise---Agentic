"""AI service abstraction for Qwen via Alibaba Cloud Model Studio (Workstream A).

Phase A1 goal (A1 brief §7-§8): a clean, env-configurable client so the backend CAN talk to
Qwen, with a safe mock fallback when no credentials are present. This is NOT the agent — no
orchestration, tool calling, or decision logic (those are A2+). See docs/ARCHITECTURE.md §5.

Public surface::

    get_ai_client()               -> AIClient   (cached accessor for app code)
    build_ai_client(settings)     -> AIClient   (explicit, test-friendly)
    AIClient                                    (interface)
    QwenClient, MockAIClient                    (implementations)
    AIResponse, ConnectivityResult              (result types)
"""

from app.services.ai.base import AIResponse, AIClient, ConnectivityResult
from app.services.ai.factory import build_ai_client, get_ai_client
from app.services.ai.mock_client import MockAIClient
from app.services.ai.qwen_client import QwenClient

__all__ = [
    "AIResponse",
    "AIClient",
    "ConnectivityResult",
    "MockAIClient",
    "QwenClient",
    "build_ai_client",
    "get_ai_client",
]
