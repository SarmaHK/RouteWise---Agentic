"""A6 decision-engine refinement tests (brief §21 scenarios 1–30 + §23 edge cases).

These exercise the **refined** :class:`~app.agent.decision.DecisionEngine` (A6 §2 — refine and
strengthen, do not replace). They prove:

* hard constraints are explicit, deterministic and *structured* (1–7, §5);
* soft preferences only re-rank candidates that already passed the hard filter (8–14, §6/§9/§10);
* normalization is predictable for every edge shape the brief lists (15–20, §8);
* ranking is score-first with a deterministic tie-break (21–24, §16);
* explanations are concise and grounded in real values (25–28, §13/§14);
* the A5 tool seam still feeds the engine and the golden demo still selects R1 (29–30, §18/§22).

Followed by the §23 edge cases: empty / all-invalid / all-tied lists, a single candidate, missing
and *impossible* values (negative, NaN, infinite), an invalid duration, duplicate ids, zero and very
large budgets, and malformed candidate objects.

Everything here runs offline on ``data_source=mock`` fixtures — no test presents figures as live
Sri Lankan transit data (AGENT_SPEC §15–§16), and no winner is hard-coded (§22).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Optional

import pytest
from fastapi.testclient import TestClient

from app.agent.decision import Decision, DecisionEngine, ExcludedCandidate, ScoredCandidate
from app.agent.orchestrator import build_agent
from app.config import get_settings
from app.schemas.candidate import CandidateAvailability, RouteCandidate
from app.schemas.route import (
    AgentState,
    ConstraintViolation,
    DataSource,
    Recommendation,
)
from app.schemas.travel_request import Luggage, TravelRequest, WalkingPreference
from app.services.ai.extraction import MockTravelRequestExtractor
from app.tools.base import ToolStatus
from app.tools.candidates import MockCandidateProvider
from app.tools.registry import build_tools

GOLDEN = (
    "I am at Colombo Fort and need to reach Ella under a budget of LKR 2,000, "
    "but I have a heavy bag and don't want to walk."
)

#: 08:00 departure — paired with a deadline it makes the arrival check deterministic (§5).
_DEPART = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)


def _at(hour: int, minute: int = 0) -> datetime:
    """A deadline on the same day as :data:`_DEPART` (keeps tests readable, never ambiguous)."""
    return datetime(2026, 1, 1, hour, minute, tzinfo=timezone.utc)


def _candidates() -> list[RouteCandidate]:
    """The deterministic mock corridor R1/R2/R3 (Colombo Fort → Ella)."""
    return MockCandidateProvider().candidates_for("Colombo Fort", "Ella")


def _request(**kwargs: Any) -> TravelRequest:
    return TravelRequest(
        origin="Colombo Fort", destination="Ella", currency="LKR", **kwargs
    )


def _candidate(candidate_id: str, **kwargs: Any) -> RouteCandidate:
    """A minimal, explicitly-mock candidate for A6 unit tests (optional fields stay absent)."""
    fields: dict[str, Any] = {
        "origin": "Colombo Fort",
        "destination": "Ella",
        "summary": f"A6 test candidate {candidate_id} (mock).",
        "modes": ["bus"],
        "availability": CandidateAvailability.unknown,
        "notes": "A6 unit-test fixture - illustrative mock data, not live transit.",
        "data_source": DataSource.mock,
    }
    fields.update(kwargs)
    return RouteCandidate(id=candidate_id, **fields)


def _golden_request() -> TravelRequest:
    return MockTravelRequestExtractor().extract(GOLDEN, {})


def _score(decision: Decision, candidate_id: str) -> float:
    return next(sc.score for sc in decision.scored if sc.candidate.id == candidate_id)


def _signals(decision: Decision, candidate_id: str) -> dict[str, float]:
    return next(sc.signals for sc in decision.scored if sc.candidate.id == candidate_id)


def _excluded_map(decision: Decision) -> dict[str, ExcludedCandidate]:
    return {e.candidate.id: e for e in decision.excluded}


def _types(exclusion: ExcludedCandidate) -> list[str]:
    """The structured violation codes (A6 §5), in the engine's fixed precedence order."""
    return [v.type for v in exclusion.violations]


def _alt(decision: Decision, candidate_id: str) -> Optional[Recommendation]:
    return next((a for a in decision.alternatives if a.id == candidate_id), None)


def _weights(decision: Decision) -> dict[str, float]:
    return decision.soft_preferences["weights"]


def _golden_decision() -> Decision:
    return DecisionEngine().decide(
        _request(budget=2000, luggage=Luggage.heavy, walking_preference=WalkingPreference.minimize),
        _candidates(),
    )


# --------------------------------------------------------------------------- #
# Hard constraints (§5) — brief §21, tests 1–7
# --------------------------------------------------------------------------- #
# 1. A within-budget candidate is selected; the over-budget one is excluded with a structured reason.
def test_01_within_budget_candidate_is_selected() -> None:
    decision = DecisionEngine().decide(_request(budget=2000), _candidates())
    assert decision.satisfied is True
    recommendation = decision.recommendation
    assert recommendation is not None
    assert recommendation.total_fare_lkr <= 2000
    assert recommendation.within_budget is True
    assert recommendation.valid is True
    assert recommendation.constraint_violations == []
    assert all(sc.candidate.total_fare_lkr <= 2000 for sc in decision.scored)

    excluded = _excluded_map(decision)
    assert set(excluded) == {"R3"}
    assert excluded["R3"].constraint == "budget"  # primary code (A3 single-string contract kept)
    assert _types(excluded["R3"]) == ["BUDGET"]
    assert "2,350" in excluded["R3"].reason and "2,000" in excluded["R3"].reason

    card = _alt(decision, "R3")
    assert card is not None
    assert card.valid is False and card.rank is None and card.score is None
    assert [v.type for v in card.constraint_violations] == ["BUDGET"]


