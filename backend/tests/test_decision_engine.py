"""A3 decision-engine tests (brief §15, tests 6–12).

Unit tests for :class:`~app.agent.decision.DecisionEngine` over the deterministic mock corridor
``Colombo Fort → Ella`` (R1 train/low-walk/LKR 1,600, R2 direct bus/more-walk/LKR 1,200,
R3 fastest/LKR 2,350 — over the golden budget). They prove hard constraints eliminate, soft
preferences rank, and nothing is silently violated (AGENT_SPEC §9–§11).

Note on the luggage-aware rule: ``walking_preference=minimize`` *alone*, or ``luggage=heavy``
*alone*, still favors the cheaper/faster/direct R2 — it is the **combination** (heavy bag +
minimize walking) that tips the decision to R1 (least walking, 1 transfer). That is genuine
reasoning over the data, not a hard-coded winner (DEMO §4.1).
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.agent.decision import Decision, DecisionEngine
from app.schemas.travel_request import Luggage, TravelRequest, WalkingPreference
from app.tools.candidates import MockCandidateProvider


def _candidates():
    return MockCandidateProvider().candidates_for("Colombo Fort", "Ella")


def _request(**kwargs) -> TravelRequest:
    return TravelRequest(
        origin="Colombo Fort", destination="Ella", currency="LKR", **kwargs
    )


def _score(decision: Decision, candidate_id: str) -> float:
    return next(
        sc.score for sc in decision.scored if sc.candidate.id == candidate_id
    )


# 6. A within-budget candidate wins; the over-budget candidate is excluded, never chosen.
def test_within_budget_beats_over_budget() -> None:
    decision = DecisionEngine().decide(
        _request(budget=2000, luggage=Luggage.heavy, walking_preference=WalkingPreference.minimize),
        _candidates(),
    )
    assert decision.recommendation is not None
    assert decision.recommendation.id != "R3"  # over-budget never wins
    assert "R3" in {e.candidate.id for e in decision.excluded}
    assert all(sc.candidate.total_fare_lkr <= 2000 for sc in decision.scored)


# 7. Walking preference influences ranking (least-walking R1 scores higher under 'minimize').
def test_walking_preference_influences_ranking() -> None:
    engine = DecisionEngine()
    minimize = engine.decide(
        _request(budget=2000, walking_preference=WalkingPreference.minimize), _candidates()
    )
    ok = engine.decide(
        _request(budget=2000, walking_preference=WalkingPreference.ok), _candidates()
    )
    # R1 has the least walking, so a stronger walking preference raises its score.
    assert _score(minimize, "R1") > _score(ok, "R1")
    # The walking weight itself is larger under 'minimize' than 'ok'.
    assert (
        minimize.soft_preferences["weights"]["walking_km"]
        > ok.soft_preferences["weights"]["walking_km"]
    )


# 8. Heavy luggage influences ranking where the candidate data supports it.
def test_heavy_luggage_influences_ranking() -> None:
    engine = DecisionEngine()
    golden = engine.decide(
        _request(budget=2000, luggage=Luggage.heavy, walking_preference=WalkingPreference.minimize),
        _candidates(),
    )
    plain = engine.decide(_request(budget=2000), _candidates())
    minimize_only = engine.decide(
        _request(budget=2000, walking_preference=WalkingPreference.minimize), _candidates()
    )
    # Heavy bag + minimize walking tips the decision to R1; without them R2 (cheaper/faster) wins.
    assert golden.recommendation.id == "R1"
    assert plain.recommendation.id == "R2"
    # Heavy luggage raises the walking weight vs no luggage at all ...
    assert (
        golden.soft_preferences["weights"]["walking_km"]
        > plain.soft_preferences["weights"]["walking_km"]
    )
    # ... and, holding the walking preference constant, raises the transfer weight too
    # (AGENT_SPEC §10 luggage-aware rule: heavy penalizes walking AND multiple transfers).
    assert (
        golden.soft_preferences["weights"]["transfers"]
        > minimize_only.soft_preferences["weights"]["transfers"]
    )


# 9. An arrival deadline eliminates a candidate that would arrive too late.
def test_arrival_deadline_elimines_late_candidate() -> None:
    # Depart 08:00, must arrive by 15:00. R1 = 420 min + 10 delay → ~15:10 (late);
    # R2 = 360 min + 30 delay → ~14:30 (ok); R3 is over budget regardless.
    request = _request(
        budget=2000,
        departure_time=datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc),
        arrival_deadline=datetime(2026, 1, 1, 15, 0, tzinfo=timezone.utc),
    )
    decision = DecisionEngine().decide(request, _candidates())
    excluded = {e.candidate.id: e.constraint for e in decision.excluded}
    assert excluded.get("R1") == "arrival_deadline"
    assert excluded.get("R3") == "budget"
    assert decision.recommendation.id == "R2"


# 10. No valid candidate → no recommendation, reported honestly.
def test_no_valid_candidate_returns_no_recommendation() -> None:
    decision = DecisionEngine().decide(_request(budget=500), _candidates())
    assert decision.recommendation is None
    assert decision.satisfied is False
    assert len(decision.excluded) == 3
    assert "No candidate fits" in decision.reasoning


# 11. Alternatives are returned correctly, with honest trade-offs and budget flags.
def test_alternatives_returned_correctly() -> None:
    decision = DecisionEngine().decide(
        _request(budget=2000, luggage=Luggage.heavy, walking_preference=WalkingPreference.minimize),
        _candidates(),
    )
    assert decision.recommendation.id == "R1"
    alternatives = {a.id: a for a in decision.alternatives}
    assert "R2" in alternatives  # valid survivor kept as an alternative
    r2 = alternatives["R2"]
    assert r2.is_recommended is False
    assert r2.within_budget is True
    assert r2.trade_offs  # honest trade-offs vs the recommendation
    # The over-budget candidate is surfaced only if clearly marked as violating the budget.
    if "R3" in alternatives:
        assert alternatives["R3"].within_budget is False


# 12. Hard constraints are never silently violated by the recommendation.
def test_hard_constraints_never_silently_violated() -> None:
    engine = DecisionEngine()
    for budget in (2000, 1500, 1300, 500):
        decision = engine.decide(_request(budget=budget), _candidates())
        recommendation = decision.recommendation
        if recommendation is not None:
            assert recommendation.total_fare_lkr <= budget
            assert recommendation.within_budget is True
        assert all(sc.candidate.total_fare_lkr <= budget for sc in decision.scored)
