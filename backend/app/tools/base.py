"""Tool seam (Workstream A) — the base contract every capability implements.

This is the **stable boundary** through which the agent consumes transit intelligence (B) and
execution (C). Per ``app/tools/README.md`` and API_CONTRACTS §6, the signatures are fixed so B/C
can replace the mocks later with **no change to agent code**.

**Phase A4** turns the A3 seam into a clean capability-execution contract (A4 brief §5–§8):

* :class:`Tool` declares *what* it is (``name``/``description``/``input_schema``/``output_schema``),
  *whether it can run* (:class:`ToolAvailability`), *where its data comes from*
  (:class:`~app.schemas.route.DataSource`), and *how its input is validated* (``args_model``).
* Every call returns a structured :class:`ToolResult` — never an arbitrary dict — carrying
  ``success`` / ``tool_name`` / ``data_source`` / ``data`` / ``error`` (A4 brief §7).
* Failures are structured too (:class:`ToolError` + :class:`ToolErrorCode`), so the agent degrades
  honestly instead of crashing (A4 brief §12).

Honesty (AGENT_SPEC §15–§16; A4 brief §21) is built in: a stub that is not built yet is
``ToolAvailability.not_implemented`` and returns a ``NOT_IMPLEMENTED`` result rather than inventing
data. Nothing here touches a database, GTFS, ML models, or a booking system — those are explicitly
out of scope (A4 brief §3).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel

from app.schemas.route import DataSource


class ToolStatus(str, Enum):
    """Outcome kind of a single tool call (surfaced in the agent action trace)."""

    ok = "ok"  # real/usable result
    mock_data = "mock_data"  # deterministic mock result (A4 default for search_routes)
    not_implemented = "not_implemented"  # seam exists, capability not built yet
    unavailable = "unavailable"  # tool unknown, disabled, or otherwise cannot run
    error = "error"  # A4: invalid input / execution error / timeout / malformed result


class ToolAvailability(str, Enum):
    """Static capability state, used for planning **and** to gate execution (A4 brief §8).

    This deliberately separates "the tool exists" from "the tool can currently return data": a
    tool may be registered yet ``not_implemented`` until a future workstream supplies the real one
    (e.g. ``check_availability`` exists but is ``not_implemented`` until Workstream C). Provenance
    (mock vs live) is **not** an availability concern — it lives on ``data_source`` (A4 brief §15).
    """

    available = "available"  # returns usable (possibly mock) data
    not_implemented = "not_implemented"  # stub — a future workstream owns the real one
    disabled = "disabled"  # explicitly turned off (e.g. by config)
    error = "error"  # registered but currently broken / uninitialised


class ToolErrorCode(str, Enum):
    """Stable machine-readable failure codes for a structured result (A4 brief §6/§12).

    Clients/agent may branch on these; ``ToolError.message`` is the human-readable companion.
    """

    INVALID_INPUT = "INVALID_INPUT"  # payload failed the tool's input validation
    UNKNOWN_TOOL = "UNKNOWN_TOOL"  # no tool registered under that name
    DUPLICATE_TOOL = "DUPLICATE_TOOL"  # registration collision (setup-time)
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"  # seam exists, capability not built yet
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"  # disabled / in an error state
    EXECUTION_ERROR = "EXECUTION_ERROR"  # the tool raised
    TIMEOUT = "TIMEOUT"  # the tool exceeded its execution budget
    MALFORMED_RESULT = "MALFORMED_RESULT"  # the tool did not return a ToolResult


@dataclass
class ToolError:
    """Structured failure detail inside a :class:`ToolResult` (A4 brief §7: ``error{code,message}``).

    ``details`` holds non-sensitive technical context (e.g. which input fields failed validation).
    """

    code: str
    message: str
    details: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Serializable ``{code, message[, details]}`` shape."""
        out: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            out["details"] = self.details
        return out


