"""A7 mock-intelligence tests (brief §23, scenarios 1–31).

Prove the A7 mock intelligence environment is deterministic, honest, internally consistent, and
correctly wired into the *existing* A4 tool seam, A5 agent loop and A6 decision engine:

* **Mock provider (1–5)** — one shared source of truth: same input ⇒ same output, a known route is
  consistent across every view, an unknown route fails honestly, nothing is random, and all related
  tools agree about the same route (brief §5/§15).
* **Fare / delay / route-details tools (6–15)** — valid route, unknown route, invalid input, mock
  provenance, and a structured result that reuses the existing ``Leg``/``RouteCandidate`` vocabulary
  (brief §7/§8/§9/§18).
* **Tool registry (16–18)** — all four Workstream-A data tools are registered and AVAILABLE and join
  the model's tool definitions automatically; the two Workstream-C tools stay NOT_IMPLEMENTED
  (brief §11/§12).
* **Agent loop (19–25)** — one tool → final, several tools → final, a tool result feeds the *next*
  decision, tool failure and unknown route are handled, and the A5 iteration limit and duplicate-call
  protection still work (brief §13/§14/§17/§20).
* **Decision engine (26–31)** — richer information reaches A6 (including the enrichment and conflict
  paths of brief §17), fare/delay/walking/luggage still influence the decision, hard constraints and
  alternatives still work, and A6 — not the mock provider — still makes the decision (brief §16/§21).

Everything runs offline: no API key, no network, no live transit service.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.agent.decision import DecisionEngine
from app.agent.orchestrator import DEFAULT_MAX_AGENT_ITERATIONS, RouteAgent, build_agent
from app.config import get_settings
from app.schemas.candidate import RouteCandidate
from app.schemas.route import AgentState, DataSource, Leg
from app.schemas.travel_request import TravelRequest
from app.services.ai.agent import (
    AgentDecision,
    AgentPlanner,
    MockAgentPlanner,
    PlannerContext,
    ToolCallRequest,
    build_tool_definitions,
)
from app.services.ai.extraction import MockTravelRequestExtractor
from app.tools.base import Tool, ToolAvailability, ToolErrorCode, ToolResult, ToolStatus
from app.tools.candidates import MockCandidateProvider
from app.tools.capabilities import (
    DelayPredictionTool,
    FareEstimationTool,
    MockRouteSearchTool,
    RouteDetailsTool,
    RouteIdArgs,
    SearchRoutesArgs,
)
from app.tools.intelligence import MOCK_INTEL_NOTE, MockRouteIntelligence
from app.tools.registry import ToolRegistry, build_tools

GOLDEN = (
    "I am at Colombo Fort and need to reach Ella under a budget of LKR 2,000, "
    "but I have a heavy bag and don't want to walk."
)
_SEARCH = {"origin": "Colombo Fort", "destination": "Ella"}

#: The four Workstream-A data tools after A7 (brief §11), in registration order.
_DATA_TOOLS = (
    "search_routes",
    "get_fare_estimate",
    "get_delay_prediction",
    "get_route_details",
)
#: The three route-scoped intelligence tools A7 adds.
_INTEL_TOOLS = _DATA_TOOLS[1:]
#: Capabilities Workstream C still owns — honest NOT_IMPLEMENTED stubs (brief §11/§27).
_C_STUBS = ("check_availability", "prepare_booking")
#: Every mock route id the shared truth holds (brief §15).
_ALL_ROUTE_IDS = ["R1", "R2", "R3", "K1", "K2", "C1", "C2"]


def _intel() -> MockRouteIntelligence:
    return MockRouteIntelligence()


def _registry() -> ToolRegistry:
    return build_tools(get_settings())


def _golden_request() -> TravelRequest:
    return MockTravelRequestExtractor().extract(GOLDEN, {})


def _request(text: str) -> TravelRequest:
    return MockTravelRequestExtractor().extract(text, {})


def _tool_call(name: str, arguments: dict[str, Any] | None = None) -> AgentDecision:
    return AgentDecision(
        kind="tool_call",
        tool_calls=[ToolCallRequest(name=name, arguments=dict(arguments or {}))],
        data_source="mock",
        model="mock-qwen",
    )


_FINAL = AgentDecision(kind="final", content="ready to decide", data_source="mock", model="mock-qwen")


class _ScriptedPlanner(AgentPlanner):
    """Replays a fixed list of decisions (the last one repeats if the loop asks for more)."""

    def __init__(self, decisions: list[AgentDecision]) -> None:
        self._decisions = decisions
        self.calls = 0

    def next_decision(self, ctx: PlannerContext) -> AgentDecision:
        index = min(self.calls, len(self._decisions) - 1)
        self.calls += 1
        return self._decisions[index]


class _RecordingPlanner(AgentPlanner):
    """Delegates to :class:`MockAgentPlanner` and snapshots the evidence it was given per turn.

    This is how scenario 21 proves a tool *result* — not a script — drives the next decision.
    """

    def __init__(self) -> None:
        self._inner = MockAgentPlanner()
        self.seen: list[dict[str, Any]] = []
        self.decisions: list[AgentDecision] = []

    def next_decision(self, ctx: PlannerContext) -> AgentDecision:
        self.seen.append(
            {
                "route_ids": list(ctx.route_ids),
                "called_tools": list(ctx.called_tools),
                "steps_taken": ctx.steps_taken,
            }
        )
        decision = self._inner.next_decision(ctx)
        self.decisions.append(decision)
        return decision


def _agent(planner: AgentPlanner, *, tools: ToolRegistry | None = None, max_iterations: int | None = None) -> RouteAgent:
    return RouteAgent(
        tools=tools or build_tools(get_settings()),
        engine=DecisionEngine(),
        planner=planner,
        max_iterations=max_iterations,
    )


def _tool_actions(context: Any) -> list[Any]:
    return [a for a in context.actions if a.tool_call is not None]


def _states(context: Any) -> list[AgentState]:
    return [a.state for a in context.actions]


def _deduped(states: list[Any]) -> list[Any]:
    """The canonical state order of a trace, ignoring how many actions each state produced."""
    return list(dict.fromkeys(states))


_CANONICAL = [
    AgentState.UNDERSTANDING,
    AgentState.PLANNING,
    AgentState.SEARCHING,
    AgentState.EVALUATING,
    AgentState.COMPLETED,
]


# --------------------------------------------------------------------------- #
# Mock provider (brief §23, scenarios 1–5) — one shared source of truth (§15)
# --------------------------------------------------------------------------- #
# 1. Same input → same output (determinism across repeated calls and fresh instances).
def test_01_same_input_returns_same_output() -> None:
    intel = _intel()
    for route_id in _ALL_ROUTE_IDS:
        assert intel.fare_estimate(route_id) == intel.fare_estimate(route_id)
        assert intel.delay_prediction(route_id) == intel.delay_prediction(route_id)
        # Legs are fresh Pydantic models each call, so compare their serialized form.
        assert [leg.model_dump() for leg in intel.route_details(route_id)["legs"]] == [
            leg.model_dump() for leg in intel.route_details(route_id)["legs"]
        ]
    assert [c.model_dump() for c in intel.candidates_for(**_SEARCH)] == [
        c.model_dump() for c in _intel().candidates_for(**_SEARCH)
    ]

    # The same determinism holds through the tool seam (registry → executor → ToolResult).
    registry = _registry()
    for name in _INTEL_TOOLS:
        first = registry.execute(name, {"route_id": "R1"}).to_dict()
        second = _registry().execute(name, {"route_id": "R1"}).to_dict()
        assert first == second


# 2. A known route returns consistent data across every view of the shared truth.
def test_02_known_route_is_consistent_across_views() -> None:
    intel = _intel()
    candidate = intel.candidate("R1")
    fare = intel.fare_estimate("R1")
    delay = intel.delay_prediction("R1")
    details = intel.route_details("R1")
    assert candidate is not None and fare and delay and details

    # One route, one set of facts: every view reports the same figures for R1.
    assert fare["route_id"] == delay["route_id"] == details["route_id"] == candidate.id == "R1"
    assert fare["total_fare_lkr"] == details["total_fare_lkr"] == candidate.total_fare_lkr == 1600.0
    assert delay["delay_risk"] == details["delay_risk"] == candidate.delay_risk == "low"
    assert (
        delay["delay_min_estimate"]
        == details["delay_min_estimate"]
        == candidate.delay_min_estimate
        == 10.0
    )
    assert details["total_duration_min"] == candidate.total_duration_min == 420.0
    assert details["transfers"] == candidate.transfers == 1
    assert details["walking_km"] == candidate.walking_km == 0.3
    assert (details["origin"], details["destination"]) == ("Colombo Fort", "Ella")

    # The leg-level detail sums to the route-level totals (never two unrelated datasets).
    legs = details["legs"]
    assert len(legs) == 3
    assert sum(leg.duration_min for leg in legs) == details["total_duration_min"]
    assert sum(leg.fare_lkr for leg in legs) == details["total_fare_lkr"]
    assert sum(leg.walking_km for leg in legs) == pytest.approx(details["walking_km"])
    assert sum(leg.delay_min_estimate for leg in legs) == details["delay_min_estimate"]
    assert sum(1 for leg in legs if leg.mode != "walk") - 1 == details["transfers"]
    assert [entry["fare_lkr"] for entry in fare["fare_breakdown"]] == [leg.fare_lkr for leg in legs]
    assert [entry["delay_min_estimate"] for entry in delay["leg_delays"]] == [
        leg.delay_min_estimate for leg in legs
    ]


# 3. An unknown route returns an honest failure — never invented data (brief §18).
def test_03_unknown_route_is_an_honest_failure() -> None:
    intel = _intel()
    assert intel.is_known("R999") is False
    assert intel.fare_estimate("R999") is None
    assert intel.delay_prediction("R999") is None
    assert intel.route_details("R999") is None
    assert intel.legs_for("R999") == []
    assert intel.candidate("R999") is None

    registry = _registry()
    for name in _INTEL_TOOLS:
        result = registry.execute(name, {"route_id": "R999"})
        assert result.success is False
        assert result.data is None  # no fabricated fare / delay / legs
        assert result.status is ToolStatus.error
        assert result.data_source is DataSource.mock
        assert result.tool_name == name
        assert result.error is not None
        assert result.error.code == ToolErrorCode.ROUTE_NOT_FOUND.value
        # The failure is *informative*: it names the route asked for and the routes that exist.
        assert "R999" in result.message
        assert result.error.details["route_id"] == "R999"
        assert result.error.details["known_route_ids"] == _ALL_ROUTE_IDS


# 4. No random values: many repeated reads of every route produce exactly one distinct payload.
def test_04_no_random_values_anywhere() -> None:
    def dump(payload: Any) -> str:
        return json.dumps(payload, sort_keys=True, default=str)

    registry = _registry()
    for route_id in _ALL_ROUTE_IDS:
        for name in _INTEL_TOOLS:
            payloads = {dump(registry.execute(name, {"route_id": route_id}).data) for _ in range(25)}
            assert len(payloads) == 1, f"{name}({route_id}) is not deterministic"

    intel = _intel()
    corridors = {dump(intel.candidates_for(**_SEARCH)) for _ in range(25)}
    assert len(corridors) == 1


# 5. All related tools agree on the same route (the §15 guarantee, for every route in the dataset).
def test_05_all_tools_agree_on_every_route() -> None:
    intel = _intel()
    provider = MockCandidateProvider(intel)
    assert intel.route_ids() == _ALL_ROUTE_IDS

    for route_id in _ALL_ROUTE_IDS:
        candidate = intel.candidate(route_id)
        fare = intel.fare_estimate(route_id)
        delay = intel.delay_prediction(route_id)
        details = intel.route_details(route_id)
        assert candidate is not None and fare and delay and details

        assert fare["route_id"] == delay["route_id"] == details["route_id"] == route_id
        assert fare["total_fare_lkr"] == candidate.total_fare_lkr == details["total_fare_lkr"]
        assert delay["delay_risk"] == candidate.delay_risk == details["delay_risk"]
        assert delay["delay_min_estimate"] == candidate.delay_min_estimate
        assert details["total_duration_min"] == candidate.total_duration_min
        assert details["transfers"] == candidate.transfers
        assert details["walking_km"] == candidate.walking_km
        assert details["summary"] == candidate.summary
        assert details["modes"] == candidate.modes

        # The search_routes view of the same truth is the same route, corridor by corridor.
        searched = {c.id: c for c in provider.candidates_for(candidate.origin, candidate.destination)}
        assert route_id in searched
        assert searched[route_id].total_fare_lkr == candidate.total_fare_lkr
        assert searched[route_id].delay_risk == candidate.delay_risk
        assert searched[route_id].total_duration_min == candidate.total_duration_min

    # A single shared dataset, not three copies: one provider instance backs every tool.
    shared = _intel()
    registry = ToolRegistry(
        [
            MockRouteSearchTool(MockCandidateProvider(shared)),
            FareEstimationTool(shared),
            DelayPredictionTool(shared),
            RouteDetailsTool(shared),
        ]
    )
    searched_r2 = registry.execute("search_routes", dict(_SEARCH)).data[1]
    assert registry.execute("get_fare_estimate", {"route_id": "R2"}).data["total_fare_lkr"] == (
        searched_r2.total_fare_lkr
    )


# --------------------------------------------------------------------------- #
# Fare tool (brief §23, scenarios 6–9; requirements §7)
# --------------------------------------------------------------------------- #
# 6. A valid route returns the deterministic mock fare with a per-leg breakdown.
def test_06_fare_valid_route() -> None:
    result = _registry().execute("get_fare_estimate", {"route_id": "R1"})
    assert result.success is True
    assert result.status is ToolStatus.mock_data
    assert result.tool_name == "get_fare_estimate"
    payload = result.data
    assert payload["route_id"] == "R1"
    assert payload["total_fare_lkr"] == 1600.0
    assert payload["currency"] == "LKR"
    assert [entry["leg_id"] for entry in payload["fare_breakdown"]] == ["R1-L1", "R1-L2", "R1-L3"]
    assert [entry["mode"] for entry in payload["fare_breakdown"]] == ["walk", "tuk", "train"]
    assert sum(entry["fare_lkr"] for entry in payload["fare_breakdown"]) == 1600.0
    assert result.meta == {"route_id": "R1", "known_route": True}
    assert "R1" in result.message and "1,600" in result.message

    # Route ids are matched tolerantly (trimmed, case-insensitive) but reported canonically.
    assert _registry().execute("get_fare_estimate", {"route_id": " r1 "}).data["route_id"] == "R1"


# 7. An unknown route is an honest ROUTE_NOT_FOUND failure (brief §18).
def test_07_fare_unknown_route() -> None:
    result = _registry().execute("get_fare_estimate", {"route_id": "R999"})
    assert result.success is False
    assert result.data is None
    assert result.error.code == ToolErrorCode.ROUTE_NOT_FOUND.value
    assert result.data_source is DataSource.mock
    assert "will not invent" in result.message


# 8. Invalid input is rejected by the executor's validation gate — never executed, never faked (§19).
@pytest.mark.parametrize(
    "payload",
    [
        {},  # missing arguments
        {"route_id": ""},  # empty string (min_length=1)
        {"route_id": 123},  # wrong type
        {"route_id": None},
        {"route_id": "R" * 65},  # over max_length
    ],
)
def test_08_fare_invalid_input(payload: dict[str, Any]) -> None:
    result = _registry().execute("get_fare_estimate", payload)
    assert result.success is False
    assert result.data is None
    assert result.status is ToolStatus.error
    assert result.error.code == ToolErrorCode.INVALID_INPUT.value
    assert "Invalid input for 'get_fare_estimate'" in result.message


# 9. Mock provenance is explicit at every level (brief §24: never claimed as real-time).
def test_09_fare_mock_provenance() -> None:
    tool = FareEstimationTool()
    assert tool.availability is ToolAvailability.available
    assert tool.data_source is DataSource.mock
    assert tool.args_model is RouteIdArgs

    result = _registry().execute("get_fare_estimate", {"route_id": "R2"})
    assert result.data_source is DataSource.mock
    assert result.status is ToolStatus.mock_data  # mock_data, never plain `ok`
    assert result.data["data_source"] == "mock"
    assert result.data["note"] == MOCK_INTEL_NOTE
    assert "not live pricing" in result.message
    assert "not live" in MOCK_INTEL_NOTE.lower()


# --------------------------------------------------------------------------- #
# Delay tool (brief §23, scenarios 10–12; requirements §8)
# --------------------------------------------------------------------------- #
# 10. A valid route returns the deterministic mock delay risk/minutes with per-leg detail.
def test_10_delay_valid_route() -> None:
    result = _registry().execute("get_delay_prediction", {"route_id": "R2"})
    assert result.success is True
    assert result.status is ToolStatus.mock_data
    payload = result.data
    assert payload["route_id"] == "R2"
    assert payload["delay_risk"] == "moderate"
    assert payload["delay_min_estimate"] == 30.0
    assert [entry["leg_id"] for entry in payload["leg_delays"]] == ["R2-L1", "R2-L2"]
    assert sum(entry["delay_min_estimate"] for entry in payload["leg_delays"]) == 30.0
    assert result.meta == {"route_id": "R2", "known_route": True}
    assert "moderate risk" in result.message


# 11. An unknown route is an honest ROUTE_NOT_FOUND failure — no invented delay.
def test_11_delay_unknown_route() -> None:
    result = _registry().execute("get_delay_prediction", {"route_id": "NOPE"})
    assert result.success is False
    assert result.data is None
    assert result.error.code == ToolErrorCode.ROUTE_NOT_FOUND.value
    assert result.error.details["known_route_ids"] == _ALL_ROUTE_IDS


# 12. Mock provenance: a simulated delay is never presented as a live one (brief §24).
def test_12_delay_mock_provenance() -> None:
    result = _registry().execute("get_delay_prediction", {"route_id": "R1"})
    assert result.data_source is DataSource.mock
    assert result.status is ToolStatus.mock_data
    assert result.data["data_source"] == "mock"
    assert result.data["note"] == MOCK_INTEL_NOTE
    assert "simulated, not a live delay" in result.message
    assert DelayPredictionTool().data_source is DataSource.mock


# --------------------------------------------------------------------------- #
# Route-details tool (brief §23, scenarios 13–15; requirements §9)
# --------------------------------------------------------------------------- #
# 13. A valid route returns leg-by-leg detail plus the route-level context the candidate carries.
def test_13_details_valid_route() -> None:
    result = _registry().execute("get_route_details", {"route_id": "R1"})
    assert result.success is True
    assert result.status is ToolStatus.mock_data
    payload = result.data
    assert payload["route_id"] == "R1"
    assert (payload["origin"], payload["destination"]) == ("Colombo Fort", "Ella")
    assert payload["summary"]
    assert payload["modes"] == ["walk", "tuk", "train"]
    assert payload["total_duration_min"] == 420.0
    assert payload["total_fare_lkr"] == 1600.0
    assert payload["transfers"] == 1
    assert payload["walking_km"] == 0.3
    assert payload["delay_risk"] == "low" and payload["delay_min_estimate"] == 10.0
    assert payload["currency"] == "LKR"
    assert result.meta == {"route_id": "R1", "known_route": True, "leg_count": 3}
    assert "3 leg(s)" in result.message


# 14. An unknown route is an honest ROUTE_NOT_FOUND failure — no invented legs.
def test_14_details_unknown_route() -> None:
    result = _registry().execute("get_route_details", {"route_id": "R999"})
    assert result.success is False
    assert result.data is None
    assert result.error.code == ToolErrorCode.ROUTE_NOT_FOUND.value
    assert result.data_source is DataSource.mock


# 15. The result is structured and reuses the EXISTING schema — no second route representation (§9).
def test_15_details_are_structured_and_reuse_the_existing_schema() -> None:
    payload = _registry().execute("get_route_details", {"route_id": "R3"}).data
    legs = payload["legs"]
    assert len(legs) == 3
    assert all(isinstance(leg, Leg) for leg in legs)  # the A3/API_CONTRACTS §3 Leg model

    first = legs[0]
    assert first.id == "R3-L1"
    assert first.mode == "tuk"
    assert (first.origin, first.destination) == ("Colombo Fort", "Colombo Fort Station")
    # The API serializes origin/destination under the documented `from`/`to` aliases.
    serialized = first.model_dump(mode="json", by_alias=True)
    assert serialized["from"] == "Colombo Fort" and serialized["to"] == "Colombo Fort Station"
    assert "origin" not in serialized and "destination" not in serialized
    assert first.data_source is DataSource.mock

    # Route-level keys use the RouteCandidate vocabulary — one shared contract, not a new shape.
    candidate = _intel().candidate("R3")
    for field in (
        "total_duration_min",
        "total_fare_lkr",
        "transfers",
        "walking_km",
        "delay_risk",
        "delay_min_estimate",
    ):
        assert payload[field] == getattr(candidate, field)
    assert payload["data_source"] == "mock" and payload["note"] == MOCK_INTEL_NOTE
    assert RouteDetailsTool().data_source is DataSource.mock


# --------------------------------------------------------------------------- #
# Tool registry (brief §23, scenarios 16–18; requirements §10/§11/§12)
# --------------------------------------------------------------------------- #
# 16. All A7 tools are registered in the ONE existing registry (no second registry — §10).
def test_16_all_a7_tools_are_registered() -> None:
    registry = _registry()
    assert registry.names() == list(_DATA_TOOLS) + list(_C_STUBS)
    for name in _DATA_TOOLS:
        tool = registry.get(name)
        assert tool is not None
        assert isinstance(tool, Tool)  # the A4 base class — no new tool base class was added
        assert tool.name == name
        assert tool.description and tool.input_schema and tool.output_schema
    # The three new tools are independent Tool subclasses sharing only the A4 seam.
    assert isinstance(registry.get("get_fare_estimate"), FareEstimationTool)
    assert isinstance(registry.get("get_delay_prediction"), DelayPredictionTool)
    assert isinstance(registry.get("get_route_details"), RouteDetailsTool)


# 17. All A7 tools are AVAILABLE and join the model's tool definitions automatically (§12).
def test_17_all_a7_tools_are_available_and_exposed() -> None:
    registry = _registry()
    assert registry.list_available() == list(_DATA_TOOLS)
    for name in _DATA_TOOLS:
        assert registry.status(name) is ToolAvailability.available

    definitions = build_tool_definitions(registry)
    assert {d["function"]["name"] for d in definitions} == set(_DATA_TOOLS)
    for name in _INTEL_TOOLS:
        definition = next(d for d in definitions if d["function"]["name"] == name)
        assert definition["type"] == "function"
        assert "route_id" in definition["function"]["parameters"]["properties"]
        assert "route_id" in definition["function"]["parameters"]["required"]

    # Registering a new AVAILABLE tool exposes it to the model with no planner change (§12).
    class _ExtraTool(FareEstimationTool):
        name = "get_extra_estimate"

    extended = ToolRegistry(
        [
            MockRouteSearchTool(),
            FareEstimationTool(),
            DelayPredictionTool(),
            RouteDetailsTool(),
            _ExtraTool(),
        ]
    )
    assert {d["function"]["name"] for d in build_tool_definitions(extended)} == set(_DATA_TOOLS) | {
        "get_extra_estimate"
    }


# 18. The future Workstream-C tools remain NOT_IMPLEMENTED (brief §11/§27).
def test_18_workstream_c_tools_remain_not_implemented() -> None:
    registry = _registry()
    for name in _C_STUBS:
        assert registry.status(name) is ToolAvailability.not_implemented
        assert name not in registry.list_available()
        tool = registry.get(name)
        assert tool is not None and tool.owner == "C"
        result = registry.execute(name, {"route_id": "R1"})
        assert result.success is False
        assert result.status is ToolStatus.not_implemented
        assert result.error.code == ToolErrorCode.NOT_IMPLEMENTED.value
        assert result.data is None
        assert "Workstream C" in result.message
    assert not ({d["function"]["name"] for d in build_tool_definitions(registry)} & set(_C_STUBS))


# --------------------------------------------------------------------------- #
# Agent loop (brief §23, scenarios 19–25; requirements §13/§14/§17/§20)
# --------------------------------------------------------------------------- #
# 19. One tool → final: the A5 single-step shape still works, and no legs are invented (§9).
def test_19_one_tool_then_final() -> None:
    context = _agent(_ScriptedPlanner([_tool_call("search_routes", _SEARCH), _FINAL])).run(
        _golden_request()
    )
    assert context.state is AgentState.COMPLETED
    assert len(context.actions) == 5
    assert _deduped(_states(context)) == _CANONICAL
    assert [a.tool_call.name for a in _tool_actions(context)] == ["search_routes"]
    assert context.recommendation is not None and context.recommendation.id == "R1"
    # get_route_details was never called, so the API shows no legs rather than invented ones.
    assert context.legs == []
    assert context.errors == []


# 20. Multiple tools → final: a model-selected multi-step sequence over the A7 intelligence.
def test_20_multiple_tools_then_final() -> None:
    planner = _ScriptedPlanner(
        [
            _tool_call("search_routes", _SEARCH),
            _tool_call("get_fare_estimate", {"route_id": "R1"}),
            _tool_call("get_delay_prediction", {"route_id": "R1"}),
            _tool_call("get_route_details", {"route_id": "R1"}),
            _FINAL,
        ]
    )
    context = _agent(planner).run(_golden_request())
    assert context.state is AgentState.COMPLETED
    calls = _tool_actions(context)
    assert [a.tool_call.name for a in calls] == list(_DATA_TOOLS)
    assert all(a.status == "done" for a in calls)
    assert all(a.tool_call.data_source is DataSource.mock for a in calls)
    assert all(a.state is AgentState.SEARCHING for a in calls)  # no new TOOL_CALLING state (§20)
    assert _deduped(_states(context)) == _CANONICAL
    assert context.recommendation.id == "R1"
    # The recommended route's legs came from the details tool result — verbatim, not invented.
    assert [leg.id for leg in context.legs] == ["R1-L1", "R1-L2", "R1-L3"]
    assert [leg.mode for leg in context.legs] == ["walk", "tuk", "train"]


# 21. A tool RESULT feeds the next decision: the mock planner only ever asks for what the evidence
#     says is still missing (brief §14), so the order is a consequence, not a script (§13).
def test_21_tool_result_feeds_the_next_decision() -> None:
    planner = _RecordingPlanner()
    context = _agent(planner).run(_golden_request())

    # Turn 1: nothing observed yet → ask for the corridor search.
    assert planner.seen[0] == {"route_ids": [], "called_tools": [], "steps_taken": 0}
    assert [c.name for c in planner.decisions[0].tool_calls] == ["search_routes"]

    # Turn 2: search RETURNED R1/R2/R3 → those exact ids are now the evidence for the fare calls.
    assert planner.seen[1]["route_ids"] == ["R1", "R2", "R3"]
    assert planner.seen[1]["called_tools"] == ["search_routes"]
    assert [c.name for c in planner.decisions[1].tool_calls] == ["get_fare_estimate"] * 3
    assert [c.arguments["route_id"] for c in planner.decisions[1].tool_calls] == ["R1", "R2", "R3"]

    # Turns 3–4: fare is now a called capability, so the next missing intelligence is asked for.
    assert planner.seen[2]["called_tools"] == ["search_routes"] + ["get_fare_estimate"] * 3
    assert [c.name for c in planner.decisions[2].tool_calls] == ["get_delay_prediction"] * 3
    assert planner.seen[3]["called_tools"][-3:] == ["get_delay_prediction"] * 3
    assert [c.name for c in planner.decisions[3].tool_calls] == ["get_route_details"] * 3

    # Turn 5: every registered capability that could add information has been used → finish.
    assert planner.seen[4]["steps_taken"] == 10
    assert planner.decisions[4].kind == "final"
    assert len(planner.seen) == 5

    assert context.state is AgentState.COMPLETED
    assert [a.tool_call.name for a in _tool_actions(context)] == [
        "search_routes",
        *(["get_fare_estimate"] * 3),
        *(["get_delay_prediction"] * 3),
        *(["get_route_details"] * 3),
    ]
    assert len(context.actions) == 14


# 22. A tool failure is handled: recorded honestly, fed back, and the agent still decides (§19).
def test_22_tool_failure_is_handled() -> None:
    context = _agent(
        _ScriptedPlanner(
            [
                _tool_call("search_routes", _SEARCH),
                _tool_call("get_fare_estimate", {}),  # missing arguments
                _FINAL,
            ]
        )
    ).run(_golden_request())
    calls = _tool_actions(context)
    assert calls[1].status == "error"
    assert calls[1].tool_call.error_code == ToolErrorCode.INVALID_INPUT.value
    assert calls[1].tool_call.data_source is DataSource.mock
    assert context.errors  # the failure was recorded, not hidden or turned into mock data
    assert context.recommendation is not None and context.recommendation.id == "R1"
    assert context.state is AgentState.COMPLETED
    assert context.legs == []  # no details result → no legs, and none invented


# 23. An unknown route is handled: honest ROUTE_NOT_FOUND, no R999 candidate, decision still made.
def test_23_unknown_route_is_handled_in_the_loop() -> None:
    context = _agent(
        _ScriptedPlanner(
            [
                _tool_call("search_routes", _SEARCH),
                _tool_call("get_fare_estimate", {"route_id": "R999"}),
                _tool_call("get_delay_prediction", {"route_id": "R999"}),
                _tool_call("get_route_details", {"route_id": "R999"}),
                _FINAL,
            ]
        )
    ).run(_golden_request())
    calls = _tool_actions(context)
    assert [a.tool_call.error_code for a in calls[1:]] == [ToolErrorCode.ROUTE_NOT_FOUND.value] * 3
    assert all(a.status == "error" for a in calls[1:])
    assert [c.id for c in context.candidates] == ["R1", "R2", "R3"]  # R999 was never fabricated
    assert len(context.errors) == 3
    assert context.recommendation.id == "R1"  # still grounded in the real candidates
    assert context.state is AgentState.COMPLETED
    assert context.legs == []


# 24. The A5 iteration limit still bounds the A7 multi-step loop; nothing is fabricated at the limit.
def test_24_iteration_limit_still_bounds_the_multi_step_loop() -> None:
    planner = _RecordingPlanner()
    context = _agent(planner, max_iterations=2).run(_golden_request())
    assert len(planner.seen) == 2  # the budget counts planner turns, not individual calls
    assert context.state is AgentState.COMPLETED  # terminates; never hangs
    assert context.recommendation is None  # no fabricated recommendation at the limit
    assert any("iteration" in e.lower() for e in context.errors)
    assert [a.tool_call.name for a in _tool_actions(context)] == [
        "search_routes",
        *(["get_fare_estimate"] * 3),
    ]

    # The full golden run fits comfortably inside the configured default bound.
    assert DEFAULT_MAX_AGENT_ITERATIONS >= 5
    assert len(_RecordingPlanner().seen) == 0  # a fresh planner has observed nothing yet
    full = _agent(_RecordingPlanner()).run(_golden_request())
    assert full.recommendation is not None


# 25. Duplicate-call protection still works, across turns and within a single turn (§18).
def test_25_duplicate_call_protection_still_works() -> None:
    # Across turns: the identical second fare call is suppressed, not re-executed.
    planner = _ScriptedPlanner(
        [
            _tool_call("search_routes", _SEARCH),
            _tool_call("get_fare_estimate", {"route_id": "R1"}),
            _tool_call("get_fare_estimate", {"route_id": "R1"}),
            _FINAL,
        ]
    )
    context = _agent(planner).run(_golden_request())
    calls = _tool_actions(context)
    assert [a.tool_call.name for a in calls] == [
        "search_routes",
        "get_fare_estimate",
        "get_fare_estimate",
    ]
    assert calls[0].status == calls[1].status == "done"
    assert calls[2].status == "error"  # the identical repeat was suppressed, not re-executed
    assert calls[2].tool_call.error_code == "REPEATED_CALL"
    assert planner.calls == 3  # the loop broke after the repeat; _FINAL was never reached
    assert any("Repeated identical" in e for e in context.errors)
    assert context.recommendation is not None  # decided from what was actually gathered

    # Within one turn: the A7 mock planner emits several calls at once, so a repeat inside the
    # same decision must be suppressed too.
    duplicated = AgentDecision(
        kind="tool_call",
        tool_calls=[
            ToolCallRequest(name="get_delay_prediction", arguments={"route_id": "R1"}),
            ToolCallRequest(name="get_delay_prediction", arguments={"route_id": "R1"}),
        ],
        data_source="mock",
        model="mock-qwen",
    )
    same_turn = _agent(
        _ScriptedPlanner([_tool_call("search_routes", _SEARCH), duplicated, _FINAL])
    ).run(_golden_request())
    same_turn_calls = _tool_actions(same_turn)
    assert [a.tool_call.error_code for a in same_turn_calls] == [None, None, "REPEATED_CALL"]

    # A different route id is NOT a duplicate: it is new information and must be executed.
    distinct = _agent(
        _ScriptedPlanner(
            [
                _tool_call("search_routes", _SEARCH),
                _tool_call("get_fare_estimate", {"route_id": "R1"}),
                _tool_call("get_fare_estimate", {"route_id": "R2"}),
                _FINAL,
            ]
        )
    ).run(_golden_request())
    assert [a.status for a in _tool_actions(distinct)] == ["done"] * 3


# --------------------------------------------------------------------------- #
# Decision engine (brief §23, scenarios 26–31; requirements §16/§17/§21)
# --------------------------------------------------------------------------- #
class _PartialSearchTool(Tool):
    """A ``search_routes`` view whose candidates lack delay figures (proves §17 enrichment)."""

    name = "search_routes"
    description = "Search candidate routes (partial view: no delay information)."
    availability = ToolAvailability.available
    data_source = DataSource.mock
    owner = "B"
    args_model = SearchRoutesArgs

    def execute(self, **kwargs: Any) -> ToolResult:
        candidates = _intel().candidates_for(kwargs.get("origin"), kwargs.get("destination"))
        for candidate in candidates:
            candidate.delay_risk = None
            candidate.delay_min_estimate = None
        return ToolResult(
            status=ToolStatus.mock_data,
            data_source=DataSource.mock,
            data=candidates,
            message=f"Partial mock search: {len(candidates)} candidate(s) without delay data.",
            tool_name=self.name,
        )


class _ContradictingDelayTool(DelayPredictionTool):
    """A delay tool that disagrees with the candidate (proves §17 conflicts are reported)."""

    def execute(self, **kwargs: Any) -> ToolResult:
        result = super().execute(**kwargs)
        payload = dict(result.data or {})
        payload["delay_risk"] = "high"
        payload["delay_min_estimate"] = 99.0
        return ToolResult(
            status=result.status,
            data_source=result.data_source,
            data=payload,
            message=result.message,
            meta=result.meta,
            tool_name=result.tool_name,
        )


# 26. Richer candidate information reaches A6 — and A6 still makes the decision (§16).
def test_26_richer_information_reaches_the_a6_engine() -> None:
    request = _golden_request()
    context = build_agent(get_settings()).run(request)

    evaluating = next(a for a in context.actions if a.state is AgentState.EVALUATING)
    assert "Consolidated mock intelligence for 3 route(s)" in evaluating.detail
    assert "(delay, details, fare)" in evaluating.detail
    assert "consistent with the structured candidates" in evaluating.detail
    assert context.errors == []  # the shared mock truth never contradicts itself (§15)

    # A7 informs, A6 decides: the engine's answer is identical to a direct call over the same
    # candidates the search tool returned, so no decision logic moved into the mock providers.
    direct = DecisionEngine().decide(request, _intel().candidates_for(**_SEARCH))
    assert context.recommendation.id == direct.recommendation.id == "R1"
    assert context.recommendation.score == direct.recommendation.score
    assert [(a.id, a.rank, a.valid) for a in context.alternatives] == [
        (a.id, a.rank, a.valid) for a in direct.alternatives
    ]
    assert [leg.id for leg in context.legs] == ["R1-L1", "R1-L2", "R1-L3"]


# 26b. §17 enrichment: a figure the candidate does not carry is filled from the tool result, so the
#      engine reasons over richer information instead of a gap.
def test_26b_missing_candidate_fields_are_filled_from_tool_results() -> None:
    registry = ToolRegistry([_PartialSearchTool(), DelayPredictionTool()])
    context = _agent(
        _ScriptedPlanner(
            [
                _tool_call("search_routes", _SEARCH),
                _tool_call("get_delay_prediction", {"route_id": "R1"}),
                _FINAL,
            ]
        ),
        tools=registry,
    ).run(_golden_request())

    by_id = {c.id: c for c in context.candidates}
    # R1 was observed → its missing delay figures were filled from the tool, not invented.
    assert by_id["R1"].delay_risk == "low"
    assert by_id["R1"].delay_min_estimate == 10.0
    # R2/R3 were never observed → they stay honestly empty rather than being guessed.
    assert by_id["R2"].delay_risk is None and by_id["R3"].delay_risk is None
    evaluating = next(a for a in context.actions if a.state is AgentState.EVALUATING)
    assert "missing candidate field(s) filled from tool results" in evaluating.detail


# 26c. §17 conflict: a contradiction is identified, the authoritative candidate value is kept, and
#      no resolution is invented.
def test_26c_contradicting_tool_result_is_reported_not_resolved() -> None:
    registry = ToolRegistry([MockRouteSearchTool(), _ContradictingDelayTool()])
    context = _agent(
        _ScriptedPlanner(
            [
                _tool_call("search_routes", _SEARCH),
                _tool_call("get_delay_prediction", {"route_id": "R1"}),
                _FINAL,
            ]
        ),
        tools=registry,
    ).run(_golden_request())

    conflicts = [e for e in context.errors if "R1.delay_risk" in e]
    assert conflicts, context.errors
    assert "the structured candidate value was kept" in conflicts[0]
    assert "'low'" in conflicts[0] and "'high'" in conflicts[0]
    # The candidate stays authoritative — the contradicting tool did not overwrite it.
    r1 = next(c for c in context.candidates if c.id == "R1")
    assert r1.delay_risk == "low"
    assert r1.delay_min_estimate == 10.0
    evaluating = next(a for a in context.actions if a.state is AgentState.EVALUATING)
    assert "conflict(s) recorded honestly" in evaluating.detail
    assert context.recommendation is not None  # the decision still completes


# 26d. §17: intelligence about a route the search never returned is reported and ignored.
def test_26d_unassociated_intelligence_is_reported_and_ignored() -> None:
    registry = ToolRegistry([MockRouteSearchTool(), FareEstimationTool()])
    context = _agent(
        _ScriptedPlanner(
            [
                _tool_call("search_routes", _SEARCH),
                _tool_call("get_fare_estimate", {"route_id": "K1"}),  # a different corridor
                _FINAL,
            ]
        ),
        tools=registry,
    ).run(_golden_request())
    assert any("'K1' intelligence was observed" in e for e in context.errors), context.errors
    assert [c.id for c in context.candidates] == ["R1", "R2", "R3"]  # K1 was not merged in
    assert context.recommendation.id == "R1"


def _candidate(**overrides: Any) -> RouteCandidate:
    """A minimal synthetic candidate for isolating one scoring signal."""
    base: dict[str, Any] = {
        "id": "X1",
        "origin": "Colombo Fort",
        "destination": "Ella",
        "summary": "Synthetic candidate",
        "modes": ["bus"],
        "total_duration_min": 360.0,
        "total_fare_lkr": 1200.0,
        "transfers": 0,
        "walking_km": 0.5,
        "delay_risk": "none",
        "delay_min_estimate": 0.0,
    }
    base.update(overrides)
    return RouteCandidate(**base)


def _plain_request(**overrides: Any) -> TravelRequest:
    """A request with origin/destination only (no soft preferences) unless overridden."""
    fields: dict[str, Any] = {
        "origin": "Colombo Fort",
        "destination": "Ella",
        "budget": 3000.0,
        "currency": "LKR",
    }
    fields.update(overrides)
    return TravelRequest(**fields).refresh_clarification()


# 27. Fare influences the decision where applicable — through the engine and through the budget gate.
def test_27_fare_influences_the_decision() -> None:
    engine = DecisionEngine()
    cheap = _candidate(id="CHEAP", total_fare_lkr=800.0)
    pricey = _candidate(id="PRICEY", total_fare_lkr=1800.0)
    decision = engine.decide(_plain_request(), [pricey, cheap])
    assert decision.recommendation.id == "CHEAP"  # identical apart from fare

    # The mock fare intelligence and the fare the engine scores are the same number (§15/§16).
    fare_payload = _registry().execute("get_fare_estimate", {"route_id": "R2"}).data
    r2 = _intel().candidate("R2")
    assert fare_payload["total_fare_lkr"] == r2.total_fare_lkr == 1200.0

    # End to end: tightening the budget below R1's mock fare changes the winner (not hard-coded).
    tight = _agent(MockAgentPlanner()).run(
        _golden_request().model_copy(update={"budget": 1200.0})
    )
    assert tight.recommendation.id == "R2"
    excluded = {a.id for a in tight.alternatives if a.valid is False}
    assert "R1" in excluded and "R3" in excluded


# 28. Delay influences the decision where applicable — and the delay the engine sees is the mock one.
def test_28_delay_influences_the_decision() -> None:
    engine = DecisionEngine()
    on_time = _candidate(id="ONTIME", delay_risk="none", delay_min_estimate=0.0)
    delayed = _candidate(id="DELAYED", delay_risk="high", delay_min_estimate=45.0)
    decision = engine.decide(_plain_request(), [delayed, on_time])
    assert decision.recommendation.id == "ONTIME"  # identical apart from delay

    # The delay intelligence the agent gathers is exactly what the engine penalizes for R2.
    delay_payload = _registry().execute("get_delay_prediction", {"route_id": "R2"}).data
    r2 = _intel().candidate("R2")
    assert delay_payload["delay_risk"] == r2.delay_risk == "moderate"
    assert delay_payload["delay_min_estimate"] == r2.delay_min_estimate == 30.0
    assert engine.DELAY_PENALTY["moderate"] > engine.DELAY_PENALTY["none"]


# 29. Walking/luggage preferences still work through the richer A7 loop.
def test_29_walking_and_luggage_preferences_still_work() -> None:
    heavy = TravelRequest(
        origin="Colombo Fort",
        destination="Ella",
        budget=2000.0,
        luggage="heavy",
        walking_preference="minimize",
    ).refresh_clarification()
    assert heavy.clarification_required is False
    with_prefs = _agent(MockAgentPlanner()).run(heavy)
    assert with_prefs.recommendation.id == "R1"  # 0.3 km walking, 1 transfer

    without_prefs = _agent(MockAgentPlanner()).run(_plain_request(budget=2000.0))
    assert without_prefs.recommendation.id == "R2"  # cheaper/faster, but 1.5 km walking
    # Both runs gathered the same richer intelligence; only the preferences differ.
    assert len(_tool_actions(with_prefs)) == len(_tool_actions(without_prefs)) == 10
    assert any("walking" in r.lower() for r in with_prefs.recommendation.reasons)


# 30. Hard constraints still work: an unaffordable corridor yields no fabricated recommendation.
def test_30_hard_constraints_still_work() -> None:
    # Budget below every mock fare on the corridor → nothing fits, and nothing is invented.
    context = _agent(MockAgentPlanner()).run(_plain_request(budget=1000.0))
    assert context.state is AgentState.COMPLETED
    assert context.recommendation is None
    assert context.legs == []
    assert context.candidates  # the corridor IS known; the budget is what excludes them
    assert all(a.valid is False for a in context.alternatives)
    assert all(
        "BUDGET" in [v.type for v in a.constraint_violations] for a in context.alternatives
    )

    # The golden budget excludes only R3 (LKR 2,350 > 2,000) and says so structurally.
    golden = _agent(MockAgentPlanner()).run(_golden_request())
    r3 = next(a for a in golden.alternatives if a.id == "R3")
    assert r3.valid is False and r3.rank is None and r3.score is None
    assert [v.type for v in r3.constraint_violations] == ["BUDGET"]
    assert "2,350" in r3.constraint_violations[0].message


# 31. Alternatives remain valid, honest and grounded in the searched candidates.
def test_31_alternatives_remain_valid() -> None:
    context = build_agent(get_settings()).run(_golden_request())
    assert context.recommendation.id == "R1"
    assert [a.id for a in context.alternatives] == ["R2", "R3"]
    assert context.recommendation.id not in [a.id for a in context.alternatives]
    assert {a.id for a in context.alternatives} <= {c.id for c in context.candidates}

    r2 = next(a for a in context.alternatives if a.id == "R2")
    assert r2.valid is True and r2.rank == 2
    assert r2.score is not None and r2.score < context.recommendation.score
    assert r2.trade_offs  # why it ranked below the recommendation
    assert r2.constraint_violations == []
    assert all(a.data_source is DataSource.mock for a in context.alternatives)
    assert context.recommendation.data_source is DataSource.mock
    assert context.data_source is DataSource.mock


# --------------------------------------------------------------------------- #
# Golden trace + the remaining A7 guarantees (§13, §14, §19, §20, §22)
# --------------------------------------------------------------------------- #
# The golden offline trace from brief §20, exactly — and only over canonical states.
def test_golden_trace_matches_the_brief_example() -> None:
    context = build_agent(get_settings()).run(_golden_request())
    assert _deduped(_states(context)) == _CANONICAL
    assert set(_states(context)) <= set(AgentState)  # no invented TOOL_CALLING state (§20)
    assert [a.seq for a in context.actions] == list(range(1, 15))
    assert [(a.state.value, a.label) for a in context.actions[:2]] == [
        ("UNDERSTANDING", context.actions[0].label),
        ("PLANNING", context.actions[1].label),
    ]
    trace = [(a.state.value, a.tool_call.name, a.status, a.tool_call.data_source.value)
             for a in _tool_actions(context)]
    assert trace == [
        ("SEARCHING", "search_routes", "done", "mock"),
        *[("SEARCHING", "get_fare_estimate", "done", "mock")] * 3,
        *[("SEARCHING", "get_delay_prediction", "done", "mock")] * 3,
        *[("SEARCHING", "get_route_details", "done", "mock")] * 3,
    ]
    assert context.actions[-2].state is AgentState.EVALUATING
    assert context.actions[-1].state is AgentState.COMPLETED
    assert context.actions[-1].label == "Decision ready"
    assert context.recommendation.id == "R1"
    assert round(context.recommendation.score, 3) == 0.472
    assert [(a.id, a.score) for a in context.alternatives] == [("R2", 0.408), ("R3", None)]
    assert [leg.id for leg in context.legs] == ["R1-L1", "R1-L2", "R1-L3"]
    assert "MOCK" in context.reasoning


# §13/§14: the sequence lives in the mock planner's evidence, never in the real agent — a registry
# without a capability simply skips that step.
def test_sequence_is_not_hardcoded_in_the_real_agent() -> None:
    # No delay tool registered → search, fare, details (the missing step is skipped, not faked).
    without_delay = ToolRegistry(
        [MockRouteSearchTool(), FareEstimationTool(), RouteDetailsTool()]
    )
    context = _agent(MockAgentPlanner(), tools=without_delay).run(_golden_request())
    assert [a.tool_call.name for a in _tool_actions(context)] == [
        "search_routes",
        *(["get_fare_estimate"] * 3),
        *(["get_route_details"] * 3),
    ]
    assert context.state is AgentState.COMPLETED

    # No search tool registered → nothing route-scoped to ask about, so the planner finishes at once.
    without_search = ToolRegistry([FareEstimationTool(), DelayPredictionTool()])
    finished = _agent(MockAgentPlanner(), tools=without_search).run(_golden_request())
    assert _tool_actions(finished) == []
    assert finished.state is AgentState.COMPLETED
    assert finished.recommendation is None

    # A corridor the mock does not know → no candidate ids, so no intelligence calls either.
    unknown = _agent(MockAgentPlanner()).run(
        TravelRequest(origin="Nowhere", destination="Elsewhere").refresh_clarification()
    )
    assert [a.tool_call.name for a in _tool_actions(unknown)] == ["search_routes"]
    assert unknown.candidates == [] and unknown.recommendation is None

    # The per-capability fan-out is a planner bound, not an agent constant.
    narrow = _agent(MockAgentPlanner(max_routes_per_tool=1)).run(_golden_request())
    assert [a.tool_call.name for a in _tool_actions(narrow)] == [
        "search_routes",
        "get_fare_estimate",
        "get_delay_prediction",
        "get_route_details",
    ]
    assert narrow.recommendation.id == "R1"


# §14: every mock-planner decision identifies itself as the mock planner, never a real model.
def test_mock_planner_decisions_are_labelled_mock_qwen() -> None:
    planner = _RecordingPlanner()
    _agent(planner).run(_golden_request())
    assert planner.decisions
    assert all(d.data_source == "mock" for d in planner.decisions)
    assert all(d.model == "mock-qwen" for d in planner.decisions)
    assert all("mock" in (d.content or "").lower() or d.content for d in planner.decisions)
    assert any("fare estimates" in d.content for d in planner.decisions)
    assert any("delay predictions" in d.content for d in planner.decisions)
    assert any("leg-by-leg route details" in d.content for d in planner.decisions)


# §19: every failure mode goes through the ONE existing ToolExecutor and stays a structured failure.
class _DisabledFareTool(FareEstimationTool):
    availability = ToolAvailability.disabled


class _RaisingFareTool(FareEstimationTool):
    def execute(self, **kwargs: Any) -> ToolResult:
        raise RuntimeError("exploded")


class _MalformedFareTool(FareEstimationTool):
    def execute(self, **kwargs: Any) -> Any:  # type: ignore[override]
        return {"not": "a ToolResult"}


@pytest.mark.parametrize(
    ("tool", "payload", "code"),
    [
        (FareEstimationTool(), {}, ToolErrorCode.INVALID_INPUT),  # missing arguments
        (DelayPredictionTool(), {"route_id": 7}, ToolErrorCode.INVALID_INPUT),  # invalid id type
        (RouteDetailsTool(), {"route_id": "R999"}, ToolErrorCode.ROUTE_NOT_FOUND),  # unknown route
        (_DisabledFareTool(), {"route_id": "R1"}, ToolErrorCode.TOOL_UNAVAILABLE),  # unavailable
        (_RaisingFareTool(), {"route_id": "R1"}, ToolErrorCode.EXECUTION_ERROR),  # execution error
        (_MalformedFareTool(), {"route_id": "R1"}, ToolErrorCode.MALFORMED_RESULT),  # malformed
    ],
)
def test_19_every_failure_mode_is_structured(tool: Tool, payload: dict[str, Any], code: ToolErrorCode) -> None:
    result = ToolRegistry([tool]).execute(tool.name, payload)
    assert result.success is False
    assert result.data is None  # a failure is never turned into successful mock data
    assert result.error is not None
    assert result.error.code == code.value
    assert result.data_source is DataSource.mock
    assert result.tool_name == tool.name
    assert result.message


# §22: the API surfaces the richer trace and the recommended route's legs — additive only.
def test_api_exposes_the_richer_mock_trace(client: Any) -> None:
    response = client.post("/api/route/plan", json={"raw_text": GOLDEN})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["recommendation"]["id"] == "R1"
    assert [leg["id"] for leg in body["legs"]] == ["R1-L1", "R1-L2", "R1-L3"]
    assert [leg["from"] for leg in body["legs"]] == [
        "Colombo Fort",
        "Pettah bus halt",
        "Colombo Fort Station",
    ]
    assert [leg["to"] for leg in body["legs"]][-1] == "Ella"
    assert all(leg["data_source"] == "mock" for leg in body["legs"])
    assert len(body["agent_actions"]) == 14
    assert _deduped([a["state"] for a in body["agent_actions"]]) == [s.value for s in _CANONICAL]
    assert all(a["data_source"] == "mock" for a in body["agent_actions"])
    # No field was added or removed from the A3/A6 response contract — except the one ADDITIVE A9
    # correlation field, ``request_id`` (A9 brief §10/§16: additive changes are allowed), which
    # matches the X-Request-Id response header.
    assert body["request_id"] == response.headers["x-request-id"]
    assert set(body) == {
        "status",
        "request",
        "recommendation",
        "legs",
        "alternatives",
        "agent_actions",
        "reasoning",
        "request_id",  # A9 additive (§10): the per-execution correlation id
    }

