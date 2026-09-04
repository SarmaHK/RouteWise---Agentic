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

Phase A2 adds travel-request extraction on top of the same abstraction::

    get_extractor()               -> TravelRequestExtractor (cached accessor)
    build_extractor(settings)     -> TravelRequestExtractor (explicit, test-friendly)
    TravelRequestExtractor                       (interface)
    QwenTravelRequestExtractor, MockTravelRequestExtractor
    MalformedExtractionError                     (safe rejection of bad model output)

Phase A5 adds the Qwen tool-calling adapter + agent planner on the same abstraction (the model
decides *which* registered tool to call next; the agent loop in ``app.agent`` executes it)::

    get_planner()                 -> AgentPlanner (cached accessor)
    build_planner(settings)       -> AgentPlanner (explicit, test-friendly)
    AgentPlanner                                 (interface)
    QwenAgentPlanner, MockAgentPlanner
    AgentDecision, ToolCallRequest, PlannerContext
    build_tool_definitions                       (available tools -> model function schemas)
"""

from app.services.ai.agent import (
    AgentDecision,
    AgentPlanner,
    MockAgentPlanner,
    PlannerContext,
    QwenAgentPlanner,
    ToolCallRequest,
    build_planner,
    build_tool_definitions,
    get_planner,
)
from app.services.ai.base import AIResponse, AIClient, ConnectivityResult
from app.services.ai.extraction import (
    MalformedExtractionError,
    MockTravelRequestExtractor,
    QwenTravelRequestExtractor,
    TravelRequestExtractor,
    build_extractor,
    get_extractor,
)
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
    "MalformedExtractionError",
    "MockTravelRequestExtractor",
    "QwenTravelRequestExtractor",
    "TravelRequestExtractor",
    "build_extractor",
    "get_extractor",
    "AgentDecision",
    "AgentPlanner",
    "MockAgentPlanner",
    "PlannerContext",
    "QwenAgentPlanner",
    "ToolCallRequest",
    "build_planner",
    "build_tool_definitions",
    "get_planner",
]
