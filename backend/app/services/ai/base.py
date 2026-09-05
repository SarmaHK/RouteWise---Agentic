"""Interface + result types for the AI service (Workstream A, Phase A1).

One stable abstraction so the rest of the backend never depends on a specific vendor SDK.
Qwen / Model Studio is one implementation; a mock is another. Swapping providers must not
change callers — the same principle as the B/C tool seam (docs/ARCHITECTURE.md §2).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal, Optional


class AIServiceUnavailableError(RuntimeError):
    """The configured live AI service could not be reached (A9 brief §7/§14).

    Raised **only** on the live path — the deterministic mock never raises it, so mock mode stays
    fully functional and deterministic with no credentials. It exists so the API can distinguish
    "the upstream model is unreachable" (a retryable ``503``, the meaning API_CONTRACTS §5 already
    reserves for a downstream/tool that is unavailable) from "the model answered with invalid
    output" (:class:`~app.services.ai.extraction.MalformedExtractionError` → ``502``) and from an
    unexpected internal bug (``500``).

    Honesty (A9 brief §14): the failure is reported as a failure. The system never silently
    pretends a live model answered, and never claims mock output came from Qwen.
    """


@dataclass
class AIResponse:
    """A normalized, provider-agnostic completion result."""

    text: str
    model: str
    data_source: Literal["live", "mock"] = "live"
    usage: dict[str, Any] = field(default_factory=dict)
    raw: Optional[dict[str, Any]] = None


@dataclass
class ConnectivityResult:
    """Result of a minimal 'can we reach the model?' check (A1 brief §8)."""

    ok: bool
    mode: Literal["live", "mock"]
    model: str
    detail: str
    latency_ms: Optional[float] = None


class AIClient(ABC):
    """Minimal AI client interface used across the backend."""

    @abstractmethod
    def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> AIResponse:
        """Return a chat completion for an OpenAI-style ``messages`` list."""

    @abstractmethod
    def check_connectivity(self) -> ConnectivityResult:
        """Verify the backend can reach the configured model.

        Must NOT raise for expected failures and must NOT invent success — return an honest
        ``ConnectivityResult`` instead (docs/DEVELOPMENT_RULES.md rule 19).
        """
