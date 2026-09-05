"""Agent execution context + state machine (Workstream A, Phase A3).

This module gives the agent an explicit, small state model (A3 brief §4) and a structured,
reusable context object that travels with a request end-to-end (A3 brief §5).

State discipline (AGENT_SPEC §5 — "do not invent new ones"):

* Only the **9 canonical** :class:`~app.schemas.route.AgentState` values are used. The A3 brief's
  conceptual ``DECIDING`` step is realized as the ``EVALUATING → COMPLETED`` boundary (the
  decision is *produced* during ``EVALUATING`` and *finalized* at ``COMPLETED``); its
  ``NEEDS_CLARIFICATION`` step is **not** a new state — the agent simply stays in
  ``UNDERSTANDING`` and returns the A2 ``clarification_required`` flags (AGENT_SPEC §18).
* The A3 happy path is ``UNDERSTANDING → PLANNING → SEARCHING → EVALUATING → COMPLETED``. No
  ``EXECUTING`` (A3 takes no actions) and no ``REPLANNING`` (no disruptions in A3).
* **A5** drives tool selection from the Qwen/mock planner in a bounded loop. The canonical states
  are unchanged, but the loop may traverse ``SEARCHING ↔ EXECUTING`` when the agent gathers info
  and then acts (A5 brief §9's illustrative ``SEARCHING → EXECUTING → SEARCHING`` flow), so those
  transitions — plus ``EXECUTING → EVALUATING`` — are permitted below. The golden single-search
  path still visits exactly ``UNDERSTANDING → PLANNING → SEARCHING → EVALUATING → COMPLETED``.
* **A7** adds no state and no transition (A7 brief §20). Its three new capabilities are
  *information-gathering* tools, so — like ``search_routes`` — they are recorded in ``SEARCHING``:
  the golden multi-step path repeats ``SEARCHING`` once per tool call and still visits exactly
  ``UNDERSTANDING → PLANNING → SEARCHING → EVALUATING → COMPLETED``. ``EXECUTING`` remains reserved
  for capabilities that act on the world (Workstream C's ``prepare_booking``).
* Invalid transitions raise :class:`InvalidTransitionError` rather than being silently applied
  (A3 brief §4: "invalid transitions prevented/handled explicitly").
* **A9** adds no state and no transition (brief §4: "do NOT invent unnecessary new states"). It
  only makes one execution *identifiable and measurable*: the context gains a lightweight
  ``request_id`` plus run counters (``iteration_count`` / ``tool_call_count`` / ``duration_ms``) so
  logs and actions can be correlated and bounded work can be reported (brief §10/§11). Those fields
  are **internal** — they are not part of the frozen ``PlanResponse`` shape except for ``request_id``,
  which the endpoint copies out for correlation. Every field is additive and defaulted, so an
  A3–A8 caller that constructs a context unchanged still works.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.logging_config import new_request_id
from app.schemas.candidate import RouteCandidate
from app.schemas.route import (
    AgentAction,
    AgentState,
    DataSource,
    Leg,
    Recommendation,
    ToolCall,
)
from app.schemas.travel_request import TravelRequest

# Forward flow from AGENT_SPEC §5, plus: ERROR reachable from any state; COMPLETED may restart
# (new request) or re-plan; ERROR may recover to IDLE/UNDERSTANDING/SEARCHING. A5 adds the
# SEARCHING ↔ EXECUTING ↔ EVALUATING edges the bounded multi-step tool loop needs (brief §9);
# no new states are introduced and the canonical forward happy path is unchanged.
ALLOWED_TRANSITIONS: dict[AgentState, set[AgentState]] = {
    AgentState.IDLE: {AgentState.UNDERSTANDING, AgentState.ERROR},
    AgentState.UNDERSTANDING: {
        AgentState.PLANNING,
        AgentState.COMPLETED,
        AgentState.ERROR,
    },
    AgentState.PLANNING: {
        AgentState.SEARCHING,
        AgentState.EVALUATING,
        AgentState.ERROR,
    },
    AgentState.SEARCHING: {
        AgentState.EVALUATING,
        AgentState.EXECUTING,  # A5: gather → act within the multi-step loop
        AgentState.ERROR,
    },
    AgentState.EVALUATING: {
        AgentState.COMPLETED,
        AgentState.EXECUTING,
        AgentState.REPLANNING,
        AgentState.ERROR,
    },
    AgentState.EXECUTING: {
        AgentState.COMPLETED,
        AgentState.REPLANNING,
        AgentState.SEARCHING,  # A5: act → gather more info
        AgentState.EVALUATING,  # A5: act → evaluate whether enough is known
        AgentState.ERROR,
    },
    AgentState.REPLANNING: {
        AgentState.SEARCHING,
        AgentState.EVALUATING,
        AgentState.COMPLETED,
        AgentState.ERROR,
    },
    AgentState.COMPLETED: {
        AgentState.IDLE,
        AgentState.UNDERSTANDING,
        AgentState.ERROR,
    },
    AgentState.ERROR: {
        AgentState.IDLE,
        AgentState.UNDERSTANDING,
        AgentState.SEARCHING,
    },
}


def _now() -> datetime:
    """Timezone-aware 'now' in UTC (matches the A2 action timestamps)."""
    return datetime.now(timezone.utc)


class InvalidTransitionError(ValueError):
    """Raised when a state transition is not permitted by :data:`ALLOWED_TRANSITIONS`."""

    def __init__(self, from_state: AgentState, to_state: AgentState) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"Invalid agent state transition: {from_state.value} → {to_state.value}."
        )


class AgentExecutionContext(BaseModel):
    """Everything the agent knows/has-done for one request (A3 brief §5).

    Kept deliberately reusable: later phases (A4+ tool loops, A6 decision engine refinements,
    Workstream B/C data) extend this object rather than replacing it.
    """

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    # --- Input & current position ---
    request: Optional[TravelRequest] = Field(
        default=None, description="The normalized request the agent is working on (A2 output)."
    )
    state: AgentState = Field(
        default=AgentState.IDLE, description="Current canonical agent state."
    )

    # --- What the agent can use / has gathered ---
    available_tools: list[str] = Field(
        default_factory=list, description="Tool names available during PLANNING."
    )
    candidates: list[RouteCandidate] = Field(
        default_factory=list, description="Candidate routes gathered during SEARCHING."
    )
    constraints: dict[str, Any] = Field(
        default_factory=dict,
        description="Snapshot of hard/soft constraints derived from the request.",
    )

    # --- Decision output ---
    recommendation: Optional[Recommendation] = Field(
        default=None, description="Selected route (None when nothing valid fits)."
    )
    alternatives: list[Recommendation] = Field(
        default_factory=list, description="Other ranked routes with honest trade-offs."
    )
    reasoning: Optional[str] = Field(
        default=None, description="Concise human explanation of the decision."
    )
    legs: list[Leg] = Field(
        default_factory=list,
        description=(
            "Leg-by-leg detail for the recommended route; populated in A7 from the mock "
            "get_route_details tool result, and empty when that capability was not called or "
            "returned nothing (never invented)."
        ),
    )

    # --- Trace, honesty, errors, timestamps ---
    actions: list[AgentAction] = Field(
        default_factory=list, description="Ordered agent-activity trace (API_CONTRACTS §4)."
    )
    visited_states: list[AgentState] = Field(
        default_factory=lambda: [AgentState.IDLE],
        description="State history for the timeline (starts at IDLE).",
    )
    errors: list[str] = Field(
        default_factory=list, description="Non-fatal problems recorded along the way."
    )
    data_source: DataSource = Field(
        default=DataSource.mock, description="Overall honesty flag for this result (A3: mock)."
    )
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    # --- A9: correlation + run metadata (brief §10/§11) ---
    request_id: str = Field(
        default_factory=new_request_id,
        description=(
            "Lightweight identifier of this one execution, so logs and actions correlate. It "
            "identifies a request, never a user, and is not persisted."
        ),
    )
    iteration_count: int = Field(
        default=0, description="Planner turns consumed by the bounded tool loop (A9 §11)."
    )
    tool_call_count: int = Field(
        default=0,
        description=(
            "Tool calls actually executed in this run. A suppressed duplicate is not counted: it "
            "never reached the tool layer (A9 §11)."
        ),
    )
    duration_ms: Optional[float] = Field(
        default=None, description="Total execution time for this run, set when it finishes (A9 §11)."
    )

    # ------------------------------------------------------------------ #
    # State machine
    # ------------------------------------------------------------------ #
    def can_advance(self, to_state: AgentState) -> bool:
        """True when ``self.state → to_state`` is a permitted transition."""
        return to_state in ALLOWED_TRANSITIONS.get(self.state, set())

    def advance(self, to_state: AgentState) -> "AgentExecutionContext":
        """Move to ``to_state``, recording history; raise on an invalid transition.

        Returns ``self`` so calls can be chained.
        """
        if not self.can_advance(to_state):
            raise InvalidTransitionError(self.state, to_state)
        self.state = to_state
        self.visited_states.append(to_state)
        self.updated_at = _now()
        return self

    # ------------------------------------------------------------------ #
    # Trace
    # ------------------------------------------------------------------ #
    def record_action(
        self,
        *,
        state: AgentState,
        label: str,
        detail: Optional[str] = None,
        tool_call: Optional[ToolCall] = None,
        status: str = "done",
        data_source: Optional[DataSource] = None,
        kind: Optional[str] = None,
    ) -> AgentAction:
        """Append an :class:`AgentAction` to the trace with the next sequence number.

        ``seq`` is assigned from the current trace length and ``timestamp`` from the clock, so the
        ordering is deterministic for a given sequence of calls and never depends on a dict/set
        iteration order (A9 brief §5). ``kind`` (A9, additive) names the action type from
        :data:`~app.schemas.route.ACTION_KINDS`.
        """
        action = AgentAction(
            seq=len(self.actions) + 1,
            state=state,
            label=label,
            detail=detail,
            tool_call=tool_call,
            status=status,
            timestamp=_now(),
            data_source=data_source,
            kind=kind,
        )
        self.actions.append(action)
        self.updated_at = action.timestamp
        return action
