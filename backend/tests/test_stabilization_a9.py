"""A9 stabilization regression tests (brief §20).

Locks in the nine guarantees A9 adds on top of A1–A8, all offline (mock mode, no API key):

* execution isolation on the shared, cached agent — no candidates/tool results/errors/actions leak
  between requests (3, 4 — brief §13);
* deterministic repeated requests under mock mode (5 — brief §12);
* deterministic action ordering and the additive ``kind`` contract (6 — brief §5);
* status ↔ last action ↔ recommendation consistency, incl. the clarification safe-stop (7 — §4/§6);
* tool-error propagation preserved and bounded (8, 9 — brief §8);
* the request identifier (10 — brief §10) and the 503 mapping for an unreachable live AI
  service (11, 12 — brief §7/§14);
* observability events present with no secrets and no raw traveller text (13 — brief §9);
* run metadata: iterations, executed tool calls, duration (14, 15 — brief §11), and the honest
  iteration-limit closing action (16 — brief §4);
* mock/live provenance honesty (17 — brief §14) and decision grounding (18–20 — brief §15).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from fastapi.testclient import TestClient

from app.agent.decision import DecisionEngine
from app.agent.orchestrator import RouteAgent, build_agent, get_agent
from app.config import get_settings
from app.logging_config import REQUEST_ID_HEADER, format_event, new_request_id
from app.schemas.route import ACTION_KINDS, AgentState, DataSource
from app.schemas.travel_request import TravelRequest
from app.services.ai.agent import (
    AgentDecision,
    AgentPlanner,
    MockAgentPlanner,
    PlannerContext,
    ToolCallRequest,
)
from app.services.ai.base import AIServiceUnavailableError
from app.services.ai.extraction import (
    MockTravelRequestExtractor,
    TravelRequestExtractor,
    get_extractor,
)
from app.tools.base import Tool, ToolAvailability, ToolErrorCode
from app.tools.capabilities import (
    DelayPredictionTool,
    FareEstimationTool,
    MockRouteSearchTool,
    RouteDetailsTool,
    SearchRoutesArgs,
)
from app.tools.executor import _MAX_TOOL_ERROR_DETAIL
from app.tools.registry import ToolRegistry, build_tools

GOLDEN = (
    "I am at Colombo Fort and need to reach Ella under a budget of LKR 2,000, "
    "but I have a heavy bag and don't want to walk."
)
_SEARCH = {"origin": "Colombo Fort", "destination": "Ella"}
_GOLDEN_ROUTE_IDS = {"R1", "R2", "R3"}


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
    """Always requests another *unique* call and never finalizes (iteration-limit scenario)."""

    def __init__(self) -> None:
        self._n = 0

    def next_decision(self, ctx: PlannerContext) -> AgentDecision:
        self._n += 1
        return _tool_call(
            "search_routes", {"origin": "Colombo Fort", "destination": f"Ella #{self._n}"}
        )


def _agent(planner: AgentPlanner, *, max_iterations: int | None = None) -> RouteAgent:
    return RouteAgent(
        tools=build_tools(get_settings()),
        engine=DecisionEngine(),
        planner=planner,
        max_iterations=max_iterations,
    )


class _RaisingSearchTool(Tool):
    """A ``search_routes`` stand-in whose implementation blows up with a verbose message."""

    name = "search_routes"
    availability = ToolAvailability.available
    args_model = SearchRoutesArgs

    def execute(self, **kwargs: Any) -> Any:
        raise RuntimeError("x" * 1000)  # deliberately verbose, like a real client error body


class _CorridorSensitiveSearchTool(Tool):
    """Raises for one corridor, delegates to the real mock search for everything else."""

    name = "search_routes"
    availability = ToolAvailability.available
    args_model = SearchRoutesArgs

    def __init__(self) -> None:
        self._delegate = MockRouteSearchTool()

    def execute(self, **kwargs: Any) -> Any:
        if (kwargs.get("origin") or "").strip() == "Nuwara Eliya":
            raise RuntimeError("upstream exploded")
        return self._delegate.execute(**kwargs)


class _UnavailableExtractor(TravelRequestExtractor):
    """Simulates a live extraction outage (A9 §7/§14)."""

    def extract(
        self, raw_text: str, hints: Optional[dict[str, Any]] = None
    ) -> TravelRequest:
        raise AIServiceUnavailableError("Model Studio could not be reached (ConnectError).")


class _UnavailableAgent:
    """Duck-typed ``RouteAgent`` replacement whose planner hits a live outage (A9 §7/§14)."""

    def run(
        self, request: TravelRequest, request_id: Optional[str] = None
    ) -> Any:
        raise AIServiceUnavailableError("Model Studio could not be reached (ConnectError).")


# --------------------------------------------------------------------------- #
# 1. The log formatter renders stable, parseable, greppable lines.
# --------------------------------------------------------------------------- #
def test_01_format_event_renders_stable_lines() -> None:
    line = format_event(
        "tool.executed",
        request_id="req_x",
        tool="search_routes",
        skipped=None,  # dropped
        executed=True,
        state=AgentState.COMPLETED,  # enums render as their wire value
    )
    assert line == (
        "event=tool.executed request_id=req_x tool=search_routes executed=true state=COMPLETED"
    )
    assert format_event("agent.start", origin="Colombo Fort") == (
        'event=agent.start origin="Colombo Fort"'  # whitespace is quoted, not split
    )


# --------------------------------------------------------------------------- #
# 2. A request id is short, unique enough, and carries no personal meaning.
# --------------------------------------------------------------------------- #
def test_02_new_request_id_is_short_unique_and_non_personal() -> None:
    first, second = new_request_id(), new_request_id()
    assert first != second
    assert re.fullmatch(r"req_[0-9a-f]{12}", first)
    assert re.fullmatch(r"req_[0-9a-f]{12}", second)


# --------------------------------------------------------------------------- #
# 3. Isolation: the shared cached agent leaks nothing between two runs (brief §13).
# --------------------------------------------------------------------------- #
def test_03_executions_are_isolated_on_the_shared_agent() -> None:
    agent = get_agent()  # the lru_cache'd singleton the API serves
    first = agent.run(_golden_request())
    second = agent.run(_golden_request())

    assert first.request_id != second.request_id
    assert first.actions is not second.actions
    assert first.errors is not second.errors
    # Distinct candidate OBJECTS per run — merging run 2's observations can never touch run 1.
    assert not ({id(c) for c in first.candidates} & {id(c) for c in second.candidates})
    assert {c.id for c in second.candidates} == _GOLDEN_ROUTE_IDS
    assert first.recommendation is not None and second.recommendation is not None
    assert first.recommendation.id == second.recommendation.id == "R1"


# --------------------------------------------------------------------------- #
# 4. Isolation: a run that recorded errors leaves no stale context for the next (§13/§24).
# --------------------------------------------------------------------------- #
def test_04_no_stale_context_after_a_failed_run() -> None:
    # ONE agent instance serves a failing run and then a good one, back to back.
    agent = RouteAgent(
        tools=ToolRegistry(
            [
                _CorridorSensitiveSearchTool(),
                FareEstimationTool(),
                DelayPredictionTool(),
                RouteDetailsTool(),
            ]
        ),
        engine=DecisionEngine(),
        planner=MockAgentPlanner(),
    )
    unknown = TravelRequest(origin="Nuwara Eliya", destination="Jaffna").refresh_clarification()
    assert unknown.clarification_required is False
    failed = agent.run(unknown)
    assert failed.errors  # the upstream failure was recorded honestly
    assert failed.recommendation is None

    clean = agent.run(_golden_request())
    assert clean.errors == []  # nothing leaked from the failed run
    assert clean.recommendation is not None and clean.recommendation.id == "R1"
    assert {c.id for c in clean.candidates} == _GOLDEN_ROUTE_IDS
    assert clean.request_id != failed.request_id


# --------------------------------------------------------------------------- #
# 5. Determinism: same request + same mock data → same decision & trace (brief §12).
# --------------------------------------------------------------------------- #
def test_05_repeated_identical_requests_are_deterministic() -> None:
    agent = get_agent()
    first = agent.run(_golden_request())
    second = agent.run(_golden_request())

    def signature(context: Any) -> list[tuple[Any, ...]]:
        # Volatile fields (request_id, timestamps, durations) are deliberately excluded.
        return [
            (
                a.seq,
                a.state,
                a.kind,
                a.label,
                a.status,
                a.tool_call.name if a.tool_call else None,
                a.tool_call.error_code if a.tool_call else None,
            )
            for a in context.actions
        ]

    assert signature(first) == signature(second)
    assert first.reasoning == second.reasoning
    assert first.recommendation == second.recommendation
    assert [leg.id for leg in first.legs] == [leg.id for leg in second.legs]
    assert first.visited_states == second.visited_states


# --------------------------------------------------------------------------- #
# 6. Action ordering is deterministic; every action carries a valid kind (brief §5).
# --------------------------------------------------------------------------- #
def test_06_action_ordering_and_kinds_are_deterministic() -> None:
    context = build_agent(get_settings()).run(_golden_request())
    assert [a.seq for a in context.actions] == list(range(1, len(context.actions) + 1))
    stamps = [a.timestamp for a in context.actions]
    assert all(stamp is not None for stamp in stamps)
    assert stamps == sorted(stamps)  # never out of order
    assert {a.kind for a in context.actions} <= ACTION_KINDS
    assert context.actions[0].kind == "understanding"
    assert context.actions[-1].kind == "completion"
    # Every action carrying a tool call is a tool_call kind — one generic consumer rule.
    assert all(a.kind == "tool_call" for a in context.actions if a.tool_call is not None)


# --------------------------------------------------------------------------- #
# 7. Status ↔ last action ↔ recommendation agree; clarification stops safely (§4/§6).
# --------------------------------------------------------------------------- #
def test_07_state_response_and_recommendation_stay_consistent(client: TestClient) -> None:
    response = client.post("/api/route/plan", json={"raw_text": GOLDEN})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["agent_actions"][-1]["state"] == body["status"]
    assert body["agent_actions"][-1]["kind"] == "completion"
    assert body["recommendation"] is not None

    # Clarification: a safe stop in UNDERSTANDING — no decision, no fabricated route.
    response = client.post("/api/route/plan", json={"raw_text": "I need to reach Ella."})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "UNDERSTANDING"
    assert body["agent_actions"][-1]["state"] == "UNDERSTANDING"
    assert body["agent_actions"][-1]["kind"] == "clarification"
    assert body["recommendation"] is None
    assert body["legs"] == []


# --------------------------------------------------------------------------- #
# 8. A verbose tool exception is bounded before it reaches the user-facing trace (§8).
# --------------------------------------------------------------------------- #
def test_08_tool_error_detail_is_bounded() -> None:
    result = ToolRegistry([_RaisingSearchTool()]).execute("search_routes", _SEARCH)
    assert result.success is False
    assert result.error is not None
    assert result.error.code == ToolErrorCode.EXECUTION_ERROR.value
    # "Tool 'search_routes' failed: " + at most 160 chars + an ellipsis — never a 1000-char body.
    assert len(result.message) <= len("Tool 'search_routes' failed: ") + _MAX_TOOL_ERROR_DETAIL + 1
    assert result.message.endswith("…")
    assert result.data_source is DataSource.mock


# --------------------------------------------------------------------------- #
# 9. A tool failure propagates through the API unchanged in meaning (brief §8).
# --------------------------------------------------------------------------- #
def test_09_tool_error_propagates_to_the_api_trace(client: TestClient) -> None:
    raising_agent = RouteAgent(
        tools=ToolRegistry([_RaisingSearchTool()]), engine=DecisionEngine()
    )
    client.app.dependency_overrides[get_agent] = lambda: raising_agent
    try:
        response = client.post("/api/route/plan", json={"raw_text": GOLDEN})
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 200  # a tool failure degrades honestly, never a 5xx
    body = response.json()
    tool_actions = [a for a in body["agent_actions"] if a.get("tool_call")]
    assert tool_actions[0]["status"] == "error"
    assert tool_actions[0]["tool_call"]["error_code"] == "EXECUTION_ERROR"
    assert tool_actions[0]["tool_call"]["data_source"] == "mock"
    assert body["recommendation"] is None  # nothing was fabricated past the failure


# --------------------------------------------------------------------------- #
# 10. The response body and the X-Request-Id header carry the same correlation id (§10).
# --------------------------------------------------------------------------- #
def test_10_response_and_header_share_one_request_id(client: TestClient) -> None:
    first = client.post("/api/route/plan", json={"raw_text": GOLDEN})
    second = client.post("/api/route/plan", json={"raw_text": GOLDEN})
    assert first.status_code == 200 and second.status_code == 200
    assert first.headers[REQUEST_ID_HEADER.lower()] == first.json()["request_id"]
    assert second.headers[REQUEST_ID_HEADER.lower()] == second.json()["request_id"]
    assert first.json()["request_id"] != second.json()["request_id"]
    assert re.fullmatch(r"req_[0-9a-f]{12}", first.json()["request_id"])


# --------------------------------------------------------------------------- #
# 11/12. An unreachable live AI service is a distinguishable, retryable 503 (§7/§14).
# --------------------------------------------------------------------------- #
def test_11_extraction_outage_maps_to_503(client: TestClient) -> None:
    client.app.dependency_overrides[get_extractor] = _UnavailableExtractor
    try:
        response = client.post("/api/route/plan", json={"raw_text": GOLDEN})
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "ERROR"
    assert body["error"]["code"] == "service_unavailable"
    assert body["error"]["retryable"] is True
    assert "could not be reached" in body["error"]["message"]


def test_12_planner_outage_maps_to_503(client: TestClient) -> None:
    client.app.dependency_overrides[get_agent] = _UnavailableAgent
    try:
        response = client.post("/api/route/plan", json={"raw_text": GOLDEN})
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "ERROR"
    assert body["error"]["code"] == "service_unavailable"
    assert body["error"]["retryable"] is True


# --------------------------------------------------------------------------- #
# 13. Observability: the §9 events fire, correlated, with no secrets or raw text (§9).
# --------------------------------------------------------------------------- #
def test_13_logs_carry_the_events_and_no_secrets(
    client: TestClient, caplog: Any
) -> None:
    marker = "seekrit-token-9f8d7c6b"  # must never appear in any log line
    with caplog.at_level(logging.INFO):
        response = client.post("/api/route/plan", json={"raw_text": GOLDEN + f" (ref {marker})"})
    assert response.status_code == 200

    rendered = "\n".join(record.getMessage() for record in caplog.records)
    for event in (
        "event=request.received",
        "event=agent.start",
        "event=travel_request.received",
        "event=tool.selected",
        "event=tool.executed",
        "event=decision.completed",
        "event=agent.completed",
        "event=plan.responded",
    ):
        assert event in rendered
    # The correlation id threads the whole run together.
    request_id = response.json()["request_id"]
    assert f"request_id={request_id}" in rendered
    # Never a credential, never the traveller's raw free text.
    assert marker not in rendered
    assert "MODEL_STUDIO_API_KEY" not in rendered


# --------------------------------------------------------------------------- #
# 14. Run metadata reports the bounded work actually done (brief §11).
# --------------------------------------------------------------------------- #
def test_14_run_metadata_reports_bounded_work() -> None:
    context = build_agent(get_settings()).run(_golden_request(), request_id="req_test_fixed")
    assert context.request_id == "req_test_fixed"  # the caller's id wins when supplied
    assert context.iteration_count >= 1
    tool_actions = [a for a in context.actions if a.kind == "tool_call"]
    assert context.tool_call_count == len(tool_actions)  # golden run: no suppressed duplicates
    assert context.duration_ms is not None and context.duration_ms >= 0


# --------------------------------------------------------------------------- #
# 15. A suppressed duplicate never reached the tool layer, so it is not counted (§11/§18).
# --------------------------------------------------------------------------- #
def test_15_suppressed_duplicate_is_not_counted_as_a_call() -> None:
    planner = _ScriptedPlanner(
        [_tool_call("search_routes", _SEARCH), _tool_call("search_routes", _SEARCH), _FINAL]
    )
    context = _agent(planner).run(_golden_request())
    tool_actions = [a for a in context.actions if a.kind == "tool_call"]
    assert len(tool_actions) == 2  # executed + suppressed — both traced honestly
    assert tool_actions[1].tool_call is not None
    assert tool_actions[1].tool_call.error_code == "REPEATED_CALL"
    assert context.tool_call_count == 1


# --------------------------------------------------------------------------- #
# 16. Iteration limit: the run completes safely and the closing action is honest (§4).
# --------------------------------------------------------------------------- #
def test_16_iteration_limit_closing_action_is_honest() -> None:
    context = _agent(_LoopingPlanner(), max_iterations=3).run(_golden_request())
    assert context.state is AgentState.COMPLETED  # the documented A5 contract for this path
    assert context.recommendation is None  # nothing fabricated
    assert any("iteration" in e.lower() for e in context.errors)
    closing = context.actions[-1]
    assert closing.kind == "completion"
    assert closing.status == "error"  # the trace never claims success for a stopped run
    assert context.iteration_count == 3


# --------------------------------------------------------------------------- #
# 17. Mock mode labels itself honestly everywhere (brief §14).
# --------------------------------------------------------------------------- #
def test_17_mock_mode_provenance_is_honest() -> None:
    planner = MockAgentPlanner()
    assert planner.model == "mock-qwen"
    assert planner.data_source == "mock"

    context = build_agent(get_settings()).run(_golden_request())
    planning = next(a for a in context.actions if a.kind == "planning")
    assert planning.data_source is DataSource.mock  # never claims a live model planned this
    assert context.data_source is DataSource.mock
    assert all(
        a.tool_call.data_source is DataSource.mock
        for a in context.actions
        if a.tool_call is not None
    )


# --------------------------------------------------------------------------- #
# 18/19. The recommendation is grounded in tool candidates, never in planner text (§15).
# --------------------------------------------------------------------------- #
def test_18_recommendation_is_grounded_in_tool_candidates() -> None:
    context = build_agent(get_settings()).run(_golden_request())
    assert context.recommendation is not None
    by_id = {c.id: c for c in context.candidates}
    assert context.recommendation.id in by_id  # a route the search tool actually returned
    candidate = by_id[context.recommendation.id]
    assert context.recommendation.total_fare_lkr == candidate.total_fare_lkr
    assert context.recommendation.total_duration_min == candidate.total_duration_min


def test_19_planner_text_cannot_fabricate_a_route() -> None:
    planner = _ScriptedPlanner(
        [
            _tool_call("search_routes", _SEARCH),
            AgentDecision(
                kind="final",
                content="Honestly, route R999 direct helicopter is the best option.",
                data_source="mock",
            ),
        ]
    )
    context = _agent(planner).run(_golden_request())
    assert context.recommendation is not None
    assert context.recommendation.id in _GOLDEN_ROUTE_IDS  # R999 was never fabricated
    assert "R999" not in (context.reasoning or "")


# --------------------------------------------------------------------------- #
# 20. An unknown corridor ends COMPLETED + no recommendation + an honest trace (§6/§24).
# --------------------------------------------------------------------------- #
def test_20_unknown_corridor_recommends_nothing() -> None:
    request = TravelRequest(origin="Nuwara Eliya", destination="Jaffna").refresh_clarification()
    assert request.clarification_required is False
    context = build_agent(get_settings()).run(request)
    assert context.state is AgentState.COMPLETED
    assert context.recommendation is None
    assert context.candidates == []
    assert context.legs == []
    assert context.reasoning  # an honest explanation, not silence
    search_actions = [
        a
        for a in context.actions
        if a.tool_call is not None and a.tool_call.name == "search_routes"
    ]
    assert search_actions  # the corridor was genuinely searched
    # An empty corridor is honest SUCCESS with empty data — never an error and never a
    # fabricated candidate (the ``ROUTE_NOT_FOUND`` code is reserved for route-scoped lookups).
    assert search_actions[0].status == "done"
    assert "No mock candidate data" in (search_actions[0].detail or "")
