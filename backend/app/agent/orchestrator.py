"""Route agent orchestrator (Workstream A, Phase A3; tool execution refined in A4).

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

**A4** routes the ``search_routes`` call through the tool seam (registry → executor → structured
:class:`~app.tools.base.ToolResult`): resolve → validate → execute → observe → decide. Invocation
stays **orchestrator-controlled** — the multi-step Qwen tool-calling loop is **A5** (A4 brief §14).
Qwen is **not** used for route selection here; it remains the A2 extractor. Mock mode is fully
functional with no API key.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from app.agent.decision import Decision, DecisionEngine
from app.agent.state import AgentExecutionContext
from app.config import Settings, get_settings
from app.schemas.route import AgentState, DataSource, ToolCall
from app.schemas.travel_request import ExtractionSource, TravelRequest
from app.tools.registry import ToolRegistry, build_tools, get_tools


class RouteAgent:
    """Orchestrates one travel request through the canonical agent states."""

    def __init__(
        self,
        tools: ToolRegistry,
        engine: Optional[DecisionEngine] = None,
    ) -> None:
        self._tools = tools
        self._engine = engine or DecisionEngine()

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #
    def run(self, request: TravelRequest) -> AgentExecutionContext:
        """Understand → (gate) → plan → search → evaluate → complete, returning the context."""
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
                "Will resolve and call the search_routes tool (via the A4 tool seam: "
                "validate → execute → structured result) to gather mock candidates, then filter "
                "hard constraints and score soft preferences. Fare/delay/availability/booking "
                "tools are not_implemented, so they are resolved but not called for data."
            ),
            data_source=DataSource.mock,
        )

        # --- SEARCHING (A4 seam: resolve → validate → execute → structured result) --- #
        context.advance(AgentState.SEARCHING)
        tool_name = "search_routes"
        search_args = {"origin": request.origin, "destination": request.destination}
        tool = self._tools.get(tool_name)  # 1–2. identify + resolve the capability
        result = self._tools.execute(tool_name, search_args)  # 3–5. validate + execute
        candidates = list(result.data or []) if result.success else []
        context.candidates = candidates
        if not result.success:
            # Honest + non-fatal: record the structured failure; EVALUATING then reports no route.
            context.errors.append(result.message)
        context.record_action(
            state=AgentState.SEARCHING,
            label=(
                "Searched for candidate routes"
                if result.success
                else "Route search returned no usable data"
            ),
            detail=result.message,
            tool_call=ToolCall(
                name=tool_name,
                args=search_args,
                status="done" if result.success else "error",
                result_summary=result.message,
                availability=(tool.availability.value if tool else None),
                data_source=result.data_source,
            ),
            status="done" if result.success else "error",
            data_source=result.data_source,
        )

        # --- EVALUATING (the decision is produced here) -------------------- #
        context.advance(AgentState.EVALUATING)
        decision = self._engine.decide(request, candidates)
        self._apply_decision(context, decision)
        context.record_action(
            state=AgentState.EVALUATING,
            label=self._evaluating_label(decision, len(candidates)),
            detail=self._evaluating_detail(decision),
            data_source=DataSource.mock,
        )

        # --- COMPLETED (decision finalized) -------------------------------- #
        context.advance(AgentState.COMPLETED)
        context.record_action(
            state=AgentState.COMPLETED,
            label=(
                "Decision ready"
                if decision.recommendation is not None
                else "Completed — no route fits the constraints"
            ),
            detail=decision.reasoning,
            data_source=DataSource.mock,
        )
        return context

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
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
    """Build a :class:`RouteAgent` with the A3 tool registry and decision engine."""
    return RouteAgent(tools=build_tools(settings), engine=DecisionEngine())


@lru_cache
def get_agent() -> RouteAgent:
    """Cached accessor for application code / the FastAPI dependency graph."""
    return build_agent(get_settings())