# 2. A candidate that exceeds the budget is excluded; the ceiling is inclusive, not approximate.
def test_02_exceeding_budget_excludes_the_candidate() -> None:
    engine = DecisionEngine()
    over = _candidate("B1", total_fare_lkr=1001, total_duration_min=300, transfers=0, walking_km=0.5)
    exact = _candidate("B2", total_fare_lkr=1000, total_duration_min=300, transfers=0, walking_km=0.5)

    decision = engine.decide(_request(budget=1000), [over])
    assert decision.recommendation is None
    assert decision.satisfied is False
    assert _types(decision.excluded[0]) == ["BUDGET"]

    # A fare exactly ON the ceiling is valid — the budget is a maximum, not a target.
    boundary = engine.decide(_request(budget=1000), [exact, over])
    assert boundary.recommendation.id == "B2"
    assert boundary.recommendation.within_budget is True
    assert _excluded_map(boundary)["B1"].constraint == "budget"


# 3. A satisfied arrival deadline excludes nobody (no false positives).
def test_03_satisfied_arrival_deadline_keeps_candidates_valid() -> None:
    request = _request(budget=2000, departure_time=_DEPART, arrival_deadline=_at(16))
    decision = DecisionEngine().decide(request, _candidates())
    assert all(e.constraint != "arrival_deadline" for e in decision.excluded)
    assert set(_excluded_map(decision)) == {"R3"}  # only the budget violation remains
    assert decision.recommendation.id == "R2"  # 360 min + 30 delay = 14:30, comfortably in time


# 4. A violated arrival deadline excludes the late candidate, with the estimated arrival stated.
def test_04_violated_arrival_deadline_excludes_candidate() -> None:
    request = _request(budget=2000, departure_time=_DEPART, arrival_deadline=_at(15))
    decision = DecisionEngine().decide(request, _candidates())
    excluded = _excluded_map(decision)
    assert excluded["R1"].constraint == "arrival_deadline"
    assert _types(excluded["R1"]) == ["ARRIVAL_DEADLINE"]
    assert "15:10" in excluded["R1"].reason  # grounded: 08:00 + 420 min + 10 known delay
    assert excluded["R3"].constraint == "budget"
    assert decision.recommendation.id == "R2"
    assert decision.recommendation.valid is True

    # A deadline with NO departure time cannot be evaluated — recorded honestly, never guessed (§7).
    undecidable = DecisionEngine().decide(_request(budget=2000, arrival_deadline=_at(9)), _candidates())
    assert any("Arrival-deadline check skipped" in a for a in undecidable.assumptions)
    assert all(e.constraint != "arrival_deadline" for e in undecidable.excluded)


# 5. Candidates must serve the requested origin and destination.
def test_05_origin_and_destination_are_enforced() -> None:
    good = _candidate("G1", total_fare_lkr=1000, total_duration_min=300, transfers=0, walking_km=0.5)
    wrong_destination = _candidate(
        "G2", destination="Kandy", total_fare_lkr=800, total_duration_min=200, transfers=0, walking_km=0.2
    )
    wrong_origin = _candidate(
        "G3", origin="Negombo", total_fare_lkr=700, total_duration_min=180, transfers=0, walking_km=0.1
    )
    decision = DecisionEngine().decide(_request(budget=2000), [good, wrong_destination, wrong_origin])
    excluded = _excluded_map(decision)
    assert decision.recommendation.id == "G1"
    assert excluded["G2"].constraint == "destination" and _types(excluded["G2"]) == ["DESTINATION"]
    assert excluded["G3"].constraint == "origin" and _types(excluded["G3"]) == ["ORIGIN"]
    assert "Ella" in excluded["G2"].reason
    assert "Colombo Fort" in excluded["G3"].reason


# 6. An explicitly unavailable service is incompatible; "unknown" availability is NOT a violation.
def test_06_unavailable_service_is_incompatible() -> None:
    common = dict(total_fare_lkr=1200, total_duration_min=300, transfers=0, walking_km=0.5)
    candidates = [
        _candidate("A0", availability=CandidateAvailability.available, **common),
        _candidate("A1", availability=CandidateAvailability.unknown, **common),
        _candidate("A2", availability=CandidateAvailability.limited, **common),
        _candidate("A3", availability=CandidateAvailability.unavailable, **common),
    ]
    decision = DecisionEngine().decide(_request(budget=2000), candidates)
    excluded = _excluded_map(decision)
    # Only the explicitly unavailable service is excluded — A3/A6 never claim real seats (§5).
    assert set(excluded) == {"A3"}
    assert _types(excluded["A3"]) == ["AVAILABILITY"]
    assert "unavailable" in excluded["A3"].reason.lower()
    assert decision.recommendation.id == "A0"
    assert {sc.candidate.id for sc in decision.scored} == {"A0", "A1", "A2"}


# 7. A candidate breaking several hard constraints reports EVERY violation, in a stable order.
def test_07_multiple_violations_are_all_reported() -> None:
    bad = _candidate(
        "M1",
        destination="Kandy",
        total_fare_lkr=5000,
        total_duration_min=900,
        transfers=3,
        walking_km=4.0,
        availability=CandidateAvailability.unavailable,
    )
    fine = _candidate("M2", total_fare_lkr=1000, total_duration_min=300, transfers=0, walking_km=0.5)
    request = _request(budget=2000, departure_time=_DEPART, arrival_deadline=_at(15))

    decision = DecisionEngine().decide(request, [bad, fine])
    exclusion = _excluded_map(decision)["M1"]
    assert _types(exclusion) == ["DESTINATION", "BUDGET", "ARRIVAL_DEADLINE", "AVAILABILITY"]
    assert exclusion.constraint == "destination"  # primary = first in the fixed precedence
    assert all(isinstance(v, ConstraintViolation) and v.message for v in exclusion.violations)
    messages = [v.message for v in exclusion.violations]
    assert len(messages) == len(set(messages)) == 4  # four distinct, grounded explanations
    assert exclusion.reason == messages[0]  # the primary reason is the first violation

    assert decision.recommendation.id == "M2"
    card = _alt(decision, "M1")
    assert card is not None and card.valid is False
    assert [v.type for v in card.constraint_violations] == _types(exclusion)


