"""A3 state-machine tests (brief §15, tests 1–5).

The A3 brief describes a *conceptual* flow (``UNDERSTANDING → EVALUATING → DECIDING →
COMPLETED``, plus ``NEEDS_CLARIFICATION``). Per AGENT_SPEC §5 ("do not invent new ones") these are
realized with the **9 canonical** :class:`~app.schemas.route.AgentState` values:

* ``UNDERSTANDING → EVALUATING`` is the canonical forward path ``UNDERSTANDING → PLANNING →
  SEARCHING → EVALUATING`` (the agent plans, searches, then evaluates).
* ``DECIDING`` is the ``EVALUATING → COMPLETED`` boundary — the decision is *produced* during
  ``EVALUATING`` and *finalized* at ``COMPLETED``; there is no separate ``DECIDING`` state.
* ``NEEDS_CLARIFICATION`` is **not** a state — the agent stays in ``UNDERSTANDING`` and returns the
  A2 clarification flags (brief §12: "stop before decision").

These tests verify that mapping and that invalid transitions are handled explicitly.
"""

from __future__ import annotations

import pytest

from app.agent.orchestrator import build_agent
from app.agent.state import (
    ALLOWED_TRANSITIONS,
    AgentExecutionContext,
    InvalidTransitionError,
)
from app.config import get_settings
from app.schemas.route import AgentState
from app.schemas.travel_request import TravelRequest

# Canonical forward path used to position a context at a given state via valid transitions.
_FORWARD_PATH: list[AgentState] = [
    AgentState.UNDERSTANDING,
    AgentState.PLANNING,
    AgentState.SEARCHING,
    AgentState.EVALUATING,
    AgentState.COMPLETED,
]


def _forward_to(state: AgentState) -> AgentExecutionContext:
    """Return a context advanced to ``state`` along the canonical happy path."""
    context = AgentExecutionContext()
    for step in _FORWARD_PATH:
        context.advance(step)
        if step is state:
            break
    return context


# 1. UNDERSTANDING → EVALUATING (canonical forward path).
def test_understanding_advances_to_evaluating() -> None:
    context = AgentExecutionContext()
    assert context.state is AgentState.IDLE
    context.advance(AgentState.UNDERSTANDING)
    context.advance(AgentState.PLANNING)
    context.advance(AgentState.SEARCHING)
    context.advance(AgentState.EVALUATING)
    assert context.state is AgentState.EVALUATING
    assert context.visited_states == [
        AgentState.IDLE,
        AgentState.UNDERSTANDING,
        AgentState.PLANNING,
        AgentState.SEARCHING,
        AgentState.EVALUATING,
    ]


# 2. EVALUATING → DECIDING (the decision boundary: EVALUATING → COMPLETED is permitted).
def test_evaluating_advances_to_decision_boundary() -> None:
    context = _forward_to(AgentState.EVALUATING)
    assert context.can_advance(AgentState.COMPLETED)
    context.advance(AgentState.COMPLETED)
    assert context.state is AgentState.COMPLETED


# 3. DECIDING → COMPLETED, and COMPLETED is terminal for success (may restart, not jump back).
def test_completed_is_terminal_and_may_restart() -> None:
    context = _forward_to(AgentState.COMPLETED)
    assert context.state is AgentState.COMPLETED
    # A new request or a re-plan may start again …
    assert context.can_advance(AgentState.UNDERSTANDING)
    # … but it cannot jump straight back into EVALUATING.
    assert not context.can_advance(AgentState.EVALUATING)


# 4. Clarification prevents the decision (agent stays in UNDERSTANDING; never reaches EVALUATING).
def test_clarification_prevents_decision() -> None:
    request = TravelRequest(destination="Ella").refresh_clarification()
    assert request.clarification_required is True

    context = build_agent(get_settings()).run(request)
    assert context.state is AgentState.UNDERSTANDING
    assert context.recommendation is None
    assert AgentState.EVALUATING not in context.visited_states
    assert AgentState.COMPLETED not in context.visited_states


# 5. Invalid transitions are prevented/handled explicitly.
def test_invalid_transition_is_handled() -> None:
    context = AgentExecutionContext()  # IDLE
    with pytest.raises(InvalidTransitionError):
        context.advance(AgentState.EVALUATING)  # IDLE → EVALUATING is not allowed
    assert context.state is AgentState.IDLE  # unchanged after the rejected transition

    context.advance(AgentState.UNDERSTANDING)
    with pytest.raises(InvalidTransitionError):
        context.advance(AgentState.SEARCHING)  # cannot skip PLANNING
    assert context.state is AgentState.UNDERSTANDING


# Extra structural guarantees (brief §15 says "at minimum").
def test_only_canonical_states_are_modelled() -> None:
    assert set(ALLOWED_TRANSITIONS.keys()) == set(AgentState)


def test_error_is_reachable_from_every_non_error_state() -> None:
    for state in AgentState:
        if state is AgentState.ERROR:
            continue
        assert AgentState.ERROR in ALLOWED_TRANSITIONS[state]
