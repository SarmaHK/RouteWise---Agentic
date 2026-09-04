"""Agent tool seam (Workstream A, Phase A3).

Public surface for the capability boundary the agent uses to reach transit intelligence (B) and
execution (C). Import from here rather than the individual modules so the seam stays single and
obvious (mirrors ``app.services.ai``). Shapes/contracts: docs/API_CONTRACTS.md §6.

A3 provides one mock capability (``search_routes``) and honest ``not_implemented`` stubs for the
rest; nothing fabricates real transit/booking data (A3 brief §6/§17).
"""

from app.tools.base import (
    Tool,
    ToolAvailability,
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
)
from app.tools.registry import ToolRegistry, build_tools, get_tools

__all__ = [
    "Tool",
    "ToolAvailability",
    "ToolResult",
    "ToolStatus",
    "not_implemented_result",
    "MockCandidateProvider",
    "MockRouteSearchTool",
    "FareEstimationTool",
    "DelayPredictionTool",
    "RouteDetailsTool",
    "AvailabilityTool",
    "BookingTool",
    "ToolRegistry",
    "build_tools",
    "get_tools",
]
