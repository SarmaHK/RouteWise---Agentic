"""Travel-request extraction tests (A2 brief §9).

Covers the 15 required natural-language scenarios via the deterministic mock extractor, plus
factory selection (mock vs Qwen), safe rejection of malformed model output, and the
no-hallucination guarantee. These run offline with no network and no credentials.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from app.config import Settings
from app.services.ai.base import AIResponse, AIClient, ConnectivityResult
from app.services.ai.extraction import (
    MalformedExtractionError,
    MockTravelRequestExtractor,
    QwenTravelRequestExtractor,
    _parse_model_json,
    build_extractor,
)
from app.services.ai.mock_client import MockAIClient

# The golden example from the A2 brief §2.
GOLDEN = (
    "I am at Colombo Fort and need to reach Ella under a budget of LKR 2,000, "
    "but I have a heavy bag and don't want to walk."
)


@pytest.fixture()
def extractor() -> MockTravelRequestExtractor:
    return MockTravelRequestExtractor()


# --- Scenario 1: the golden example --------------------------------------- #
def test_scenario_01_golden(extractor: MockTravelRequestExtractor) -> None:
    tr = extractor.extract(GOLDEN)
    assert tr.origin == "Colombo Fort"
    assert tr.destination == "Ella"
    assert tr.budget == 2000.0
    assert tr.currency == "LKR"
    assert tr.luggage is not None and tr.luggage.value == "heavy"
    assert tr.walking_preference is not None
    assert tr.walking_preference.value == "minimize"
    assert tr.clarification_required is False
    assert tr.extraction_source is not None and tr.extraction_source.value == "mock"


# --- Scenario 2: plain origin/destination --------------------------------- #
def test_scenario_02_origin_destination(extractor: MockTravelRequestExtractor) -> None:
    tr = extractor.extract("I need to travel from Colombo Fort to Ella.")
    assert tr.origin == "Colombo Fort"
    assert tr.destination == "Ella"
    assert tr.budget is None
    assert tr.clarification_required is False


# --- Scenario 3: reversed phrasing + informal currency -------------------- #
def test_scenario_03_reversed_and_rupees(extractor: MockTravelRequestExtractor) -> None:
    tr = extractor.extract("Get me to Ella from Colombo Fort for under 2000 rupees.")
    assert tr.origin == "Colombo Fort"
    assert tr.destination == "Ella"
    assert tr.budget == 2000.0
    assert tr.currency == "LKR"


# --- Scenario 4: luggage only --------------------------------------------- #
def test_scenario_04_luggage_only(extractor: MockTravelRequestExtractor) -> None:
    tr = extractor.extract("I have a heavy suitcase.")
    assert tr.luggage is not None and tr.luggage.value == "heavy"
    assert tr.origin is None and tr.destination is None
    assert tr.clarification_required is True
    assert set(tr.missing_fields) == {"origin", "destination"}


# --- Scenario 5: walking only --------------------------------------------- #
def test_scenario_05_walking_only(extractor: MockTravelRequestExtractor) -> None:
    tr = extractor.extract("I don't want to walk much.")
    assert tr.walking_preference is not None
    assert tr.walking_preference.value == "minimize"
    assert tr.clarification_required is True


# --- Scenario 6: departure time ------------------------------------------- #
def test_scenario_06_departure_time(extractor: MockTravelRequestExtractor) -> None:
    tr = extractor.extract("I want to leave Colombo around 8 AM.")
    assert tr.origin == "Colombo"
    assert tr.departure_time is not None and tr.departure_time.hour == 8
    assert tr.destination is None
    assert tr.clarification_required is True
    assert tr.assumptions  # recorded the "today's date" assumption honestly


# --- Scenario 7: arrival deadline ----------------------------------------- #
def test_scenario_07_arrival_deadline(extractor: MockTravelRequestExtractor) -> None:
    tr = extractor.extract("I need to reach Ella before 6 PM.")
    assert tr.destination == "Ella"
    assert tr.arrival_deadline is not None and tr.arrival_deadline.hour == 18
    assert tr.origin is None
    assert tr.clarification_required is True


# --- Scenario 8: destination + budget, origin missing --------------------- #
def test_scenario_08_missing_origin(extractor: MockTravelRequestExtractor) -> None:
    tr = extractor.extract("I need to go to Ella under 2000.")
    assert tr.destination == "Ella"
    assert tr.budget == 2000.0
    assert tr.origin is None
    assert tr.clarification_required is True
    assert "origin" in tr.missing_fields


# --- Scenario 9: origin + budget, destination missing --------------------- #
def test_scenario_09_missing_destination(extractor: MockTravelRequestExtractor) -> None:
    tr = extractor.extract("I'm at Colombo Fort and have a budget of 2000.")
    assert tr.origin == "Colombo Fort"
    assert tr.budget == 2000.0
    assert tr.destination is None
    assert tr.clarification_required is True
    assert "destination" in tr.missing_fields


# --- Scenario 10: nothing concrete (no hallucination) --------------------- #
def test_scenario_10_vague_nothing(extractor: MockTravelRequestExtractor) -> None:
    tr = extractor.extract("I want to travel somewhere.")
    assert tr.origin is None
    assert tr.destination is None
    assert tr.budget is None
    assert tr.luggage is None
    assert tr.walking_preference is None
    assert tr.clarification_required is True
    assert set(tr.missing_fields) == {"origin", "destination"}


# --- Scenario 11: everything at once -------------------------------------- #
def test_scenario_11_all_constraints(extractor: MockTravelRequestExtractor) -> None:
    tr = extractor.extract(
        "I need to reach Ella from Colombo Fort before 6 PM, with a heavy bag, "
        "and I don't want to walk much."
    )
    assert tr.origin == "Colombo Fort"
    assert tr.destination == "Ella"
    assert tr.arrival_deadline is not None and tr.arrival_deadline.hour == 18
    assert tr.luggage is not None and tr.luggage.value == "heavy"
    assert tr.walking_preference is not None
    assert tr.walking_preference.value == "minimize"
    assert tr.clarification_required is False


# --- Scenario 12: budget fragment only ------------------------------------ #
def test_scenario_12_budget_fragment(extractor: MockTravelRequestExtractor) -> None:
    tr = extractor.extract("under LKR 2,000")
    assert tr.budget == 2000.0
    assert tr.currency == "LKR"
    assert tr.origin is None and tr.destination is None
    assert tr.clarification_required is True


# --- Scenario 13: synonyms (big suitcase / low-walking) ------------------- #
def test_scenario_13_synonyms(extractor: MockTravelRequestExtractor) -> None:
    tr = extractor.extract("I've got a big suitcase and need a low-walking option.")
    assert tr.luggage is not None and tr.luggage.value == "heavy"
    assert tr.walking_preference is not None
    assert tr.walking_preference.value == "minimize"


# --- Scenario 14: vague "cheaply" preserved, budget NOT invented ---------- #
def test_scenario_14_cheap_no_budget(extractor: MockTravelRequestExtractor) -> None:
    tr = extractor.extract("Can you get me there cheaply?")
    assert tr.budget is None  # never fabricate a number from "cheaply"
    assert tr.preferences.get("cost") == "cheap"  # but preserve the preference
    assert tr.origin is None and tr.destination is None
    assert tr.clarification_required is True


# --- Scenario 15: malformed model output is rejected safely --------------- #
def test_scenario_15_parse_rejects_garbage() -> None:
    with pytest.raises(MalformedExtractionError):
        _parse_model_json("this is not json at all")
    with pytest.raises(MalformedExtractionError):
        _parse_model_json("")


def test_parse_accepts_fenced_and_wrapped_json() -> None:
    assert _parse_model_json('```json\n{"origin": "Ella"}\n```')["origin"] == "Ella"
    assert _parse_model_json('Sure! {"destination": "Ella"} hope that helps') == {
        "destination": "Ella"
    }


# --- No-hallucination guard across every scenario ------------------------- #
@pytest.mark.parametrize(
    "text",
    [
        GOLDEN,
        "I need to travel from Colombo Fort to Ella.",
        "Get me to Ella from Colombo Fort for under 2000 rupees.",
        "I have a heavy suitcase.",
        "I don't want to walk much.",
        "I want to leave Colombo around 8 AM.",
        "I need to reach Ella before 6 PM.",
        "I need to go to Ella under 2000.",
        "I'm at Colombo Fort and have a budget of 2000.",
        "I want to travel somewhere.",
        "under LKR 2,000",
        "I've got a big suitcase and need a low-walking option.",
        "Can you get me there cheaply?",
    ],
)
def test_never_invents_a_budget_number(
    extractor: MockTravelRequestExtractor, text: str
) -> None:
    tr = extractor.extract(text)
    mentions_number = any(ch.isdigit() for ch in text)
    if not mentions_number:
        assert tr.budget is None  # a budget appears only when a number was stated
    assert tr.extraction_source is not None and tr.extraction_source.value == "mock"


# --- Factory selection ---------------------------------------------------- #
def test_build_extractor_returns_mock_without_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MODEL_STUDIO_API_KEY", raising=False)
    assert isinstance(
        build_extractor(Settings(_env_file=None)), MockTravelRequestExtractor
    )


def test_build_extractor_returns_qwen_with_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_STUDIO_API_KEY", "test-key")
    assert isinstance(
        build_extractor(Settings(_env_file=None)), QwenTravelRequestExtractor
    )


@pytest.mark.skipif(
    not os.getenv("MODEL_STUDIO_API_KEY"),
    reason=(
        "MODEL_STUDIO_API_KEY not set - real Qwen extraction NOT verified "
        "(A2 permits mock-only; set the key to run this)."
    ),
)
def test_real_qwen_extraction_live() -> None:
    """End-to-end extraction through the EXISTING Qwen client (only with a real key)."""
    extractor = build_extractor(Settings(_env_file=None))
    assert isinstance(extractor, QwenTravelRequestExtractor)
    tr = extractor.extract(GOLDEN)
    assert tr.extraction_source is not None and tr.extraction_source.value == "qwen"
    assert tr.origin and tr.destination  # real model understood the golden example


# --- Qwen extractor: uses the EXISTING AIClient, rejects bad output ------- #
class _FakeClient(AIClient):
    """A stand-in AIClient that returns a canned completion (no network)."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.last_kwargs: dict[str, Any] = {}

    def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> AIResponse:
        self.last_kwargs = kwargs
        return AIResponse(text=self._text, model="fake", data_source="live")

    def check_connectivity(self) -> ConnectivityResult:  # pragma: no cover - unused here
        return ConnectivityResult(ok=True, mode="live", model="fake", detail="fake")


