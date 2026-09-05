"""A5 Qwen tool-calling adapter tests (brief §21, parsing 1–8 + mock 16–18 + live 19–20).

These exercise :mod:`app.services.ai.agent` in isolation — the smallest clean seam that turns a
model response into a normalized :class:`AgentDecision` and offers tools to the model. They prove:

* a valid tool call / valid args / multiple tool calls are parsed faithfully (1–3);
* a final answer with no tool call is recognized (4);
* malformed tool calls (bad JSON args, empty name, non-dict args) degrade safely, never crash (5,7);
* an unknown tool name is normalized (passed through for the loop to reject), and only AVAILABLE
  tools are exposed to the model so it cannot keep calling a stub (6,8 — brief §6);
* a failed :class:`ToolResult` is fed back **verbatim** — never rewritten as a success (brief §11);
* the deterministic mock planner simulates multi-step selection and is always labelled ``mock``
  (16–18 — brief §13);
* real Qwen tool calling is exercised only when ``MODEL_STUDIO_API_KEY`` is present, and is
  honestly SKIPPED (not faked) otherwise (19–20 — brief §12/§21).
"""

from __future__ import annotations

import json
import os
from typing import Any

import pytest

from app.config import Settings, get_settings
from app.schemas.route import DataSource
from app.services.ai.agent import (
    AgentDecision,
    MockAgentPlanner,
    PlannerContext,
    QwenAgentPlanner,
    ToolCallRequest,
    assistant_tool_call_message,
    build_agent_messages,
    build_planner,
    build_tool_definitions,
    tool_result_message,
)
from app.services.ai.base import AIResponse, AIClient, ConnectivityResult
from app.tools.base import ToolErrorCode, ToolResult
from app.tools.registry import build_tools

GOLDEN = (
    "I am at Colombo Fort and need to reach Ella under a budget of LKR 2,000, "
    "but I have a heavy bag and don't want to walk."
)

_LIVE_KEY = os.getenv("MODEL_STUDIO_API_KEY")
_SKIP_LIVE = "MODEL_STUDIO_API_KEY not set - real Qwen tool calling NOT verified (mock only)."


# --------------------------------------------------------------------------- #
# Test doubles
# --------------------------------------------------------------------------- #
class _ScriptedClient(AIClient):
    """Returns a pre-baked :class:`AIResponse` so planner parsing is tested in isolation."""

    def __init__(self, response: AIResponse) -> None:
        self._response = response
        self.last_kwargs: dict[str, Any] = {}

    def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> AIResponse:
        self.last_kwargs = kwargs
        return self._response

    def check_connectivity(self) -> ConnectivityResult:
        return ConnectivityResult(ok=True, mode="live", model="test", detail="", latency_ms=0.0)


def _tool_call_response(*calls: dict[str, Any], content: str = "") -> AIResponse:
    """A raw chat/completions response whose first choice carries ``tool_calls``."""
    return AIResponse(
        text=content,
        model="qwen-max",
        data_source="live",
        usage={},
        raw={"choices": [{"message": {"content": content, "tool_calls": list(calls)}}]},
    )


def _final_response(content: str) -> AIResponse:
    """A raw response with plain content and no tool calls (a final answer)."""
    return AIResponse(
        text=content,
        model="qwen-max",
        data_source="live",
        usage={},
        raw={"choices": [{"message": {"content": content}}]},
    )


def _ctx() -> PlannerContext:
    registry = build_tools(get_settings())
    snapshot = {"origin": "Colombo Fort", "destination": "Ella"}
    return PlannerContext(
        messages=build_agent_messages(snapshot),
        tools=build_tool_definitions(registry),
        travel_request=snapshot,
        tool_names=registry.names(),
        steps_taken=0,
    )


