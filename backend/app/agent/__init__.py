"""Route agent (Workstream A, Phase A3) — orchestration + decision.

Public surface for the agent layer described in ``app/agent/README.md`` and docs/AGENT_SPEC.md.
Import from here rather than the individual modules so the boundary stays single and obvious
(mirrors ``app.services.ai`` and ``app.tools``).

A3 adds the first real reasoning layer:

* :class:`AgentExecutionContext` + the canonical state machine (``app.agent.state``),
* :class:`DecisionEngine` — transparent, deterministic hard-filter + soft-score routing
  (``app.agent.decision``), and
* :class:`RouteAgent` — the orchestrator that drives the states and calls tools
  (``app.agent.orchestrator``).
"""

from app.agent.decision import (
    Decision,
    DecisionEngine,
    ExcludedCandidate,
    ScoredCandidate,
)
from app.agent.orchestrator import RouteAgent, build_agent, get_agent
from app.agent.state import (
    ALLOWED_TRANSITIONS,
    AgentExecutionContext,
    InvalidTransitionError,
)

__all__ = [
    "Decision",
    "DecisionEngine",
    "ExcludedCandidate",
    "ScoredCandidate",
    "RouteAgent",
    "build_agent",
    "get_agent",
    "ALLOWED_TRANSITIONS",
    "AgentExecutionContext",
    "InvalidTransitionError",
]
