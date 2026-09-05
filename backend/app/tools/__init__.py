"""Agent tool seam (Workstream A; A4 contract, A7 mock intelligence).

Public surface for the capability boundary the agent uses to reach transit intelligence (B) and
execution (C). Import from here rather than the individual modules so the seam stays single and
obvious (mirrors ``app.services.ai``). Shapes/contracts: docs/API_CONTRACTS.md §6.

A4 provides the clean capability-execution contract — a structured ``ToolResult`` (success /
tool_name / data_source / data / error), Pydantic input validation, an explicit availability model,
and a safe ``ToolExecutor``. **A7** fills that contract with deterministic mock intelligence: four
``AVAILABLE`` data tools (``search_routes``, ``get_fare_estimate``, ``get_delay_prediction``,
``get_route_details``) reading **one** shared mock dataset (``intelligence.py``), plus honest
``not_implemented`` stubs for the two Workstream C capabilities. Nothing fabricates real
transit/booking data (A4 brief §10/§21; A7 brief §11/§18/§27).
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
    RouteIdArgs,
    SearchRoutesArgs,
)
from app.tools.executor import ToolExecutor
from app.tools.intelligence import MockRoute, MockRouteIntelligence
from app.tools.registry import DuplicateToolError, ToolRegistry, build_tools, get_tools

__all__ = [
    "Tool",
    "ToolAvailability",
    "ToolError",
    "ToolErrorCode",
    "ToolResult",
    "ToolStatus",
    "not_implemented_result",
    "MockRoute",
    "MockRouteIntelligence",
    "MockCandidateProvider",
    "SearchRoutesArgs",
    "RouteIdArgs",
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
