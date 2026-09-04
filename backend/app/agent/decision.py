"""Transparent, deterministic decision engine (Workstream A, Phase A3).

This is the agent's reasoning core for A3: given a validated
:class:`~app.schemas.travel_request.TravelRequest` and a list of
:class:`~app.schemas.candidate.RouteCandidate`, it **filters hard constraints**, **scores soft
preferences**, **ranks**, picks a recommendation, keeps alternatives with honest trade-offs, and
explains *why* — all deterministically (A3 brief §8–§9; AGENT_SPEC §8–§11).

Why deterministic (not an LLM): AGENT_SPEC §6 requires "same inputs + same mock data ⇒ same
recommendation" for a reliable demo, and the A3 brief §10 says *do not* make Qwen blindly decide.
Qwen remains used for A2 natural-language understanding only; a Qwen-phrased explanation is a
later, additive enhancement behind the same seam.

The scoring model (documented here because AGENT_SPEC §8 left weights "TBD until A6"):

1. **Hard filter** (§9): origin, destination, ``total_fare_lkr <= budget``, and estimated
   arrival ``<= arrival_deadline`` (arrival = departure + duration + predicted delay). A
   candidate violating any hard constraint is *excluded*, never silently dropped.
2. **Soft score** (§10): each lower-is-better signal (``walking_km``, ``total_duration_min``,
   ``transfers``, ``total_fare_lkr``) is min–max normalized across the survivors (best → 1.0),
   combined with base weights ``walking 0.30 / duration 0.25 / transfers 0.20 / fare 0.25``.
3. **Luggage/preference awareness** (§10 golden rule): ``walking_preference=minimize`` scales the
   walking weight ×1.75 (``ok`` ×0.6); ``luggage=heavy`` scales walking ×1.5 **and** transfers
   ×1.4 (``none`` scales walking ×0.8). Weights are renormalized to sum to 1.
4. **Delay penalty**: ``none 0 / low 0.02 / moderate 0.06 / high 0.12`` subtracted from the score.
5. **Rank** by score (tie-break: lower fare → fewer transfers → id). The top is the
   recommendation; the rest become alternatives.

This is genuine reasoning over data, not a hard-coded winner: for the golden Colombo Fort → Ella
corridor, ``heavy`` + ``minimize`` selects R1 (least walking, 1 transfer) while the *same*
candidates with no preferences select R2 (cheaper, faster, direct) — see tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Optional

from app.schemas.candidate import RouteCandidate
from app.schemas.route import DataSource, Recommendation
from app.schemas.travel_request import TravelRequest

_INF = float("inf")


@dataclass
class ScoredCandidate:
    """A hard-constraint survivor with its computed score and normalized signals."""

    candidate: RouteCandidate
    score: float
    signals: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


@dataclass
class ExcludedCandidate:
    """A candidate removed by a hard constraint, with the honest reason why."""

    candidate: RouteCandidate
    constraint: str  # origin | destination | budget | arrival_deadline
    reason: str  # human-readable, e.g. "Over budget (LKR 2,350 > LKR 2,000)."


@dataclass
class Decision:
    """The full, explainable result of evaluating candidates against a request."""

    recommendation: Optional[Recommendation]
    alternatives: list[Recommendation]
    reasoning: Optional[str]
    scored: list[ScoredCandidate]
    excluded: list[ExcludedCandidate]
    hard_constraints: dict[str, Any]
    soft_preferences: dict[str, Any]
    assumptions: list[str]
    satisfied: bool  # True when at least one candidate met every hard constraint
    data_source: DataSource = DataSource.mock


def _lkr(value: Optional[float]) -> str:
    return f"LKR {value:,.0f}" if value is not None else "—"


def _km(value: Optional[float]) -> str:
    return f"{value:g} km" if value is not None else "—"


def _mins(value: Optional[float]) -> str:
    return f"{int(round(value))} min" if value is not None else "—"


class DecisionEngine:
    """Deterministic hard-filter + soft-score route decision engine (A3)."""

    #: Base soft-signal weights (all "lower is better"); renormalized after preference scaling.
    BASE_WEIGHTS: dict[str, float] = {
        "walking_km": 0.30,
        "total_duration_min": 0.25,
        "transfers": 0.20,
        "total_fare_lkr": 0.25,
    }

    #: Delay-risk penalty subtracted from the normalized score.
    DELAY_PENALTY: dict[str, float] = {
        "none": 0.0,
        "low": 0.02,
        "moderate": 0.06,
        "high": 0.12,
    }

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def decide(
        self, request: TravelRequest, candidates: list[RouteCandidate]
    ) -> Decision:
        """Evaluate ``candidates`` against ``request`` and produce a :class:`Decision`."""
        assumptions: list[str] = []
        hard = self._hard_snapshot(request)
        weights = self._weights_for(request)
        soft = self._soft_snapshot(request, weights)

        if not candidates:
            reasoning = (
                f"No mock candidate routes are available for "
                f"{request.origin or '?'} → {request.destination or '?'} in Phase A3."
            )
            return Decision(
                recommendation=None,
                alternatives=[],
                reasoning=reasoning,
                scored=[],
                excluded=[],
                hard_constraints=hard,
                soft_preferences=soft,
                assumptions=assumptions,
                satisfied=False,
            )

        survivors, excluded = self._apply_hard_constraints(
            request, candidates, assumptions
        )
        scored = self._score_survivors(survivors, weights)
        scored.sort(
            key=lambda sc: (
                -sc.score,
                sc.candidate.total_fare_lkr if sc.candidate.total_fare_lkr is not None else _INF,
                sc.candidate.transfers if sc.candidate.transfers is not None else _INF,
                sc.candidate.id,
            )
        )

        if not scored:
            # Every candidate violated a hard constraint — report honestly (§9), never pick one.
            closest = min(
                excluded,
                key=lambda e: (e.candidate.total_fare_lkr or _INF),
                default=None,
            )
            reasoning = self._no_survivor_reasoning(request, excluded, closest)
            alternatives = [
                self._excluded_to_recommendation(e) for e in excluded[:3]
            ]
            return Decision(
                recommendation=None,
                alternatives=alternatives,
                reasoning=reasoning,
                scored=[],
                excluded=excluded,
                hard_constraints=hard,
                soft_preferences=soft,
                assumptions=assumptions,
                satisfied=False,
            )

        winner = scored[0]
        winner.reasons = self._reasons_for(request, winner, scored)
        recommendation = self._to_recommendation(winner, is_recommended=True)
        recommendation.within_budget = self._within_budget(request, winner.candidate)

        alternatives = self._build_alternatives(
            request, winner.candidate, scored[1:], excluded
        )
        reasoning = self._reasoning(request, winner, scored[1:], excluded)

        return Decision(
            recommendation=recommendation,
            alternatives=alternatives,
            reasoning=reasoning,
            scored=scored,
            excluded=excluded,
            hard_constraints=hard,
            soft_preferences=soft,
            assumptions=assumptions,
            satisfied=True,
        )

    # ------------------------------------------------------------------ #
    # Hard constraints (§9)
    # ------------------------------------------------------------------ #
    def _hard_snapshot(self, request: TravelRequest) -> dict[str, Any]:
        return {
            "origin": request.origin,
            "destination": request.destination,
            "budget_lkr": request.budget,
            "arrival_deadline": (
                request.arrival_deadline.isoformat()
                if request.arrival_deadline
                else None
            ),
        }

    def _apply_hard_constraints(
        self,
        request: TravelRequest,
        candidates: list[RouteCandidate],
        assumptions: list[str],
    ) -> tuple[list[RouteCandidate], list[ExcludedCandidate]]:
        survivors: list[RouteCandidate] = []
        excluded: list[ExcludedCandidate] = []

        check_deadline = bool(request.departure_time and request.arrival_deadline)
        if request.arrival_deadline and not request.departure_time:
            assumptions.append(
                "Arrival-deadline check skipped: no departure time was given, so estimated "
                "arrival cannot be computed."
            )

        for candidate in candidates:
            violation = self._hard_violation(request, candidate, check_deadline)
            if violation is None:
                survivors.append(candidate)
            else:
                constraint, reason = violation
                excluded.append(
                    ExcludedCandidate(
                        candidate=candidate, constraint=constraint, reason=reason
                    )
                )
        return survivors, excluded

    def _hard_violation(
        self, request: TravelRequest, candidate: RouteCandidate, check_deadline: bool
    ) -> Optional[tuple[str, str]]:
        """Return ``(constraint, reason)`` if a hard constraint fails, else ``None``."""
        # Origin / destination are guaranteed by the corridor search, but enforced defensively.
        if request.origin and candidate.origin and (
            candidate.origin.strip().lower() != request.origin.strip().lower()
        ):
            return "origin", f"Does not start at {request.origin}."
        if request.destination and candidate.destination and (
            candidate.destination.strip().lower() != request.destination.strip().lower()
        ):
            return "destination", f"Does not reach {request.destination}."

        # Budget ceiling.
        if (
            request.budget is not None
            and candidate.total_fare_lkr is not None
            and candidate.total_fare_lkr > request.budget
        ):
            return "budget", (
                f"Over budget ({_lkr(candidate.total_fare_lkr)} > {_lkr(request.budget)})."
            )

        # Arrival deadline (only when both a departure time and a deadline are known).
        if (
            check_deadline
            and candidate.total_duration_min is not None
            and request.departure_time is not None
            and request.arrival_deadline is not None
        ):
            duration = timedelta(minutes=candidate.total_duration_min)
            delay = timedelta(minutes=candidate.delay_min_estimate or 0.0)
            est_arrival = request.departure_time + duration + delay
            if est_arrival > request.arrival_deadline:
                return "arrival_deadline", (
                    "Arrives after your deadline (est. "
                    f"{est_arrival:%H:%M} with predicted delay)."
                )
        return None

    # ------------------------------------------------------------------ #
    # Soft scoring (§10)
    # ------------------------------------------------------------------ #
    def _weights_for(self, request: TravelRequest) -> dict[str, float]:
        weights = dict(self.BASE_WEIGHTS)
        walk_pref = request.walking_preference.value if request.walking_preference else None
        luggage = request.luggage.value if request.luggage else None

        if walk_pref == "minimize":
            weights["walking_km"] *= 1.75
        elif walk_pref == "ok":
            weights["walking_km"] *= 0.6

        if luggage == "heavy":
            weights["walking_km"] *= 1.5
            weights["transfers"] *= 1.4
        elif luggage == "none":
            weights["walking_km"] *= 0.8

        total = sum(weights.values()) or 1.0
        return {name: round(w / total, 6) for name, w in weights.items()}

    def _soft_snapshot(
        self, request: TravelRequest, weights: dict[str, float]
    ) -> dict[str, Any]:
        return {
            "walking_preference": (
                request.walking_preference.value if request.walking_preference else None
            ),
            "luggage": request.luggage.value if request.luggage else None,
            "departure_time": (
                request.departure_time.isoformat() if request.departure_time else None
            ),
            "weights": weights,
        }

    def _score_survivors(
        self, survivors: list[RouteCandidate], weights: dict[str, float]
    ) -> list[ScoredCandidate]:
        if not survivors:
            return []

        # Min–max range per signal across survivors (lower is better).
        ranges: dict[str, tuple[float, float]] = {}
        for signal in self.BASE_WEIGHTS:
            values = [
                float(getattr(c, signal))
                for c in survivors
                if getattr(c, signal) is not None
            ]
            if values:
                ranges[signal] = (min(values), max(values))

        scored: list[ScoredCandidate] = []
        for candidate in survivors:
            signals: dict[str, float] = {}
            total = 0.0
            for signal, weight in weights.items():
                value = getattr(candidate, signal)
                if value is None or signal not in ranges:
                    norm = 0.0  # unknown signal earns no credit (never fabricate a value)
                else:
                    low, high = ranges[signal]
                    norm = 1.0 if high == low else (high - float(value)) / (high - low)
                signals[signal] = round(norm, 4)
                total += weight * norm

            penalty = self.DELAY_PENALTY.get((candidate.delay_risk or "").lower(), 0.0)
            score = round(max(0.0, min(1.0, total - penalty)), 3)
            scored.append(
                ScoredCandidate(candidate=candidate, score=score, signals=signals)
            )
        return scored

    # ------------------------------------------------------------------ #
    # Explanation (§8: concise reasons referencing the user's own constraints)
    # ------------------------------------------------------------------ #
    def _reasons_for(
        self,
        request: TravelRequest,
        winner: ScoredCandidate,
        scored: list[ScoredCandidate],
    ) -> list[str]:
        candidate = winner.candidate
        reasons: list[str] = []

        if (
            request.budget is not None
            and candidate.total_fare_lkr is not None
            and candidate.total_fare_lkr <= request.budget
        ):
            reasons.append(
                f"Within your {_lkr(request.budget)} budget (≈{_lkr(candidate.total_fare_lkr)})."
            )

        least_walk = self._is_least(candidate.walking_km, scored, "walking_km")
        if request.luggage and request.luggage.value == "heavy":
            transfers = candidate.transfers
            reasons.append(
                "Suitable for heavy luggage "
                f"({transfers} transfer{'s' if transfers != 1 else ''}"
                + (", least walking of the viable routes" if least_walk else "")
                + ")."
            )
        elif least_walk and request.walking_preference and (
            request.walking_preference.value == "minimize"
        ):
            reasons.append(
                f"Least walking of the viable routes (≈{_km(candidate.walking_km)}), "
                "matching your preference."
            )
        elif least_walk:
            reasons.append(
                f"Least walking of the viable routes (≈{_km(candidate.walking_km)})."
            )

        if self._is_least(candidate.total_duration_min, scored, "total_duration_min"):
            reasons.append(f"Fastest viable option (≈{_mins(candidate.total_duration_min)}).")
        if self._is_least(candidate.total_fare_lkr, scored, "total_fare_lkr"):
            reasons.append(
                f"Cheapest viable option (≈{_lkr(candidate.total_fare_lkr)})."
            )
        if (candidate.delay_risk or "").lower() in ("none", "low"):
            reasons.append("Low delay risk.")

        # De-duplicate while preserving order; keep it concise (max 4).
        seen: set[str] = set()
        unique = [r for r in reasons if not (r in seen or seen.add(r))]
        return unique[:4]

    @staticmethod
    def _is_least(
        value: Optional[float], scored: list[ScoredCandidate], signal: str
    ) -> bool:
        if value is None:
            return False
        others = [
            float(getattr(sc.candidate, signal))
            for sc in scored
            if getattr(sc.candidate, signal) is not None
        ]
        return bool(others) and float(value) <= min(others)

    def _trade_offs(
        self, request: TravelRequest, alt: RouteCandidate, rec: RouteCandidate
    ) -> list[str]:
        trade_offs: list[str] = []
        if (
            alt.total_fare_lkr is not None
            and rec.total_fare_lkr is not None
            and alt.total_fare_lkr < rec.total_fare_lkr
        ):
            trade_offs.append(
                f"Cheaper (≈{_lkr(alt.total_fare_lkr)} vs {_lkr(rec.total_fare_lkr)})."
            )
        if (
            alt.total_duration_min is not None
            and rec.total_duration_min is not None
            and alt.total_duration_min < rec.total_duration_min
        ):
            trade_offs.append(
                f"Faster (≈{_mins(alt.total_duration_min)} vs {_mins(rec.total_duration_min)})."
            )
        if (
            alt.walking_km is not None
            and rec.walking_km is not None
            and alt.walking_km > rec.walking_km
        ):
            trade_offs.append(
                f"More walking (≈{_km(alt.walking_km)} vs {_km(rec.walking_km)})."
            )
        if (
            alt.transfers is not None
            and rec.transfers is not None
            and alt.transfers > rec.transfers
        ):
            trade_offs.append(f"More transfers ({alt.transfers} vs {rec.transfers}).")
        if (
            request.budget is not None
            and alt.total_fare_lkr is not None
            and alt.total_fare_lkr > request.budget
        ):
            trade_offs.append(
                f"Over budget (≈{_lkr(alt.total_fare_lkr)} > {_lkr(request.budget)})."
            )
        if not trade_offs:
            trade_offs.append("Similar overall; ranked slightly lower.")
        return trade_offs

    # ------------------------------------------------------------------ #
    # Recommendation / alternatives construction
    # ------------------------------------------------------------------ #
    def _to_recommendation(
        self, scored: ScoredCandidate, is_recommended: bool
    ) -> Recommendation:
        candidate = scored.candidate
        rationale = scored.reasons[0] if scored.reasons else None
        return Recommendation(
            id=candidate.id,
            summary=candidate.summary,
            total_duration_min=candidate.total_duration_min,
            total_fare_lkr=candidate.total_fare_lkr,
            transfers=candidate.transfers,
            walking_km=candidate.walking_km,
            within_budget=None,  # set by caller context below
            delay_risk=candidate.delay_risk,
            score=scored.score,
            rationale=rationale,
            reasons=list(scored.reasons),
            trade_offs=[],
            is_recommended=is_recommended,
            data_source=candidate.data_source,
        )

    def _build_alternatives(
        self,
        request: TravelRequest,
        rec_candidate: RouteCandidate,
        runners_up: list[ScoredCandidate],
        excluded: list[ExcludedCandidate],
    ) -> list[Recommendation]:
        alternatives: list[Recommendation] = []

        # Valid survivors first, ranked, each with honest trade-offs vs the recommendation (§11).
        for scored in runners_up:
            rec = self._to_recommendation(scored, is_recommended=False)
            rec.within_budget = self._within_budget(request, scored.candidate)
            rec.trade_offs = self._trade_offs(request, scored.candidate, rec_candidate)
            alternatives.append(rec)

        # Then any hard-constraint violators, clearly marked (§11), so the user sees why they lost.
        for exclusion in excluded:
            rec = Recommendation(
                id=exclusion.candidate.id,
                summary=exclusion.candidate.summary,
                total_duration_min=exclusion.candidate.total_duration_min,
                total_fare_lkr=exclusion.candidate.total_fare_lkr,
                transfers=exclusion.candidate.transfers,
                walking_km=exclusion.candidate.walking_km,
                within_budget=self._within_budget(request, exclusion.candidate),
                delay_risk=exclusion.candidate.delay_risk,
                score=None,
                rationale=exclusion.reason,
                trade_offs=[exclusion.reason],
                is_recommended=False,
                data_source=exclusion.candidate.data_source,
            )
            alternatives.append(rec)

        return alternatives[:3]

    def _excluded_to_recommendation(
        self, exclusion: ExcludedCandidate
    ) -> Recommendation:
        candidate = exclusion.candidate
        return Recommendation(
            id=candidate.id,
            summary=candidate.summary,
            total_duration_min=candidate.total_duration_min,
            total_fare_lkr=candidate.total_fare_lkr,
            transfers=candidate.transfers,
            walking_km=candidate.walking_km,
            within_budget=False,
            delay_risk=candidate.delay_risk,
            score=None,
            rationale=exclusion.reason,
            trade_offs=[exclusion.reason],
            is_recommended=False,
            data_source=candidate.data_source,
        )

    @staticmethod
    def _within_budget(
        request: TravelRequest, candidate: RouteCandidate
    ) -> Optional[bool]:
        if request.budget is None or candidate.total_fare_lkr is None:
            return None
        return candidate.total_fare_lkr <= request.budget

    # ------------------------------------------------------------------ #
    # Reasoning summary (§17)
    # ------------------------------------------------------------------ #
    def _reasoning(
        self,
        request: TravelRequest,
        winner: ScoredCandidate,
        runners_up: list[ScoredCandidate],
        excluded: list[ExcludedCandidate],
    ) -> str:
        # The recommendation carries within_budget for the frontend; set it here too.
        rec = winner.candidate
        parts: list[str] = []
        why = "; ".join(r.rstrip(".") for r in winner.reasons) if winner.reasons else (
            "best overall fit for your constraints"
        )
        parts.append(f"Recommended {rec.id} ({rec.summary.rstrip('.')}): {why}.")

        if runners_up:
            alt = runners_up[0].candidate
            trade = self._trade_offs(request, alt, rec)
            parts.append(f"{alt.id} is a viable alternative — {' '.join(trade)}")

        if excluded:
            names = ", ".join(f"{e.candidate.id} ({e.reason.rstrip('.')})" for e in excluded)
            parts.append(
                f"Excluded {len(excluded)} candidate(s) that broke a hard constraint: {names}."
            )

        parts.append("All figures are MOCK data for Phase A3, not live transit information.")
        return " ".join(parts)

    def _no_survivor_reasoning(
        self,
        request: TravelRequest,
        excluded: list[ExcludedCandidate],
        closest: Optional[ExcludedCandidate],
    ) -> str:
        if request.budget is not None and closest is not None:
            return (
                f"No candidate fits your {_lkr(request.budget)} budget; the closest is "
                f"{_lkr(closest.candidate.total_fare_lkr)} ({closest.candidate.id}). "
                "Would you like to raise the budget or change the departure time? "
                "(MOCK data — Phase A3.)"
            )
        reasons = "; ".join(
            f"{e.candidate.id}: {e.reason.rstrip('.')}" for e in excluded
        )
        return (
            f"No candidate satisfied every hard constraint ({reasons}). "
            "(MOCK data — Phase A3.)"
        )
