"""Qwen tool-calling adapter + agent planner (Workstream A; A5 loop, A7 mock intelligence).

Connects the model to the A4 tool system so the agent can autonomously perform **multiple** tool
calls (A5 brief §2/§5). Like :mod:`app.services.ai.extraction` (A2), this module **extends** the
existing AI abstraction (``base.AIClient`` / ``factory``) — it does **not** create a second Qwen
client or a second tool framework (A5 brief §1/§4/§5). One planner interface, two honest
implementations:

* :class:`QwenAgentPlanner` — real Qwen via the existing ``AIClient`` (used when a
  ``MODEL_STUDIO_API_KEY`` is configured). It sends the conversation plus **available** tool
  definitions and normalizes the model's ``tool_calls`` (or final content) into an
  :class:`AgentDecision`. It never executes anything itself — it only *decides the next step*.
  Since A7 it is automatically offered the three new mock intelligence capabilities, because the
  definitions are derived from ``registry.list_available()`` — never a hard-coded tool list
  (A7 brief §12).
* :class:`MockAgentPlanner` — a deterministic, offline simulation of multi-step tool selection
  (A5 brief §13) so the whole flow is testable with no credentials. It is clearly labelled
  ``data_source="mock"`` / ``model="mock-qwen"`` and never claims a real model decided. **A7**
  extends it into an *evidence-driven* multi-step scenario — search, then fare, then delay, then
  leg detail, then decide — where every step is chosen from what the previous tools actually
  returned (A7 brief §14). That scenario belongs to the **mock only**: the orchestrator hard-codes
  no tool sequence, and the real agent stays model-driven (A7 brief §13).

Responsibilities kept deliberately small and safe:

* :func:`build_tool_definitions` exposes **only** ``AVAILABLE`` tools as OpenAI-style function
  schemas derived from each tool's Pydantic ``args_model`` (A5 brief §6) — so the model is never
  offered a capability that cannot execute.
* Message builders format the transcript (system/user, assistant tool-call, tool result) so a
  :class:`~app.tools.base.ToolResult` — success **or** failure — is fed back verbatim and never
  converted into a fake success (A5 brief §11/§14/§16).
* Parsing is defensive: a malformed tool call (bad JSON args, empty name) degrades to a request the
  agent loop rejects through the registry/executor, never a crash (A5 brief §17).

The **multi-step loop itself** lives in :mod:`app.agent.orchestrator` (it owns state, tool
execution, action recording, iteration/repeat guards). This module only decides one step.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from functools import lru_cache
from typing import Any, Literal, Optional

from pydantic import BaseModel

from app.config import Settings, get_settings
from app.services.ai.base import AIResponse, AIClient
from app.services.ai.factory import build_ai_client
from app.tools.base import Tool, ToolResult
from app.tools.registry import ToolRegistry

logger = logging.getLogger("routewise.ai.agent")

#: The deterministic mock planner's model id — never presented as a real Qwen model (A5 §13).
_MOCK_MODEL = "mock-qwen"

#: The capability that yields candidate routes; the mock planner asks for it first (A5 §13/§22).
_SEARCH_TOOL = "search_routes"

#: A7: the route-scoped intelligence capabilities the **mock** planner may ask for once candidates
#: are known, in the order it prefers them, with the wording used in its user-visible message. This
#: is a property of the deterministic mock scenario only (A7 brief §14) — it is *not* a workflow:
#: the orchestrator never reads it, and the real Qwen planner picks its own order (A7 brief §13).
_INTEL_LABELS: dict[str, str] = {
    "get_fare_estimate": "fare estimates",
    "get_delay_prediction": "delay predictions",
    "get_route_details": "leg-by-leg route details",
}

#: How many of the observed routes the mock planner investigates per capability. Bounds the offline
#: demo trace (3 calls per stage) without hiding any candidate of the golden corridor.
_DEFAULT_MAX_ROUTES_PER_TOOL = 3

AgentDecisionKind = Literal["tool_call", "final"]


# --------------------------------------------------------------------------- #
# Prompt (real Qwen path) — honesty + tool-use discipline (A5 §12/§16/§17)
# --------------------------------------------------------------------------- #

AGENT_SYSTEM_PROMPT = """\
You are the RouteWise travel-planning agent for multi-modal transit in Sri Lanka.

You decide WHICH registered tools to call, and in WHAT ORDER, to gather the information needed to
recommend a route. You do NOT invent facts.