@dataclass
class ToolResult:
    """Structured (not prose) tool output so the agent can reason/score over it.

    A4 refines the A3 result into the standard contract (brief §7) — ``success`` / ``tool_name`` /
    ``data_source`` / ``data`` / ``error`` — while keeping the A3 ``status`` / ``message`` / ``meta``
    detail for the action trace. ``success`` is **derived** (``error is None``) so it can never
    contradict the error. ``data`` is intentionally untyped: each tool documents its own output
    schema (``output_schema``) and the agent reads only the fields it needs. ``data_source`` keeps
    provenance honest — mock is never presented as real-time.
    """

    status: ToolStatus = ToolStatus.ok
    data_source: DataSource = DataSource.mock
    data: Any = None
    message: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
    tool_name: str = ""
    error: Optional[ToolError] = None

    @property
    def success(self) -> bool:
        """True when the call produced a usable result (no structured error)."""
        return self.error is None

    def to_dict(self) -> dict[str, Any]:
        """The standard structured-result shape (A4 brief §7)."""
        return {
            "success": self.success,
            "tool_name": self.tool_name,
            "status": self.status.value,
            "data_source": self.data_source.value,
            "data": self.data,
            "message": self.message,
            "error": self.error.to_dict() if self.error else None,
        }

    @classmethod
    def failure(
        cls,
        tool_name: str,
        code: ToolErrorCode | str,
        message: str,
        *,
        status: ToolStatus = ToolStatus.error,
        data_source: DataSource = DataSource.mock,
        data: Any = None,
        details: Optional[dict[str, Any]] = None,
    ) -> "ToolResult":
        """Build a structured failure result (``success is False``)."""
        code_value = code.value if isinstance(code, ToolErrorCode) else str(code)
        return cls(
            status=status,
            data_source=data_source,
            data=data,
            message=message,
            tool_name=tool_name,
            error=ToolError(code=code_value, message=message, details=details),
        )


class Tool(ABC):
    """Base class for every agent capability (A4 brief §5).

    Concrete tools set the class-level metadata and implement :meth:`execute`. The metadata is
    declarative so a planner (and, later, an LLM) can reason about capabilities without executing
    anything. Input validation and safe execution are centralized in
    :class:`~app.tools.executor.ToolExecutor` (A4 brief §6/§11) — a tool only implements its own
    logic in :meth:`execute`.
    """

    #: Stable tool name the agent calls by (API_CONTRACTS §6).
    name: str = "tool"
    #: One-line human description of what the tool does.
    description: str = ""
    #: JSON-schema-ish description of accepted keyword args (human-facing; ``args_model`` enforces).
    input_schema: dict[str, Any] = {}
    #: JSON-schema-ish description of the ``ToolResult.data`` payload.
    output_schema: dict[str, Any] = {}
    #: Static capability state for planning + execution gating (A4 brief §8).
    availability: ToolAvailability = ToolAvailability.not_implemented
    #: Which future workstream owns the real implementation ("A", "B", or "C").
    owner: str = "A"
    #: A4: Pydantic model validating the input before execution (``None`` ⇒ no structured args).
    args_model: Optional[type[BaseModel]] = None
    #: A4: default provenance of this tool's data (metadata; each result carries its own).
    data_source: DataSource = DataSource.mock
    #: A4: optional per-tool execution timeout override in seconds (``None`` ⇒ executor default).
    timeout_s: Optional[float] = None

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Run the capability and return a structured :class:`ToolResult`.

        Implementations MUST NOT raise for "not built yet" — they return a
        ``ToolStatus.not_implemented`` result so the agent can degrade honestly. The executor wraps
        this call with validation, a timeout, and exception/malformed-result guards.
        """
        raise NotImplementedError

    def describe(self) -> dict[str, Any]:
        """A serializable snapshot of this tool's metadata (A4 brief §15: name/description/status/
        data_source), for planning and the UI. Exposes no implementation internals."""
        return {
            "name": self.name,
            "description": self.description,
            "status": self.availability.value.upper(),
            "availability": self.availability.value,
            "data_source": self.data_source.value,
            "owner": self.owner,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }


def not_implemented_result(
    tool_name: str,
    owner: str,
    detail: Optional[str] = None,
) -> ToolResult:
    """Helper for stub capabilities: an honest 'not built yet' structured result.

    Keeps A4 free of fabricated data (AGENT_SPEC §16; A4 brief §21) while proving the seam works.
    Used both by the stub tools' ``execute`` and by the executor's availability gate.
    """
    message = (
        f"'{tool_name}' is not implemented yet "
        f"(future Workstream {owner} capability)."
    )
    if detail:
        message = f"{message} {detail}"
    return ToolResult(
        status=ToolStatus.not_implemented,
        data_source=DataSource.mock,
        data=None,
        message=message,
        tool_name=tool_name,
        error=ToolError(code=ToolErrorCode.NOT_IMPLEMENTED.value, message=message),
    )