# --------------------------------------------------------------------------- #
# Soft preferences (§6/§9/§10) — brief §21, tests 8–14
# --------------------------------------------------------------------------- #
# 8. "minimize" walking raises the walking weight and flips the winner to the least-walking route.
def test_08_walking_minimization_prefers_least_walking() -> None:
    near = _candidate(
        "W1", total_fare_lkr=1200, total_duration_min=360, transfers=0, walking_km=0.1,
        delay_risk="none", delay_min_estimate=0,
    )
    far = _candidate(
        "W2", total_fare_lkr=1000, total_duration_min=300, transfers=0, walking_km=3.0,
        delay_risk="none", delay_min_estimate=0,
    )
    engine = DecisionEngine()
    minimize = engine.decide(
        _request(budget=2000, walking_preference=WalkingPreference.minimize), [near, far]
    )
    ok = engine.decide(_request(budget=2000, walking_preference=WalkingPreference.ok), [near, far])

    assert minimize.recommendation.id == "W1"  # least walking wins when walking is minimized
    assert ok.recommendation.id == "W2"  # ... and loses when walking is merely "ok"
    assert _weights(minimize)["walking_km"] > _weights(ok)["walking_km"]
    assert _score(minimize, "W1") > _score(ok, "W1")


# 9. "normal" walking applies no adjustment at all (weights identical to an unstated preference).
def test_09_normal_walking_leaves_weights_at_baseline() -> None:
    engine = DecisionEngine()
    plain = engine.decide(_request(budget=2000), _candidates())
    normal = engine.decide(_request(budget=2000, walking_preference=WalkingPreference.normal), _candidates())
    ok = engine.decide(_request(budget=2000, walking_preference=WalkingPreference.ok), _candidates())
    minimize = engine.decide(
        _request(budget=2000, walking_preference=WalkingPreference.minimize), _candidates()
    )

    assert _weights(normal) == _weights(plain)  # "normal" is the documented baseline
    walking = [
        _weights(d)["walking_km"] for d in (ok, normal, minimize)
    ]
    assert walking == sorted(walking)  # ok < normal < minimize
    for decision in (plain, normal, ok, minimize):
        assert sum(_weights(decision).values()) == pytest.approx(1.0, abs=1e-5)  # renormalized (§9)
    assert normal.recommendation.id == plain.recommendation.id == "R2"


# 10. "ok" walking lowers the walking weight, so a longer-walk route can win.
def test_10_walking_accepted_lowers_the_walking_weight() -> None:
    engine = DecisionEngine()
    ok = engine.decide(_request(budget=2000, walking_preference=WalkingPreference.ok), _candidates())
    plain = engine.decide(_request(budget=2000), _candidates())
    assert _weights(ok)["walking_km"] < _weights(plain)["walking_km"]
    assert ok.recommendation.id == "R2"  # 1.5 km of walking is acceptable here
    assert _score(ok, "R1") < _score(plain, "R1")  # the least-walking route loses relative weight


# 11. Heavy luggage raises the walking AND transfer weights; it never hard-codes a winner (§22).
def test_11_heavy_luggage_penalizes_walking_and_transfers() -> None:
    engine = DecisionEngine()
    golden = _golden_decision()
    heavy_only = engine.decide(_request(budget=2000, luggage=Luggage.heavy), _candidates())
    none_luggage = engine.decide(_request(budget=2000, luggage=Luggage.none), _candidates())
    plain = engine.decide(_request(budget=2000), _candidates())
    minimize_only = engine.decide(
        _request(budget=2000, walking_preference=WalkingPreference.minimize), _candidates()
    )

    assert golden.recommendation.id == "R1"  # heavy + minimize -> least walking, 1 transfer
    assert heavy_only.recommendation.id == "R2"  # heavy ALONE does not force R1 (§22)
    assert plain.recommendation.id == "R2"

    assert _weights(golden)["walking_km"] > _weights(plain)["walking_km"]
    assert _weights(golden)["transfers"] > _weights(minimize_only)["transfers"]
    assert _weights(none_luggage)["walking_km"] < _weights(plain)["walking_km"]


# 12. Fewer transfers rank higher when everything else is equal.
def test_12_fewer_transfers_rank_higher() -> None:
    common = dict(total_fare_lkr=1000, total_duration_min=300, walking_km=0.5, delay_risk="none", delay_min_estimate=0)
    direct = _candidate("T1", transfers=0, **common)
    changes = _candidate("T2", transfers=2, **common)
    engine = DecisionEngine()

    decision = engine.decide(_request(budget=2000), [direct, changes])
    assert decision.recommendation.id == "T1"
    assert _score(decision, "T1") == pytest.approx(1.0)
    assert _score(decision, "T2") == pytest.approx(0.8)  # lost exactly the transfers weight

    heavy = engine.decide(_request(budget=2000, luggage=Luggage.heavy), [direct, changes])
    plain = engine.decide(_request(budget=2000), [direct, changes])
    assert _weights(heavy)["transfers"] > _weights(plain)["transfers"]  # luggage-aware (§9)


# 13. A faster route ranks higher when everything else is equal.
def test_13_faster_route_ranks_higher() -> None:
    common = dict(total_fare_lkr=1000, transfers=0, walking_km=0.5, delay_risk="none", delay_min_estimate=0)
    fast = _candidate("F1", total_duration_min=200, **common)
    slow = _candidate("F2", total_duration_min=400, **common)

    decision = DecisionEngine().decide(_request(budget=2000), [fast, slow])
    assert decision.recommendation.id == "F1"
    assert _score(decision, "F1") == pytest.approx(1.0)
    assert _score(decision, "F2") == pytest.approx(0.75)  # lost exactly the duration weight
    assert any("Fastest" in r for r in decision.recommendation.reasons)
    assert _alt(decision, "F2").rank == 2 and _alt(decision, "F2").valid is True


# 14. Known delay data is penalized (minutes AND risk level) — never predicted here (§10).
def test_14_delay_information_is_penalized_not_predicted() -> None:
    common = dict(total_fare_lkr=1000, total_duration_min=300, transfers=0, walking_km=0.5, delay_risk="none")
    engine = DecisionEngine()

    minutes = engine.decide(
        _request(budget=2000),
        [
            _candidate("D0", delay_min_estimate=0, **common),
            _candidate("D60", delay_min_estimate=60, **common),
            _candidate("D600", delay_min_estimate=600, **common),
        ],
    )
    assert minutes.recommendation.id == "D0"
    assert _score(minutes, "D0") == pytest.approx(1.0)
    assert _score(minutes, "D60") == pytest.approx(0.94)  # 60 min * 0.001
    # The per-minute penalty is capped, so an extreme delay cannot dominate the weighted features.
    assert _score(minutes, "D600") == _score(minutes, "D60")
    assert DecisionEngine.DELAY_MINUTES_CAP == 60.0

    base = {k: v for k, v in common.items() if k != "delay_risk"}
    risks = engine.decide(
        _request(budget=2000),
        [
            _candidate("K0", delay_risk="none", delay_min_estimate=0, **base),
            _candidate("K1", delay_risk="low", delay_min_estimate=0, **base),
            _candidate("K2", delay_risk="moderate", delay_min_estimate=0, **base),
            _candidate("K3", delay_risk="high", delay_min_estimate=0, **base),
        ],
    )
    ordered = [_score(risks, f"K{i}") for i in range(4)]
    assert ordered == sorted(ordered, reverse=True)  # none > low > moderate > high
    assert ordered[0] == pytest.approx(1.0) and ordered[3] == pytest.approx(0.88)
    assert risks.assumptions == []  # delay was consumed as given, nothing was invented