# --------------------------------------------------------------------------- #
# Parsing (brief §21, 1–8)
# --------------------------------------------------------------------------- #
# 1. A valid tool call is parsed into a normalized decision.
def test_parses_a_valid_tool_call() -> None:
    response = _tool_call_response(
        {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "search_routes",
                "arguments": json.dumps({"origin": "Colombo Fort", "destination": "Ella"}),
            },
        }
    )
    decision = QwenAgentPlanner(_ScriptedClient(response)).next_decision(_ctx())
    assert decision.kind == "tool_call"
    assert decision.is_tool_call is True
    assert decision.data_source == "live"
    assert len(decision.tool_calls) == 1
    call = decision.tool_calls[0]
    assert call.name == "search_routes"
    assert call.arguments == {"origin": "Colombo Fort", "destination": "Ella"}
    assert call.id == "call_1"


# 2. Arguments supplied as a dict (some providers) are accepted as-is.
def test_parses_arguments_supplied_as_a_dict() -> None:
    response = _tool_call_response(
        {
            "id": "c",
            "type": "function",
            "function": {
                "name": "search_routes",
                "arguments": {"origin": "Kandy", "destination": "Ella"},
            },
        }
    )
    decision = QwenAgentPlanner(_ScriptedClient(response)).next_decision(_ctx())
    assert decision.tool_calls[0].arguments == {"origin": "Kandy", "destination": "Ella"}


# 3. Multiple tool calls in one response are preserved in order.
def test_parses_multiple_tool_calls_in_order() -> None:
    response = _tool_call_response(
        {"id": "c1", "function": {"name": "search_routes", "arguments": "{}"}},
        {"id": "c2", "function": {"name": "get_fare_estimate", "arguments": "{}"}},
    )
    decision = QwenAgentPlanner(_ScriptedClient(response)).next_decision(_ctx())
    assert decision.is_tool_call is True
    assert [c.name for c in decision.tool_calls] == ["search_routes", "get_fare_estimate"]
    assert [c.id for c in decision.tool_calls] == ["c1", "c2"]


# 4. A final answer with no tool call is recognized as ``final``.
def test_final_answer_without_tool_call() -> None:
    response = _final_response("I have enough information to decide.")
    decision = QwenAgentPlanner(_ScriptedClient(response)).next_decision(_ctx())
    assert decision.kind == "final"
    assert decision.is_tool_call is False
    assert decision.tool_calls == []
    assert decision.content == "I have enough information to decide."


# 5. A malformed tool call (invalid JSON arguments) degrades to ``{}`` — never a crash.
def test_malformed_arguments_degrade_to_empty_dict() -> None:
    response = _tool_call_response(
        {"id": "c", "function": {"name": "search_routes", "arguments": "{not valid json"}}
    )
    decision = QwenAgentPlanner(_ScriptedClient(response)).next_decision(_ctx())
    assert decision.kind == "tool_call"
    # Empty args are handed to the loop, whose validation rejects them with INVALID_INPUT (§17).
    assert decision.tool_calls[0].arguments == {}


# 5b. A tool call with an empty name is normalized (the loop rejects it as UNKNOWN_TOOL).
def test_empty_tool_name_is_normalized_not_crashing() -> None:
    response = _tool_call_response({"id": "c", "function": {"name": "", "arguments": "{}"}})
    decision = QwenAgentPlanner(_ScriptedClient(response)).next_decision(_ctx())
    assert decision.tool_calls[0].name == ""


# 6. An unknown tool name is passed through verbatim (the loop, not the adapter, rejects it).
def test_unknown_tool_name_is_passed_through() -> None:
    response = _tool_call_response(
        {"id": "c", "function": {"name": "launch_missiles", "arguments": "{}"}}
    )
    decision = QwenAgentPlanner(_ScriptedClient(response)).next_decision(_ctx())
    assert decision.tool_calls[0].name == "launch_missiles"


# 7. Non-dict/non-str arguments (e.g. a list or number) normalize to ``{}``.
@pytest.mark.parametrize("bad", [["not", "a", "dict"], 42, None, True])
def test_non_object_arguments_normalize_to_empty_dict(bad: Any) -> None:
    response = _tool_call_response({"id": "c", "function": {"name": "search_routes", "arguments": bad}})
    decision = QwenAgentPlanner(_ScriptedClient(response)).next_decision(_ctx())
    assert decision.tool_calls[0].arguments == {}