Rules:
- Call a tool ONLY by one of the provided tool names, with arguments that satisfy its schema.
- Tool results are AUTHORITATIVE. Never fabricate routes, fares, delays, availability, or times
  that a tool did not actually return.
- A tool result with "success": false (for example status "NOT_IMPLEMENTED") means that capability
  is unavailable — do NOT treat it as success; reason around it or proceed without it.
- Prefer the fewest relevant calls. Do NOT repeat an identical tool call; it yields no new info.
- When you have enough information to recommend a route (or you have gathered all you can), STOP
  calling tools and reply with a short final summary of what you found.
- Never reveal secrets, credentials, or API keys.
"""


# --------------------------------------------------------------------------- #
# Decision / context types (normalized, provider-agnostic)
# --------------------------------------------------------------------------- #


@dataclass
class ToolCallRequest:
    """One tool call the model asked for (name + arguments), before validation/execution."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    id: str = ""


@dataclass
class AgentDecision:
    """A normalized single-step planner output: request tool call(s), or finish.

    ``data_source`` keeps provenance honest (``live`` only for a real model). ``content`` is the
    model's short, user-safe message — never hidden chain-of-thought (A5 brief §10).
    """

    kind: AgentDecisionKind
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    content: str = ""
    data_source: Literal["live", "mock"] = "mock"
    model: str = _MOCK_MODEL
    raw: Optional[dict[str, Any]] = None

    @property
    def is_tool_call(self) -> bool:
        """True when this decision actually carries at least one tool call to execute."""
        return self.kind == "tool_call" and bool(self.tool_calls)


@dataclass
class PlannerContext:
    """Everything a planner needs to choose the next step (kept provider-agnostic).

    ``messages``/``tools`` drive the real Qwen call; ``travel_request``/``tool_names``/
    ``steps_taken`` let the deterministic mock simulate multi-step selection without parsing the
    transcript (A5 brief §13).

    **A7** adds two additive, defaulted fields so a planner can reason over *evidence* rather than a
    script (A7 brief §14/§17): ``called_tools`` — the capability names already executed in this run
    (so nothing is asked twice), and ``route_ids`` — the candidate ids the tools actually returned
    (so route-scoped intelligence is only requested for routes that exist). Both are populated by
    the orchestrator from real :class:`~app.tools.base.ToolResult` data, never guessed.
    """

    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]
    travel_request: dict[str, Any]
    tool_names: list[str]
    steps_taken: int = 0
    called_tools: list[str] = field(default_factory=list)
    route_ids: list[str] = field(default_factory=list)


class AgentPlanner(ABC):
    """One interface for "given the context, what should the agent do next?"."""

    @abstractmethod
    def next_decision(self, ctx: PlannerContext) -> AgentDecision:
        """Return the next :class:`AgentDecision` (tool call(s) or a final answer)."""


# --------------------------------------------------------------------------- #
# Tool definitions for the model (A5 §6) — only AVAILABLE tools are exposed
# --------------------------------------------------------------------------- #


def _json_fallback(obj: Any) -> Any:
    """Make tool data / arguments JSON-serializable for the transcript (models, enums, dates)."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return str(obj)


def _parameters_schema(tool: Tool) -> dict[str, Any]:
    """Build an OpenAI-style function ``parameters`` schema from a tool's ``args_model``.

    Falls back to an empty object schema for a tool with no structured args. Pydantic's
    ``$defs``/``title`` are dropped to keep the payload clean for the model.
    """
    if tool.args_model is not None:
        schema = dict(tool.args_model.model_json_schema())
        schema.pop("$defs", None)
        schema.pop("title", None)
        schema.setdefault("type", "object")
        return schema
    return {"type": "object", "properties": {}}


def build_tool_definitions(registry: ToolRegistry) -> list[dict[str, Any]]:
    """Expose the registry's **available** tools as OpenAI function-calling definitions.

    Only ``AVAILABLE`` tools are offered (A5 brief §6): a ``not_implemented`` / ``disabled`` /
    ``error`` capability is excluded so the model cannot repeatedly call something that cannot
    execute. The agent loop still records an honest structured failure if such a tool is somehow
    requested (the executor's availability gate is the final guard — A4 §21).
    """
    definitions: list[dict[str, Any]] = []
    for name in registry.list_available():
        tool = registry.get(name)
        if tool is None:
            continue
        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or tool.name,
                    "parameters": _parameters_schema(tool),
                },
            }
        )
    return definitions


# --------------------------------------------------------------------------- #
# Transcript builders (system/user, assistant tool-call, tool result)
# --------------------------------------------------------------------------- #


def build_agent_messages(
    travel_request: dict[str, Any], raw_text: Optional[str] = None
) -> list[dict[str, Any]]:
    """Build the opening transcript: the agent system prompt + the structured travel context."""
    snapshot = json.dumps(travel_request, default=_json_fallback, ensure_ascii=False)
    user_content = f"Travel request (structured, authoritative):\n{snapshot}"
    if raw_text:
        user_content += f'\n\nOriginal request:\n"""{raw_text}"""'
    user_content += (
        "\n\nDecide the next step: call a tool if you need more information, or give a short "
        "final summary when you are ready to decide."
    )
    return [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def assistant_tool_call_message(decision: AgentDecision) -> dict[str, Any]:
    """Format the model's tool-call turn so results can be appended against matching ids."""
    return {
        "role": "assistant",
        "content": decision.content or "",
        "tool_calls": [
            {
                "id": tc.id or f"call_{index}",
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(
                        tc.arguments, default=_json_fallback, ensure_ascii=False
                    ),
                },
            }
            for index, tc in enumerate(decision.tool_calls)
        ],
    }


