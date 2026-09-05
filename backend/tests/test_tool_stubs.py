"""A4 mock-tool + future-stub tests (brief §10, §21, §18 "Mock" / "Future stubs").

Prove the two honesty halves of the A4 tool set:

* ``search_routes`` is the one capability that returns data — deterministic, and explicitly
  labelled ``data_source=mock`` (never presented as live);
* an unknown corridor is an honest empty success, not an error and not an invented route;
* every remaining Workstream-C capability (availability, booking) returns an honest
  ``NOT_IMPLEMENTED`` structured result and fabricates **no** data.

**A7 note (brief §11):** ``get_fare_estimate``, ``get_delay_prediction`` and ``get_route_details``
were stubs in A4 and are now AVAILABLE deterministic *mock* tools, so they moved out of ``_STUBS``
below. Their behaviour is covered by ``tests/test_mock_intelligence_a7.py`` (scenarios 6–15);
this module keeps proving the honesty of the two capabilities Workstream C still owns.
"""

from __future__ import annotations

from app.config import get_settings
from app.schemas.route import DataSource
from app.tools.base import ToolErrorCode, ToolStatus
from app.tools.registry import build_tools

# The two honest stubs left after A7 (real implementations belong to Workstream C — brief §11).
_STUBS = (
    "check_availability",
    "prepare_booking",
)

_KNOWN = {"origin": "Colombo Fort", "destination": "Ella"}


def _registry():
    return build_tools(get_settings())


# --- Mock tool (brief §10/§18 "Mock") ------------------------------------------------- #
# 1. search_routes returns deterministic mock data (same input ⇒ same output).
def test_search_routes_returns_deterministic_mock_data() -> None:
    registry = _registry()
    a = registry.execute("search_routes", dict(_KNOWN))
    b = registry.execute("search_routes", dict(_KNOWN))
    assert a.success is True and b.success is True
    assert [c.id for c in a.data] == ["R1", "R2", "R3"]
    assert [c.total_fare_lkr for c in a.data] == [c.total_fare_lkr for c in b.data]


# 2. The result explicitly identifies its mock source (data_source + status + per-candidate).
def test_search_result_is_explicitly_mock() -> None:
    result = _registry().execute("search_routes", dict(_KNOWN))
    assert result.data_source is DataSource.mock
    assert result.status is ToolStatus.mock_data
    assert result.tool_name == "search_routes"
    assert result.meta["corridor_known"] is True
    assert all(c.data_source is DataSource.mock for c in result.data)


# 3. An unknown corridor is an honest empty success — not an error, not an invented route.
def test_unknown_corridor_returns_empty_success() -> None:
    result = _registry().execute(
        "search_routes", {"origin": "Nowhere", "destination": "Elsewhere"}
    )
    assert result.success is True  # a known-empty answer, not a failure
    assert result.data == []
    assert result.meta["corridor_known"] is False
    assert result.data_source is DataSource.mock


# --- Future stubs (brief §10/§21, §18 "Future stubs") --------------------------------- #
# 4. Every remaining Workstream-C capability returns an honest NOT_IMPLEMENTED result.
def test_future_stubs_return_not_implemented() -> None:
    registry = _registry()
    for name in _STUBS:
        result = registry.execute(name)
        assert result.success is False
        assert result.status is ToolStatus.not_implemented
        assert result.tool_name == name
        assert result.error is not None
        assert result.error.code == ToolErrorCode.NOT_IMPLEMENTED.value
        assert result.data is None
        assert result.data_source is DataSource.mock
        assert "not implemented" in result.message.lower()


# 5. The availability/booking stubs never fabricate numbers, even given a plausible payload.
def test_stubs_never_fabricate_data() -> None:
    registry = _registry()
    for name in _STUBS:
        result = registry.execute(name, {"route_id": "R1"})
        assert result.data is None  # no invented seat availability / booking reference
        assert result.success is False
        assert result.status is ToolStatus.not_implemented
        assert result.data_source is DataSource.mock
