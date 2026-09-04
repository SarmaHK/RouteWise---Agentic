"""A5 bounded multi-step agent-loop tests (brief §21, loop 9–15 + tool-call validation §17).

Drive :class:`~app.agent.orchestrator.RouteAgent` with scripted planners (offline, no API key) to
prove the loop is model-driven yet strictly bounded and honest:

* one tool → final, and tool → tool → final, in a model-selected order (9,10);
* a tool failure is fed back and the agent recovers to a grounded decision (11);
* a repeated identical call is suppressed, not re-executed (12 — §18);
* the iteration limit stops the loop safely with **no** fabricated recommendation (13 — §8);
* no recommendation is invented when no candidate data exists (14 — §16);
* the action trace stays ordered over canonical states only (15 — §9);
* unknown tools, invalid args, and unavailable tools are rejected through the A4 seam with a
  structured ``error_code`` — never executed as arbitrary code, never faked (§14/§17).
"""

from __future__ import annotations

from typing import Any

import pytest

from app.agent.decision import DecisionEngine
from app.agent.orchestrator import DEFAULT_MAX_AGENT_ITERATIONS, RouteAgent
from app.config import Settings, get_settings
from app.schemas.route import AgentState, DataSource, ToolCall
from app.schemas.travel_request import TravelRequest
from app.services.ai.agent import (
    AgentDecision,
    AgentPlanner,
    PlannerContext,
    ToolCallRequest,
)
from app.services.ai.extraction import MockTravelRequestExtractor
from app.tools.registry import ToolRegistry, build_tools

GOLDEN = (
    "I am at Colombo Fort and need to reach Ella under a budget of LKR 2,000, "
    "but I have a heavy bag and don't want to walk."
)
_SEARCH = {"origin": "Colombo Fort", "destination": "Ella"}


def _golden_request() -> TravelRequest:
    return MockTravelRequestExtractor().extract(GOLDEN, {})


def _tool_call(name: str, arguments: dict[str, Any] | None = None) -> AgentDecision:
    return AgentDecision(
        kind="tool_call",
        tool_calls=[ToolCallRequest(name=name, arguments=dict(arguments or {}))],
        data_source="mock",
    )


_FINAL = AgentDecision(kind="final", content="ready to decide", data_source="mock")


class _ScriptedPlanner(AgentPlanner):
    """Replays a fixed list of decisions (the last one repeats if the loop asks for more)."""

    def __init__(self, decisions: list[AgentDecision]) -> None:
        self._decisions = decisions
        self.calls = 0

    def next_decision(self, ctx: PlannerContext) -> AgentDecision:
        index = min(self.calls, len(self._decisions) - 1)
        self.calls += 1
        return self._decisions[index]


class _LoopingPlanner(AgentPlanner):
    """Always requests another *unique* call and never finalizes — for the iteration-limit test."""

    def __init__(self) -> None:
        self._n = 0

    def next_decision(self, ctx: PlannerContext) -> AgentDecision:
        self._n += 1
        return _tool_call("search_routes", {"origin": "Colombo Fort", "destination": f"Ella #{self._n}"})


def _agent(planner: AgentPlanner, *, max_iterations: int | None = None) -> RouteAgent:
    return RouteAgent(
        tools=build_tools(get_settings()),
        engine=DecisionEngine(),
        planner=planner,
        max_iterations=max_iterations,
    )


def _tool_actions(context: Any) -> list[Any]:
    return [a for a in context.actions if a.tool_call is not None]


# --------------------------------------------------------------------------- #
# Loop behaviour (brief §21, 9–15)
# --------------------------------------------------------------------------- #
# 9. One tool call, then a final decision → the canonical five-action golden path.
def test_single_tool_then_final_decision() -> None:
    agent = _agent(_ScriptedPlanner([_tool_call("search_routes", _SEARCH), _FINAL]))
    context = agent.run(_golden_request())
    assert [a.state for a in context.actions] == [
        AgentState.UNDERSTANDING,
        AgentState.PLANNING,
        AgentState.SEARCHING,
        AgentState.EVALUATING,
        AgentState.COMPLETED,
    ]
    assert len(context.candidates) == 3
    assert context.recommendation is not None  # grounded in the searched candidates
    assert context.recommendation.id == "R1"