# --------------------------------------------------------------------------- #
# Normalization (§8) — brief §21, tests 15–20
# --------------------------------------------------------------------------- #
# 15. Two candidates: min–max normalization gives the best 1.0 and the worst 0.0.
def test_15_two_candidates_normalize_across_the_full_range() -> None:
    engine = DecisionEngine()
    best = _candidate("N1", total_fare_lkr=1000, total_duration_min=300, transfers=0, walking_km=0.5)
    worst = _candidate("N2", total_fare_lkr=2000, total_duration_min=400, transfers=2, walking_km=1.5)

    ranges = engine.normalize_features([best, worst])
    assert ranges == {
        "walking_km": (0.5, 1.5),
        "total_duration_min": (300.0, 400.0),
        "transfers": (0.0, 2.0),
        "total_fare_lkr": (1000.0, 2000.0),
    }
    weights = engine.calculate_weights(_request(budget=2000))
    assert engine.score_candidate(best, weights, ranges).signals == {
        "walking_km": 1.0,
        "total_duration_min": 1.0,
        "transfers": 1.0,
        "total_fare_lkr": 1.0,
    }
    assert engine.score_candidate(worst, weights, ranges).signals == {
        "walking_km": 0.0,
        "total_duration_min": 0.0,
        "transfers": 0.0,
        "total_fare_lkr": 0.0,
    }
    assert engine.score_candidate(best, weights, ranges).score == pytest.approx(1.0)
    assert engine.score_candidate(worst, weights, ranges).score == pytest.approx(0.0)


# 16. A single candidate: no divide-by-zero, everything normalizes to 1.0, no invented alternative.
def test_16_single_candidate_is_stable_and_not_padded() -> None:
    engine = DecisionEngine()
    only = _candidate("S1", total_fare_lkr=1500, total_duration_min=420, transfers=1, walking_km=0.8)

    ranges = engine.normalize_features([only])
    assert all(low == high for low, high in ranges.values())  # degenerate range, handled (§8)
    scored = engine.score_candidate(only, engine.calculate_weights(_request(budget=2000)), ranges)
    assert set(scored.signals.values()) == {1.0}
    assert scored.score == pytest.approx(1.0)

    decision = engine.decide(_request(budget=2000), [only])
    assert decision.recommendation.id == "S1"
    assert decision.recommendation.rank == 1
    assert decision.recommendation.valid is True
    assert decision.alternatives == []  # §12: never fabricate an alternative
    assert len(decision.scored) == 1


# 17. Identical candidates tie on score and are ordered by the deterministic tie-break.
def test_17_identical_candidates_tie_and_break_deterministically() -> None:
    same = dict(
        total_fare_lkr=1200, total_duration_min=360, transfers=0, walking_km=1.0,
        delay_risk="low", delay_min_estimate=10,
    )
    candidates = [_candidate("Z9", **same), _candidate("A1", **same), _candidate("M5", **same)]
    engine = DecisionEngine()

    decision = engine.decide(_request(budget=2000), candidates)
    scores = [_score(decision, c.id) for c in candidates]
    assert len(set(scores)) == 1  # genuinely tied
    assert [sc.candidate.id for sc in decision.scored] == ["A1", "M5", "Z9"]  # stable id order
    assert [sc.rank for sc in decision.scored] == [1, 2, 3]
    assert decision.recommendation.id == "A1"

    # Re-ordering the input must not change the ranking — no randomness, no dict-order reliance (§16).
    again = engine.decide(_request(budget=2000), list(reversed(candidates)))
    assert [sc.candidate.id for sc in again.scored] == ["A1", "M5", "Z9"]
    assert _score(decision, "A1") == _score(again, "A1")


# 18. A missing feature earns no credit — it is never filled with an invented value.
def test_18_missing_feature_is_never_fabricated() -> None:
    engine = DecisionEngine()
    sparse = _candidate("P1", total_fare_lkr=1000, total_duration_min=300, transfers=0, walking_km=None)
    full = _candidate("P2", total_fare_lkr=1000, total_duration_min=300, transfers=0, walking_km=2.0)

    ranges = engine.normalize_features([sparse, full])
    assert ranges["walking_km"] == (2.0, 2.0)  # only the KNOWN value defines the range
    weights = engine.calculate_weights(_request(budget=2000))
    assert engine.score_candidate(sparse, weights, ranges).signals["walking_km"] == 0.0
    assert engine.score_candidate(full, weights, ranges).signals["walking_km"] == 1.0

    decision = engine.decide(_request(budget=2000), [sparse, full])
    assert decision.recommendation.id == "P2"
    assert sparse.walking_km is None  # the candidate was never mutated / back-filled
    assert decision.assumptions == []  # an absent value is not an "invalid" value

    # When NO survivor carries a feature, the feature is absent — not zero-filled (§7).
    assert "walking_km" not in engine.normalize_features([_candidate("P3", walking_km=None)])


