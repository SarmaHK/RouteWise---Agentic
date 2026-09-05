"""Shared deterministic mock route intelligence (Workstream A, Phase A7).

This module is the **single source of mock route truth**. Every intelligence capability the agent
can call in A7 reads from the one dataset below, so the four tools can never disagree about a
route (A7 brief §5/§15):

    search_routes(Colombo Fort → Ella) → R1/R2/R3 candidates
    get_fare_estimate(R1)              → R1's fare        (the same R1)
    get_delay_prediction(R1)           → R1's delay       (the same R1)
    get_route_details(R1)              → R1's legs        (the same R1)

Guarantees:

* **Deterministic** — the data is a frozen, module-level table: same input ⇒ same output, with no
  randomness, no clocks, and no I/O (A7 brief §5/§7).
* **Internally consistent** — the leg-level detail is constructed so it *sums* to the route-level
  figures: leg durations → ``total_duration_min``, leg fares → ``total_fare_lkr``, leg walking →
  ``walking_km``, leg delays → ``delay_min_estimate``, and the number of vehicle legs − 1 →
  ``transfers``. ``tests/test_mock_intelligence_a7.py`` asserts those invariants, so a future edit
  that breaks consistency fails loudly instead of silently contradicting itself.
* **Honest** — every payload carries ``data_source="mock"`` and a note saying the figures are
  illustrative. Nothing here claims to be real-time pricing, a live delay, or a seat (A7 brief §24).
* **Bounded** — an unknown route id yields ``None`` from every accessor, which the tools turn into
  a structured ``ROUTE_NOT_FOUND`` failure. A route is never invented (A7 brief §18).

Architecture (A7 brief §3/§10): the **agent** decides what it needs, the **tools**
(:mod:`app.tools.capabilities`) expose the capabilities, **this provider** returns deterministic
data, and the **A6 decision engine** decides. Neither the agent nor the decision engine imports
this module; only the tools do.

Workstream B replacement point (A7 brief §26): B swaps this module's dataset for real
PostgreSQL/PostGIS/GTFS-backed intelligence **behind the same tool contracts**. Because the agent
and the decision engine only ever see :class:`~app.tools.base.ToolResult` payloads, the agent does
not change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from app.schemas.candidate import CandidateAvailability, RouteCandidate
from app.schemas.route import DataSource, Leg

_WS_RE = re.compile(r"\s+")

#: Honesty note carried by every mock candidate (unchanged wording from A3).
MOCK_NOTE = "Mock candidate (Phase A3) — illustrative, not live Sri Lankan transit data."

#: Honesty note carried by every mock fare/delay/details payload (A7 brief §7/§8/§24).
MOCK_INTEL_NOTE = (
    "Deterministic mock intelligence (Phase A7) — illustrative, simulated, "
    "not live pricing, not a live delay, and not a seat/booking."
)


def normalize_corridor(origin: Optional[str], destination: Optional[str]) -> tuple[str, str]:
    """Normalize a corridor key: lowercase, trimmed, internal whitespace collapsed."""

    def norm(value: Optional[str]) -> str:
        return _WS_RE.sub(" ", (value or "").strip().lower())

    return norm(origin), norm(destination)


@dataclass(frozen=True)
class MockRoute:
    """One route in the shared mock truth: candidate-level figures **plus** leg-level detail.

    Frozen so no caller can mutate the dataset (a mutable fixture would make "same input ⇒ same
    output" depend on call order). ``legs`` are :class:`~app.schemas.route.Leg` kwargs; fresh models
    are built per call.
    """

    id: str
    origin: str
    destination: str
    summary: str
    modes: tuple[str, ...]
    total_duration_min: float
    total_fare_lkr: float
    transfers: int
    walking_km: float
    delay_risk: str
    delay_min_estimate: float
    legs: tuple[dict[str, Any], ...] = ()

    def candidate_kwargs(self) -> dict[str, Any]:
        """The :class:`RouteCandidate` view of this route (the authoritative structured shape)."""
        return {
            "id": self.id,
            "summary": self.summary,
            "modes": list(self.modes),
            "total_duration_min": self.total_duration_min,
            "total_fare_lkr": self.total_fare_lkr,
            "transfers": self.transfers,
            "walking_km": self.walking_km,
            "delay_risk": self.delay_risk,
            "delay_min_estimate": self.delay_min_estimate,
        }


# --------------------------------------------------------------------------- #
# The dataset — Colombo Fort → Ella (the golden corridor, docs/DEMO.md §4.1) plus two neighbouring
# corridors so "unknown route" and "unknown corridor" are both demonstrable. R3 is deliberately
# over the golden LKR 2,000 budget so the A6 hard-constraint filter has something to exclude. The
# *winner* is never decided here — the A6 engine computes it from the request (A7 brief §6/§21).
# --------------------------------------------------------------------------- #
_ROUTES: tuple[MockRoute, ...] = (
    MockRoute(
        id="R1",
        origin="Colombo Fort",
        destination="Ella",
        summary="Walk + tuk to the station, then the hill-country train Colombo → Ella.",
        modes=("walk", "tuk", "train"),
        total_duration_min=420.0,
        total_fare_lkr=1600.0,
        transfers=1,
        walking_km=0.3,
        delay_risk="low",
        delay_min_estimate=10.0,
        legs=(
            {
                "id": "R1-L1",
                "mode": "walk",
                "origin": "Colombo Fort",
                "destination": "Pettah bus halt",
                "duration_min": 5.0,
                "fare_lkr": 0.0,
                "walking_km": 0.3,
                "delay_risk": "none",
                "delay_min_estimate": 0.0,
                "notes": "Short access walk, kept to 300 m for a heavy bag.",
            },
            {
                "id": "R1-L2",
                "mode": "tuk",
                "origin": "Pettah bus halt",
                "destination": "Colombo Fort Station",
                "duration_min": 15.0,
                "fare_lkr": 300.0,
                "walking_km": 0.0,
                "delay_risk": "low",
                "delay_min_estimate": 2.0,
                "notes": "Three-wheeler hop to the platform entrance.",
            },
            {
                "id": "R1-L3",
                "mode": "train",
                "origin": "Colombo Fort Station",
                "destination": "Ella",
                "duration_min": 400.0,
                "fare_lkr": 1300.0,
                "walking_km": 0.0,
                "delay_risk": "low",
                "delay_min_estimate": 8.0,
                "notes": "Hill-country line; no change of train en route.",
            },
        ),
    ),
    MockRoute(
        id="R2",
        origin="Colombo Fort",
        destination="Ella",
        summary="Direct bus Colombo → Ella with a short walk at each end.",
        modes=("walk", "bus"),
        total_duration_min=360.0,
        total_fare_lkr=1200.0,
        transfers=0,
        walking_km=1.5,
        delay_risk="moderate",
        delay_min_estimate=30.0,
        legs=(
            {
                "id": "R2-L1",
                "mode": "walk",
                "origin": "Colombo Fort",
                "destination": "Bastian Hill bus stop",
                "duration_min": 25.0,
                "fare_lkr": 0.0,
                "walking_km": 1.5,
                "delay_risk": "none",
                "delay_min_estimate": 0.0,
                "notes": "Access walk to the intercity bus stop (1.5 km in total).",
            },
            {
                "id": "R2-L2",
                "mode": "bus",
                "origin": "Bastian Hill bus stop",
                "destination": "Ella",
                "duration_min": 335.0,
                "fare_lkr": 1200.0,
                "walking_km": 0.0,
                "delay_risk": "moderate",
                "delay_min_estimate": 30.0,
                "notes": "Single bus, no transfer; road traffic makes the delay moderate.",
            },
        ),
    ),
    MockRoute(
        id="R3",
        origin="Colombo Fort",
        destination="Ella",
        summary="Tuk + train + connecting bus — fastest, but 2 transfers and over budget.",
        modes=("tuk", "train", "bus"),
        total_duration_min=330.0,
        total_fare_lkr=2350.0,
        transfers=2,
        walking_km=0.4,
        delay_risk="low",
        delay_min_estimate=10.0,
        legs=(
            {
                "id": "R3-L1",
                "mode": "tuk",
                "origin": "Colombo Fort",
                "destination": "Colombo Fort Station",
                "duration_min": 25.0,
                "fare_lkr": 350.0,
                "walking_km": 0.4,
                "delay_risk": "low",
                "delay_min_estimate": 2.0,
                "notes": "Includes the 0.4 km walk from the station exit to the tuk stand.",
            },
            {
                "id": "R3-L2",
                "mode": "train",
                "origin": "Colombo Fort Station",
                "destination": "Nanu Oya",
                "duration_min": 245.0,
                "fare_lkr": 1500.0,
                "walking_km": 0.0,
                "delay_risk": "low",
                "delay_min_estimate": 8.0,
                "notes": "Hill-country line; alight at Nanu Oya for the connecting bus.",
            },
            {
                "id": "R3-L3",
                "mode": "bus",
                "origin": "Nanu Oya",
                "destination": "Ella",
                "duration_min": 60.0,
                "fare_lkr": 500.0,
                "walking_km": 0.0,
                "delay_risk": "none",
                "delay_min_estimate": 0.0,
                "notes": "Connecting bus for the last leg into Ella.",
            },
        ),
    ),
    MockRoute(
        id="K1",
        origin="Kandy",
        destination="Ella",
        summary="Scenic hill-country train Kandy → Ella (minimal walking).",
        modes=("walk", "train"),
        total_duration_min=420.0,
        total_fare_lkr=1200.0,
        transfers=0,
        walking_km=0.4,
        delay_risk="low",
        delay_min_estimate=10.0,
        legs=(
            {
                "id": "K1-L1",
                "mode": "walk",
                "origin": "Kandy",
                "destination": "Kandy Station",
                "duration_min": 20.0,
                "fare_lkr": 0.0,
                "walking_km": 0.4,
                "delay_risk": "none",
                "delay_min_estimate": 0.0,
                "notes": "Access walk to Kandy Station.",
            },
            {
                "id": "K1-L2",
                "mode": "train",
                "origin": "Kandy Station",
                "destination": "Ella",
                "duration_min": 400.0,
                "fare_lkr": 1200.0,
                "walking_km": 0.0,
                "delay_risk": "low",
                "delay_min_estimate": 10.0,
                "notes": "Direct scenic service; no change of train.",
            },
        ),
    ),
    MockRoute(
        id="K2",
        origin="Kandy",
        destination="Ella",
        summary="Direct bus Kandy → Ella (cheaper, more walking at the stops).",
        modes=("walk", "bus"),
        total_duration_min=330.0,
        total_fare_lkr=800.0,
        transfers=0,
        walking_km=1.2,
        delay_risk="moderate",
        delay_min_estimate=25.0,
        legs=(
            {
                "id": "K2-L1",
                "mode": "walk",
                "origin": "Kandy",
                "destination": "Kandy bus stand",
                "duration_min": 20.0,
                "fare_lkr": 0.0,
                "walking_km": 1.2,
                "delay_risk": "none",
                "delay_min_estimate": 0.0,
                "notes": "Access walk to the bus stand.",
            },
            {
                "id": "K2-L2",
                "mode": "bus",
                "origin": "Kandy bus stand",
                "destination": "Ella",
                "duration_min": 310.0,
                "fare_lkr": 800.0,
                "walking_km": 0.0,
                "delay_risk": "moderate",
                "delay_min_estimate": 25.0,
                "notes": "Single bus, no transfer.",
            },
        ),
    ),
    MockRoute(
        id="C1",
        origin="Colombo Fort",
        destination="Kandy",
        summary="Intercity train Colombo Fort → Kandy (low walking, comfortable).",
        modes=("walk", "train"),
        total_duration_min=150.0,
        total_fare_lkr=1500.0,
        transfers=0,
        walking_km=0.3,
        delay_risk="low",
        delay_min_estimate=8.0,
        legs=(
            {
                "id": "C1-L1",
                "mode": "walk",
                "origin": "Colombo Fort",
                "destination": "Colombo Fort Station",
                "duration_min": 12.0,
                "fare_lkr": 0.0,
                "walking_km": 0.3,
                "delay_risk": "none",
                "delay_min_estimate": 0.0,
                "notes": "Access walk to the platform.",
            },
            {
                "id": "C1-L2",
                "mode": "train",
                "origin": "Colombo Fort Station",
                "destination": "Kandy",
                "duration_min": 138.0,
                "fare_lkr": 1500.0,
                "walking_km": 0.0,
                "delay_risk": "low",
                "delay_min_estimate": 8.0,
                "notes": "Direct intercity service.",
            },
        ),
    ),
    MockRoute(
        id="C2",
        origin="Colombo Fort",
        destination="Kandy",
        summary="Express bus Colombo → Kandy (cheaper, a bit more walking).",
        modes=("walk", "bus"),
        total_duration_min=180.0,
        total_fare_lkr=900.0,
        transfers=0,
        walking_km=1.0,
        delay_risk="moderate",
        delay_min_estimate=20.0,
        legs=(
            {
                "id": "C2-L1",
                "mode": "walk",
                "origin": "Colombo Fort",
                "destination": "Bastian Hill bus stop",
                "duration_min": 15.0,
                "fare_lkr": 0.0,
                "walking_km": 1.0,
                "delay_risk": "none",
                "delay_min_estimate": 0.0,
                "notes": "Access walk to the express-bus stop.",
            },
            {
                "id": "C2-L2",
                "mode": "bus",
                "origin": "Bastian Hill bus stop",
                "destination": "Kandy",
                "duration_min": 165.0,
                "fare_lkr": 900.0,
                "walking_km": 0.0,
                "delay_risk": "moderate",
                "delay_min_estimate": 20.0,
                "notes": "Single express bus, no transfer.",
            },
        ),
    ),
)

#: Route-id index. Ids are unique across corridors, so one flat index is enough — and it is what
#: makes ``get_fare_estimate("R1")`` and ``search_routes(...)``'s R1 provably the *same* route.
_BY_ID: dict[str, MockRoute] = {route.id.upper(): route for route in _ROUTES}

#: Corridor index, built from the same routes (never a second copy of the data).
_BY_CORRIDOR: dict[tuple[str, str], list[MockRoute]] = {}
for _route in _ROUTES:
    _BY_CORRIDOR.setdefault(normalize_corridor(_route.origin, _route.destination), []).append(
        _route
    )


class MockRouteIntelligence:
    """The A7 deterministic mock intelligence provider — one dataset, four honest views.

    Stateless and side-effect free: every accessor builds **fresh** models/dicts so callers never
    share mutable state, and the same argument always produces the same payload (A7 brief §5).
    Accessors return ``None`` for an unknown route id; the *tool* turns that into a structured
    ``ROUTE_NOT_FOUND`` failure (A7 brief §18), so no layer ever fabricates a route.
    """

    #: Every payload from this provider is mock by definition (A7 brief §11/§24).
    data_source = DataSource.mock

    # ------------------------------------------------------------------ #
    # Route / corridor lookup
    # ------------------------------------------------------------------ #
    def route_ids(self) -> list[str]:
        """All known mock route ids, in dataset order."""
        return [route.id for route in _ROUTES]

    def is_known(self, route_id: Optional[str]) -> bool:
        """True when the mock truth holds this route id (trimmed, case-insensitive)."""
        return self._lookup(route_id) is not None

    def known_corridors(self) -> list[tuple[str, str]]:
        """The corridors this mock knows about (for honest 'unknown corridor' messaging)."""
        return sorted(_BY_CORRIDOR.keys())

    def has_corridor(self, origin: Optional[str], destination: Optional[str]) -> bool:
        """True when the provider holds mock data for this corridor."""
        return normalize_corridor(origin, destination) in _BY_CORRIDOR

    def routes_for(self, origin: Optional[str], destination: Optional[str]) -> list[MockRoute]:
        """The mock routes for a corridor, or ``[]`` when the corridor is unknown."""
        return list(_BY_CORRIDOR.get(normalize_corridor(origin, destination), []))

    def candidates_for(
        self, origin: Optional[str], destination: Optional[str]
    ) -> list[RouteCandidate]:
        """Fresh mock candidates for a corridor — the ``search_routes`` view of the same truth."""
        return [
            RouteCandidate(
                origin=(origin or "").strip(),
                destination=(destination or "").strip(),
                availability=CandidateAvailability.unknown,
                notes=MOCK_NOTE,
                data_source=DataSource.mock,
                **route.candidate_kwargs(),
            )
            for route in self.routes_for(origin, destination)
        ]

    def candidate(self, route_id: Optional[str]) -> Optional[RouteCandidate]:
        """The authoritative structured candidate for one route id, or ``None`` when unknown."""
        route = self._lookup(route_id)
        if route is None:
            return None
        return RouteCandidate(
            origin=route.origin,
            destination=route.destination,
            availability=CandidateAvailability.unknown,
            notes=MOCK_NOTE,
            data_source=DataSource.mock,
            **route.candidate_kwargs(),
        )

    # ------------------------------------------------------------------ #
    # The three A7 intelligence views (fare / delay / details)
    # ------------------------------------------------------------------ #
    def fare_estimate(self, route_id: Optional[str]) -> Optional[dict[str, Any]]:
        """The ``get_fare_estimate`` payload for a route, or ``None`` when the route is unknown.

        Field names follow the existing contract (API_CONTRACTS §3/§6 and ``RouteCandidate``):
        ``total_fare_lkr`` + ``currency``. The A7 brief's ``estimated_fare_lkr`` example maps onto
        that established name so there is only **one** fare vocabulary (A7 brief §7/§9).
        """
        route = self._lookup(route_id)
        if route is None:
            return None
        return {
            "route_id": route.id,
            "origin": route.origin,
            "destination": route.destination,
            "total_fare_lkr": route.total_fare_lkr,
            "currency": "LKR",
            "fare_breakdown": [
                {"leg_id": leg["id"], "mode": leg["mode"], "fare_lkr": leg["fare_lkr"]}
                for leg in route.legs
            ],
            "data_source": DataSource.mock.value,
            "note": MOCK_INTEL_NOTE,
        }

    def delay_prediction(self, route_id: Optional[str]) -> Optional[dict[str, Any]]:
        """The ``get_delay_prediction`` payload for a route, or ``None`` when unknown.

        Uses the existing ``delay_risk`` / ``delay_min_estimate`` names (the A7 brief's
        ``predicted_delay_minutes`` example maps onto ``delay_min_estimate``). The ``note`` states
        plainly that this is simulated — never a live delay (A7 brief §8/§24).
        """
        route = self._lookup(route_id)
        if route is None:
            return None
        return {
            "route_id": route.id,
            "origin": route.origin,
            "destination": route.destination,
            "delay_risk": route.delay_risk,
            "delay_min_estimate": route.delay_min_estimate,
            "leg_delays": [
                {
                    "leg_id": leg["id"],
                    "mode": leg["mode"],
                    "delay_risk": leg["delay_risk"],
                    "delay_min_estimate": leg["delay_min_estimate"],
                }
                for leg in route.legs
            ],
            "data_source": DataSource.mock.value,
            "note": MOCK_INTEL_NOTE,
        }

    def route_details(self, route_id: Optional[str]) -> Optional[dict[str, Any]]:
        """The ``get_route_details`` payload for a route, or ``None`` when unknown.

        Reuses the existing :class:`~app.schemas.route.Leg` / :class:`RouteCandidate` vocabulary
        instead of inventing a second route representation (A7 brief §9): ``legs`` are ``Leg``
        models and the route-level fields use the names the candidate already carries.
        """
        route = self._lookup(route_id)
        if route is None:
            return None
        return {
            "route_id": route.id,
            "origin": route.origin,
            "destination": route.destination,
            "summary": route.summary,
            "modes": list(route.modes),
            "legs": self.legs_for(route.id),
            "total_duration_min": route.total_duration_min,
            "total_fare_lkr": route.total_fare_lkr,
            "currency": "LKR",
            "transfers": route.transfers,
            "walking_km": route.walking_km,
            "delay_risk": route.delay_risk,
            "delay_min_estimate": route.delay_min_estimate,
            "data_source": DataSource.mock.value,
            "note": MOCK_INTEL_NOTE,
        }

    def legs_for(self, route_id: Optional[str]) -> list[Leg]:
        """Fresh :class:`Leg` models for a route (``[]`` when the route is unknown)."""
        route = self._lookup(route_id)
        if route is None:
            return []
        return [Leg(data_source=DataSource.mock, **leg) for leg in route.legs]

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    @staticmethod
    def _lookup(route_id: Optional[str]) -> Optional[MockRoute]:
        """Resolve a route id tolerantly (trimmed, case-insensitive) or return ``None``."""
        if not route_id:
            return None
        return _BY_ID.get(str(route_id).strip().upper())