# 10. Tool → tool → final: a model-selected sequence, with an honest NOT_IMPLEMENTED in the middle.
def test_multiple_tool_calls_then_final() -> None:
    agent = _agent(
        _ScriptedPlanner(
            [_tool_call("search_routes", _SEARCH), _tool_call("get_fare_estimate", {"route_id": "R1"}), _FINAL]
        )
    )
    context = agent.run(_golden_request())
    calls = _tool_actions(context)
    assert [a.tool_call.name for a in calls] == ["search_routes", "get_fare_estimate"]
    assert calls[0].status == "done"
    assert calls[1].status == "error"  # the fare stub is not built — never faked (§14)
    assert calls[1].tool_call.error_code == "NOT_IMPLEMENTED"
    assert context.recommendation is not None  # still decides from the search candidates
    assert context.state is AgentState.COMPLETED


# 11. A tool failure is fed back and the agent recovers to a grounded decision.
def test_recovers_after_a_tool_failure() -> None:
    agent = _agent(
        _ScriptedPlanner(
            [_tool_call("get_delay_prediction", {"route_id": "R1"}), _tool_call("search_routes", _SEARCH), _FINAL]
        )
    )
    context = agent.run(_golden_request())
    assert context.errors  # the failure was recorded honestly, not hidden
    assert context.recommendation is not None  # ...and the agent recovered
    assert context.state is AgentState.COMPLETED


# 12. A repeated identical call is suppressed (not re-executed) and the loop stops (§18).
def test_repeated_identical_call_is_suppressed() -> None:
    agent = _agent(
        _ScriptedPlanner([_tool_call("search_routes", _SEARCH), _tool_call("search_routes", _SEARCH), _FINAL])
    )
    context = agent.run(_golden_request())
    calls = _tool_actions(context)
    assert len(calls) == 2  # first executed, the identical repeat was suppressed
    assert calls[0].status == "done"
    assert calls[1].status == "error"
    assert calls[1].tool_call.error_code == "REPEATED_CALL"
    # The decision is still grounded in the first (only) execution's candidates.
    assert len(context.candidates) == 3
    assert context.recommendation is not None


# 13. The iteration limit stops the loop safely, preserving actions, fabricating nothing (§8).
def test_iteration_limit_stops_the_loop() -> None:
    agent = _agent(_LoopingPlanner(), max_iterations=3)
    context = agent.run(_golden_request())
    assert context.state is AgentState.COMPLETED  # terminates; never hangs
    assert context.recommendation is None  # §8: no fabricated recommendation at the limit
    assert any("iteration" in e.lower() for e in context.errors)
    assert len(_tool_actions(context)) == 3  # observed actions are preserved
    assert context.actions[-1].state is AgentState.COMPLETED


# 13b. With no explicit bound, the configured default is used.
def test_default_iteration_limit_is_applied() -> None:
    context = _agent(_LoopingPlanner()).run(_golden_request())
    assert len(_tool_actions(context)) == DEFAULT_MAX_AGENT_ITERATIONS
    assert context.recommendation is None


# 14. No candidate data → no recommendation is invented (§16).
def test_no_recommendation_when_no_candidates_found() -> None:
    agent = _agent(
        _ScriptedPlanner([_tool_call("search_routes", {"origin": "Nowhere", "destination": "Elsewhere"}), _FINAL])
    )
    context = agent.run(_golden_request())
    assert context.candidates == []
    assert context.recommendation is None
    assert context.state is AgentState.COMPLETED


# 15. The action trace is ordered, seq-numbered, and uses only canonical states (§9/§10).
def test_action_trace_is_ordered_and_canonical() -> None:
    agent = _agent(
        _ScriptedPlanner([_tool_call("search_routes", _SEARCH), _tool_call("get_fare_estimate", {}), _FINAL])
    )
    context = agent.run(_golden_request())
    assert [a.seq for a in context.actions] == list(range(1, len(context.actions) + 1))
    assert all(a.state in set(AgentState) for a in context.actions)  # never an invented state
    assert context.actions[0].state is AgentState.UNDERSTANDING
    assert context.actions[-1].state is AgentState.COMPLETED


# --------------------------------------------------------------------------- #
# Tool-call validation through the A4 seam (brief §17) — never arbitrary execution
# --------------------------------------------------------------------------- #
def test_unknown_tool_is_rejected_not_executed() -> None:
    agent = _agent(_ScriptedPlanner([_tool_call("launch_missiles"), _FINAL]))
    context = agent.run(_golden_request())
    call = _tool_actions(context)[0]
    assert call.status == "error"
    assert call.tool_call.error_code == "UNKNOWN_TOOL"
    assert call.tool_call.availability is None  # not a registered capability
    assert context.recommendation is None