# 8. Only AVAILABLE tools are exposed to the model, so a stub can never be called repeatedly (§6).
# A7 (brief §12): the three new mock intelligence tools join the definitions automatically because
# they are derived from ToolRegistry.list_available() — the list is never hard-coded here.
def test_build_tool_definitions_exposes_only_available_tools() -> None:
    registry = build_tools(get_settings())
    definitions = build_tool_definitions(registry)
    names = {d["function"]["name"] for d in definitions}
    # The four AVAILABLE mock data tools are exposed; the Workstream-C stubs are excluded.
    assert names == {
        "search_routes",
        "get_fare_estimate",
        "get_delay_prediction",
        "get_route_details",
    }
    assert names == set(registry.list_available())  # derived, never duplicated (§12)
    assert "check_availability" not in names and "prepare_booking" not in names

    search = next(d for d in definitions if d["function"]["name"] == "search_routes")
    assert search["type"] == "function"
    assert search["function"]["description"]
    params = search["function"]["parameters"]
    assert params["type"] == "object"
    assert "origin" in params["properties"] and "destination" in params["properties"]
    assert {"origin", "destination"} <= set(params.get("required", []))

    # A7: each intelligence tool advertises the route_id argument the model must supply.
    fare = next(d for d in definitions if d["function"]["name"] == "get_fare_estimate")
    assert "route_id" in fare["function"]["parameters"]["properties"]
    assert "route_id" in fare["function"]["parameters"].get("required", [])


# --------------------------------------------------------------------------- #
# Transcript builders (brief §11/§16) — a failure is fed back verbatim
# --------------------------------------------------------------------------- #
def test_tool_result_message_feeds_a_failure_verbatim() -> None:
    failure = ToolResult.failure(
        "get_fare_estimate", ToolErrorCode.NOT_IMPLEMENTED, "'get_fare_estimate' is not built yet."
    )
    message = tool_result_message("call_9", failure)
    assert message["role"] == "tool"
    assert message["tool_call_id"] == "call_9"
    payload = json.loads(message["content"])
    assert payload["success"] is False  # §11: a failure is NEVER rewritten as a success
    assert payload["error"]["code"] == "NOT_IMPLEMENTED"


def test_assistant_tool_call_message_keeps_stable_ids() -> None:
    decision = AgentDecision(
        kind="tool_call",
        tool_calls=[
            ToolCallRequest(name="search_routes", arguments={"origin": "A", "destination": "B"}, id="call_1")
        ],
        content="gathering",
    )
    message = assistant_tool_call_message(decision)
    assert message["role"] == "assistant"
    assert message["content"] == "gathering"
    tool_call = message["tool_calls"][0]
    assert tool_call["id"] == "call_1"
    assert tool_call["type"] == "function"
    assert tool_call["function"]["name"] == "search_routes"
    assert json.loads(tool_call["function"]["arguments"]) == {"origin": "A", "destination": "B"}


def test_build_agent_messages_carries_system_and_context() -> None:
    messages = build_agent_messages(
        {"origin": "Colombo Fort", "destination": "Ella", "budget": 2000}, raw_text=GOLDEN
    )
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "Colombo Fort" in messages[1]["content"]
    assert GOLDEN in messages[1]["content"]  # the original request is available to the model


# --------------------------------------------------------------------------- #
# Deterministic mock planner (brief §21, 16–18)
# --------------------------------------------------------------------------- #
# 16. The mock simulates the canonical multi-step flow: gather candidates, then decide.
def test_mock_planner_requests_search_then_finalizes() -> None:
    planner = MockAgentPlanner()
    registry = build_tools(get_settings())
    snapshot = {"origin": "Colombo Fort", "destination": "Ella"}

    first = planner.next_decision(
        PlannerContext(
            messages=[], tools=[], travel_request=snapshot, tool_names=registry.names(), steps_taken=0
        )
    )
    assert first.kind == "tool_call"
    assert first.tool_calls[0].name == "search_routes"
    assert first.tool_calls[0].arguments == snapshot
    assert first.data_source == "mock"
    assert first.model == "mock-qwen"

    second = planner.next_decision(
        PlannerContext(
            messages=[], tools=[], travel_request=snapshot, tool_names=registry.names(), steps_taken=1
        )
    )
    assert second.kind == "final"
    assert second.is_tool_call is False


