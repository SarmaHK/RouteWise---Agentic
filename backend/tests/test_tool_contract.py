"""A4 tool-contract tests (brief §5–§7, §15, §18 "Tool contract").

Prove the clean capability contract in :mod:`app.tools.base` and the ``search_routes`` input model:

* valid tool input is accepted; invalid input is rejected *before* execution (Pydantic);
* every result conforms to the structured shape (``success`` / ``tool_name`` / ``data_source`` /
  ``data`` / ``error``) — never an arbitrary dict;
* ``success`` is derived from ``error`` so it can never contradict the failure detail;
* tool metadata (``describe``) exposes name/description/status/data_source without internals.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.route import DataSource
from app.tools.base import (
    ToolError,
    ToolErrorCode,
    ToolResult,
    ToolStatus,
)
from app.tools.capabilities import MockRouteSearchTool, SearchRoutesArgs


# --- Input validation (brief §6): valid accepted, invalid rejected ------------------- #
# 1. A well-formed payload validates and round-trips its declared fields.
def test_args_model_accepts_valid_input() -> None:
    args = SearchRoutesArgs.model_validate(
        {"origin": "Colombo Fort", "destination": "Ella"}
    )
    assert args.origin == "Colombo Fort"
    assert args.destination == "Ella"
    assert args.departure_time is None  # optional, forward-compatible
    assert args.preferences == {}


# 2. A missing required field is rejected (malformed input never reaches the tool).
def test_args_model_rejects_missing_destination() -> None:
    with pytest.raises(ValidationError):
        SearchRoutesArgs.model_validate({"origin": "Colombo Fort"})


# 3. An empty required string is rejected (min_length=1).
def test_args_model_rejects_empty_origin() -> None:
    with pytest.raises(ValidationError):
        SearchRoutesArgs.model_validate({"origin": "", "destination": "Ella"})


# 4. Undeclared keys are dropped (extra="ignore") so they cannot leak into execute().
def test_args_model_ignores_extra_keys() -> None:
    args = SearchRoutesArgs.model_validate(
        {"origin": "A", "destination": "B", "unexpected": "drop-me"}
    )
    assert "unexpected" not in args.model_dump()


# --- Structured result contract (brief §7): shape + derived success ------------------- #
# 5. A success result serializes to exactly the documented structured shape.
def test_tool_result_to_dict_matches_contract() -> None:
    result = ToolResult(
        status=ToolStatus.mock_data,
        data_source=DataSource.mock,
        data={"candidates": []},
        message="ok",
        tool_name="search_routes",
    )
    payload = result.to_dict()
    assert set(payload) == {
        "success",
        "tool_name",
        "status",
        "data_source",
        "data",
        "message",
        "error",
    }
    assert payload["success"] is True
    assert payload["tool_name"] == "search_routes"
    assert payload["status"] == "mock_data"
    assert payload["data_source"] == "mock"
    assert payload["error"] is None


# 6. ``success`` is derived from ``error`` — it can never contradict the failure detail.
def test_success_is_derived_from_error() -> None:
    assert ToolResult().success is True  # no error ⇒ success
    failed = ToolResult(error=ToolError(code="X", message="boom"))
    assert failed.success is False


# 7. ToolResult.failure builds a structured failure (success False + error{code,message}).
def test_tool_result_failure_is_structured() -> None:
    result = ToolResult.failure(
        "get_delay_prediction",
        ToolErrorCode.INVALID_INPUT,
        "bad payload",
        details={"errors": []},
    )
    assert result.success is False
    assert result.status is ToolStatus.error
    assert result.error is not None
    assert result.error.code == "INVALID_INPUT"
    payload = result.to_dict()
    assert payload["success"] is False
    assert payload["error"]["code"] == "INVALID_INPUT"
    assert payload["error"]["message"] == "bad payload"
    assert payload["error"]["details"] == {"errors": []}


# --- Tool metadata (brief §15): enough to reason about a capability, no internals ----- #
# 8. describe() exposes the documented metadata for the one available mock tool.
def test_available_tool_metadata_is_valid() -> None:
    meta = MockRouteSearchTool().describe()
    assert meta["name"] == "search_routes"
    assert meta["status"] == "AVAILABLE"  # upper-cased availability
    assert meta["availability"] == "available"
    assert meta["data_source"] == "mock"  # provenance kept separate from availability
    assert meta["owner"] == "B"
    assert meta["description"]
    # The args model is wired so the executor can validate input before running.
    assert MockRouteSearchTool.args_model is SearchRoutesArgs