# 19. Tied feature values normalize identically (no artificial differentiation).
def test_19_tied_values_normalize_identically() -> None:
    engine = DecisionEngine()
    common = dict(total_duration_min=300, transfers=0, walking_km=1.0)
    cheap_a = _candidate("C1", total_fare_lkr=1000, **common)
    cheap_b = _candidate("C2", total_fare_lkr=1000, **common)
    pricey = _candidate("C3", total_fare_lkr=2000, **common)

    ranges = engine.normalize_features([cheap_a, cheap_b, pricey])
    assert ranges["total_fare_lkr"] == (1000.0, 2000.0)
    weights = engine.calculate_weights(_request(budget=2500))
    assert engine.score_candidate(cheap_a, weights, ranges).signals["total_fare_lkr"] == 1.0
    assert engine.score_candidate(cheap_b, weights, ranges).signals["total_fare_lkr"] == 1.0
    assert engine.score_candidate(pricey, weights, ranges).signals["total_fare_lkr"] == 0.0

    decision = engine.decide(_request(budget=2500), [cheap_a, cheap_b, pricey])
    assert _score(decision, "C1") == _score(decision, "C2") > _score(decision, "C3")


# 20. Many candidates with wide ranges: normalization stays in [0, 1] and order-preserving.
def test_20_wide_ranges_normalize_monotonically_within_the_unit_interval() -> None:
    engine = DecisionEngine()
    candidates = [
        _candidate(
            f"V{i}",
            total_fare_lkr=fare,
            total_duration_min=100 * (i + 1),
            transfers=i,
            walking_km=0.5 * i,
        )
        for i, fare in enumerate([500, 1000, 1500, 3000, 9000])
    ]
    ranges = engine.normalize_features(candidates)
    assert ranges["total_fare_lkr"] == (500.0, 9000.0)
    assert ranges["total_duration_min"] == (100.0, 500.0)

    weights = engine.calculate_weights(_request(budget=10000))
    norms = [engine.score_candidate(c, weights, ranges).signals["total_fare_lkr"] for c in candidates]
    assert all(0.0 <= n <= 1.0 for n in norms)
    assert norms == sorted(norms, reverse=True)  # lower fare -> higher normalized value
    assert norms[0] == 1.0 and norms[-1] == 0.0
    assert norms[1] == pytest.approx(round((9000 - 1000) / (9000 - 500), 4))  # a real mid-range value


# --------------------------------------------------------------------------- #
# Ranking (§16) — brief §21, tests 21–24
# --------------------------------------------------------------------------- #
# 21. The highest-scoring VALID candidate is the recommendation, ranked 1.
def test_21_highest_score_wins() -> None:
    decision = _golden_decision()
    recommendation = decision.recommendation
    assert recommendation is not None
    assert recommendation.score == max(sc.score for sc in decision.scored)
    assert recommendation.rank == 1
    assert decision.scored[0].candidate.id == recommendation.id
    assert [sc.rank for sc in decision.scored] == list(range(1, len(decision.scored) + 1))
    assert all(a.rank is None or a.rank > 1 for a in decision.alternatives)
    assert decision.satisfied is True


# 22. Ties break deterministically: score -> fare -> transfers -> stable id (never random).
def test_22_tie_break_is_deterministic() -> None:
    engine = DecisionEngine()
    common = dict(total_duration_min=300, walking_km=0.5)
    tied = [
        ScoredCandidate(candidate=_candidate("B2", total_fare_lkr=1500, transfers=1, **common), score=0.8),
        ScoredCandidate(candidate=_candidate("A2", total_fare_lkr=1500, transfers=1, **common), score=0.8),
        ScoredCandidate(candidate=_candidate("C2", total_fare_lkr=1000, transfers=3, **common), score=0.8),
        ScoredCandidate(candidate=_candidate("D2", total_fare_lkr=None, transfers=0, **common), score=0.8),
        ScoredCandidate(candidate=_candidate("E2", total_fare_lkr=2000, transfers=0, **common), score=0.8),
    ]
    expected = ["C2", "A2", "B2", "E2", "D2"]  # cheapest first, unknown fare last, then stable id
    ranked = engine.rank_candidates(list(tied))
    assert [s.candidate.id for s in ranked] == expected
    assert [s.rank for s in ranked] == [1, 2, 3, 4, 5]
    assert [s.candidate.id for s in engine.rank_candidates(list(reversed(tied)))] == expected

    # A higher score always outranks a lower one, whatever the fare.
    mixed = engine.rank_candidates(
        [
            ScoredCandidate(candidate=_candidate("X1", total_fare_lkr=9000, transfers=9), score=0.5),
            ScoredCandidate(candidate=_candidate("X2", total_fare_lkr=100, transfers=0), score=0.9),
        ]
    )
    assert [s.candidate.id for s in mixed] == ["X2", "X1"]
    assert [s.rank for s in mixed] == [1, 2]


# 23. An invalid candidate can never win, even when it dominates every feature.
def test_23_invalid_candidate_cannot_win() -> None:
    weak = _candidate("V1", total_fare_lkr=1000, total_duration_min=400, transfers=1, walking_km=1.0)
    dominant_but_invalid = _candidate(
        "V2", total_fare_lkr=5000, total_duration_min=100, transfers=0, walking_km=0.0,
        delay_risk="none", delay_min_estimate=0,
    )
    decision = DecisionEngine().decide(_request(budget=2000), [weak, dominant_but_invalid])
    assert decision.recommendation.id == "V1"
    assert decision.recommendation.valid is True
    assert "V2" not in {sc.candidate.id for sc in decision.scored}
    assert _excluded_map(decision)["V2"].constraint == "budget"

    card = _alt(decision, "V2")
    assert card is not None
    assert card.valid is False and card.rank is None and card.score is None
    assert [v.type for v in card.constraint_violations] == ["BUDGET"]


# 24. Alternatives are ordered: valid runners-up first (ranked), then clearly-marked exclusions.
def test_24_alternatives_are_ordered_correctly() -> None:
    decision = _golden_decision()
    assert decision.recommendation.id == "R1"
    assert [a.id for a in decision.alternatives] == ["R2", "R3"]
    assert len(decision.alternatives) <= 3

    runner_up, excluded_card = decision.alternatives
    assert runner_up.valid is True and runner_up.rank == 2 and runner_up.score is not None
    assert runner_up.is_recommended is False and runner_up.trade_offs
    assert excluded_card.valid is False and excluded_card.rank is None and excluded_card.score is None
    assert excluded_card.constraint_violations

    valid_ranks = [decision.recommendation.rank, runner_up.rank]
    assert valid_ranks == sorted(valid_ranks) == [1, 2]


