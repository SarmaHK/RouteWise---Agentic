"""Route agent orchestrator (Workstream A; A3 states, A4 tool seam, A5 multi-step loop).

:class:`RouteAgent` is the first real reasoning/orchestration layer. Given a validated
:class:`~app.schemas.travel_request.TravelRequest` (A2 output) it drives the canonical state
machine and returns a populated :class:`~app.agent.state.AgentExecutionContext`:

    UNDERSTANDING → PLANNING → SEARCHING → EVALUATING → COMPLETED

(A3 brief §2/§12; AGENT_SPEC §5). The decision itself is computed by the deterministic
:class:`~app.agent.decision.DecisionEngine` — the agent *orchestrates* (state, tools, trace) and
delegates *scoring* to the engine, keeping both testable in isolation.

Honesty guards (A3 brief §10/§17; AGENT_SPEC §15–§16):

* If the request still needs clarification, the agent **stops before deciding** and stays in
  ``UNDERSTANDING`` (A3 brief §12) — no invented state, no fabricated route.
* Every route figure comes from the mock candidate provider and is labelled ``data_source=mock``.
* The agent never claims real seats/fares/availability; the fare/delay/availability/booking
  tools are honest ``not_implemented`` stubs, gated by the A4 tool-availability model so they are
  resolved but never called for data.

**A4** routed the ``search_routes`` call through the tool seam (registry → executor → structured
:class:`~app.tools.base.ToolResult`). **A5** generalizes that single call into a *bounded,
model-driven* multi-step loop: a planner (:mod:`app.services.ai.agent`) decides **which** registered
tool to call next (real Qwen when a key is configured, else a deterministic mock), and this
orchestrator validates → resolves → executes it through the A4 seam, records the action, feeds the
structured result (success **or** failure) back, and repeats until the planner finishes or
``MAX_AGENT_ITERATIONS`` is reached (A5 brief §2/§7/§8). The tool *sequence* is model-selected, not
hard-coded. The final recommendation is still computed by the deterministic
:class:`~app.agent.decision.DecisionEngine` over tool-gathered candidates — the planner never
invents route facts (A5 brief §15/§16). Mock mode is fully functional with no API key.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Optional

from app.agent.decision import Decision, DecisionEngine
from app.agent.state import AgentExecutionContext
from app.config import Settings, get_settings
from app.schemas.route import AgentState, DataSource, ToolCall
from app.schemas.travel_request import ExtractionSource, TravelRequest
from app.services.ai.agent import (
    AgentPlanner,
    PlannerContext,
    ToolCallRequest,
    assistant_tool_call_message,
    build_agent_messages,
    build_planner,
    build_tool_definitions,
    get_planner,
    tool_result_message,
)
from app.tools.base import ToolResult
from app.tools.registry import ToolRegistry, build_tools, get_tools

#: Default upper bound on autonomous tool-calling turns for one request (A5 brief §8). Overridden
#: by ``settings.max_agent_iterations`` / the ``MAX_AGENT_ITERATIONS`` env var.
DEFAULT_MAX_AGENT_ITERATIONS = 8

#: Capabilities that *act* on the world rather than gather information — mapped to ``EXECUTING``
#: (A5 brief §9's illustrative ``SEARCHING → EXECUTING → SEARCHING`` flow). Every other tool is an
#: information-gathering step mapped to ``SEARCHING``. All such tools are ``not_implemented`` stubs
#: today, so this only matters once Workstream B/C supply real capabilities — no new agent states
#: are introduced either way.
_ACTION_TOOLS = frozenset({"prepare_booking"})

#: Argument keys never surfaced to the frontend action trace (A5 brief §10: sanitize args).
_SENSITIVE_ARG_KEYS = frozenset(
    {"token", "api_key", "apikey", "key", "secret", "password", "authorization", "auth"}
)

#: Long string arguments are truncated in the trace so the timeline stays readable (A5 §10).
_MAX_ARG_LEN = 120


class RouteAgent:
    """Orchestrates one travel request through the canonical agent states."""

    def __init__(
        self,
        tools: ToolRegistry,
        engine: Optional[DecisionEngine] = None,
        planner: Optional[AgentPlanner] = None,
        max_iterations: Optional[int] = None,
    ) -> None:
        self._tools = tools
        self._engine = engine or DecisionEngine()
        # A5: the planner decides *which* tool to call next; default to the cached app planner
        # (real Qwen when a key is configured, else the deterministic mock — A5 brief §12/§13).
        self._planner = planner or get_planner()
        self._max_iterations = (
            max_iterations
            if max_iterations is not None and max_iterations > 0
            else DEFAULT_MAX_AGENT_ITERATIONS
        )

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #
    def run(self, request: TravelRequest) -> AgentExecutionContext:
        """Understand → (gate) → plan → [bounded multi-step tool loop] → evaluate → complete."""
        context = AgentExecutionContext(
            request=request,
            available_tools=self._tools.names(),
            data_source=DataSource.mock,
        )
        extraction_source = self._extraction_data_source(request)

        # --- UNDERSTANDING ------------------------------------------------- #
        context.advance(AgentState.UNDERSTANDING)
        context.record_action(
            state=AgentState.UNDERSTANDING,
            label="Understood travel request",
            detail=self._understanding_detail(request),
            data_source=extraction_source,
        )

        # Clarification gate (A3 brief §12): stop before deciding, stay in UNDERSTANDING.
        if request.clarification_required:
            missing = ", ".join(request.missing_fields) or "a required detail"
            context.record_action(
                state=AgentState.UNDERSTANDING,
                label="Clarification required",
                detail=(
                    f"Cannot plan yet — missing: {missing}. No route searched or decided "
                    "(the agent stops before the decision when a hard constraint is unknown)."
                ),
                status="active",
                data_source=extraction_source,
            )
            context.reasoning = (
                "I need a little more information before I can plan this trip: "
                + " ".join(request.clarification_questions)
            )
            return context

        # --- PLANNING ------------------------------------------------------ #
        context.advance(AgentState.PLANNING)
        context.record_action(
            state=AgentState.PLANNING,
            label="Planned the approach",
            detail=(
                "Will let the planner choose which registered tool(s) to call, and in what order, "
                "to gather what it needs (A5 bounded multi-step loop), executing each through the "
                "A4 tool seam (validate → execute → structured result) and feeding results back, "
                "then score the gathered candidates. Only AVAILABLE tools are offered to the "
                "model; not_implemented capabilities are excluded so they are never called."
            ),
            data_source=DataSource.mock,
        )

        # --- Bounded multi-step tool loop (A5 §7): the planner SELECTS, we EXECUTE --- #
        # The tool *sequence* is model-driven (never hard-coded): each turn the planner decides
        # whether it needs another tool call or is ready to finish. Every call is validated +
        # executed through the A4 seam (registry → executor → structured ToolResult), recorded as
        # an action, and fed back — success OR failure — so the next decision stays grounded
        # (§11/§16). The loop is strictly bounded by ``self._max_iterations`` (§8): it can never
        # run away, and repeated identical calls are suppressed (§18).
        snapshot = self._travel_snapshot(request)
        transcript = build_agent_messages(snapshot, raw_text=request.raw_text)
        tool_defs = build_tool_definitions(self._tools)  # only AVAILABLE tools are offered (§6)
        seen_calls: set[str] = set()  # fingerprints of executed calls, for repeat detection (§18)
        steps_taken = 0
        iteration = 0
        limit_hit = False

        while iteration < self._max_iterations:
            iteration += 1
            ctx = PlannerContext(
                messages=transcript,
                tools=tool_defs,
                travel_request=snapshot,
                tool_names=self._tools.names(),
                steps_taken=steps_taken,
            )
            decision = self._planner.next_decision(ctx)
            if not decision.is_tool_call:
                break  # the planner signalled it is ready to decide (§7)

            # Give each requested call a stable id so the assistant turn and its tool-result
            # messages pair up in the transcript (real Qwen supplies ids; the mock does not).
            for index, call in enumerate(decision.tool_calls):
                if not call.id:
                    call.id = f"call_{iteration}_{index}"
            transcript.append(assistant_tool_call_message(decision))

            repeated = False
            for call in decision.tool_calls:
                fingerprint = self._fingerprint(call)
                if fingerprint in seen_calls:
                    # §18: an identical call yields no new information — do NOT re-execute it.
                    repeated = True
                    suppressed = ToolResult.failure(
                        call.name or "tool",
                        "REPEATED_CALL",
                        f"Repeated identical '{call.name}' call skipped (no new information).",
                    )
                    context.errors.append(suppressed.message)
                    self._record_tool_action(context, call, suppressed, repeated=True)
                    transcript.append(tool_result_message(call.id, suppressed))
                    continue

                seen_calls.add(fingerprint)
                target_state = self._state_for_tool(call.name)
                if target_state != context.state and not context.can_advance(target_state):
                    # An action tool requested before any gathering (e.g. straight from PLANNING,
                    # where → EXECUTING is not a canonical edge): fall back to SEARCHING so we
                    # NEVER apply an invalid transition (§9). EXECUTING is still used once a
                    # gathering step makes SEARCHING → EXECUTING reachable.
                    target_state = AgentState.SEARCHING
                if context.state != target_state:
                    context.advance(target_state)  # SEARCHING (gather) or EXECUTING (act) — §9
                result = self._tools.execute(call.name, call.arguments)
                steps_taken += 1
                if result.success and call.name == "search_routes":
                    # Ground the eventual decision in the structured candidates the tool actually
                    # returned (§15/§16) — the planner never invents these facts.
                    context.candidates = list(result.data or [])
                if not result.success:
                    context.errors.append(result.message)
                self._record_tool_action(context, call, result)
                transcript.append(tool_result_message(call.id, result))
            if repeated:
                break  # stop looping; finalize from what was already gathered (§18)
        else:
            # The budget expired without the planner finishing → terminate safely (§8), preserving
            # the observed actions and fabricating nothing.
            limit_hit = True

        self._finalize(context, request, limit_hit)
        return context

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _finalize(
        self,
        context: AgentExecutionContext,
        request: TravelRequest,
        limit_hit: bool,
    ) -> None:
        """Evaluate the gathered candidates and advance to COMPLETED (A5 §8/§15/§16).

        The recommendation is produced by the deterministic :class:`DecisionEngine` over the
        candidates the tools actually returned — the planner only *selected* tools, it never
        invents route facts. If the iteration budget was exhausted, we stop honestly with **no**
        recommendation rather than fabricate one (§8).
        """
        context.advance(AgentState.EVALUATING)
        if limit_hit:
            message = (
                f"Stopped after {self._max_iterations} tool-calling iteration(s) without a final "
                "decision (MAX_AGENT_ITERATIONS). No recommendation was fabricated."
            )
            context.errors.append(message)
            context.record_action(
                state=AgentState.EVALUATING,
                label="Stopped — iteration limit reached",
                detail=message,
                status="error",
                data_source=DataSource.mock,
            )
            context.reasoning = (
                "I could not reach a confident decision within the allowed number of tool-calling "
                f"steps ({self._max_iterations}). What I observed: "
                + ("; ".join(context.errors) if context.errors else "no usable tool results.")
            )
            completed_label = "Completed — stopped at the iteration limit"
            completed_detail = context.reasoning
        else:
            decision = self._engine.decide(request, context.candidates)
            self._apply_decision(context, decision)
            context.record_action(
                state=AgentState.EVALUATING,
                label=self._evaluating_label(decision, len(context.candidates)),
                detail=self._evaluating_detail(decision),
                data_source=DataSource.mock,
            )
            completed_label = (
                "Decision ready"
                if decision.recommendation is not None
                else "Completed — no route fits the constraints"
            )
            completed_detail = decision.reasoning

        context.advance(AgentState.COMPLETED)
        context.record_action(
            state=AgentState.COMPLETED,
            label=completed_label,
            detail=completed_detail,
            data_source=DataSource.mock,
        )

    def _record_tool_action(
        self,
        context: AgentExecutionContext,
        call: ToolCallRequest,
        result: ToolResult,
        *,
        repeated: bool = False,
    ) -> None:
        """Record one tool call (executed or suppressed) as an agent action (A5 §10).

        The trace carries the resolved tool's ``availability``, the call's ``data_source``, and —
        on failure — the structured ``error_code``, with args sanitized (secrets redacted, long
        values truncated). No credentials or hidden reasoning are ever exposed.
        """
        tool = self._tools.get(call.name)
        success = result.success
        if repeated:
            label = f"Repeated '{call.name}' call skipped"
        elif success:
            label = f"Called '{call.name}'"
        else:
            label = f"'{call.name}' returned no usable data"
        context.record_action(
            state=context.state,
            label=label,
            detail=result.message,
            tool_call=ToolCall(
                name=call.name,
                args=self._sanitize_args(call.arguments),
                status="done" if success else "error",
                result_summary=result.message,
                availability=(tool.availability.value if tool else None),
                data_source=result.data_source,
                error_code=(result.error.code if result.error else None),
            ),
            status="done" if success else "error",
            data_source=result.data_source,
        )

    @staticmethod
    def _travel_snapshot(request: TravelRequest) -> dict[str, Any]:
        """A JSON-safe snapshot of the understood request handed to the planner (A5 §12/§13)."""
        return request.model_dump(
            mode="json",
            include={
                "origin",
                "destination",
                "budget",
                "currency",
                "luggage",
                "walking_preference",
                "departure_time",
                "arrival_deadline",
                "preferences",
            },
            exclude_none=True,
        )

    @staticmethod
    def _state_for_tool(name: str) -> AgentState:
        """Map a tool to the canonical state its call represents (A5 §9: no new states)."""
        return AgentState.EXECUTING if name in _ACTION_TOOLS else AgentState.SEARCHING

    @staticmethod
    def _sanitize_args(args: dict[str, Any]) -> dict[str, Any]:
        """Redact secrets and truncate long values before an arg summary reaches the UI (§10)."""
        safe: dict[str, Any] = {}
        for key, value in (args or {}).items():
            if key.lower() in _SENSITIVE_ARG_KEYS:
                safe[key] = "[redacted]"
            elif isinstance(value, str) and len(value) > _MAX_ARG_LEN:
                safe[key] = value[:_MAX_ARG_LEN] + "…"
            else:
                safe[key] = value
        return safe

    @staticmethod
    def _fingerprint(call: ToolCallRequest) -> str:
        """A canonical identity for a call (name + args) used for repeat detection (§18)."""
        try:
            canon = json.dumps(call.arguments, sort_keys=True, default=str)
        except (TypeError, ValueError):
            canon = str(call.arguments)
        return f"{call.name}|{canon}"

    @staticmethod
    def _extraction_data_source(request: TravelRequest) -> DataSource:
        """Map the A2 extraction provenance onto the action's honesty flag."""
        if request.extraction_source == ExtractionSource.qwen:
            return DataSource.live
        return DataSource.mock

    @staticmethod
    def _understanding_detail(request: TravelRequest) -> str:
        understood = [
            f"{key}={value}"
            for key, value in request.model_dump(
                include={
                    "origin",
                    "destination",
                    "budget",
                    "currency",
                    "luggage",
                    "walking_preference",
                },
                exclude_none=True,
            ).items()
        ]
        return "Understood the travel request: " + (
            ", ".join(understood) if understood else "(no explicit constraints)"
        )

    @staticmethod
    def _apply_decision(context: AgentExecutionContext, decision: Decision) -> None:
        context.recommendation = decision.recommendation
        context.alternatives = decision.alternatives
        context.reasoning = decision.reasoning
        context.constraints = {
            "hard": decision.hard_constraints,
            "soft": decision.soft_preferences,
        }
        # Surface any honest engine assumptions (e.g. a skipped deadline check) on the request,
        # which already carries an ``assumptions`` list in the API response.
        if decision.assumptions and context.request is not None:
            context.request.assumptions.extend(decision.assumptions)

    @staticmethod
    def _evaluating_label(decision: Decision, candidate_count: int) -> str:
        if decision.recommendation is not None:
            return f"Evaluated {candidate_count} candidate route(s)"
        return f"Evaluated {candidate_count} candidate route(s) — none viable"

    @staticmethod
    def _evaluating_detail(decision: Decision) -> str:
        parts: list[str] = []
        if decision.scored:
            ranked = ", ".join(
                f"{sc.candidate.id}={sc.score:.3f}" for sc in decision.scored
            )
            parts.append(f"Scored viable routes (higher is better): {ranked}.")
        if decision.excluded:
            excluded = "; ".join(
                f"{e.candidate.id} — {e.reason.rstrip('.')}" for e in decision.excluded
            )
            parts.append(f"Excluded by hard constraints: {excluded}.")
        if not parts:
            parts.append("No candidates to evaluate for this corridor.")
        return " ".join(parts)


def build_agent(settings: Settings) -> RouteAgent:
    """Build a :class:`RouteAgent`: A4 tool registry + A3 decision engine + A5 planner.

    The planner is real Qwen when ``MODEL_STUDIO_API_KEY`` is set, else the deterministic mock
    (A5 §12/§13); the loop bound comes from ``settings.max_agent_iterations`` (A5 §8).
    """
    return RouteAgent(
        tools=build_tools(settings),
        engine=DecisionEngine(),
        planner=build_planner(settings),
        max_iterations=settings.max_agent_iterations,
    )


@lru_cache
def get_agent() -> RouteAgent:
    """Cached accessor for application code / the FastAPI dependency graph."""
    return build_agent(get_settings())
