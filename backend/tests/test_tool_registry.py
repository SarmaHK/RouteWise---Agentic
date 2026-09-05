"""A4 tool-registry tests (brief §9, §12, §18 "Registry").

Prove the registry is a reliable, non-abstract name-keyed entry point:

* register → get / names / list_available / status behave predictably;
* duplicate registration is rejected clearly (``DuplicateToolError``), both via ``register`` and
  via the constructor;
* an unknown tool resolves to ``None`` and executes to a structured ``UNKNOWN_TOOL`` failure
  (never an exception);
* the A3 keyword ``call`` form stays equivalent to the A4 ``execute`` form (back-compat).
"""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.tools.base import ToolAvailability, ToolErrorCode, ToolStatus
from app.tools.capabilities import MockRouteSearchTool
from app.tools.registry import DuplicateToolError, ToolRegistry, build_tools

# The six documented capabilities, in registration order (API_CONTRACTS §6; capabilities.py).
_EXPECTED_NAMES = [
    "search_routes",
    "get_fare_estimate",
    "get_delay_prediction",
    "get_route_details",
    "check_availability",
    "prepare_booking",
]


def _registry() -> ToolRegistry:
    return build_tools(get_settings())


# 1. A registered tool is retrievable by name; an unknown name resolves to None.
def test_register_and_get() -> None:
    registry = _registry()
    tool = registry.get("search_routes")
    assert tool is not None
    assert tool.name == "search_routes"
    assert registry.get("does_not_exist") is None


# 2. names() lists every registered tool in a stable order.
def test_names_lists_all_tools_in_order() -> None:
    assert _registry().names() == _EXPECTED_NAMES


# 3. list_available() returns only tools that can currently return data.
# A7 (brief §11): the four Workstream-A data tools are AVAILABLE; the two Workstream-C tools stay
# NOT_IMPLEMENTED. This list is derived from ToolRegistry — never duplicated elsewhere (§12).
def test_list_available_is_the_four_mock_data_tools() -> None:
    assert _registry().list_available() == [
        "search_routes",
        "get_fare_estimate",
        "get_delay_prediction",
        "get_route_details",
    ]


# 4. status() reports availability, or None for an unknown tool.
def test_status_reports_availability() -> None:
    registry = _registry()
    assert registry.status("search_routes") is ToolAvailability.available
    # A7: fare/delay/details are implemented as deterministic MOCK tools …
    assert registry.status("get_fare_estimate") is ToolAvailability.available
    assert registry.status("get_route_details") is ToolAvailability.available
    # … while the Workstream-C capabilities are still honestly unimplemented.
    assert registry.status("check_availability") is ToolAvailability.not_implemented
    assert registry.status("prepare_booking") is ToolAvailability.not_implemented
    assert registry.status("does_not_exist") is None


# 5. describe() returns metadata for every tool (used by PLANNING + the UI).
def test_describe_covers_every_tool() -> None:
    described = _registry().describe()
    assert len(described) == len(_EXPECTED_NAMES)
    by_name = {d["name"]: d for d in described}
    assert by_name["search_routes"]["status"] == "AVAILABLE"
    assert by_name["check_availability"]["status"] == "NOT_IMPLEMENTED"


# 6. Duplicate registration via register() is rejected clearly.
def test_duplicate_registration_rejected_via_register() -> None:
    registry = ToolRegistry()
    registry.register(MockRouteSearchTool())
    with pytest.raises(DuplicateToolError) as excinfo:
        registry.register(MockRouteSearchTool())
    assert excinfo.value.name == "search_routes"
    assert isinstance(excinfo.value, ValueError)  # a clear, catchable setup-time error


# 7. Duplicate registration via the constructor is rejected too.
def test_duplicate_registration_rejected_via_constructor() -> None:
    with pytest.raises(DuplicateToolError):
        ToolRegistry([MockRouteSearchTool(), MockRouteSearchTool()])


# 8. Executing an unknown tool returns a structured UNKNOWN_TOOL failure (never raises).
def test_execute_unknown_tool_is_structured_failure() -> None:
    result = _registry().execute("does_not_exist", {"origin": "A", "destination": "B"})
    assert result.success is False
    assert result.status is ToolStatus.unavailable
    assert result.tool_name == "does_not_exist"
    assert result.error is not None
    assert result.error.code == ToolErrorCode.UNKNOWN_TOOL.value


# 9. The A3 keyword ``call`` form is equivalent to the A4 ``execute`` form (back-compat).
def test_call_and_execute_are_equivalent() -> None:
    registry = _registry()
    via_call = registry.call("search_routes", origin="Colombo Fort", destination="Ella")
    via_execute = registry.execute(
        "search_routes", {"origin": "Colombo Fort", "destination": "Ella"}
    )
    assert [c.id for c in via_call.data] == [c.id for c in via_execute.data]
    assert via_call.status is via_execute.status is ToolStatus.mock_data
