"""A4 agent-integration tests (brief §14, §18 "Agent integration").

Prove the A3 orchestrator now drives the A4 tool seam correctly (identify → resolve → validate →
execute → structured result → decide) **without** the A5 multi-step Qwen loop:

* the agent resolves the one available capability (``search_routes``);
* on the golden request it executes the tool and reaches a mock decision (recommendation R1), with
  the action trace carrying the additive ``availability`` / ``data_source`` fields;
* when the resolved tool is disabled, the agent degrades honestly (no recommendation, no crash);
* when the tool raises at runtime, the agent records a structured failure and still completes.
"""

from __future__ import annotations

from typing import Any

from app.agent.decision import DecisionEngine
from app.agent.orchestrator import RouteAgent, build_agent
from app.config import get_settings
from app.schemas.route import AgentState, DataSource
from app.schemas.travel_request import TravelRequest
from app.services.ai.extraction import MockTravelRequestExtractor
from app.tools.base import Tool, ToolAvailability, ToolResult, ToolStatus
from app.tools.capabilities import SearchRoutesArgs
from app.tools.registry import ToolRegistry, build_tools

GOLDEN = (
    "I am at Colombo Fort and need to reach Ella under a budget of LKR 2,000, "
    "but I have a heavy bag and don't want to walk."
)


def _golden_request() -> TravelRequest:
    return MockTravelRequestExtractor().extract(GOLDEN, {})


class _DisabledSearchTool(Tool):
    """Stands in for ``search_routes`` when the capability is turned off."""

    name = "search_routes"
    availability = ToolAvailability.disabled
    args_model = SearchRoutesArgs

    def execute(self, **kwargs: Any) -> ToolResult:  # pragma: no cover — gated before running
        return ToolResult(status=ToolStatus.ok, data=[], tool_name=self.name)


class _RaisingSearchTool(Tool):
    """Stands in for ``search_routes`` when the implementation blows up at runtime."""

    name = "search_routes"
    availability = ToolAvailability.available
    args_model = SearchRoutesArgs

    def execute(self, **kwargs: Any) -> ToolResult:
        raise RuntimeError("exploded")


# 1. The agent can resolve the one available capability through the registry.
def test_agent_resolves_available_tool() -> None:
    registry = build_tools(get_settings())
    assert registry.status("search_routes") is ToolAvailability.available
    assert registry.list_available() == ["search_routes"]
    assert registry.get("search_routes") is not None


# 2. The agent executes search_routes and reaches a mock decision, with A4 trace metadata.
def test_agent_executes_search_and_decides() -> None:
    context = build_agent(get_settings()).run(_golden_request())
    assert context.state is AgentState.COMPLETED
    assert context.recommendation is not None
    assert context.recommendation.id == "R1"
    assert len(context.candidates) == 3

    searching = context.actions[2]
    assert searching.state is AgentState.SEARCHING
    assert searching.status == "done"
    assert searching.tool_call is not None
    assert searching.tool_call.name == "search_routes"
    # Additive A4 fields on the recorded tool call (API_CONTRACTS §4).
    assert searching.tool_call.availability == "available"
    assert searching.tool_call.data_source is DataSource.mock
    assert context.data_source is DataSource.mock


# 3. When the resolved tool is disabled, the agent degrades honestly (no crash, no fabrication).
def test_agent_handles_disabled_tool() -> None:
    agent = RouteAgent(
        tools=ToolRegistry([_DisabledSearchTool()]), engine=DecisionEngine()
    )
    context = agent.run(_golden_request())
    assert context.state is AgentState.COMPLETED
    assert context.recommendation is None  # nothing was fabricated
    assert context.candidates == []
    assert context.errors  # the structured failure was recorded honestly

    searching = context.actions[2]
    assert searching.status == "error"
    assert searching.tool_call is not None
    assert searching.tool_call.availability == "disabled"


# 4. When the tool raises at runtime, the agent records a structured failure and still completes.
def test_agent_does_not_crash_on_tool_failure() -> None:
    agent = RouteAgent(
        tools=ToolRegistry([_RaisingSearchTool()]), engine=DecisionEngine()
    )
    context = agent.run(_golden_request())
    assert context.state is AgentState.COMPLETED  # the agent never crashes on a tool failure
    assert context.recommendation is None
    assert context.candidates == []
    assert context.errors

    searching = context.actions[2]
    assert searching.status == "error"
    assert searching.detail is not None
    assert "exploded" in searching.detail.lower()