def test_invalid_args_are_rejected_by_validation() -> None:
    # origin is empty and destination is missing → SearchRoutesArgs validation fails (§17).
    agent = _agent(_ScriptedPlanner([_tool_call("search_routes", {"origin": ""}), _FINAL]))
    context = agent.run(_golden_request())
    call = _tool_actions(context)[0]
    assert call.status == "error"
    assert call.tool_call.error_code == "INVALID_INPUT"
    assert context.candidates == []


def test_unavailable_tool_returns_not_implemented_and_never_fakes_data() -> None:
    agent = _agent(_ScriptedPlanner([_tool_call("check_availability", {"route_id": "R1"}), _FINAL]))
    context = agent.run(_golden_request())
    call = _tool_actions(context)[0]
    assert call.status == "error"
    assert call.tool_call.error_code == "NOT_IMPLEMENTED"
    assert call.tool_call.availability == "not_implemented"
    assert context.recommendation is None


# An action capability entered *after* gathering runs in EXECUTING (§9 illustrative flow), and the
# SEARCHING → EXECUTING → EVALUATING edges are exercised without inventing a state.
def test_action_tool_after_search_runs_in_executing_state() -> None:
    agent = _agent(_ScriptedPlanner([_tool_call("search_routes", _SEARCH), _tool_call("prepare_booking", {}), _FINAL]))
    context = agent.run(_golden_request())
    calls = _tool_actions(context)
    assert calls[0].state is AgentState.SEARCHING
    assert calls[1].state is AgentState.EXECUTING
    assert calls[1].tool_call.error_code == "NOT_IMPLEMENTED"  # honest stub (§14)
    assert context.actions[-2].state is AgentState.EVALUATING
    assert context.actions[-1].state is AgentState.COMPLETED


# An action capability requested straight from PLANNING must not apply an invalid transition; the
# loop falls back to the canonical SEARCHING state instead of crashing (§9).
def test_action_tool_first_falls_back_to_searching_state() -> None:
    agent = _agent(_ScriptedPlanner([_tool_call("prepare_booking", {}), _FINAL]))
    context = agent.run(_golden_request())
    call = _tool_actions(context)[0]
    assert call.state is AgentState.SEARCHING  # PLANNING → EXECUTING is not canonical
    assert call.tool_call.error_code == "NOT_IMPLEMENTED"
    assert context.state is AgentState.COMPLETED


# --------------------------------------------------------------------------- #
# Contract + configuration (brief §8/§23)
# --------------------------------------------------------------------------- #
def test_tool_call_error_code_is_additive_and_optional() -> None:
    call = ToolCall(name="search_routes")  # no error_code supplied → preserved A3/A4 contract
    assert call.error_code is None
    assert call.model_dump()["error_code"] is None


def test_max_iterations_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_AGENT_ITERATIONS", "3")
    settings = Settings(_env_file=None)
    assert settings.max_agent_iterations == 3
    assert settings.public_view()["max_agent_iterations"] == 3
    assert "model_studio_api_key" not in settings.public_view()  # still never leaks the secret


def test_agent_uses_a_mock_data_source_throughout() -> None:
    context = _agent(_ScriptedPlanner([_tool_call("search_routes", _SEARCH), _FINAL])).run(_golden_request())
    assert context.data_source is DataSource.mock
    assert all(c.data_source is DataSource.mock for c in context.candidates)
    assert context.recommendation is not None
    assert context.recommendation.data_source is DataSource.mock


def test_custom_registry_without_search_finalizes_cleanly() -> None:
    # A registry with no search_routes: the loop still finalizes (no candidates, no crash).
    from app.tools.capabilities import FareEstimationTool

    agent = RouteAgent(
        tools=ToolRegistry([FareEstimationTool()]),
        engine=DecisionEngine(),
        planner=_ScriptedPlanner([_tool_call("get_fare_estimate", {}), _FINAL]),
    )
    context = agent.run(_golden_request())
    assert context.state is AgentState.COMPLETED
    assert context.recommendation is None
    assert _tool_actions(context)[0].tool_call.error_code == "NOT_IMPLEMENTED"
