"""Transparent, deterministic route decision engine (Workstream A).

This is the agent's reasoning core: given a validated
:class:`~app.schemas.travel_request.TravelRequest` and a list of
:class:`~app.schemas.candidate.RouteCandidate`, it **filters hard constraints**, **normalizes
features**, **scores soft preferences**, **ranks**, picks a recommendation, keeps alternatives with
honest trade-offs, and explains *why* — all deterministically.

**History.** A3 introduced this engine; **A6 refines and strengthens it** (A6 brief §2) without
replacing the working A3/A4/A5 architecture. The public contract is unchanged — ``decide(request,
candidates) -> Decision`` — and the golden Colombo Fort → Ella behaviour is preserved (heavy bag +
minimize walking selects R1; the *same* candidates with no preferences select R2). A6 adds:

* **Structured hard constraints** (§5): :meth:`DecisionEngine.validate_constraints` collects *every*
  violation (origin, destination, budget, arrival deadline, and an explicitly ``unavailable``
  service) as :class:`~app.schemas.route.ConstraintViolation` objects instead of stopping at the
  first. The *primary* (first, in a fixed precedence) still drives ``ExcludedCandidate.constraint``
  so the A3 single-string contract is preserved.
* **Honest feature handling** (§7/§23): impossible values (negative / NaN / infinite fare, duration,
  walking, transfers, delay) are treated as *unknown* — never silently accepted — and recorded as
  assumptions; malformed candidates and duplicate ids are filtered defensively.
* **Robust normalization** (§8): :meth:`DecisionEngine.normalize_features` behaves predictably for
  one candidate, ties, identical values, two candidates, and missing features.
* **Delay minutes** (§10): scoring consumes ``delay_min_estimate`` (small, capped penalty) in
  addition to ``delay_risk`` — it never *predicts* delay, so Workstream B can later supply real
  delay predictions through the same fields with no architecture change (§19).
* **Route-comparison output** (§11): each :class:`~app.schemas.route.Recommendation` now carries
  additive ``rank`` / ``valid`` / ``strengths`` / ``constraint_violations`` fields.

Why deterministic (not an LLM): AGENT_SPEC §6 requires "same inputs + same mock data ⇒ same
recommendation", and the A6 brief §2 says *do not* let Qwen choose the winner. Qwen remains used for
A2 understanding and A5 tool selection only; the deterministic engine is authoritative for selection.

The scoring model (AGENT_SPEC §8 left weights "TBD until A6" — A6 now defines them):

1. **Hard filter** (§5): origin, destination, ``total_fare_lkr <= budget``, estimated arrival
   ``<= arrival_deadline`` (arrival = departure + duration + known delay), and explicit
   ``unavailable`` service. A candidate violating any hard constraint is *excluded*, never silently
   dropped, and keeps its structured violations for debugging/alternative presentation.
2. **Soft score** (§9): each lower-is-better feature (``walking_km``, ``total_duration_min``,
   ``transfers``, ``total_fare_lkr``) is min–max normalized across the survivors (best → 1.0) and
   combined with base weights ``walking 0.30 / duration 0.25 / transfers 0.20 / fare 0.25``.
3. **Luggage/preference awareness** (§9): ``walking_preference=minimize`` scales the walking weight
   ×1.75 (``ok`` ×0.6); ``luggage=heavy`` scales walking ×1.5 **and** transfers ×1.4 (``none``
   scales walking ×0.8). Weights are renormalized to sum to 1 — never LLM-generated.
4. **Delay penalty** (§10): ``delay_risk`` ``none 0 / low 0.02 / moderate 0.06 / high 0.12`` **plus**
   ``0.001`` per known ``delay_min_estimate`` minute (capped at 60 min → ≤ 0.06), subtracted from the
   weighted score and clamped to ``[0, 1]``.
5. **Rank** (§16) by score, tie-broken deterministically by lower fare → fewer transfers → stable
   id. The top valid candidate is the recommendation; the rest become alternatives.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Optional

from app.schemas.candidate import CandidateAvailability, RouteCandidate
from app.schemas.route import ConstraintViolation, DataSource, Recommendation
from app.schemas.travel_request import TravelRequest

_INF = float("inf")


@dataclass
class ScoredCandidate:
    """A hard-constraint survivor with its computed score, normalized signals, and rank."""

    candidate: RouteCandidate
    score: float
    signals: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    rank: Optional[int] = None  # A6 §11: 1-based rank among valid candidates (set by rank_candidates)


@dataclass
class ExcludedCandidate:
    """A candidate removed by a hard constraint, with the honest reason why.

    ``constraint`` / ``reason`` describe the **primary** (first, in a fixed precedence) violation so
    the A3 single-string contract is preserved; ``violations`` (A6 §5, additive) carries *every*
    structured violation for debugging and transparent alternative presentation.
    """

    candidate: RouteCandidate
    constraint: str  # primary: origin | destination | budget | arrival_deadline | availability
    reason: str  # primary human-readable reason, e.g. "Over budget (LKR 2,350 > LKR 2,000)."
    violations: list[ConstraintViolation] = field(default_factory=list)  # A6 §5: all violations


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
    """Deterministic hard-filter → normalize → soft-score → rank → explain engine (A3, refined A6).

    The methods follow the focused structure the A6 brief §17 asks for — ``validate_constraints``,
    ``normalize_features``, ``calculate_weights``, ``score_candidate``, ``rank_candidates``,
    ``build_reasons``, ``build_result`` — without growing into an enterprise optimization framework.
    """

    #: Base soft-signal weights (all "lower is better"); renormalized after preference scaling (§9).
    BASE_WEIGHTS: dict[str, float] = {
        "walking_km": 0.30,
        "total_duration_min": 0.25,
        "transfers": 0.20,
        "total_fare_lkr": 0.25,
    }

    #: The normalized lower-is-better features (§7). Delay is a *penalty*, not a normalized feature.
    #: Workstream B can extend this set later (add a candidate field + a base weight) with no change
    #: to the decision flow (§19) — e.g. a real ``waiting_time_min`` when such data exists.
    FEATURES: tuple[str, ...] = (
        "walking_km",
        "total_duration_min",
        "transfers",
        "total_fare_lkr",
    )

    #: Numeric candidate fields that must be finite and non-negative when present (§23). A value
    #: that fails this is treated as *unknown* (never silently accepted) and recorded as an
    #: assumption by :meth:`_prepare_candidates`.
    _NUMERIC_FIELDS: tuple[str, ...] = (
        "total_fare_lkr",
        "total_duration_min",
        "walking_km",
        "transfers",
        "delay_min_estimate",
    )

    #: Delay-risk penalty subtracted from the normalized score (§10).
    DELAY_PENALTY: dict[str, float] = {
        "none": 0.0,
        "low": 0.02,
        "moderate": 0.06,
        "high": 0.12,
    }

    #: A6 §10: known ``delay_min_estimate`` also costs score — small and capped so a large delay
    #: never dominates the weighted features. Consumes delay data only when already present; the
    #: engine never predicts delay (that is Workstream B, behind the same fields — §19).
    DELAY_MINUTES_PENALTY_PER_MIN: float = 0.001
    DELAY_MINUTES_CAP: float = 60.0

    #: Ordinal delay-risk levels, used only to phrase an honest "higher delay risk" trade-off (§13).
    _DELAY_RANK: dict[str, int] = {"none": 0, "low": 1, "moderate": 2, "high": 3}

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def decide(
        self, request: TravelRequest, candidates: list[RouteCandidate]
    ) -> Decision:
        """Evaluate ``candidates`` against ``request`` and produce a :class:`Decision`.

        Flow (A6 §2): prepare/validate candidates → hard-constraint filter → normalize features →
        weighted score → deterministic rank → recommendation + alternatives + concise explanation.
        The winner is always drawn from *valid* candidates only (§12); nothing is fabricated.
        """
        assumptions: list[str] = []
        hard = self._hard_snapshot(request)
        weights = self.calculate_weights(request)
        soft = self._soft_snapshot(request, weights)

        # §23: filter malformed candidates / duplicate ids and note impossible values (no mutation).
        prepared = self._prepare_candidates(candidates, assumptions)

        if not prepared:
            reasoning = (
                f"No mock candidate routes are available for "
                f"{request.origin or '?'} → {request.destination or '?'} in Phase A6."
            )
            return self.build_result(
                recommendation=None,
                alternatives=[],
                reasoning=reasoning,
                scored=[],
                excluded=[],
                hard=hard,
                soft=soft,
                assumptions=assumptions,
                satisfied=False,
            )

        survivors, excluded = self._apply_hard_constraints(request, prepared, assumptions)
        ranges = self.normalize_features(survivors)
        scored = [self.score_candidate(c, weights, ranges) for c in survivors]
        scored = self.rank_candidates(scored)

        if not scored:
            # Every candidate violated a hard constraint — report honestly (§12), never pick one.
            closest = min(excluded, key=lambda e: self._fare_or_inf(e.candidate), default=None)
            reasoning = self._no_survivor_reasoning(request, excluded, closest)
            alternatives = [
                self._excluded_to_recommendation(request, e) for e in excluded[:3]
            ]
            return self.build_result(
                recommendation=None,
                alternatives=alternatives,
                reasoning=reasoning,
                scored=[],
                excluded=excluded,
                hard=hard,
                soft=soft,
                assumptions=assumptions,
                satisfied=False,
            )

        winner = scored[0]
        winner.reasons = self.build_reasons(request, winner, scored)
        recommendation = self._to_recommendation(request, winner, scored, is_recommended=True)
        alternatives = self._build_alternatives(
            request, winner.candidate, scored[1:], excluded, scored
        )
        reasoning = self._reasoning(request, winner, scored[1:], excluded)

        return self.build_result(
            recommendation=recommendation,
            alternatives=alternatives,
            reasoning=reasoning,
            scored=scored,
            excluded=excluded,
            hard=hard,
            soft=soft,
            assumptions=assumptions,
            satisfied=True,
        )

    # ------------------------------------------------------------------ #
    # Candidate preparation & sanitization (§23)
    # ------------------------------------------------------------------ #
    def _prepare_candidates(
        self, candidates: list[RouteCandidate], assumptions: list[str]
    ) -> list[RouteCandidate]:
        """Defensively filter the candidate list without mutating any candidate.

        * A non-:class:`RouteCandidate` item (a malformed object) is skipped and noted.
        * A duplicate ``id`` is skipped (first wins) so ranking stays deterministic (§16/§23).
        * An impossible numeric value is *recorded* here and treated as unknown during scoring /
          constraint checks (``_clean_number``) — never silently accepted (§23).
        """
        prepared: list[RouteCandidate] = []
        seen_ids: set[str] = set()
        for item in candidates or []:
            if not isinstance(item, RouteCandidate):
                assumptions.append(
                    "Skipped a malformed candidate (not a RouteCandidate object)."
                )
                continue
            candidate_id = item.id
            if candidate_id in seen_ids:
                assumptions.append(
                    f"Ignored a duplicate candidate id '{candidate_id}' (kept the first)."
                )
                continue
            seen_ids.add(candidate_id)
            for name in self._NUMERIC_FIELDS:
                raw = getattr(item, name, None)
                if raw is not None and self._clean_number(raw) is None:
                    assumptions.append(
                        f"Candidate {candidate_id}: invalid {name} ({raw!r}) treated as unknown."
                    )
            prepared.append(item)
        return prepared

    @staticmethod
    def _clean_number(value: Any) -> Optional[float]:
        """Return ``value`` as a finite, non-negative float, or ``None`` when missing/impossible.

        A6 §23: negative, ``NaN``, infinite, boolean, or non-numeric values are *not* silently
        accepted — they reduce to ``None`` (unknown) so the engine reasons only over plausible data.
        A legitimate ``0`` is preserved (it is finite and non-negative).
        """
        if value is None or isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number) or number < 0:
            return None
        return number

    def _fare_or_inf(self, candidate: RouteCandidate) -> float:
        fare = self._clean_number(candidate.total_fare_lkr)
        return fare if fare is not None else _INF

    # ------------------------------------------------------------------ #
    # Hard constraints (§5)
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
            violations = self.validate_constraints(request, candidate, check_deadline)
            if not violations:
                survivors.append(candidate)
            else:
                primary = violations[0]  # fixed precedence → deterministic primary constraint
                excluded.append(
                    ExcludedCandidate(
                        candidate=candidate,
                        constraint=primary.type.lower(),
                        reason=primary.message,
                        violations=violations,
                    )
                )
        return survivors, excluded

    def validate_constraints(
        self, request: TravelRequest, candidate: RouteCandidate, check_deadline: bool
    ) -> list[ConstraintViolation]:
        """Return **every** hard-constraint violation for ``candidate`` (A6 §5), in fixed order.

        Precedence is stable — origin → destination → budget → arrival deadline → availability — so
        the *primary* violation (``violations[0]``) is deterministic and ``ExcludedCandidate.
        constraint`` keeps the A3 single-string meaning. An empty list means the candidate is valid.
        Values are sanitized (§23): an impossible fare/duration is unknown, so it cannot trigger a
        budget/deadline violation on fabricated data.
        """
        violations: list[ConstraintViolation] = []

        # Origin / destination are guaranteed by the corridor search, but enforced defensively.
        if (
            request.origin
            and candidate.origin
            and candidate.origin.strip().lower() != request.origin.strip().lower()
        ):
            violations.append(
                ConstraintViolation(
                    type="ORIGIN", message=f"Does not start at {request.origin}."
                )
            )
        if (
            request.destination
            and candidate.destination
            and candidate.destination.strip().lower() != request.destination.strip().lower()
        ):
            violations.append(
                ConstraintViolation(
                    type="DESTINATION",
                    message=f"Does not reach {request.destination}.",
                )
            )

        # Budget ceiling.
        fare = self._clean_number(candidate.total_fare_lkr)
        if request.budget is not None and fare is not None and fare > request.budget:
            violations.append(
                ConstraintViolation(
                    type="BUDGET",
                    message=f"Over budget ({_lkr(fare)} > {_lkr(request.budget)}).",
                )
            )

        # Arrival deadline (only when both a departure time and a deadline are known).
        if check_deadline and request.departure_time is not None and (
            request.arrival_deadline is not None
        ):
            duration = self._clean_number(candidate.total_duration_min)
            if duration is not None:
                delay = self._clean_number(candidate.delay_min_estimate) or 0.0
                est_arrival = request.departure_time + timedelta(
                    minutes=duration + delay
                )
                if est_arrival > request.arrival_deadline:
                    violations.append(
                        ConstraintViolation(
                            type="ARRIVAL_DEADLINE",
                            message=(
                                "Arrives after your deadline (est. "
                                f"{est_arrival:%H:%M} with known delay)."
                            ),
                        )
                    )

        # Availability is a hard constraint ONLY when explicitly reported unavailable (§5). The
        # honest default is ``unknown`` (A3/A6 never claim real seats), which is NOT a violation.
        if candidate.availability == CandidateAvailability.unavailable:
            violations.append(
                ConstraintViolation(
                    type="AVAILABILITY",
                    message="Service is reported unavailable for this route.",
                )
            )

        return violations

    # ------------------------------------------------------------------ #
    # Soft scoring (§8/§9/§10)
    # ------------------------------------------------------------------ #
    def calculate_weights(self, request: TravelRequest) -> dict[str, float]:
        """Base weights adjusted by the user's soft preferences, renormalized to sum to 1 (§9).

        Deterministic and never LLM-generated. ``minimize`` walking raises the walking weight
        (``ok`` lowers it); ``heavy`` luggage raises walking **and** transfer weights (``none``
        lowers walking). The multipliers are fixed so the ranking is reproducible.
        """
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

    def normalize_features(
        self, survivors: list[RouteCandidate]
    ) -> dict[str, tuple[float, float]]:
        """Min–max range per feature across the survivors that carry a *valid* value (§8).

        Robust by construction across every edge case the brief lists:

        * **one candidate / all identical** → ``high == low`` → normalized 1.0 for all (no
          differentiation, no divide-by-zero);
        * **two candidates / different ranges** → ordinary min–max, best (lowest) → 1.0;
        * **missing feature** → a candidate without it earns no credit (0.0) at scoring time; if
          *no* survivor carries the feature it is simply absent here (never a fabricated value).
        """
        ranges: dict[str, tuple[float, float]] = {}
        for feature in self.FEATURES:
            values: list[float] = []
            for candidate in survivors:
                value = self._clean_number(getattr(candidate, feature, None))
                if value is not None:
                    values.append(value)
            if values:
                ranges[feature] = (min(values), max(values))
        return ranges

    def score_candidate(
        self,
        candidate: RouteCandidate,
        weights: dict[str, float],
        ranges: dict[str, tuple[float, float]],
    ) -> ScoredCandidate:
        """Normalize one candidate's features, apply weights, subtract the delay penalty (§9/§10).

        Each lower-is-better feature is scaled to ``[0, 1]`` (best → 1.0); an unknown feature earns
        no credit. The weighted sum minus the documented delay penalty is clamped to ``[0, 1]`` and
        rounded to 3 decimals — deterministic and reproducible.
        """
        signals: dict[str, float] = {}
        total = 0.0
        for feature, weight in weights.items():
            value = self._clean_number(getattr(candidate, feature, None))
            if value is None or feature not in ranges:
                norm = 0.0  # unknown feature earns no credit (never fabricate a value)
            else:
                low, high = ranges[feature]
                norm = 1.0 if high == low else (high - value) / (high - low)
            signals[feature] = round(norm, 4)
            total += weight * norm

        penalty = self._delay_penalty(candidate)
        score = round(max(0.0, min(1.0, total - penalty)), 3)
        return ScoredCandidate(candidate=candidate, score=score, signals=signals)

    def _delay_penalty(self, candidate: RouteCandidate) -> float:
        """Documented delay penalty (§10): ``delay_risk`` level + small capped ``delay_min_estimate``.

        Consumes delay information **only when it is already present** in the candidate — the engine
        never predicts delay or calls a model. Workstream B can later supply real delay predictions
        through the same fields with no change here (§19).
        """
        risk = (candidate.delay_risk or "").strip().lower()
        penalty = self.DELAY_PENALTY.get(risk, 0.0)
        minutes = self._clean_number(candidate.delay_min_estimate)
        if minutes is not None:
            penalty += min(minutes, self.DELAY_MINUTES_CAP) * self.DELAY_MINUTES_PENALTY_PER_MIN
        return penalty

    def rank_candidates(self, scored: list[ScoredCandidate]) -> list[ScoredCandidate]:
        """Sort by score and assign a 1-based rank; deterministic tie-break (§16).

        Order: higher score → lower fare → fewer transfers → stable id. No randomness and no
        dependence on dictionary iteration order; unknown fare/transfers sort last on that key.
        """
        def sort_key(sc: ScoredCandidate) -> tuple[float, float, float, str]:
            fare = self._clean_number(sc.candidate.total_fare_lkr)
            transfers = self._clean_number(sc.candidate.transfers)
            return (
                -sc.score,
                fare if fare is not None else _INF,
                transfers if transfers is not None else _INF,
                sc.candidate.id,
            )

        scored.sort(key=sort_key)
        for index, sc in enumerate(scored, start=1):
            sc.rank = index
        return scored

    # ------------------------------------------------------------------ #
    # Explanation (§13/§14: concise, grounded factors — never hidden chain-of-thought)
    # ------------------------------------------------------------------ #
    def build_reasons(
        self,
        request: TravelRequest,
        winner: ScoredCandidate,
        scored: list[ScoredCandidate],
    ) -> list[str]:
        """Concise, grounded reasons the winner fits the request (§14).

        Every reason references a real candidate/request value; a factor is only mentioned when the
        data supports it (never a reason for a fact that does not exist).
        """
        candidate = winner.candidate
        reasons: list[str] = []

        fare = self._clean_number(candidate.total_fare_lkr)
        if request.budget is not None and fare is not None and fare <= request.budget:
            reasons.append(
                f"Within your {_lkr(request.budget)} budget (≈{_lkr(fare)})."
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
        if (candidate.delay_risk or "").strip().lower() in ("none", "low"):
            reasons.append("Low delay risk.")

        return self._dedupe(reasons)[:4]

    def _strengths_for(
        self,
        request: TravelRequest,
        candidate: RouteCandidate,
        scored: list[ScoredCandidate],
    ) -> list[str]:
        """Grounded ✓ strengths for route comparison (§11/§13) — only real, present facts.

        Symmetric counterpart to :meth:`_trade_offs`: lets the UI show what each *valid* route is
        good at (within budget, least walking, fastest, cheapest, fewest transfers, low delay).
        """
        strengths: list[str] = []
        fare = self._clean_number(candidate.total_fare_lkr)
        if request.budget is not None and fare is not None and fare <= request.budget:
            strengths.append(f"Within your {_lkr(request.budget)} budget.")
        if self._is_least(candidate.walking_km, scored, "walking_km"):
            strengths.append(f"Least walking (≈{_km(candidate.walking_km)}).")
        if self._is_least(candidate.total_duration_min, scored, "total_duration_min"):
            strengths.append(f"Fastest (≈{_mins(candidate.total_duration_min)}).")
        if self._is_least(fare, scored, "total_fare_lkr"):
            strengths.append(f"Cheapest (≈{_lkr(fare)}).")
        if self._is_least(candidate.transfers, scored, "transfers"):
            strengths.append(f"Fewest transfers ({candidate.transfers}).")
        if (candidate.delay_risk or "").strip().lower() in ("none", "low"):
            strengths.append("Low delay risk.")
        return self._dedupe(strengths)[:4]

    def _is_least(
        self, value: Optional[float], scored: list[ScoredCandidate], signal: str
    ) -> bool:
        """True when ``value`` is the smallest valid ``signal`` across ``scored`` (§14 grounding)."""
        cleaned = self._clean_number(value)
        if cleaned is None:
            return False
        others = [
            other
            for other in (
                self._clean_number(getattr(sc.candidate, signal, None)) for sc in scored
            )
            if other is not None
        ]
        return bool(others) and cleaned <= min(others)

    def _trade_offs(
        self, request: TravelRequest, alt: RouteCandidate, rec: RouteCandidate
    ) -> list[str]:
        """Grounded ✗ trade-offs for ``alt`` relative to the recommendation ``rec`` (§13)."""
        trade_offs: list[str] = []

        alt_fare = self._clean_number(alt.total_fare_lkr)
        rec_fare = self._clean_number(rec.total_fare_lkr)
        if alt_fare is not None and rec_fare is not None and alt_fare < rec_fare:
            trade_offs.append(f"Cheaper (≈{_lkr(alt_fare)} vs {_lkr(rec_fare)}).")

        alt_dur = self._clean_number(alt.total_duration_min)
        rec_dur = self._clean_number(rec.total_duration_min)
        if alt_dur is not None and rec_dur is not None and alt_dur < rec_dur:
            trade_offs.append(f"Faster (≈{_mins(alt_dur)} vs {_mins(rec_dur)}).")

        alt_walk = self._clean_number(alt.walking_km)
        rec_walk = self._clean_number(rec.walking_km)
        if alt_walk is not None and rec_walk is not None and alt_walk > rec_walk:
            trade_offs.append(f"More walking (≈{_km(alt_walk)} vs {_km(rec_walk)}).")

        alt_transfers = self._clean_number(alt.transfers)
        rec_transfers = self._clean_number(rec.transfers)
        if (
            alt_transfers is not None
            and rec_transfers is not None
            and alt_transfers > rec_transfers
        ):
            trade_offs.append(
                f"More transfers ({int(alt_transfers)} vs {int(rec_transfers)})."
            )

        alt_risk = self._DELAY_RANK.get((alt.delay_risk or "").strip().lower(), -1)
        rec_risk = self._DELAY_RANK.get((rec.delay_risk or "").strip().lower(), -1)
        if alt_risk > rec_risk >= 0:
            trade_offs.append(
                f"Higher delay risk ({alt.delay_risk} vs {rec.delay_risk})."
            )

        if request.budget is not None and alt_fare is not None and alt_fare > request.budget:
            trade_offs.append(
                f"Over budget (≈{_lkr(alt_fare)} > {_lkr(request.budget)})."
            )

        if not trade_offs:
            # Nothing in the §13 trade-off vocabulary differs, so say only what is true: it ranked
            # lower. Claiming it is "similar" could contradict a real difference (A6 §14).
            trade_offs.append("Ranked slightly lower overall.")
        return trade_offs

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        """De-duplicate while preserving order (keeps explanations concise and non-repetitive)."""
        seen: set[str] = set()
        return [item for item in items if not (item in seen or seen.add(item))]

    # ------------------------------------------------------------------ #
    # Recommendation / alternatives construction (§11/§12/§13)
    # ------------------------------------------------------------------ #
    def _to_recommendation(
        self,
        request: TravelRequest,
        scored: ScoredCandidate,
        all_scored: list[ScoredCandidate],
        is_recommended: bool,
    ) -> Recommendation:
        """Build a **valid** route card (recommendation or ranked alternative) with A6 §11 fields."""
        candidate = scored.candidate
        reasons = list(scored.reasons)
        rationale = reasons[0] if reasons else None
        return Recommendation(
            id=candidate.id,
            summary=candidate.summary,
            total_duration_min=candidate.total_duration_min,
            total_fare_lkr=candidate.total_fare_lkr,
            transfers=candidate.transfers,
            walking_km=candidate.walking_km,
            within_budget=self._within_budget(request, candidate),
            delay_risk=candidate.delay_risk,
            score=scored.score,
            rationale=rationale,
            reasons=reasons,
            trade_offs=[],  # set by the caller for alternatives (vs the recommendation)
            rank=scored.rank,
            valid=True,
            strengths=self._strengths_for(request, candidate, all_scored),
            constraint_violations=[],
            is_recommended=is_recommended,
            data_source=candidate.data_source,
        )

    def _build_alternatives(
        self,
        request: TravelRequest,
        rec_candidate: RouteCandidate,
        runners_up: list[ScoredCandidate],
        excluded: list[ExcludedCandidate],
        all_scored: list[ScoredCandidate],
    ) -> list[Recommendation]:
        """Ranked valid runners-up (with trade-offs) then excluded routes (clearly marked) (§12/§13).

        Alternatives are never fabricated: they are the other *real* candidates. A single valid
        candidate yields no runners-up, so no alternative is invented (§12).
        """
        alternatives: list[Recommendation] = []

        for scored in runners_up:
            rec = self._to_recommendation(request, scored, all_scored, is_recommended=False)
            rec.trade_offs = self._trade_offs(request, scored.candidate, rec_candidate)
            alternatives.append(rec)

        # Then any hard-constraint violators, clearly marked with their structured violations (§5),
        # so the user sees exactly why they lost instead of a silent discard.
        for exclusion in excluded:
            alternatives.append(self._excluded_to_recommendation(request, exclusion))

        return alternatives[:3]

    def _excluded_to_recommendation(
        self, request: TravelRequest, exclusion: ExcludedCandidate
    ) -> Recommendation:
        """Build an **invalid** route card that preserves why it was excluded (§5/§11)."""
        candidate = exclusion.candidate
        return Recommendation(
            id=candidate.id,
            summary=candidate.summary,
            total_duration_min=candidate.total_duration_min,
            total_fare_lkr=candidate.total_fare_lkr,
            transfers=candidate.transfers,
            walking_km=candidate.walking_km,
            within_budget=self._within_budget(request, candidate),
            delay_risk=candidate.delay_risk,
            score=None,
            rationale=exclusion.reason,
            reasons=[],
            trade_offs=[exclusion.reason],
            rank=None,
            valid=False,
            strengths=[],
            constraint_violations=list(exclusion.violations),
            is_recommended=False,
            data_source=candidate.data_source,
        )

    def _within_budget(
        self, request: TravelRequest, candidate: RouteCandidate
    ) -> Optional[bool]:
        if request.budget is None:
            return None
        fare = self._clean_number(candidate.total_fare_lkr)
        if fare is None:
            return None
        return fare <= request.budget

    # ------------------------------------------------------------------ #
    # Reasoning summary (§14)
    # ------------------------------------------------------------------ #
    def _reasoning(
        self,
        request: TravelRequest,
        winner: ScoredCandidate,
        runners_up: list[ScoredCandidate],
        excluded: list[ExcludedCandidate],
    ) -> str:
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

        parts.append("All figures are MOCK data for Phase A6, not live transit information.")
        return " ".join(parts)

    def _no_survivor_reasoning(
        self,
        request: TravelRequest,
        excluded: list[ExcludedCandidate],
        closest: Optional[ExcludedCandidate],
    ) -> str:
        if request.budget is not None and closest is not None:
            closest_fare = self._clean_number(closest.candidate.total_fare_lkr)
            return (
                f"No candidate fits your {_lkr(request.budget)} budget; the closest is "
                f"{_lkr(closest_fare)} ({closest.candidate.id}). "
                "Would you like to raise the budget or change the departure time? "
                "(MOCK data — Phase A6.)"
            )
        reasons = "; ".join(
            f"{e.candidate.id}: {e.reason.rstrip('.')}" for e in excluded
        )
        return (
            f"No candidate satisfied every hard constraint ({reasons}). "
            "(MOCK data — Phase A6.)"
        )

    # ------------------------------------------------------------------ #
    # Result assembly (§17 build_result)
    # ------------------------------------------------------------------ #
    def build_result(
        self,
        *,
        recommendation: Optional[Recommendation],
        alternatives: list[Recommendation],
        reasoning: Optional[str],
        scored: list[ScoredCandidate],
        excluded: list[ExcludedCandidate],
        hard: dict[str, Any],
        soft: dict[str, Any],
        assumptions: list[str],
        satisfied: bool,
    ) -> Decision:
        """Assemble the explainable :class:`Decision` (single construction point for all paths)."""
        return Decision(
            recommendation=recommendation,
            alternatives=alternatives,
            reasoning=reasoning,
            scored=scored,
            excluded=excluded,
            hard_constraints=hard,
            soft_preferences=soft,
            assumptions=assumptions,
            satisfied=satisfied,
            data_source=DataSource.mock,
        )
