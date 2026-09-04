"""Qwen tool-calling adapter + agent planner (Workstream A, Phase A5).

Connects the model to the A4 tool system so the agent can autonomously perform **multiple** tool
calls (A5 brief §2/§5). Like :mod:`app.services.ai.extraction` (A2), this module **extends** the
existing AI abstraction (``base.AIClient`` / ``factory``) — it does **not** create a second Qwen
client or a second tool framework (A5 brief §1/§4/§5). One planner interface, two honest
implementations:

* :class:`QwenAgentPlanner` — real Qwen via the existing ``AIClient`` (used when a
  ``MODEL_STUDIO_API_KEY`` is configured). It sends the conversation plus **available** tool
  definitions and normalizes the model's ``tool_calls`` (or final content) into an
  :class:`AgentDecision`. It never executes anything itself — it only *decides the next step*.
* :class:`MockAgentPlanner` — a deterministic, offline simulation of multi-step tool selection
  (A5 brief §13) so the whole flow is testable with no credentials. It is clearly labelled
  ``data_source="mock"`` / ``model="mock-qwen"`` and never claims a real model decided.

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

#: The one capability the golden flow needs; the mock planner requests it first (A5 §13/§22).
_SEARCH_TOOL = "search_routes"

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
    """

    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]
    travel_request: dict[str, Any]
    tool_names: list[str]
    steps_taken: int = 0


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

    Simulates the canonical flow (A5 brief §13/§22): *gather route candidates first, then decide*.
    It requests ``search_routes`` once when it is a registered capability and nothing has been
    gathered yet, then produces a final decision — so it never loops and never fabricates. The
    agent loop still validates/executes the call through the registry+executor, so a disabled or
    failing ``search_routes`` degrades honestly exactly as it would for a real model.
    """

    def next_decision(self, ctx: PlannerContext) -> AgentDecision:
        if ctx.steps_taken == 0 and _SEARCH_TOOL in ctx.tool_names:
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
        return AgentDecision(
            kind="final",
            tool_calls=[],
            content="I have enough information to decide from the gathered tool results.",
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
