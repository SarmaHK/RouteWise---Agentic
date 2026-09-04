"""Tool registry + dependency injection (Workstream A, Phase A3).

The registry is the single place the agent looks tools up **by name** (AGENT_SPEC §7). It also
lets the agent *plan*: :meth:`ToolRegistry.describe` exposes each tool's metadata so the
PLANNING step can reason about which capabilities are worth calling without executing them.

The DI shape mirrors ``app/services/ai/factory.py``: an explicit :func:`build_tools` (test
friendly) plus a cached :func:`get_tools` accessor for app code / the FastAPI dependency graph.

In A3 the registry contents are config-independent — every capability is a mock or an honest
stub regardless of settings — so ``settings`` is accepted for signature parity with the other
factories and future use (Workstream B/C may enable real tools from config), but not read yet.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Optional

from app.config import Settings, get_settings
from app.tools.base import Tool, ToolResult, ToolStatus
from app.tools.capabilities import (
    AvailabilityTool,
    BookingTool,
    DelayPredictionTool,
    FareEstimationTool,
    MockRouteSearchTool,
    RouteDetailsTool,
)


class ToolRegistry:
    """A name-keyed collection of :class:`Tool` capabilities."""

    def __init__(self, tools: list[Tool]) -> None:
        self._tools: dict[str, Tool] = {tool.name: tool for tool in tools}

    def get(self, name: str) -> Optional[Tool]:
        """Return the tool registered under ``name``, or ``None``."""
        return self._tools.get(name)

    def names(self) -> list[str]:
        """All registered tool names (stable order: registration order)."""
        return list(self._tools.keys())

    def describe(self) -> list[dict[str, Any]]:
        """Metadata for every tool — used by the agent's PLANNING step."""
        return [tool.describe() for tool in self._tools.values()]

    def call(self, name: str, **kwargs: Any) -> ToolResult:
        """Execute a tool by name, degrading honestly if it is unknown."""
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                status=ToolStatus.unavailable,
                message=f"Unknown tool '{name}'.",
            )
        return tool.execute(**kwargs)


def _default_tools() -> list[Tool]:
    """The A3 tool set: one mock search + honest stubs for the B/C-owned capabilities."""
    return [
        MockRouteSearchTool(),
        FareEstimationTool(),
        DelayPredictionTool(),
        RouteDetailsTool(),
        AvailabilityTool(),
        BookingTool(),
    ]


def build_tools(settings: Settings) -> ToolRegistry:  # noqa: ARG001 — see module docstring
    """Build the registry. ``settings`` is accepted for factory parity; A3 ignores it."""
    return ToolRegistry(_default_tools())


@lru_cache
def get_tools() -> ToolRegistry:
    """Cached accessor for application code / the FastAPI dependency graph."""
    return build_tools(get_settings())
