"""Deterministic mock candidate provider (Workstream A, Phase A3).

This is the ONLY source of route candidates in A3. It returns a small, fixed set of obviously
mock candidates for a few Sri-Lankan corridors so the decision engine has real structure to
reason over — it is **not** a fake "live Sri Lankan transit system" (A3 brief §7, §17).

Guarantees:

* **Deterministic** — same ``(origin, destination)`` always yields the same candidates, so the
  demo and tests are reproducible (AGENT_SPEC §6).
* **Honest** — every candidate is ``data_source=mock`` with a note saying so; unknown corridors
  return an empty list (the agent then reports honestly rather than inventing routes).
* **Signature-stable** — Workstream B replaces this with real ``search_routes`` data later with
  no change to the :class:`~app.schemas.candidate.RouteCandidate` shape (API_CONTRACTS §6/§9).

The Colombo Fort → Ella corridor mirrors docs/DEMO.md §4.1 (R1/R2/R3), including one candidate
deliberately over the golden budget so the hard-constraint filter has something to exclude.
Values are illustrative (DEMO §4 explicitly says so) — the *winner* is never hard-coded; it is
computed by the decision engine from the request's constraints/preferences.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from app.schemas.candidate import CandidateAvailability, RouteCandidate
from app.schemas.route import DataSource

_WS_RE = re.compile(r"\s+")

_MOCK_NOTE = "Mock candidate (Phase A3) — illustrative, not live Sri Lankan transit data."


def _key(origin: Optional[str], destination: Optional[str]) -> tuple[str, str]:
    """Normalize a corridor key: lowercase, trimmed, internal whitespace collapsed."""
    def norm(value: Optional[str]) -> str:
        return _WS_RE.sub(" ", (value or "").strip().lower())

    return norm(origin), norm(destination)


# Corridor fixtures, keyed by normalized (origin, destination). Each dict is the kwargs for a
# RouteCandidate; fresh models are built on every call so callers never share mutable state.
_FIXTURES: dict[tuple[str, str], list[dict[str, Any]]] = {
    ("colombo fort", "ella"): [
        {
            "id": "R1",
            "summary": "Walk + tuk to the station, then the hill-country train Colombo → Ella.",
            "modes": ["walk", "tuk", "train"],
            "total_duration_min": 420.0,
            "total_fare_lkr": 1600.0,
            "transfers": 1,
            "walking_km": 0.3,
            "delay_risk": "low",
            "delay_min_estimate": 10.0,
        },
        {
            "id": "R2",
            "summary": "Direct bus Colombo → Ella with a short walk at each end.",
            "modes": ["walk", "bus"],
            "total_duration_min": 360.0,
            "total_fare_lkr": 1200.0,
            "transfers": 0,
            "walking_km": 1.5,
            "delay_risk": "moderate",
            "delay_min_estimate": 30.0,
        },
        {
            "id": "R3",
            "summary": "Tuk + train + connecting bus — fastest, but 2 transfers and over budget.",
            "modes": ["tuk", "train", "bus"],
            "total_duration_min": 330.0,
            "total_fare_lkr": 2350.0,
            "transfers": 2,
            "walking_km": 0.4,
            "delay_risk": "low",
            "delay_min_estimate": 10.0,
        },
    ],
    ("kandy", "ella"): [
        {
            "id": "K1",
            "summary": "Scenic hill-country train Kandy → Ella (minimal walking).",
            "modes": ["walk", "train"],
            "total_duration_min": 420.0,
            "total_fare_lkr": 1200.0,
            "transfers": 0,
            "walking_km": 0.4,
            "delay_risk": "low",
            "delay_min_estimate": 10.0,
        },
        {
            "id": "K2",
            "summary": "Direct bus Kandy → Ella (cheaper, more walking at the stops).",
            "modes": ["walk", "bus"],
            "total_duration_min": 330.0,
            "total_fare_lkr": 800.0,
            "transfers": 0,
            "walking_km": 1.2,
            "delay_risk": "moderate",
            "delay_min_estimate": 25.0,
        },
    ],
    ("colombo fort", "kandy"): [
        {
            "id": "C1",
            "summary": "Intercity train Colombo Fort → Kandy (low walking, comfortable).",
            "modes": ["walk", "train"],
            "total_duration_min": 150.0,
            "total_fare_lkr": 1500.0,
            "transfers": 0,
            "walking_km": 0.3,
            "delay_risk": "low",
            "delay_min_estimate": 8.0,
        },
        {
            "id": "C2",
            "summary": "Express bus Colombo → Kandy (cheaper, a bit more walking).",
            "modes": ["walk", "bus"],
            "total_duration_min": 180.0,
            "total_fare_lkr": 900.0,
            "transfers": 0,
            "walking_km": 1.0,
            "delay_risk": "moderate",
            "delay_min_estimate": 20.0,
        },
    ],
}


class MockCandidateProvider:
    """Small deterministic provider of mock :class:`RouteCandidate` objects."""

    #: Every candidate from this provider is mock by definition.
    data_source = DataSource.mock

    def candidates_for(
        self, origin: Optional[str], destination: Optional[str]
    ) -> list[RouteCandidate]:
        """Return fresh mock candidates for a corridor, or ``[]`` if it is unknown."""
        fixtures = _FIXTURES.get(_key(origin, destination))
        if not fixtures:
            return []
        return [
            RouteCandidate(
                origin=(origin or "").strip(),
                destination=(destination or "").strip(),
                availability=CandidateAvailability.unknown,
                notes=_MOCK_NOTE,
                data_source=DataSource.mock,
                **fixture,
            )
            for fixture in fixtures
        ]

    def has_corridor(self, origin: Optional[str], destination: Optional[str]) -> bool:
        """True when the provider holds mock data for this corridor."""
        return _key(origin, destination) in _FIXTURES

    def known_corridors(self) -> list[tuple[str, str]]:
        """The corridors this mock knows about (for honest 'unknown corridor' messaging)."""
        return sorted(_FIXTURES.keys())
