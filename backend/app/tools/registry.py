"""Tool registry + execution wiring (Workstream A, Phase A4).

The registry is the single place the agent looks tools up **by name** (AGENT_SPEC §7) and the entry
point for running them (A4 brief §9/§11). It supports the full lifecycle the agent needs:

    register → get / names / list_available / status → execute → structured ToolResult

Delegation keeps responsibilities clean: the registry **resolves** a tool by name and hands it to a
:class:`~app.tools.executor.ToolExecutor`, which **validates + runs** it and always returns a
structured result. Unknown names degrade to a structured ``UNKNOWN_TOOL`` failure rather than
raising; duplicate registrations are rejected clearly at wiring time (``DuplicateToolError``).

The DI shape mirrors ``app/services/ai/factory.py``: an explicit :func:`build_tools` (test friendly)
plus a cached :func:`get_tools` accessor for app code / the FastAPI dependency graph. Registry
contents are config-independent in A4 — every capability is a mock or an honest stub regardless of
settings — so ``settings`` is accepted for signature parity and future use (Workstream B/C may
enable real tools from config), but not read yet.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Optional

from app.config import Settings, get_settings
from app.tools.base import (
    Tool,
    ToolAvailability,
    ToolErrorCode,
    ToolResult,
    ToolStatus,
)
from app.tools.candidates import MockCandidateProvider
from app.tools.capabilities import (
    AvailabilityTool,
    BookingTool,
    DelayPredictionTool,
    FareEstimationTool,
    MockRouteSearchTool,
    RouteDetailsTool,
)
from app.tools.executor import ToolExecutor
from app.tools.intelligence import MockRouteIntelligence


class DuplicateToolError(ValueError):
    """Raised when a tool name is registered twice (A4 brief §9: reject duplicates clearly)."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Tool '{name}' is already registered.")


class ToolRegistry:
    """A name-keyed collection of :class:`Tool` capabilities plus the execution entry point."""

    def __init__(
        self,
        tools: Optional[list[Tool]] = None,
        executor: Optional[ToolExecutor] = None,
    ) -> None:
        self._tools: dict[str, Tool] = {}
        self._executor = executor or ToolExecutor()
        for tool in tools or []:
            self.register(tool)

    # ------------------------------------------------------------------ #
    # Registration / lookup
    # ------------------------------------------------------------------ #
    def register(self, tool: Tool) -> None:
        """Add a tool; reject a duplicate name clearly (A4 brief §9)."""
        if tool.name in self._tools:
            raise DuplicateToolError(tool.name)
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        """Return the tool registered under ``name``, or ``None``."""
        return self._tools.get(name)

    def names(self) -> list[str]:
        """All registered tool names (stable order: registration order)."""
        return list(self._tools.keys())

    def list_available(self) -> list[str]:
        """Names of tools that can currently return data (``availability == available``)."""
        return [
            tool.name
            for tool in self._tools.values()
            if tool.availability is ToolAvailability.available
        ]

    def status(self, name: str) -> Optional[ToolAvailability]:
        """The availability state of a tool, or ``None`` if it is unknown (A4 brief §9)."""
        tool = self._tools.get(name)
        return tool.availability if tool else None

    def describe(self) -> list[dict[str, Any]]:
        """Metadata for every tool — used by the agent's PLANNING step and the UI (A4 brief §15)."""
        return [tool.describe() for tool in self._tools.values()]

    # ------------------------------------------------------------------ #
    # Execution
    # ------------------------------------------------------------------ #
    def execute(self, name: str, payload: Optional[dict[str, Any]] = None) -> ToolResult:
        """Resolve → validate → execute a tool by name, always returning a structured result.

        An unknown name is a structured ``UNKNOWN_TOOL`` failure, never an exception (A4 brief §12).
        """
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult.failure(
                name,
                ToolErrorCode.UNKNOWN_TOOL,
                f"Unknown tool '{name}'.",
                status=ToolStatus.unavailable,
            )
        return self._executor.execute(tool, payload)

    def call(self, name: str, **kwargs: Any) -> ToolResult:
        """A3-compatible keyword form of :meth:`execute` (preserved for existing callers)."""
        return self.execute(name, kwargs)


def _default_tools() -> list[Tool]:
    """The A7 tool set: four deterministic mock intelligence tools + the two honest C stubs.

    **One shared** :class:`~app.tools.intelligence.MockRouteIntelligence` instance backs all four
    data tools, so ``search_routes`` and the fare/delay/details tools can never disagree about the
    same route id (A7 brief §15). This function is the only place tool implementations are wired:
    Workstream B/C later swap the providers here — behind the same names, ``args_model`` and
    ``ToolResult`` contract — with no change to the agent (A7 brief §26/§27).
    """
    intelligence = MockRouteIntelligence()
    return [
        MockRouteSearchTool(MockCandidateProvider(intelligence)),
        FareEstimationTool(intelligence),
        DelayPredictionTool(intelligence),
        RouteDetailsTool(intelligence),
        AvailabilityTool(),
        BookingTool(),
    ]


def build_tools(settings: Settings) -> ToolRegistry:  # noqa: ARG001 — see module docstring
    """Build the registry. ``settings`` is accepted for factory parity; A4 ignores it."""
    return ToolRegistry(_default_tools())


@lru_cache
def get_tools() -> ToolRegistry:
    """Cached accessor for application code / the FastAPI dependency graph."""
    return build_tools(get_settings())
