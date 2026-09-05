"""Deterministic mock candidate provider (Workstream A; A3 facade over the A7 shared truth).

This is the provider behind ``search_routes``: it returns a small, fixed set of obviously mock
candidates for a few Sri-Lankan corridors so the decision engine has real structure to reason over
— it is **not** a fake "live Sri Lankan transit system" (A3 brief §7/§17).

**A7 change (brief §15 — data consistency):** the corridor fixtures that used to live in this
module were *moved*, not copied, into :mod:`app.tools.intelligence`, which is now the single source
of mock route truth shared by ``search_routes``, ``get_fare_estimate``, ``get_delay_prediction``
and ``get_route_details``. Duplicating R1/R2/R3 inside each tool would let them disagree about the
same route, so this class is now a thin, stable facade over that one dataset:

* the A3 public surface is unchanged (``candidates_for`` / ``has_corridor`` / ``known_corridors`` /
  ``data_source``), so every existing caller and test keeps working;
* the returned :class:`~app.schemas.candidate.RouteCandidate` shape is unchanged (API_CONTRACTS
  §6/§9 — additive only), which is where Workstream B later plugs real ``search_routes`` data in.

Guarantees (inherited from the shared dataset):

* **Deterministic** — same ``(origin, destination)`` always yields the same candidates, so the demo
  and tests are reproducible (AGENT_SPEC §6).
* **Honest** — every candidate is ``data_source=mock`` with a note saying so; unknown corridors
  return an empty list (the agent then reports honestly rather than inventing routes).
* **Consistent** — a candidate's fare/delay figures are the *same* numbers ``get_fare_estimate``
  and ``get_delay_prediction`` return for that route id (A7 brief §15).

The Colombo Fort → Ella corridor mirrors docs/DEMO.md §4.1 (R1/R2/R3), including one candidate
deliberately over the golden budget so the hard-constraint filter has something to exclude. Values
are illustrative (DEMO §4 explicitly says so) — the *winner* is never hard-coded; it is computed by
the decision engine from the request's constraints/preferences.
"""

from __future__ import annotations

from typing import Optional

from app.schemas.candidate import RouteCandidate
from app.schemas.route import DataSource
from app.tools.intelligence import MockRouteIntelligence


class MockCandidateProvider:
    """Small deterministic provider of mock :class:`RouteCandidate` objects.

    A3's candidate source, now backed by the A7 shared mock route truth so the four intelligence
    tools can never contradict each other about the same route.
    """

    #: Every candidate from this provider is mock by definition.
    data_source = DataSource.mock

    def __init__(self, intelligence: Optional[MockRouteIntelligence] = None) -> None:
        self._intelligence = intelligence or MockRouteIntelligence()

    @property
    def intelligence(self) -> MockRouteIntelligence:
        """The shared mock route truth this provider reads from (A7 brief §15)."""
        return self._intelligence

    def candidates_for(
        self, origin: Optional[str], destination: Optional[str]
    ) -> list[RouteCandidate]:
        """Return fresh mock candidates for a corridor, or ``[]`` if it is unknown."""
        return self._intelligence.candidates_for(origin, destination)

    def has_corridor(self, origin: Optional[str], destination: Optional[str]) -> bool:
        """True when the provider holds mock data for this corridor."""
        return self._intelligence.has_corridor(origin, destination)

    def known_corridors(self) -> list[tuple[str, str]]:
        """The corridors this mock knows about (for honest 'unknown corridor' messaging)."""
        return self._intelligence.known_corridors()
