"""Agent tool seam (Workstream A, Phase A4).

Public surface for the capability boundary the agent uses to reach transit intelligence (B) and
execution (C). Import from here rather than the individual modules so the seam stays single and
obvious (mirrors ``app.services.ai``). Shapes/contracts: docs/API_CONTRACTS.md §6.

A4 provides the clean capability-execution contract — a structured ``ToolResult`` (success /
tool_name / data_source / data / error), Pydantic input validation, an explicit availability model,
and a safe ``ToolExecutor`` — with one mock capability (``search_routes``) and honest
``not_implemented`` stubs for the rest; nothing fabricates real transit/booking data
(A4 brief §10/§21).
"""

from app.tools.base import (
    Tool,
    ToolAvailability,
    ToolError,
    ToolErrorCode,
    ToolResult,
    ToolStatus,
    not_implemented_result,
)
from app.tools.candidates import MockCandidateProvider
from app.tools.capabilities import (
    AvailabilityTool,
    BookingTool,
    DelayPredictionTool,
    FareEstimationTool,
    MockRouteSearchTool,
    RouteDetailsTool,
    SearchRoutesArgs,
)
from app.tools.executor import ToolExecutor
from app.tools.registry import DuplicateToolError, ToolRegistry, build_tools, get_tools

__all__ = [
    "Tool",
    "ToolAvailability",
    "ToolError",
    "ToolErrorCode",
    "ToolResult",
    "ToolStatus",
    "not_implemented_result",
    "MockCandidateProvider",
    "SearchRoutesArgs",
    "MockRouteSearchTool",
    "FareEstimationTool",
    "DelayPredictionTool",
    "RouteDetailsTool",
    "AvailabilityTool",
    "BookingTool",
    "ToolExecutor",
    "DuplicateToolError",
    "ToolRegistry",
    "build_tools",
    "get_tools",
]
