"""Travel-request extraction (Workstream A, Phase A2 — Request Understanding).

Turns a natural-language travel request into a validated
:class:`~app.schemas.travel_request.TravelRequest`:

    NATURAL LANGUAGE -> Qwen structured extraction -> Pydantic validation -> TravelRequest

This module EXTENDS the existing AI abstraction (``base.AIClient`` / ``factory``) — it does
NOT create a second Qwen client (A2 brief §4). Two extractors share one interface:

* :class:`QwenTravelRequestExtractor` — real Qwen via the existing ``AIClient`` (used when a
  ``MODEL_STUDIO_API_KEY`` is configured). Malformed/invalid model output is rejected safely
  with :class:`MalformedExtractionError` — never silently accepted (A2 brief §5).
* :class:`MockTravelRequestExtractor` — deterministic, offline rule-based extraction for
  testing without credentials. It is clearly labelled ``extraction_source="mock"`` and never
  pretends real Qwen was used (A2 brief §5).

Both are honest: they extract only what is present, never invent values, and surface missing
hard constraints through the TravelRequest clarification fields (A2 brief §3/§6).
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Optional

from pydantic import ValidationError

from app.config import Settings, get_settings
from app.schemas.travel_request import ExtractionSource, TravelRequest
from app.services.ai.base import AIClient
from app.services.ai.factory import build_ai_client

logger = logging.getLogger("routewise.ai.extraction")

# Sri Lanka Standard Time is UTC+05:30. A fixed offset avoids a tzdata dependency on Windows
# (docs/DEVELOPMENT_RULES.md rule 9 — no unnecessary deps); A2 only needs time-of-day.
_SL_TZ = timezone(timedelta(hours=5, minutes=30))


class MalformedExtractionError(ValueError):
    """Raised when model output cannot be parsed or fails TravelRequest validation.

    The endpoint maps this to a safe 502 (structured error envelope) rather than crashing or
    accepting invalid AI output (A2 brief §5/§9).
    """


# --------------------------------------------------------------------------- #
# Prompt (real Qwen path)
# --------------------------------------------------------------------------- #

EXTRACTION_SYSTEM_PROMPT = """\
You are a precise travel-request information extractor for a Sri Lanka multi-modal transit \
assistant.

Given a traveller's natural-language request, extract structured trip information and respond \
with ONLY a single valid JSON object. No prose, no markdown, no code fences.

Rules:
- Extract ONLY information explicitly present in the request. NEVER guess, infer, or invent \
values that were not stated.
- If a field is unknown or not stated, use null (or omit it). Do not fabricate placeholders.
- Preserve every stated constraint and preference (budget, luggage, walking, times).
- Normalize obvious values safely (e.g. "2,000 rupees" -> 2000; "8 AM" -> an ISO 8601 time). \
Do NOT normalize ambiguous values.
- Distinguish hard constraints (origin, destination, budget, arrival deadline) from soft \
preferences (walking comfort, luggage, cheapness).
- If required information (origin or destination) is missing or ambiguous, leave it null, set \
"clarification_required" to true, and add a short question to "clarification_questions".