def test_qwen_extractor_parses_valid_json() -> None:
    client = _FakeClient(
        '{"origin": "Colombo Fort", "destination": "Ella", "budget": 2000, '
        '"currency": "LKR", "luggage": "heavy", "walking_preference": "minimize"}'
    )
    tr = QwenTravelRequestExtractor(client).extract(GOLDEN)
    assert tr.origin == "Colombo Fort"
    assert tr.destination == "Ella"
    assert tr.budget == 2000.0
    assert tr.extraction_source is not None and tr.extraction_source.value == "qwen"
    assert tr.clarification_required is False
    # Requests strict JSON from the model.
    assert client.last_kwargs.get("response_format") == {"type": "json_object"}


def test_qwen_extractor_rejects_garbage() -> None:
    client = _FakeClient("Sorry, I cannot help with that.")
    with pytest.raises(MalformedExtractionError):
        QwenTravelRequestExtractor(client).extract(GOLDEN)


def test_qwen_extractor_rejects_invalid_field_types() -> None:
    # Valid JSON, but budget is a non-numeric string -> Pydantic must reject it safely.
    client = _FakeClient('{"origin": "Colombo Fort", "budget": "not-a-number"}')
    with pytest.raises(MalformedExtractionError):
        QwenTravelRequestExtractor(client).extract("from Colombo Fort")


def test_qwen_extractor_flags_missing_origin_as_clarification() -> None:
    client = _FakeClient('{"destination": "Ella"}')
    tr = QwenTravelRequestExtractor(client).extract("I need to reach Ella")
    assert tr.origin is None
    assert tr.clarification_required is True
    assert "origin" in tr.missing_fields


# --- Hints (explicit structured fields) win over inferred values ---------- #
def test_hints_override_extraction(extractor: MockTravelRequestExtractor) -> None:
    tr = extractor.extract(
        "I want to travel somewhere.", hints={"origin": "Kandy", "destination": "Ella"}
    )
    assert tr.origin == "Kandy"
    assert tr.destination == "Ella"
    assert tr.clarification_required is False


def test_mock_ai_client_is_not_used_as_an_extractor() -> None:
    # Guard: the plain MockAIClient echo is NOT valid extraction JSON, so wiring it into the
    # Qwen extractor path must fail safely rather than fabricate a request.
    with pytest.raises(MalformedExtractionError):
        QwenTravelRequestExtractor(MockAIClient()).extract(GOLDEN)