# --------------------------------------------------------------------------- #
# Explanation (§13/§14) — brief §21, tests 25–28
# --------------------------------------------------------------------------- #
# 25. Reasons are concise and grounded in the real request/candidate values.
def test_25_reasons_are_grounded_in_real_values() -> None:
    recommendation = _golden_decision().recommendation
    assert recommendation.reasons and len(recommendation.reasons) <= 4
    assert recommendation.rationale == recommendation.reasons[0]
    assert any("LKR 2,000" in r for r in recommendation.reasons)  # the real budget
    assert any("LKR 1,600" in r for r in recommendation.reasons)  # R1's real fare
    assert any("heavy luggage" in r.lower() for r in recommendation.reasons)
    assert any("1 transfer" in r for r in recommendation.reasons)
    # R1 is neither the fastest nor the cheapest survivor, so neither claim may appear (§14).
    assert not any("Fastest" in r for r in recommendation.reasons)
    assert not any("Cheapest" in r for r in recommendation.reasons)
    # Strengths are grounded the same way, and a valid card carries no violations (§11).
    assert any("Least walking" in s for s in recommendation.strengths)
    assert any("0.3 km" in s for s in recommendation.strengths)
    assert recommendation.constraint_violations == []


# 26. No reason or strength may reference data the candidate does not have.
def test_26_no_reason_references_missing_data() -> None:
    sparse = _candidate(
        "S1", total_fare_lkr=None, total_duration_min=None, transfers=None, walking_km=None, delay_risk=None
    )
    full = _candidate(
        "S2", total_fare_lkr=1000, total_duration_min=300, transfers=0, walking_km=1.0, delay_risk="low"
    )
    decision = DecisionEngine().decide(_request(), [sparse, full])  # no budget stated

    recommendation = decision.recommendation
    assert recommendation.id == "S2"
    assert recommendation.reasons
    for text in recommendation.reasons + recommendation.strengths:
        assert "—" not in text and "None" not in text  # no placeholder for absent data
    assert any("LKR 1,000" in r for r in recommendation.reasons)
    assert not any("budget" in r.lower() for r in recommendation.reasons)  # none was stated
    assert recommendation.within_budget is None  # unknown, not a fabricated True/False

    card = _alt(decision, "S1")
    assert card is not None
    assert card.reasons == [] and card.rationale is None and card.strengths == []
    assert card.trade_offs  # still explains itself (§13)
    assert sparse.total_fare_lkr is None  # never mutated / back-filled


# 27. Every alternative carries useful, grounded trade-offs (valid runners-up and exclusions).
def test_27_alternatives_have_trade_offs() -> None:
    decision = _golden_decision()
    assert decision.alternatives
    for alternative in decision.alternatives:
        assert alternative.is_recommended is False
        assert alternative.trade_offs, f"{alternative.id} has no trade-offs"
        assert len(alternative.trade_offs) <= 6  # concise, user-facing (§13)

    runner_up = _alt(decision, "R2")
    assert any(t.startswith("Cheaper") for t in runner_up.trade_offs)
    assert any(t.startswith("Faster") for t in runner_up.trade_offs)
    assert any(t.startswith("More walking") for t in runner_up.trade_offs)
    assert any(t.startswith("Higher delay risk") for t in runner_up.trade_offs)
    assert not any(t.startswith("More transfers") for t in runner_up.trade_offs)  # R2 has fewer (0 vs 1)
    assert runner_up.strengths  # §11: valid alternatives show strengths too

    excluded_card = _alt(decision, "R3")
    assert excluded_card.valid is False
    assert any("budget" in t.lower() for t in excluded_card.trade_offs)
    assert excluded_card.strengths == []


# 28. When no route can be offered the result says so honestly — nothing is invented.
def test_28_no_route_result_is_honest() -> None:
    engine = DecisionEngine()

    empty = engine.decide(_request(budget=2000), [])
    assert empty.recommendation is None
    assert empty.alternatives == []
    assert empty.scored == [] and empty.excluded == []
    assert empty.satisfied is False
    assert empty.reasoning and "No mock candidate routes" in empty.reasoning
    assert "Colombo Fort" in empty.reasoning and "Ella" in empty.reasoning
    assert empty.data_source is DataSource.mock

    unaffordable = engine.decide(_request(budget=500), _candidates())  # every candidate over budget
    assert unaffordable.recommendation is None
    assert unaffordable.satisfied is False
    assert len(unaffordable.excluded) == 3
    assert "No candidate fits" in unaffordable.reasoning
    assert "MOCK" in unaffordable.reasoning
    assert unaffordable.alternatives
    assert all(a.valid is False for a in unaffordable.alternatives)
    assert all(a.score is None and a.rank is None for a in unaffordable.alternatives)
    assert all(a.constraint_violations for a in unaffordable.alternatives)
    # The honest "closest" option is a REAL candidate (R2 at LKR 1,200) — never invented.
    assert "R2" in unaffordable.reasoning and "LKR 1,200" in unaffordable.reasoning


# --------------------------------------------------------------------------- #
# Integration (§18/§22) — brief §21, tests 29–30
# --------------------------------------------------------------------------- #
# 29. The A5 tool seam still feeds the A6 engine (no orchestrator/tool change was needed).
# A7 (brief §16): the loop now also gathers fare/delay/details, yet the engine still decides from
# the SAME candidate values — the richer intelligence is merged, not substituted, so the A6 outcome
# (R1, rank 1, valid, its strengths and R3's BUDGET violation) is bit-for-bit unchanged.
def test_29_a5_tool_output_feeds_the_a6_engine() -> None:
    settings = get_settings()
    result = build_tools(settings).call("search_routes", origin="Colombo Fort", destination="Ella")
    assert result.status is ToolStatus.mock_data
    assert result.data_source is DataSource.mock
    assert [c.id for c in result.data] == ["R1", "R2", "R3"]

    request = _golden_request()
    decision = DecisionEngine().decide(request, result.data)
    assert decision.recommendation.id == "R1"
    assert decision.data_source is DataSource.mock

    # The same candidates flow through the A5/A7 agent loop and the A6 fields survive untouched.
    context = build_agent(settings).run(request)
    assert context.state is AgentState.COMPLETED
    # A7 (brief §20): the canonical state order is unchanged; only the number of SEARCHING tool
    # calls grew, and no new state was introduced.
    states = [a.state for a in context.actions]
    assert list(dict.fromkeys(states)) == [
        AgentState.UNDERSTANDING,
        AgentState.PLANNING,
        AgentState.SEARCHING,
        AgentState.EVALUATING,
        AgentState.COMPLETED,
    ]
    recommendation = context.recommendation
    assert recommendation.id == "R1"
    assert recommendation.valid is True and recommendation.rank == 1
    assert recommendation.strengths and recommendation.constraint_violations == []
    # The engine's decision is identical to the direct call above (§16: A7 informs, A6 decides).
    assert recommendation.score == decision.recommendation.score
    assert [(c.id, c.total_fare_lkr, c.delay_risk) for c in context.candidates] == [
        (c.id, c.total_fare_lkr, c.delay_risk) for c in result.data
    ]
    invalid = [a for a in context.alternatives if a.valid is False]
    assert invalid and invalid[0].constraint_violations


