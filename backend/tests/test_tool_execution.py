"""A4 tool-execution tests (brief §11–§13, §21, §18 "Execution").

Exercise :class:`~app.tools.executor.ToolExecutor` — the single safe layer between the registry and
a tool — with purpose-built test doubles. Every path must return a structured :class:`ToolResult`
and never raise to the caller:

* an ``available`` tool executes and returns its data;
* invalid arguments are rejected before execution (``INVALID_INPUT``);
* a raising tool becomes ``EXECUTION_ERROR``; a non-``ToolResult`` return becomes
  ``MALFORMED_RESULT``; a slow tool becomes ``TIMEOUT`` (bounded execution);
* a ``disabled`` tool is gated to ``TOOL_UNAVAILABLE`` **without running**;
* a ``not_implemented`` stub is gated to ``NOT_IMPLEMENTED`` even if its ``execute`` would
  fabricate success — the core data-honesty guarantee (brief §21).
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from app.tools.base import (
    Tool,
    ToolAvailability,
    ToolErrorCode,
    ToolResult,
    ToolStatus,
)
from app.tools.capabilities import MockRouteSearchTool
from app.tools.executor import ToolExecutor


@pytest.fixture()
def executor() -> Any:
    ex = ToolExecutor()
    yield ex
    ex.shutdown()


# --- Test doubles: each isolates one executor guard ---------------------------------- #
class _RaisingTool(Tool):
    name = "raising"
    availability = ToolAvailability.available

    def execute(self, **kwargs: Any) -> ToolResult:
        raise RuntimeError("boom")


class _MalformedTool(Tool):
    name = "malformed"
    availability = ToolAvailability.available

    def execute(self, **kwargs: Any) -> Any:  # deliberately returns a non-ToolResult
        return {"not": "a ToolResult"}


class _SlowTool(Tool):
    name = "slow"
    availability = ToolAvailability.available
    timeout_s = 0.05  # tiny budget so the test is fast and deterministic

    def execute(self, **kwargs: Any) -> ToolResult:
        time.sleep(0.4)
        return ToolResult(tool_name=self.name)


class _DisabledTool(Tool):
    name = "disabled"
    availability = ToolAvailability.disabled

    def __init__(self) -> None:
        self.ran = False

    def execute(self, **kwargs: Any) -> ToolResult:
        self.ran = True
        return ToolResult(tool_name=self.name)


class _PoisonedStub(Tool):
    """``not_implemented`` but its execute() WOULD fabricate success — the gate must stop it."""

    name = "poisoned"
    availability = ToolAvailability.not_implemented
    owner = "B"

    def __init__(self) -> None:
        self.ran = False

    def execute(self, **kwargs: Any) -> ToolResult:
        self.ran = True
        return ToolResult(
            status=ToolStatus.ok, data={"fabricated": True}, tool_name=self.name
        )


# 1. An available tool executes and returns its (mock) data through the executor.
def test_available_tool_executes(executor: ToolExecutor) -> None:
    result = executor.execute(
        MockRouteSearchTool(), {"origin": "Colombo Fort", "destination": "Ella"}
    )
    assert result.success is True
    assert result.status is ToolStatus.mock_data
    assert [c.id for c in result.data] == ["R1", "R2", "R3"]
    assert result.tool_name == "search_routes"


# 2. Invalid arguments are rejected before execution (never reach the implementation).
def test_invalid_arguments_return_structured_error(executor: ToolExecutor) -> None:
    result = executor.execute(MockRouteSearchTool(), {"origin": "Colombo Fort"})
    assert result.success is False
    assert result.status is ToolStatus.error
    assert result.error is not None
    assert result.error.code == ToolErrorCode.INVALID_INPUT.value
    assert result.data is None
    assert result.error.details  # carries a non-sensitive validation summary


# 3. A tool that raises becomes a structured EXECUTION_ERROR (the agent never crashes).
def test_tool_exception_returns_structured_error(executor: ToolExecutor) -> None:
    result = executor.execute(_RaisingTool(), {})
    assert result.success is False
    assert result.error is not None
    assert result.error.code == ToolErrorCode.EXECUTION_ERROR.value
    assert "boom" in result.message


# 4. A tool that returns a non-ToolResult is caught as MALFORMED_RESULT.
def test_malformed_result_handled_safely(executor: ToolExecutor) -> None:
    result = executor.execute(_MalformedTool(), {})
    assert result.success is False
    assert result.error is not None
    assert result.error.code == ToolErrorCode.MALFORMED_RESULT.value


# 5. A slow tool is bounded by its timeout — the executor returns, it does not hang.
def test_slow_tool_times_out(executor: ToolExecutor) -> None:
    result = executor.execute(_SlowTool(), {})
    assert result.success is False
    assert result.error is not None
    assert result.error.code == ToolErrorCode.TIMEOUT.value


# 6. A disabled tool is gated to TOOL_UNAVAILABLE and its execute() never runs.
def test_disabled_tool_is_gated_and_never_runs(executor: ToolExecutor) -> None:
    tool = _DisabledTool()
    result = executor.execute(tool, {})
    assert result.success is False
    assert result.status is ToolStatus.unavailable
    assert result.error is not None
    assert result.error.code == ToolErrorCode.TOOL_UNAVAILABLE.value
    assert tool.ran is False  # the availability gate short-circuits before execution


# 7. Data honesty (brief §21): a not_implemented stub can NEVER fabricate a success.
def test_not_implemented_gate_prevents_fabricated_success(
    executor: ToolExecutor,
) -> None:
    tool = _PoisonedStub()
    result = executor.execute(tool, {})
    assert result.success is False
    assert result.status is ToolStatus.not_implemented
    assert result.error is not None
    assert result.error.code == ToolErrorCode.NOT_IMPLEMENTED.value
    assert result.data is None  # the fabricated payload never escapes
    assert tool.ran is False  # execute() was never called
