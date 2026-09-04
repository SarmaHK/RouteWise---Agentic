"""Tool seam (Workstream A, Phase A3) — the base contract every capability implements.

This is the **stable boundary** through which the agent consumes transit intelligence (B) and
execution (C). Per ``app/tools/README.md`` and API_CONTRACTS §6, the signatures are fixed now so
B/C can replace the mocks later with **no change to agent code**.

A3 ships only minimal mock/stub capabilities (A3 brief §6). Nothing here touches a database,
GTFS, ML models, or a booking system — those are explicitly out of scope (A3 brief §19).

Design notes:

* :class:`Tool` is metadata + ``execute``. Metadata (``name``/``description``/``input_schema``/
  ``output_schema``/``availability``) lets the agent *plan* which tools are worth calling
  (AGENT_SPEC §6–§7) without hard-coding names.
* Every result carries a :class:`~app.schemas.route.DataSource` so the system is always honest
  about provenance (AGENT_SPEC §15). A stub that is not built yet returns
  ``ToolStatus.not_implemented`` rather than inventing data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from app.schemas.route import DataSource


class ToolStatus(str, Enum):
    """Outcome of a single tool call (surfaced in the agent action trace)."""

    ok = "ok"  # real/usable result
    mock_data = "mock_data"  # deterministic mock result (A3 default for search)
    not_implemented = "not_implemented"  # seam exists, capability not built yet
    unavailable = "unavailable"  # tool present but cannot run (e.g. missing config)


class ToolAvailability(str, Enum):
    """Static capability level, used by the agent when PLANNING which tools to call."""

    available = "available"  # returns usable (possibly mock) data
    mock = "mock"  # deterministic mock only
    not_implemented = "not_implemented"  # stub — a future workstream owns the real one


@dataclass
class ToolResult:
    """Structured (not prose) tool output so the agent can reason/score over it.

    ``data`` is intentionally untyped: each tool documents its own output schema, and the agent
    reads only the fields it needs. ``data_source`` keeps provenance honest.
    """

    status: ToolStatus
    data_source: DataSource = DataSource.mock
    data: Any = None
    message: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


class Tool(ABC):
    """Base class for every agent capability (A3 brief §6).

    Concrete tools set the class-level metadata and implement :meth:`execute`. The metadata is
    deliberately declarative so it can be exposed to a planner (and, later, to an LLM) without
    executing anything.
    """

    #: Stable tool name the agent calls by (API_CONTRACTS §6).
    name: str = "tool"
    #: One-line human description of what the tool does.
    description: str = ""
    #: JSON-schema-ish description of accepted keyword args.
    input_schema: dict[str, Any] = {}
    #: JSON-schema-ish description of the ``ToolResult.data`` payload.
    output_schema: dict[str, Any] = {}
    #: Static capability level for planning.
    availability: ToolAvailability = ToolAvailability.not_implemented
    #: Which future workstream owns the real implementation ("A", "B", or "C").
    owner: str = "A"

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Run the capability and return a structured :class:`ToolResult`.

        Implementations MUST NOT raise for "not built yet" — they return a
        ``ToolStatus.not_implemented`` result so the agent can degrade honestly.
        """
        raise NotImplementedError

    def describe(self) -> dict[str, Any]:
        """A serializable snapshot of this tool's metadata (for planning / debugging)."""
        return {
            "name": self.name,
            "description": self.description,
            "availability": self.availability.value,
            "owner": self.owner,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }


def not_implemented_result(
    tool_name: str,
    owner: str,
    detail: Optional[str] = None,
) -> ToolResult:
    """Helper for stub capabilities: an honest 'not built yet' result.

    Keeps A3 free of fabricated data (AGENT_SPEC §16) while proving the seam works.
    """
    message = (
        f"'{tool_name}' is not implemented in Phase A3 "
        f"(future Workstream {owner} capability)."
    )
    if detail:
        message = f"{message} {detail}"
    return ToolResult(
        status=ToolStatus.not_implemented,
        data_source=DataSource.mock,
        data=None,
        message=message,
    )