# 29b. The additive A6 fields are serialized by POST /api/route/plan (API_CONTRACTS §9; brief §24).
def test_29b_api_serializes_the_additive_a6_fields(client: TestClient) -> None:
    response = client.post("/api/route/plan", json={"raw_text": GOLDEN})
    assert response.status_code == 200
    body = response.json()

    recommendation = body["recommendation"]
    assert recommendation["rank"] == 1
    assert recommendation["valid"] is True
    assert isinstance(recommendation["strengths"], list) and recommendation["strengths"]
    assert recommendation["constraint_violations"] == []
    # The A3 contract is untouched.
    assert recommendation["id"] == "R1" and recommendation["is_recommended"] is True
    assert recommendation["within_budget"] is True and recommendation["score"] is not None

    invalid = [a for a in body["alternatives"] if a["valid"] is False]
    assert invalid
    assert invalid[0]["rank"] is None and invalid[0]["score"] is None
    assert [v["type"] for v in invalid[0]["constraint_violations"]] == ["BUDGET"]
    assert invalid[0]["constraint_violations"][0]["message"]


# 30. The golden demo scenario still resolves correctly — and R1 is NOT hard-coded (§22).
def test_30_golden_demo_scenario_remains_correct() -> None:
    request = _golden_request()
    assert request.origin == "Colombo Fort" and request.destination == "Ella"
    assert request.budget == 2000
    assert request.luggage is Luggage.heavy
    assert request.walking_preference is WalkingPreference.minimize

    decision = DecisionEngine().decide(request, _candidates())
    recommendation = decision.recommendation
    assert recommendation.id == "R1"
    assert recommendation.total_fare_lkr <= 2000 and recommendation.within_budget is True
    assert recommendation.data_source is DataSource.mock  # clearly mock (§22)
    assert "MOCK" in decision.reasoning
    assert any("heavy luggage" in r.lower() for r in recommendation.reasons)  # luggage considered
    assert any("Least walking" in s for s in recommendation.strengths)  # walking preference honored
    assert _excluded_map(decision)["R3"].constraint == "budget"  # LKR 2,350 > the LKR 2,000 ceiling
    assert decision.alternatives  # real alternatives, none invented

    # The winner is COMPUTED from the data + preferences: drop either and R2 wins instead.
    assert DecisionEngine().decide(_request(budget=2000), _candidates()).recommendation.id == "R2"
    without_r1 = DecisionEngine().decide(request, [c for c in _candidates() if c.id != "R1"])
    assert without_r1.recommendation.id == "R2"


# --------------------------------------------------------------------------- #
# Edge cases (brief §23)
# --------------------------------------------------------------------------- #
# E1. Zero budget: only a genuinely free route is valid — nothing is silently accepted.
def test_edge_zero_budget_only_accepts_a_free_route() -> None:
    engine = DecisionEngine()
    unaffordable = engine.decide(_request(budget=0), _candidates())
    assert unaffordable.recommendation is None
    assert len(unaffordable.excluded) == 3
    assert all(_types(e) == ["BUDGET"] for e in unaffordable.excluded)

    free = _candidate("F0", total_fare_lkr=0, total_duration_min=300, transfers=0, walking_km=0.5)
    paid = _candidate("F1", total_fare_lkr=500, total_duration_min=200, transfers=0, walking_km=0.2)
    decision = engine.decide(_request(budget=0), [free, paid])
    assert decision.recommendation.id == "F0"  # a real 0 fare is a legitimate value, not "missing"
    assert decision.recommendation.within_budget is True
    assert _excluded_map(decision)["F1"].constraint == "budget"


# E2. A very large budget excludes nothing and keeps every score inside [0, 1].
def test_edge_very_large_budget_excludes_nothing() -> None:
    decision = DecisionEngine().decide(_request(budget=10**9), _candidates())
    assert decision.excluded == []
    assert len(decision.scored) == 3
    assert decision.recommendation is not None
    assert all(0.0 <= sc.score <= 1.0 for sc in decision.scored)
    assert all(a.valid is True for a in decision.alternatives)
    assert all(a.constraint_violations == [] for a in decision.alternatives)


# E3. Impossible values are treated as UNKNOWN (never accepted) and are recorded as assumptions.
def test_edge_impossible_values_are_treated_as_unknown() -> None:
    clean = DecisionEngine._clean_number
    assert clean(-1) is None
    assert clean(math.nan) is None
    assert clean(math.inf) is None
    assert clean(-math.inf) is None
    assert clean(True) is None  # a bool is not a measurement
    assert clean("not-a-number") is None
    assert clean(None) is None
    assert clean(0) == 0.0  # a legitimate zero is preserved
    assert clean("1200") == 1200.0  # a numeric string IS coerced

    negative = _candidate("N1", total_fare_lkr=-500, total_duration_min=300, transfers=0, walking_km=0.5)
    decision = DecisionEngine().decide(_request(budget=100), [negative])
    assert decision.excluded == []  # an impossible fare cannot fabricate a budget violation
    assert decision.recommendation.id == "N1"
    assert decision.recommendation.within_budget is None  # unknown, not "True"
    assert any("invalid total_fare_lkr" in a for a in decision.assumptions)
    assert _signals(decision, "N1")["total_fare_lkr"] == 0.0  # unknown earns no credit
    assert negative.total_fare_lkr == -500  # the candidate itself was never mutated


