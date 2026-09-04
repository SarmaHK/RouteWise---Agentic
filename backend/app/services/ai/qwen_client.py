"""Qwen client for Alibaba Cloud Model Studio (OpenAI-compatible) — Workstream A, Phase A1.

Uses ``httpx`` to call the OpenAI-compatible ``chat/completions`` endpoint, so we avoid adding
a vendor SDK (docs/DEVELOPMENT_RULES.md rule 9). The API key is read from settings and is
NEVER logged. Connectivity failures are returned as results, not raised (honest reporting).
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.config import Settings
from app.services.ai.base import AIResponse, AIClient, ConnectivityResult

logger = logging.getLogger("routewise.ai.qwen")

_DEFAULT_TIMEOUT = 20.0


class QwenClient(AIClient):
    """Talks to Alibaba Cloud Model Studio via its OpenAI-compatible HTTP API."""

    def __init__(self, settings: Settings, timeout: float = _DEFAULT_TIMEOUT) -> None:
        self._api_key = settings.model_studio_api_key
        self._base_url = settings.model_studio_base_url.rstrip("/")
        self._model = settings.model_name
        self._timeout = timeout

    def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> AIResponse:
        payload: dict[str, Any] = {"model": self._model, "messages": messages, **kwargs}
        data = self._post_chat(payload)
        choices = data.get("choices") or [{}]
        message = choices[0].get("message") or {}
        return AIResponse(
            text=message.get("content", "") or "",
            model=data.get("model", self._model),
            data_source="live",
            usage=data.get("usage") or {},
            raw=data,
        )

    def check_connectivity(self) -> ConnectivityResult:
        """Send a minimal 1-token prompt to confirm real connectivity. Never invents success."""
        started = time.perf_counter()
        try:
            data = self._post_chat(
                {
                    "model": self._model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                }
            )
        except httpx.HTTPError as exc:
            latency = (time.perf_counter() - started) * 1000
            # Log the exception CLASS only — never the request headers (which carry the key).
            logger.warning("Qwen connectivity check failed: %s", exc.__class__.__name__)
            return ConnectivityResult(
                ok=False,
                mode="live",
                model=self._model,
                detail=f"{exc.__class__.__name__}: {exc}",
                latency_ms=latency,
            )
        latency = (time.perf_counter() - started) * 1000
        return ConnectivityResult(
            ok=True,
            mode="live",
            model=data.get("model", self._model),
            detail="Model Studio reachable; chat/completions responded.",
            latency_ms=latency,
        )

    def _post_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}/chat/completions"
        # NOTE: `headers` (which carry the key) are never logged.
        response = httpx.post(url, json=payload, headers=headers, timeout=self._timeout)
        response.raise_for_status()
        return response.json()
