"""A3 agent-orchestration tests (brief §15, tests 13–18), updated for A7 mock intelligence.

Exercise :class:`~app.agent.orchestrator.RouteAgent` and the tool seam end to end (offline, no
API key). They prove the agent reaches a decision for a valid request, stops early for
clarification, records an ordered action trace, uses deterministic mock tools, reports
unavailable capabilities honestly, and never reaches a real external transit service.
"""

from __future__ import annotations

from app.agent.orchestrator import build_agent
from app.config import get_settings
from app.schemas.route import AgentState, DataSource
from app.schemas.travel_request import TravelRequest
from app.services.ai.extraction import MockTravelRequestExtractor
from app.tools.base import ToolAvailability, ToolStatus
from app.tools.registry import build_tools

GOLDEN = (
    "I am at Colombo Fort and need to reach Ella under a budget of LKR 2,000, "
    "but I have a heavy bag and don't want to walk."
)

# Capabilities that are still honest stubs after A7 (real ones belong to Workstream C).
_STUB_TOOLS = (
    "check_availability",
    "prepare_booking",
)

# A7 (brief §11): the four Workstream-A data tools are AVAILABLE, deterministic and explicitly mock.
_MOCK_TOOLS = (
    "search_routes",
    "get_fare_estimate",
    "get_delay_prediction",
    "get_route_details",
)


def _golden_request() -> TravelRequest:
    return MockTravelRequestExtractor().extract(GOLDEN, {})


# 13. A valid TravelRequest reaches a decision.
def test_valid_request_reaches_decision() -> None:
    context = build_agent(get_settings()).run(_golden_request())
    assert context.state is AgentState.COMPLETED
    assert context.recommendation is not None
    assert context.recommendation.id == "R1"
    assert context.reasoning  # an explanation is produced


# 14. A clarification-required request stops early (before any search or decision).
def test_clarification_request_stops_early() -> None:
    request = TravelRequest(destination="Ella").refresh_clarification()
    assert request.clarification_required is True
    context = build_agent(get_settings()).run(request)
    assert context.state is AgentState.UNDERSTANDING
    assert context.recommendation is None
    assert context.candidates == []  # never searched
    assert len(context.actions) == 2  # "understood" + "clarification required"


# 15. Agent actions are generated in the correct order with a recorded tool call.
# A7 (brief §20): the canonical state order is unchanged and no new state (e.g. TOOL_CALLING) was
# invented, but the trace now holds several SEARCHING tool calls instead of a single search.
def test_agent_actions_are_generated_in_order() -> None:
    context = build_agent(get_settings()).run(_golden_request())
    states = [a.state for a in context.actions]
    assert list(dict.fromkeys(states)) == [
        AgentState.UNDERSTANDING,
        AgentState.PLANNING,
        AgentState.SEARCHING,
        AgentState.EVALUATING,
        AgentState.COMPLETED,
    ]
    assert [a.seq for a in context.actions] == list(range(1, len(context.actions) + 1))
    searching = context.actions[2]
    assert searching.tool_call is not None
    assert searching.tool_call.name == "search_routes"
    # Every tool call in the multi-step trace stays in a canonical state and stays mock.
    tool_actions = [a for a in context.actions if a.tool_call is not None]
    assert len(tool_actions) > 1
    assert all(a.state is AgentState.SEARCHING for a in tool_actions)
    assert all(a.tool_call.data_source is DataSource.mock for a in tool_actions)


# 16. Mock tools work deterministically (same input ⇒ same output).
def test_mock_tools_are_deterministic() -> None:
    agent = build_agent(get_settings())
    first = agent.run(_golden_request())
    second = agent.run(_golden_request())
    assert first.recommendation.id == second.recommendation.id == "R1"
    assert first.recommendation.score == second.recommendation.score

    registry = build_tools(get_settings())
    a = registry.call("search_routes", origin="Colombo Fort", destination="Ella")
    b = registry.call("search_routes", origin="Colombo Fort", destination="Ella")
    assert [c.id for c in a.data] == [c.id for c in b.data] == ["R1", "R2", "R3"]
    assert [c.total_fare_lkr for c in a.data] == [c.total_fare_lkr for c in b.data]


# 17. Unavailable capabilities are reported honestly (not fabricated).
# A7 (brief §11): fare/delay/details became AVAILABLE *mock* tools, so the honest stubs that remain
# are the two Workstream-C capabilities. The new tools are honest the other way round — available,
# but explicitly labelled mock and never presented as live transit intelligence.
def test_unavailable_capabilities_reported_honestly() -> None:
    registry = build_tools(get_settings())
    for name in _STUB_TOOLS:
        result = registry.call(name)
        assert result.status is ToolStatus.not_implemented
        assert "not implemented" in result.message.lower()
        tool = registry.get(name)
        assert tool is not None
        assert tool.availability is ToolAvailability.not_implemented
        assert tool.owner == "C"

    for name in _MOCK_TOOLS:
        tool = registry.get(name)
        assert tool is not None
        assert tool.availability is ToolAvailability.available
        assert tool.data_source is DataSource.mock
        assert tool.owner == "B"  # the REAL implementation still belongs to Workstream B


# 18. No real external transit service is called (everything is mock; C tools are stubs).
def test_no_real_external_transit_service_is_called() -> None:
    context = build_agent(get_settings()).run(_golden_request())
    assert all(c.data_source is DataSource.mock for c in context.candidates)
    assert context.recommendation.data_source is DataSource.mock
    assert context.data_source is DataSource.mock
    # A7: every tool call the agent actually made in the multi-step trace is mock too.
    tool_calls = [a.tool_call for a in context.actions if a.tool_call is not None]
    assert tool_calls and all(call.data_source is DataSource.mock for call in tool_calls)

    registry = build_tools(get_settings())
    search = registry.call("search_routes", origin="Colombo Fort", destination="Ella")
    assert search.status is ToolStatus.mock_data
    assert search.data_source is DataSource.mock
    for name in _STUB_TOOLS:
        assert registry.call(name).status is ToolStatus.not_implemented
    # A7: the intelligence tools return deterministic mock payloads — never live data, never a
    # network call (no HTTP client exists anywhere in app/tools).
    for name in ("get_fare_estimate", "get_delay_prediction", "get_route_details"):
        intel = registry.call(name, route_id="R1")
        assert intel.status is ToolStatus.mock_data
        assert intel.data_source is DataSource.mock
        assert "mock" in intel.message.lower()
