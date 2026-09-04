"""Tool execution layer (Workstream A, Phase A4).

Realizes the A4 flow (brief §11):

    Agent → ToolRegistry → ToolExecutor → Tool → structured ToolResult

The executor is the single place that turns "call a tool" into a **safe, structured** outcome, so
individual tools stay simple and the agent never needs to know their internals:

* **Availability gate** (brief §8/§21) — a ``not_implemented`` / ``disabled`` / ``error`` tool never
  runs, so a stub can never fabricate a successful result.
* **Input validation** (brief §6) — an ``available`` tool with an ``args_model`` has its payload
  validated by Pydantic *before* execution; malformed input returns a structured ``INVALID_INPUT``
  failure and never reaches the implementation.
* **Bounded execution** (brief §13) — the call runs under a small timeout so a slow/hung tool cannot
  hang the agent (a hackathon-MVP mechanism, not a job queue).
* **Guards** (brief §12) — any exception becomes ``EXECUTION_ERROR``; a non-``ToolResult`` return
  becomes ``MALFORMED_RESULT``.

Every path returns a :class:`ToolResult`; the executor never raises to the agent and never invents
data.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any, Optional

from pydantic import ValidationError

from app.tools.base import (
    Tool,
    ToolAvailability,
    ToolErrorCode,
    ToolResult,
    ToolStatus,
    not_implemented_result,
)

logger = logging.getLogger(__name__)

#: Default per-call budget. Mock tools return instantly; this only guards a future slow/hung tool.
DEFAULT_TOOL_TIMEOUT_S = 5.0


def _validation_details(exc: ValidationError) -> dict[str, Any]:
    """A small, non-sensitive summary of Pydantic validation errors for ``ToolError.details``."""
    return {
        "errors": [
            {
                "loc": [str(part) for part in err.get("loc", ())],
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in exc.errors()
        ]
    }


class ToolExecutor:
    """Runs a resolved :class:`Tool` safely and always returns a structured :class:`ToolResult`."""

    def __init__(
        self,
        default_timeout_s: float = DEFAULT_TOOL_TIMEOUT_S,
        max_workers: int = 4,
    ) -> None:
        self._default_timeout_s = default_timeout_s
        # A small reusable pool so a slow tool cannot block the agent indefinitely (brief §13).
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="tool-exec"
        )

    def execute(self, tool: Tool, payload: Optional[dict[str, Any]] = None) -> ToolResult:
        """Validate → run → normalize one tool call into a structured result."""
        payload = dict(payload or {})

        # 1. Availability gate (brief §8/§21) — non-executable states never run.
        if tool.availability is ToolAvailability.not_implemented:
            return not_implemented_result(tool.name, tool.owner)
        if tool.availability is ToolAvailability.disabled:
            return ToolResult.failure(
                tool.name,
                ToolErrorCode.TOOL_UNAVAILABLE,
                f"Tool '{tool.name}' is disabled.",
                status=ToolStatus.unavailable,
            )
        if tool.availability is ToolAvailability.error:
            return ToolResult.failure(
                tool.name,
                ToolErrorCode.TOOL_UNAVAILABLE,
                f"Tool '{tool.name}' is in an error state and cannot run.",
                status=ToolStatus.unavailable,
            )

        # 2. Input validation (brief §6) — only for tools that declare a structured args model.
        kwargs: dict[str, Any] = payload
        if tool.args_model is not None:
            try:
                validated = tool.args_model.model_validate(payload)
            except ValidationError as exc:
                details = _validation_details(exc)
                first = details["errors"][0]["msg"] if details["errors"] else "invalid payload"
                return ToolResult.failure(
                    tool.name,
                    ToolErrorCode.INVALID_INPUT,
                    f"Invalid input for '{tool.name}': {first}.",
                    status=ToolStatus.error,
                    details=details,
                )
            # Only validated, declared fields reach the implementation (extra keys are dropped).
            kwargs = validated.model_dump()

        # 3. Bounded execution + exception guard (brief §12/§13).
        timeout_s = tool.timeout_s or self._default_timeout_s
        try:
            future = self._pool.submit(tool.execute, **kwargs)
            result = future.result(timeout=timeout_s)
        except FutureTimeoutError:
            # The worker thread cannot be force-killed; the agent still gets a structured failure.
            logger.warning("Tool '%s' timed out after %ss.", tool.name, timeout_s)
            return ToolResult.failure(
                tool.name,
                ToolErrorCode.TIMEOUT,
                f"Tool '{tool.name}' timed out after {timeout_s}s.",
                status=ToolStatus.error,
            )
        except Exception as exc:  # noqa: BLE001 — the agent must never crash on a tool failure
            logger.warning("Tool '%s' raised during execution: %s", tool.name, exc)
            return ToolResult.failure(
                tool.name,
                ToolErrorCode.EXECUTION_ERROR,
                f"Tool '{tool.name}' failed: {exc}",
                status=ToolStatus.error,
            )

        # 4. Malformed-result guard (brief §12).
        if not isinstance(result, ToolResult):
            return ToolResult.failure(
                tool.name,
                ToolErrorCode.MALFORMED_RESULT,
                f"Tool '{tool.name}' returned a non-structured result "
                f"({type(result).__name__}).",
                status=ToolStatus.error,
            )

        if not result.tool_name:
            result.tool_name = tool.name
        return result

    def shutdown(self) -> None:
        """Release the worker pool (best-effort; safe to call more than once)."""
        self._pool.shutdown(wait=False)
