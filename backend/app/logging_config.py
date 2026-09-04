"""Minimal logging foundation for the backend (Phase A1).

Configures one consistent log format for the whole app. IMPORTANT: secrets are never
logged — the Model Studio API key is excluded from every log path (see
``config.Settings.public_view``).
"""

from __future__ import annotations

import logging


def configure_logging(level: str = "INFO") -> None:
    """Set up root logging with a single, consistent format.

    Safe to call more than once; ``basicConfig`` is a no-op if handlers exist.
    """
    logging.basicConfig(
        level=getattr(logging, str(level).upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    # Quieten noisy third-party loggers during local development.
    logging.getLogger("httpx").setLevel(logging.WARNING)