# 16b. The mock is deterministic: the same context always yields the same decision.
def test_mock_planner_is_deterministic() -> None:
    planner = MockAgentPlanner()
    registry = build_tools(get_settings())
    ctx = PlannerContext(
        messages=[],
        tools=[],
        travel_request={"origin": "X", "destination": "Y"},
        tool_names=registry.names(),
        steps_taken=0,
    )
    a = planner.next_decision(ctx)
    b = planner.next_decision(ctx)
    assert a.tool_calls[0].name == b.tool_calls[0].name == "search_routes"
    assert a.tool_calls[0].arguments == b.tool_calls[0].arguments


# 17. When search_routes is not a registered capability, the mock has nothing to gather → final.
def test_mock_planner_finalizes_when_search_not_registered() -> None:
    decision = MockAgentPlanner().next_decision(
        PlannerContext(
            messages=[],
            tools=[],
            travel_request={"origin": "X", "destination": "Y"},
            tool_names=["get_fare_estimate"],  # search_routes absent
            steps_taken=0,
        )
    )
    assert decision.kind == "final"


# 18. Mock decisions are always labelled mock and never claim a real model decided (§13).
def test_mock_planner_is_labelled_mock() -> None:
    decision = MockAgentPlanner().next_decision(
        PlannerContext(messages=[], tools=[], travel_request={}, tool_names=[], steps_taken=5)
    )
    assert decision.data_source == "mock"
    assert decision.model == "mock-qwen"


def test_build_planner_selects_mock_without_a_key() -> None:
    settings = Settings(_env_file=None, model_studio_api_key="")
    assert settings.ai_enabled is False
    assert isinstance(build_planner(settings), MockAgentPlanner)


def test_build_planner_selects_qwen_with_a_key() -> None:
    settings = Settings(_env_file=None, model_studio_api_key="test-key")
    assert settings.ai_enabled is True
    assert isinstance(build_planner(settings), QwenAgentPlanner)


# --------------------------------------------------------------------------- #
# Real Qwen (brief §21, 19–20) — live only, honestly skipped without a key
# --------------------------------------------------------------------------- #
# 19. A live round trip normalizes the model's decision (tool call or final) as ``live``.
@pytest.mark.skipif(not _LIVE_KEY, reason=_SKIP_LIVE)
def test_live_qwen_tool_calling_round_trip() -> None:
    settings = Settings(_env_file=None)
    planner = build_planner(settings)
    registry = build_tools(settings)
    snapshot = {"origin": "Colombo Fort", "destination": "Ella", "budget": 2000}
    decision = planner.next_decision(
        PlannerContext(
            messages=build_agent_messages(snapshot, raw_text=GOLDEN),
            tools=build_tool_definitions(registry),
            travel_request=snapshot,
            tool_names=registry.names(),
            steps_taken=0,
        )
    )
    assert decision.data_source == "live"
    assert decision.kind in ("tool_call", "final")
    if decision.is_tool_call:
        # A live model may only call a registered tool (the loop would reject anything else).
        assert decision.tool_calls[0].name in registry.names()


# 20. Even with live Qwen selecting tools, the ROUTE figures stay mock (honesty, §15/§16).
@pytest.mark.skipif(not _LIVE_KEY, reason=_SKIP_LIVE)
def test_live_agent_run_keeps_route_data_mock() -> None:
    from app.agent.orchestrator import build_agent
    from app.schemas.route import AgentState
    from app.services.ai.extraction import MockTravelRequestExtractor

    settings = Settings(_env_file=None)
    context = build_agent(settings).run(MockTravelRequestExtractor().extract(GOLDEN, {}))
    assert context.state is AgentState.COMPLETED
    if context.recommendation is not None:
        assert context.recommendation.data_source is DataSource.mock
    assert all(c.data_source is DataSource.mock for c in context.candidates)
