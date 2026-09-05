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
from app.tools.capabilities import (
    AvailabilityTool,
    BookingTool,
    DelayPredictionTool,
    FareEstimationTool,
    MockRouteSearchTool,
    RouteDetailsTool,
)
from app.tools.executor import ToolExecutor


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


def _default_tools(
    enable_workstream_b: bool = True, enable_workstream_c: bool = False
) -> list[Tool]:
    """The tool set: Workstream B and C capabilities enabled when requested."""
    return [
        MockRouteSearchTool(),
        FareEstimationTool(as_stub=not enable_workstream_b),
        DelayPredictionTool(as_stub=not enable_workstream_b),
        RouteDetailsTool(as_stub=not enable_workstream_b),
        AvailabilityTool(as_stub=not enable_workstream_c),
        BookingTool(),
    ]


def build_tools(settings: Optional[Settings] = None) -> ToolRegistry:
    """Build the registry. Reads capability flags from settings when provided."""
    s = settings or get_settings()
    enable_b = getattr(s, "enable_transit_intelligence", False)
    enable_c = getattr(s, "enable_autonomous_execution", False)
    return ToolRegistry(
        _default_tools(enable_workstream_b=enable_b, enable_workstream_c=enable_c)
    )


@lru_cache
def get_tools() -> ToolRegistry:
    """Cached accessor for application code / the FastAPI dependency graph."""
    return build_tools(get_settings())
