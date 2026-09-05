"""Logging + request-correlation foundation for the backend (A1 base, extended in A9).

Configures one consistent log format for the whole app. IMPORTANT: secrets are never
logged — the Model Studio API key is excluded from every log path (see
``config.Settings.public_view``).

**A9 (observability)** extends this existing foundation rather than adding a tracing framework
or a new dependency (A9 brief §9/§10/§25). Two small, boring helpers make one agent execution
followable end-to-end:

* :func:`new_request_id` — a short, random, **non-personal** identifier for one execution, so the
  HTTP request, the extraction, every tool call and the final decision can be correlated in the
  logs (and quoted back from the response). It identifies *a request*, never a user: nothing here
  stores, tracks, or derives personal information (A9 brief §10).
* :func:`format_event` — renders one observability event as a stable ``event=<name> key=value``
  line (logfmt-style), so logs are greppable by event name and machine-parseable without a
  platform. Callers pass **only** short, non-sensitive summaries: never an API key, a password,
  the raw natural-language request, or hidden chain-of-thought (A9 brief §9).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

#: Response header carrying the execution identifier, so a client can correlate a result with the
#: backend logs without parsing the body (A9 brief §10). Additive — no JSON contract change.
REQUEST_ID_HEADER = "X-Request-Id"


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


def new_request_id() -> str:
    """A short, unique-enough identifier for one agent execution (A9 brief §10).

    Deliberately lightweight: a ``req_`` prefix plus 12 hex characters — readable in a log line
    and quotable in a demo, with no personal meaning and no persistence. It is **not** a session,
    a user id, or an idempotency key (A9 brief §10/§12).
    """
    return f"req_{uuid.uuid4().hex[:12]}"


def format_event(event: str, **fields: Any) -> str:
    """Render one observability event as ``event=<name> key=value ...`` (A9 brief §9).

    ``None`` fields are dropped so a line never carries ``key=None`` noise, an enum is rendered by
    its ``value`` and a bool as ``true``/``false``, so the line stays parseable by eye and by a
    grep. A value containing whitespace is quoted. Only short summaries should be passed here —
    this helper formats, it does not filter secrets, so callers must not hand it credentials or the
    traveller's raw text.
    """
    parts = [f"event={event}"]
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, bool):
            text = "true" if value else "false"
        elif hasattr(value, "value"):  # an Enum: log the wire value, not the repr
            text = str(value.value)
        else:
            text = str(value)
        if any(char.isspace() for char in text):
            text = '"{}"'.format(text.replace('"', "'"))
        parts.append(f"{key}={text}")
    return " ".join(parts)