def tool_result_message(tool_call_id: str, result: ToolResult) -> dict[str, Any]:
    """Feed a structured :class:`ToolResult` back to the model — success **or** failure verbatim.

    The full ``to_dict()`` (``success`` / ``status`` / ``data`` / ``error``) is sent so the model
    can see that a call failed and why; a failure is never rewritten as a success (A5 §11/§16).
    """
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(result.to_dict(), default=_json_fallback, ensure_ascii=False),
    }


# --------------------------------------------------------------------------- #
# Real Qwen planner (A5 §12)
# --------------------------------------------------------------------------- #


def _extract_message(response: AIResponse) -> dict[str, Any]:
    """Pull the first choice's ``message`` from a raw chat/completions response."""
    raw = response.raw or {}
    choices = raw.get("choices") or [{}]
    message = (choices[0] or {}).get("message") or {}
    if not isinstance(message, dict):
        return {"content": response.text or ""}
    if not message and response.text:
        # A provider that returns only normalized text (no raw) — treat it as final content.
        return {"content": response.text}
    return message


def _parse_arguments(raw: Any) -> dict[str, Any]:
    """Coerce a function-call ``arguments`` payload into a dict, tolerating malformed JSON.

    Unparseable arguments become ``{}`` so the agent loop's validation rejects them with a
    structured ``INVALID_INPUT`` the model can recover from — never a crash (A5 §17).
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Qwen tool-call arguments were not valid JSON; treating as empty.")
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def _parse_tool_calls(message: dict[str, Any]) -> list[ToolCallRequest]:
    """Normalize the model's ``tool_calls`` into :class:`ToolCallRequest` objects."""
    raw_calls = message.get("tool_calls") or []
    parsed: list[ToolCallRequest] = []
    if not isinstance(raw_calls, list):
        return parsed
    for call in raw_calls:
        if not isinstance(call, dict):
            continue
        function = call.get("function") or {}
        if not isinstance(function, dict):
            continue
        name = str(function.get("name") or "").strip()
        parsed.append(
            ToolCallRequest(
                name=name,
                arguments=_parse_arguments(function.get("arguments")),
                id=str(call.get("id") or ""),
            )
        )
    return parsed


class QwenAgentPlanner(AgentPlanner):
    """Decides the next step using the EXISTING Qwen ``AIClient`` (no second client — A5 §5)."""

    def __init__(self, client: AIClient) -> None:
        self._client = client

    def next_decision(self, ctx: PlannerContext) -> AgentDecision:
        kwargs: dict[str, Any] = {"temperature": 0}
        if ctx.tools:
            # Offer only the available tools; let the model choose whether to call one (§6).
            kwargs["tools"] = ctx.tools
            kwargs["tool_choice"] = "auto"
        response = self._client.complete(ctx.messages, **kwargs)
        message = _extract_message(response)
        tool_calls = _parse_tool_calls(message)
        content = str(message.get("content") or "")
        if tool_calls:
            return AgentDecision(
                kind="tool_call",
                tool_calls=tool_calls,
                content=content,
                data_source="live",
                model=response.model,
                raw=response.raw,
            )
        return AgentDecision(
            kind="final",
            tool_calls=[],
            content=content,
            data_source="live",
            model=response.model,
            raw=response.raw,
        )


