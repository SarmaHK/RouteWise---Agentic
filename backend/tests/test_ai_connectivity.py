"""REAL Qwen connectivity check (A1 brief §8, §14, §20).

This test contacts Alibaba Cloud Model Studio ONLY when ``MODEL_STUDIO_API_KEY`` is present.
When credentials are unavailable it SKIPS with an explicit message — we never claim
connectivity that was not actually tested (docs/DEVELOPMENT_RULES.md rule 19).
"""

from __future__ import annotations

import os

import pytest

from app.config import Settings
from app.services.ai import QwenClient


@pytest.mark.skipif(
    not os.getenv("MODEL_STUDIO_API_KEY"),
    reason=(
        "MODEL_STUDIO_API_KEY not set - real Qwen connectivity NOT verified "
        "(A1 permits mock-only; set the key to run this)."
    ),
)
def test_real_qwen_connectivity() -> None:
    settings = Settings(_env_file=None)  # reads MODEL_STUDIO_API_KEY from the environment
    result = QwenClient(settings).check_connectivity()
    assert result.mode == "live"
    assert result.ok is True, f"Model Studio connectivity failed: {result.detail}"