# E4. An invalid duration is unknown — it can neither fake nor hide a deadline exclusion.
def test_edge_invalid_duration_is_unknown_not_late() -> None:
    broken = _candidate("B1", total_fare_lkr=1000, total_duration_min=-120, transfers=0, walking_km=0.5)
    decision = DecisionEngine().decide(
        _request(budget=2000, departure_time=_DEPART, arrival_deadline=_at(9)), [broken]
    )
    assert decision.excluded == []
    assert decision.recommendation.id == "B1"
    assert any("invalid total_duration_min" in a for a in decision.assumptions)
    assert _signals(decision, "B1")["total_duration_min"] == 0.0
    assert "total_duration_min" not in DecisionEngine().normalize_features([broken])


# E5. NaN / infinite fares are rejected as impossible rather than scored as "free".
def test_edge_nan_and_infinite_fares_are_rejected() -> None:
    common = dict(total_duration_min=300, transfers=0, walking_km=0.5)
    decision = DecisionEngine().decide(
        _request(budget=2000),
        [
            _candidate("NAN", total_fare_lkr=math.nan, **common),
            _candidate("INF", total_fare_lkr=math.inf, **common),
            _candidate("OKR", total_fare_lkr=1500, **common),
        ],
    )
    assert decision.recommendation.id == "OKR"
    assert decision.recommendation.within_budget is True
    for candidate_id in ("NAN", "INF"):
        card = _alt(decision, candidate_id)
        assert card is not None and card.within_budget is None and card.score is not None
    assert sum("invalid total_fare_lkr" in a for a in decision.assumptions) == 2
    assert decision.excluded == []  # impossible data is unknown, not a violation


# E6. Duplicate candidate ids are de-duplicated (first wins) so ranking stays deterministic.
def test_edge_duplicate_ids_are_deduplicated() -> None:
    first = _candidate("D1", total_fare_lkr=1000, total_duration_min=300, transfers=0, walking_km=0.5)
    duplicate = _candidate("D1", total_fare_lkr=2000, total_duration_min=400, transfers=1, walking_km=1.5)
    decision = DecisionEngine().decide(_request(budget=2500), [first, duplicate])
    assert len(decision.scored) == 1
    assert decision.recommendation.id == "D1"
    assert decision.recommendation.total_fare_lkr == 1000  # the first occurrence was kept
    assert any("duplicate candidate id 'D1'" in a for a in decision.assumptions)
    assert decision.excluded == []


# E7. Malformed candidate objects are skipped, not crashed on (§23).
def test_edge_malformed_candidates_are_skipped() -> None:
    good = _candidate("G1", total_fare_lkr=1000, total_duration_min=300, transfers=0, walking_km=0.5)
    malformed: list[Any] = [{"id": "G2"}, "not-a-candidate", None, 42]
    decision = DecisionEngine().decide(_request(budget=2000), [good, *malformed])
    assert decision.recommendation.id == "G1"
    assert len(decision.scored) == 1
    assert decision.excluded == []
    assert (
        decision.assumptions.count("Skipped a malformed candidate (not a RouteCandidate object).")
        == len(malformed)
    )


# E8. Missing delay data is not invented, and a bare request still produces a decision.
def test_edge_missing_delay_data_is_not_invented() -> None:
    engine = DecisionEngine()
    common = dict(total_fare_lkr=1000, total_duration_min=300, transfers=0, walking_km=0.5)
    unknown_delay = _candidate("A1", **common)  # no delay_risk / delay_min_estimate at all
    no_delay = _candidate("A2", delay_risk="none", delay_min_estimate=0, **common)

    decision = engine.decide(_request(budget=2000), [unknown_delay, no_delay])
    assert _score(decision, "A1") == _score(decision, "A2")  # unknown delay costs nothing extra
    assert decision.assumptions == []  # nothing was assumed about delay
    assert decision.recommendation.id == "A1"  # tie -> stable id order

    bare = engine.decide(TravelRequest(origin="Colombo Fort", destination="Ella"), _candidates())
    assert bare.recommendation is not None
    assert bare.recommendation.within_budget is None  # no budget was stated
    assert bare.hard_constraints["budget_lkr"] is None


# E9. The decision exposes exactly the hard/soft inputs it used (debuggability, §5/§9).
def test_edge_decision_exposes_its_constraints_and_weights() -> None:
    decision = DecisionEngine().decide(
        _request(
            budget=2000,
            luggage=Luggage.heavy,
            walking_preference=WalkingPreference.minimize,
            departure_time=_DEPART,
            arrival_deadline=_at(15),
        ),
        _candidates(),
    )
    assert decision.hard_constraints == {
        "origin": "Colombo Fort",
        "destination": "Ella",
        "budget_lkr": 2000,
        "arrival_deadline": _at(15).isoformat(),
    }
    assert decision.soft_preferences["luggage"] == "heavy"
    assert decision.soft_preferences["walking_preference"] == "minimize"
    assert decision.soft_preferences["departure_time"] == _DEPART.isoformat()
    assert set(_weights(decision)) == set(DecisionEngine.FEATURES)
    assert sum(_weights(decision).values()) == pytest.approx(1.0, abs=1e-5)
    assert decision.data_source is DataSource.mock


# E10. The additive A6 fields serialize for the frontend without breaking the A3 contract (§24).
def test_edge_recommendation_serializes_additive_fields() -> None:
    violation = ConstraintViolation(type="BUDGET", message="Over budget (LKR 2,350 > LKR 2,000).")
    card = Recommendation(
        id="R3", summary="s", rank=None, valid=False, strengths=[], constraint_violations=[violation]
    )
    dumped = card.model_dump(mode="json")
    assert dumped["valid"] is False and dumped["rank"] is None
    assert dumped["strengths"] == []
    assert dumped["constraint_violations"] == [
        {"type": "BUDGET", "message": "Over budget (LKR 2,350 > LKR 2,000)."}
    ]
    for key in (
        "id",
        "summary",
        "within_budget",
        "score",
        "rationale",
        "reasons",
        "trade_offs",
        "is_recommended",
        "data_source",
    ):
        assert key in dumped  # every A3 field is still present

    # A legacy payload with no A6 keys still validates and defaults safely.
    legacy = Recommendation.model_validate({"id": "R1", "summary": "s"})
    assert legacy.rank is None and legacy.valid is None
    assert legacy.strengths == [] and legacy.constraint_violations == []