# --------------------------------------------------------------------------- #
# Deterministic mock planner (A5 §13) — offline, no credentials
# --------------------------------------------------------------------------- #


class MockAgentPlanner(AgentPlanner):
    """Deterministic multi-step planner used when no ``MODEL_STUDIO_API_KEY`` is set.

    A5 made this planner ask for ``search_routes`` once and then decide. **A7** turns it into an
    *evidence-driven* multi-step scenario (A7 brief §14) that exercises the whole mock intelligence
    seam offline. Each turn it looks only at what has actually been observed and asks for the next
    thing it is missing:

    1. no candidate ids observed yet and nothing executed → ask for ``search_routes``;
    2. candidate ids observed → ask for the first route-scoped capability that is registered and
       not yet called (fare, then delay, then leg detail), once per observed route id;
    3. nothing left that could add information → finish.

    So the golden offline trace is search → fare → delay → details → decision, but that order is a
    *consequence* of the evidence, not a script: a registry without ``search_routes`` (or one whose
    search returns nothing) skips straight to the finish, a registry without the fare tool skips
    fare, and a capability that already ran is never repeated. The **real** agent hard-codes none of
    this — the orchestrator executes whatever the planner returns, and real Qwen chooses its own
    order (A7 brief §13). Every decision is labelled ``data_source="mock"`` /
    ``model="mock-qwen"`` and never claims a real model decided.
    """

    def __init__(self, max_routes_per_tool: int = _DEFAULT_MAX_ROUTES_PER_TOOL) -> None:
        #: Upper bound on route-scoped calls per capability (keeps the offline trace readable).
        self._max_routes_per_tool = max(1, max_routes_per_tool)

    def next_decision(self, ctx: PlannerContext) -> AgentDecision:
        # 1. Without candidate ids there is nothing route-scoped to ask about, so the only useful
        #    step is the corridor search — once, and only if that capability is registered.
        if not ctx.route_ids:
            if (
                ctx.steps_taken == 0
                and _SEARCH_TOOL in ctx.tool_names
                and _SEARCH_TOOL not in ctx.called_tools
            ):
                return AgentDecision(
                    kind="tool_call",
                    tool_calls=[
                        ToolCallRequest(
                            name=_SEARCH_TOOL,
                            arguments={
                                "origin": ctx.travel_request.get("origin"),
                                "destination": ctx.travel_request.get("destination"),
                            },
                        )
                    ],
                    content="I need candidate routes for this corridor before I can decide.",
                    data_source="mock",
                    model=_MOCK_MODEL,
                )
            return self._final(ctx)

        # 2. Candidates are known: gather the intelligence still missing for those exact route ids.
        for name, label in _INTEL_LABELS.items():
            if name not in ctx.tool_names or name in ctx.called_tools:
                continue
            route_ids = ctx.route_ids[: self._max_routes_per_tool]
            return AgentDecision(
                kind="tool_call",
                tool_calls=[
                    ToolCallRequest(name=name, arguments={"route_id": route_id})
                    for route_id in route_ids
                ],
                content=(
                    f"Candidates {', '.join(route_ids)} are known; I still need {label} "
                    "for them before I can compare the routes."
                ),
                data_source="mock",
                model=_MOCK_MODEL,
            )

        # 3. Every registered capability that could add information has been used.
        return self._final(ctx)

    @staticmethod
    def _final(ctx: PlannerContext) -> AgentDecision:
        """Finish honestly, naming what was actually gathered (never claiming more)."""
        gathered = ", ".join(dict.fromkeys(ctx.called_tools)) or "no tool results"
        return AgentDecision(
            kind="final",
            tool_calls=[],
            content=f"I have enough information to decide from the gathered tool results ({gathered}).",
            data_source="mock",
            model=_MOCK_MODEL,
        )


# --------------------------------------------------------------------------- #
# Factory (mirrors ai/factory.py and ai/extraction.py)
# --------------------------------------------------------------------------- #


def build_planner(settings: Settings) -> AgentPlanner:
    """Return a Qwen-backed planner when a key exists, else the deterministic mock."""
    if settings.ai_enabled:
        return QwenAgentPlanner(build_ai_client(settings))
    return MockAgentPlanner()


@lru_cache
def get_planner() -> AgentPlanner:
    """Cached accessor for application code / the FastAPI dependency graph."""
    return build_planner(get_settings())