Respond with JSON of exactly this shape (every field optional except the clarification \
metadata; use null for unknown values):
{
  "origin": string | null,
  "destination": string | null,
  "budget": number | null,
  "currency": string,
  "luggage": "none" | "light" | "heavy" | null,
  "walking_preference": "minimize" | "normal" | "ok" | null,
  "departure_time": ISO 8601 string | null,
  "arrival_deadline": ISO 8601 string | null,
  "preferences": object,
  "clarification_required": boolean,
  "clarification_questions": string[],
  "assumptions": string[]
}
"""


def _build_messages(raw_text: str, hints: dict[str, Any]) -> list[dict[str, str]]:
    """Build the OpenAI-style messages for the extraction call."""
    hint_note = ""
    if hints:
        hint_note = (
            "\n\nStructured fields the user already provided (authoritative — merge them "
            "with the text):\n" + json.dumps(hints, default=str, ensure_ascii=False)
        )
    user_content = (
        f'Traveller request:\n"""{raw_text}"""{hint_note}\n\nReturn only the JSON object.'
    )
    return [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _parse_model_json(text: str) -> dict[str, Any]:
    """Parse a model completion into a JSON object, tolerating code fences / stray prose.

    Raises :class:`MalformedExtractionError` when no JSON object can be recovered.
    """
    if not text or not text.strip():
        raise MalformedExtractionError("Empty model response.")
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise MalformedExtractionError("Model response is not valid JSON.")
        try:
            data = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise MalformedExtractionError(
                f"Model response is not valid JSON: {exc}"
            ) from exc
    if not isinstance(data, dict):
        raise MalformedExtractionError("Model JSON is not an object.")
    return data


# --------------------------------------------------------------------------- #
# Interface + shared finalization
# --------------------------------------------------------------------------- #


class TravelRequestExtractor(ABC):
    """One interface for turning natural language into a ``TravelRequest``."""

    @abstractmethod
    def extract(
        self, raw_text: str, hints: Optional[dict[str, Any]] = None
    ) -> TravelRequest:
        """Extract and validate a ``TravelRequest`` from ``raw_text`` (+ optional hints)."""


def _normalize(data: dict[str, Any]) -> dict[str, Any]:
    """Coerce extracted/hint values into shapes TravelRequest accepts. Drops None values.

    Only SAFE normalizations are applied (comma-stripped numbers, lowercased enums). A value
    that cannot be normalized is left as-is so Pydantic rejects it -> ``MalformedExtractionError``
    rather than being silently dropped (A2 brief §5 — don't silently accept invalid output).
    """
    out: dict[str, Any] = {k: v for k, v in data.items() if v is not None}
    if isinstance(out.get("luggage"), str):
        out["luggage"] = out["luggage"].strip().lower()
    if isinstance(out.get("walking_preference"), str):
        out["walking_preference"] = out["walking_preference"].strip().lower()
    budget = out.get("budget")
    if isinstance(budget, str):
        cleaned = budget.replace(",", "").strip()
        try:
            out["budget"] = float(cleaned)
        except ValueError:
            out["budget"] = cleaned  # un-coercible -> Pydantic will reject it (not silent)
    elif isinstance(budget, (int, float)):
        out["budget"] = float(budget)
    if isinstance(out.get("currency"), str):
        out["currency"] = out["currency"].strip().upper() or "LKR"
    return out


def _finalize(
    extracted: dict[str, Any],
    hints: Optional[dict[str, Any]],
    source: ExtractionSource,
    raw_text: Optional[str],
) -> TravelRequest:
    """Merge extraction + explicit hints, validate, and compute clarification state.

    Explicit structured ``hints`` (fields the user set directly) win over inferred values.
    Validation failure is converted to :class:`MalformedExtractionError` (safe rejection).
    """
    data: dict[str, Any] = dict(extracted or {})
    for key, value in (hints or {}).items():
        if key == "raw_text" or value is None:
            continue
        if key == "preferences" and not value:
            continue  # don't clobber extracted preferences with an empty default
        data[key] = value

    data = _normalize(data)
    if raw_text:
        data["raw_text"] = raw_text
    data["extraction_source"] = source.value

    try:
        travel_request = TravelRequest.model_validate(data)
    except ValidationError as exc:
        raise MalformedExtractionError(
            f"Extracted travel request failed validation: {exc}"
        ) from exc
    travel_request.refresh_clarification()
    return travel_request


# --------------------------------------------------------------------------- #
# Real Qwen extractor
# --------------------------------------------------------------------------- #


class QwenTravelRequestExtractor(TravelRequestExtractor):
    """Extraction backed by the EXISTING Qwen ``AIClient`` (no second client)."""

    def __init__(self, client: AIClient) -> None:
        self._client = client

    def extract(
        self, raw_text: str, hints: Optional[dict[str, Any]] = None
    ) -> TravelRequest:
        messages = _build_messages(raw_text or "", hints or {})
        response = self._client.complete(
            messages, response_format={"type": "json_object"}, temperature=0
        )
        data = _parse_model_json(response.text)
        # Qwen may set its own clarification flags; recompute from required fields so the
        # contract stays consistent and honest regardless of the model's self-assessment.
        data.pop("missing_fields", None)
        return _finalize(data, hints, ExtractionSource.qwen, raw_text)


# --------------------------------------------------------------------------- #
# Deterministic mock extractor (offline, no credentials)
# --------------------------------------------------------------------------- #

# A small Sri-Lanka gazetteer so the mock can find places deterministically. Longest names
# are matched first (e.g. "Colombo Fort" before "Colombo").
_PLACES: tuple[str, ...] = (
    "Colombo Fort",
    "Nuwara Eliya",
    "Anuradhapura",
    "Polonnaruwa",
    "Trincomalee",
    "Batticaloa",
    "Kurunegala",
    "Ratnapura",
    "Hambantota",
    "Bandarawela",
    "Kataragama",
    "Hikkaduwa",
    "Wellawaya",
    "Colombo",
    "Kandy",
    "Galle",
    "Jaffna",
    "Negombo",
    "Matara",
    "Badulla",
    "Kalutara",
    "Bentota",
    "Sigiriya",
    "Dambulla",
    "Haputale",
    "Pettah",
    "Ella",
    "Fort",
)
_PLACE_CANON: dict[str, str] = {p.lower(): p for p in _PLACES}
_PLACE_RE = re.compile(
    r"\b(?:"
    + "|".join(re.escape(p) for p in sorted(_PLACES, key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)

# Cue phrases immediately preceding a place, longest-first wins (so "arrive at" beats "at").
_CUES: tuple[tuple[str, str], ...] = (
    ("leaving from", "origin"),
    ("departing from", "origin"),
    ("starting from", "origin"),
    ("start from", "origin"),
    ("starting at", "origin"),
    ("start at", "origin"),
    ("currently at", "origin"),
    ("i am at", "origin"),
    ("i'm at", "origin"),
    ("am at", "origin"),
    ("get me to", "dest"),
    ("get to", "dest"),
    ("go to", "dest"),
    ("going to", "dest"),
    ("travel to", "dest"),
    ("travelling to", "dest"),
    ("head to", "dest"),
    ("arrive at", "dest"),
    ("arrive in", "dest"),
    ("from", "origin"),
    ("leave", "origin"),
    ("leaving", "origin"),
    ("depart", "origin"),
    ("departing", "origin"),
    ("near", "origin"),
    ("reach", "dest"),
    ("reaching", "dest"),
    ("towards", "dest"),
    ("toward", "dest"),
    ("to", "dest"),
    ("at", "origin"),
)

_BUDGET_RE = re.compile(
    r"(?:budget(?:\s+of)?|under|below|less\s+than|within|max(?:imum)?(?:\s+budget)?)\s*"
    r"(?:lkr|rs\.?|rupees?)?\s*(\d[\d,]*(?:\.\d+)?)",
    re.IGNORECASE,
)
_TIME_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)\b", re.IGNORECASE)
_DEPART_CUE_RE = re.compile(
    r"\b(?:leave|leaving|depart|departing|departure|start|starting|set off|head out)\b",
    re.IGNORECASE,
)
_ARRIVAL_CUE_RE = re.compile(
    r"\b(?:before|by|no later than|until|arrive by|arrive before|reach by|reach before)\b",
    re.IGNORECASE,
)
_LUGGAGE_NONE_RE = re.compile(
    r"\b(?:no|without|zero)\s+(?:bag|bags|luggage|suitcase)\b|\bempty[- ]handed\b"
    r"|\bnothing to carry\b",
    re.IGNORECASE,
)
_LUGGAGE_HEAVY_RE = re.compile(
    r"\b(?:heavy|big|large|bulky|huge)\b.{0,15}\b(?:bag|bags|suitcase|luggage|backpack|case)\b"
    r"|\b(?:bag|suitcase|luggage)\b.{0,10}\b(?:heavy|big|large|bulky)\b",
    re.IGNORECASE,
)
_LUGGAGE_LIGHT_RE = re.compile(
    r"\b(?:light|small|tiny|compact)\b.{0,12}\b(?:bag|bags|suitcase|luggage|backpack)\b"
    r"|\b(?:hand|cabin)\s+luggage\b|\bonly a backpack\b",
    re.IGNORECASE,
)
_WALK_OK_RE = re.compile(
    r"\b(?:ok|okay|fine|happy|willing|don'?t mind|do not mind)\b.{0,20}\bwalk",
    re.IGNORECASE,
)
_WALK_MIN_RE = re.compile(
    r"\b(?:don'?t|do not|dont|avoid|minimi[sz]e|less|low|minimal|little|no|not much|reduce)\b"
    r".{0,20}\bwalk|\blow[- ]walking\b",
    re.IGNORECASE,
)
_CHEAP_RE = re.compile(
    r"\b(?:cheap|cheapest|cheaply|economical|budget[- ]friendly|low[- ]cost)\b",
    re.IGNORECASE,
)


def _to_datetime(hour: int, minute: int, is_pm: bool) -> datetime:
    """Build a Sri-Lanka-time datetime for a time-of-day, assuming today's date."""
    if hour == 12:
        hour = 12 if is_pm else 0
    elif is_pm:
        hour += 12
    now = datetime.now(_SL_TZ)
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _find_places(text: str) -> tuple[Optional[str], Optional[str]]:
    """Return (origin, destination) using the nearest-longest cue phrase before each place."""
    lower = text.lower()
    origin: Optional[str] = None
    destination: Optional[str] = None
    for match in _PLACE_RE.finditer(text):
        place = _PLACE_CANON.get(match.group(0).lower())
        if not place:
            continue
        before = lower[: match.start()].rstrip()
        if before.endswith(" the"):
            before = before[:-4].rstrip()
        role, best = None, -1
        for phrase, cue_role in _CUES:
            if before == phrase or before.endswith(" " + phrase):
                if len(phrase) > best:
                    best, role = len(phrase), cue_role
        if role == "origin" and origin is None:
            origin = place
        elif role == "dest" and destination is None:
            destination = place
    return origin, destination


def _find_budget(text: str) -> Optional[float]:
    match = _BUDGET_RE.search(text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _find_currency(text: str) -> str:
    lowered = text.lower()
    if "usd" in lowered or "dollar" in lowered or "$" in lowered:
        return "USD"
    if "eur" in lowered or "euro" in lowered or "\u20ac" in lowered:
        return "EUR"
    return "LKR"


def _find_time(text: str) -> Optional[tuple[int, int, bool]]:
    match = _TIME_RE.search(text)
    if not match:
        return None
    try:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
    except (TypeError, ValueError):
        return None
    if not (1 <= hour <= 12 and 0 <= minute <= 59):
        return None
    is_pm = match.group(3).lower().startswith("p")
    return hour, minute, is_pm


def _extract_from_text(text: str) -> dict[str, Any]:
    """Deterministic rule-based extraction. Returns only what is genuinely present."""
    extracted: dict[str, Any] = {}
    if not text:
        return extracted

    origin, destination = _find_places(text)
    if origin:
        extracted["origin"] = origin
    if destination:
        extracted["destination"] = destination

    budget = _find_budget(text)
    if budget is not None:
        extracted["budget"] = budget
        extracted["currency"] = _find_currency(text)

    if _LUGGAGE_NONE_RE.search(text):
        extracted["luggage"] = "none"
    elif _LUGGAGE_HEAVY_RE.search(text):
        extracted["luggage"] = "heavy"
    elif _LUGGAGE_LIGHT_RE.search(text):
        extracted["luggage"] = "light"

    if _WALK_OK_RE.search(text):
        extracted["walking_preference"] = "ok"
    elif _WALK_MIN_RE.search(text):
        extracted["walking_preference"] = "minimize"

    time_parts = _find_time(text)
    if time_parts:
        hour, minute, is_pm = time_parts
        if _DEPART_CUE_RE.search(text):
            extracted["departure_time"] = _to_datetime(hour, minute, is_pm)
            extracted.setdefault("assumptions", []).append(
                "Assumed today's date for the stated time (no explicit date given)."
            )
        elif _ARRIVAL_CUE_RE.search(text):
            extracted["arrival_deadline"] = _to_datetime(hour, minute, is_pm)
            extracted.setdefault("assumptions", []).append(
                "Assumed today's date for the stated deadline (no explicit date given)."
            )

    if _CHEAP_RE.search(text) and budget is None:
        # Preserve a vague cost preference WITHOUT inventing a numeric budget.
        extracted.setdefault("preferences", {})["cost"] = "cheap"

    return extracted


class MockTravelRequestExtractor(TravelRequestExtractor):
    """Offline deterministic extractor used when no ``MODEL_STUDIO_API_KEY`` is set."""

    def extract(
        self, raw_text: str, hints: Optional[dict[str, Any]] = None
    ) -> TravelRequest:
        extracted = _extract_from_text(raw_text or "")
        return _finalize(extracted, hints, ExtractionSource.mock, raw_text)


# --------------------------------------------------------------------------- #
# Factory (mirrors ai/factory.py)
# --------------------------------------------------------------------------- #


def build_extractor(settings: Settings) -> TravelRequestExtractor:
    """Return a Qwen-backed extractor when a key exists, else the deterministic mock."""
    if settings.ai_enabled:
        return QwenTravelRequestExtractor(build_ai_client(settings))
    return MockTravelRequestExtractor()


@lru_cache
def get_extractor() -> TravelRequestExtractor:
    """Cached accessor for application code / the FastAPI dependency."""
    return build_extractor(get_settings())
