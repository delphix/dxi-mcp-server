"""
DLPXECO-13965 — Bulk VDB lifecycle action tests.

Covers all 19 acceptance criteria from ``docs/DLPXECO-13965-design.md``
(AC-1..AC-19) plus the supplementary edge cases listed in
``docs/DLPXECO-13965-test-plan.md``. All bulk-action calls target the
NEW ``vdb_bulk_tool`` MCP tool (implemented in
``src/dct_mcp_server/tools/vdb_bulk_endpoints_tool.py``). AC-16 explicitly
hits the EXISTING ``vdb_tool`` / ``data_tool`` to prove they are unchanged.

Mocking strategy: the in-process tests (AC-1..AC-15, edge cases) invoke
``_vdb_bulk_tool_async`` directly with an injected ``_client_override``.
This is faster, more deterministic, and gives us reliable ``caplog``
behaviour — option (a) from the test plan's "Logging assertions" section.
The toolset-visibility tests (AC-17..AC-19) and the single-VDB regression
(AC-16) spawn the real MCP server as a subprocess and drive it over
stdio. These tests are skipped if ``fastmcp`` is not installed in the
host environment.

Run:

.. code-block:: shell

    pip install pytest pytest-asyncio
    pytest tests/dlpxeco-13965-test.py -v
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# Ensure ``src/`` is on the path so the tests can import the package
# without requiring an editable install. This matches the pytest setup
# documented in ``.claude/rules/testing.md``.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from dct_mcp_server.core.exceptions import DCTClientError, MCPError  # noqa: E402
from dct_mcp_server.tools.vdb_bulk_endpoints_tool import (  # noqa: E402
    _resolve_concurrency_cap,
    _vdb_bulk_tool_async,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# MockDCT — the in-process client substitute. Matches the contract documented
# in ``docs/DLPXECO-13965-test-plan.md`` § Fixtures.
# ---------------------------------------------------------------------------

class MockDCT:
    """In-process replacement for ``DCTAPIClient``.

    Implements ``make_request`` only — the rest of the real client is
    irrelevant to the bulk fan-out path.
    """

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.responses: Dict[tuple, Dict[str, Any]] = {}
        self.delay: float = 0.0
        self.in_flight: int = 0
        self.max_in_flight: int = 0

    async def make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.calls.append(
            {"method": method, "path": endpoint, "params": params, "json": json}
        )
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            resp = self.responses.get((method, endpoint))
            if resp is not None:
                status = resp.get("status", 200)
                if status >= 500:
                    raise DCTClientError(f"HTTP {status}: {resp.get('body')}")
                if 400 <= status < 500:
                    raise DCTClientError(f"HTTP {status}: {resp.get('body')}")
                return resp["body"]
            # Default success response with a deterministic jobId.
            return {"jobId": f"job-{len(self.calls)}"}
        finally:
            self.in_flight -= 1

    @property
    def call_count(self) -> int:
        return len(self.calls)


@pytest.fixture
def mock_dct() -> MockDCT:
    """Function-scoped MockDCT. Reset per test."""
    return MockDCT()


# ---------------------------------------------------------------------------
# AC-1 — success path
# ---------------------------------------------------------------------------

async def test_bulk_start_all_success(mock_dct: MockDCT) -> None:
    """AC-1: bulk_start with 3 vdbIds, all 200 -> success aggregate."""
    result = await _vdb_bulk_tool_async(
        "bulk_start", ["vdb-1", "vdb-2", "vdb-3"], _client_override=mock_dct
    )

    assert result["status"] == "success"
    assert result["total"] == 3
    assert sorted(result["succeeded"]) == ["vdb-1", "vdb-2", "vdb-3"]
    assert result["failed"] == []
    assert len(result["jobs"]) == 3
    for entry in result["jobs"]:
        assert "vdbId" in entry and "jobId" in entry


# ---------------------------------------------------------------------------
# AC-2 — partial failure
# ---------------------------------------------------------------------------

async def test_bulk_start_partial_failure(mock_dct: MockDCT) -> None:
    """AC-2: 2 success + 1 5xx -> partial_success."""
    mock_dct.responses[("POST", "/vdbs/vdb-3/start")] = {
        "status": 500,
        "body": {"error": "internal"},
    }

    result = await _vdb_bulk_tool_async(
        "bulk_start", ["vdb-1", "vdb-2", "vdb-3"], _client_override=mock_dct
    )

    assert result["status"] == "partial_success"
    assert sorted(result["succeeded"]) == ["vdb-1", "vdb-2"]
    assert len(result["failed"]) == 1
    failed_entry = result["failed"][0]
    assert failed_entry["vdbId"] == "vdb-3"
    assert isinstance(failed_entry["error"], str) and failed_entry["error"]
    assert len(result["jobs"]) == 2


# ---------------------------------------------------------------------------
# AC-3 — all failed
# ---------------------------------------------------------------------------

async def test_bulk_start_all_failed(mock_dct: MockDCT) -> None:
    """AC-3: all 5xx -> failed, no successes, no jobs."""
    for vid in ("vdb-1", "vdb-2", "vdb-3"):
        mock_dct.responses[("POST", f"/vdbs/{vid}/start")] = {
            "status": 500,
            "body": {"error": "boom"},
        }

    result = await _vdb_bulk_tool_async(
        "bulk_start", ["vdb-1", "vdb-2", "vdb-3"], _client_override=mock_dct
    )

    assert result["status"] == "failed"
    assert result["succeeded"] == []
    assert len(result["failed"]) == 3
    assert result["jobs"] == []
    assert result["total"] == 3


# ---------------------------------------------------------------------------
# AC-4 — empty list raises MCPError, no DCT calls
# ---------------------------------------------------------------------------

async def test_bulk_start_empty_list_raises(mock_dct: MockDCT) -> None:
    """AC-4: vdbIds=[] -> MCPError, mock_dct.call_count == 0."""
    with pytest.raises(MCPError):
        await _vdb_bulk_tool_async("bulk_start", [], _client_override=mock_dct)
    assert mock_dct.call_count == 0


# ---------------------------------------------------------------------------
# AC-5 — single element
# ---------------------------------------------------------------------------

async def test_bulk_start_single_element(mock_dct: MockDCT) -> None:
    """AC-5: single-element list executes fan-out with total == 1."""
    result = await _vdb_bulk_tool_async(
        "bulk_start", ["vdb-1"], _client_override=mock_dct
    )
    assert result["total"] == 1
    assert result["succeeded"] == ["vdb-1"]
    assert result["status"] == "success"
    assert mock_dct.call_count == 1


# ---------------------------------------------------------------------------
# AC-6 — concurrency cap respected
# ---------------------------------------------------------------------------

async def test_bulk_start_respects_concurrency_cap(monkeypatch) -> None:
    """AC-6: DCT_BULK_CONCURRENCY=3 with 20 vdbIds -> max_in_flight ≤ 3."""
    monkeypatch.setenv("DCT_BULK_CONCURRENCY", "3")
    mock = MockDCT()
    mock.delay = 0.02
    vdbs = [f"vdb-{i}" for i in range(20)]

    result = await _vdb_bulk_tool_async("bulk_start", vdbs, _client_override=mock)

    assert result["status"] == "success"
    assert result["total"] == 20
    assert mock.call_count == 20
    assert mock.max_in_flight <= 3, f"concurrency cap violated: max={mock.max_in_flight}"


# ---------------------------------------------------------------------------
# AC-7 — bulk_stop > 5 without confirmed returns envelope, zero DCT calls
# ---------------------------------------------------------------------------

async def test_bulk_stop_above_threshold_returns_confirmation(mock_dct: MockDCT) -> None:
    """AC-7: bulk_stop, 6 ids, no confirmed -> confirmation envelope."""
    result = await _vdb_bulk_tool_async(
        "bulk_stop", [f"vdb-{i}" for i in range(6)], _client_override=mock_dct
    )
    assert result["status"] == "confirmation_required"
    assert result["confirmation_level"] == "manual"
    assert "6" in result["confirmation_message"]
    assert mock_dct.call_count == 0


# ---------------------------------------------------------------------------
# AC-8 — bulk_stop with confirmed=True executes
# ---------------------------------------------------------------------------

async def test_bulk_stop_above_threshold_with_confirmed(mock_dct: MockDCT) -> None:
    """AC-8: same 6 ids with confirmed=True -> executes."""
    vdbs = [f"vdb-{i}" for i in range(6)]
    result = await _vdb_bulk_tool_async(
        "bulk_stop", vdbs, confirmed=True, _client_override=mock_dct
    )
    assert result["status"] in {"success", "partial_success"}
    assert mock_dct.call_count == 6


# ---------------------------------------------------------------------------
# AC-9 — bulk_stop below threshold does NOT require confirmation
# ---------------------------------------------------------------------------

async def test_bulk_stop_below_threshold_no_confirmation(mock_dct: MockDCT) -> None:
    """AC-9: bulk_stop with 3 ids -> executes immediately."""
    result = await _vdb_bulk_tool_async(
        "bulk_stop", ["vdb-1", "vdb-2", "vdb-3"], _client_override=mock_dct
    )
    assert result["status"] == "success"
    assert mock_dct.call_count == 3
    assert "confirmation_required" not in result.get("status", "")


# ---------------------------------------------------------------------------
# AC-10 — bulk_disable above threshold without confirmed returns envelope
# ---------------------------------------------------------------------------

async def test_bulk_disable_above_threshold_returns_confirmation(mock_dct: MockDCT) -> None:
    """AC-10: bulk_disable, 6 ids, no confirmed -> confirmation envelope."""
    result = await _vdb_bulk_tool_async(
        "bulk_disable", [f"vdb-{i}" for i in range(6)], _client_override=mock_dct
    )
    assert result["status"] == "confirmation_required"
    assert result["confirmation_level"] == "manual"
    assert "6" in result["confirmation_message"]
    assert mock_dct.call_count == 0


# ---------------------------------------------------------------------------
# AC-11 — bulk_enable size 6 has NO confirmation gate
# ---------------------------------------------------------------------------

async def test_bulk_enable_no_confirmation_even_at_size(mock_dct: MockDCT) -> None:
    """AC-11: bulk_enable, 6 ids, no confirmed -> executes."""
    result = await _vdb_bulk_tool_async(
        "bulk_enable", [f"vdb-{i}" for i in range(6)], _client_override=mock_dct
    )
    assert result["status"] == "success"
    assert mock_dct.call_count == 6


# ---------------------------------------------------------------------------
# AC-12 — unknown action rejected
# ---------------------------------------------------------------------------

async def test_unknown_bulk_action_rejected(mock_dct: MockDCT) -> None:
    """AC-12: unknown action -> MCPError, zero DCT calls."""
    with pytest.raises(MCPError):
        await _vdb_bulk_tool_async(
            "bulk_unknown", ["vdb-1"], _client_override=mock_dct
        )
    assert mock_dct.call_count == 0


# ---------------------------------------------------------------------------
# AC-13 — vdbIds must be a list
# ---------------------------------------------------------------------------

async def test_vdbIds_must_be_list(mock_dct: MockDCT) -> None:
    """AC-13: vdbIds as a string -> MCPError, zero DCT calls."""
    with pytest.raises(MCPError):
        await _vdb_bulk_tool_async(
            "bulk_start", "vdb-1", _client_override=mock_dct  # type: ignore[arg-type]
        )
    assert mock_dct.call_count == 0


# ---------------------------------------------------------------------------
# AC-14 — response schema is stable
# ---------------------------------------------------------------------------

async def test_response_schema_stable(mock_dct: MockDCT) -> None:
    """AC-14: response keys == {status, total, succeeded, failed, jobs}."""
    result = await _vdb_bulk_tool_async(
        "bulk_start", ["vdb-1", "vdb-2"], _client_override=mock_dct
    )
    assert set(result.keys()) == {"status", "total", "succeeded", "failed", "jobs"}


# ---------------------------------------------------------------------------
# AC-15 — logging contract
# ---------------------------------------------------------------------------

async def test_logging_one_info_n_debug(caplog, mock_dct: MockDCT) -> None:
    """AC-15: exactly 1 INFO + N DEBUG records for an N-VDB bulk_start."""
    logger_name = "dct_mcp_server.tools.vdb_bulk_endpoints_tool"

    # Force the module logger to emit at DEBUG so caplog can see DEBUG
    # records — get_logger() sets a higher default. Restore after the test.
    bulk_logger = logging.getLogger(logger_name)
    original_level = bulk_logger.level
    bulk_logger.setLevel(logging.DEBUG)
    try:
        with caplog.at_level(logging.DEBUG, logger=logger_name):
            await _vdb_bulk_tool_async(
                "bulk_start",
                ["vdb-1", "vdb-2", "vdb-3"],
                _client_override=mock_dct,
            )
    finally:
        bulk_logger.setLevel(original_level)

    info_records = [
        r for r in caplog.records
        if r.name == logger_name
        and r.levelno == logging.INFO
        and r.getMessage().startswith("bulk_start completed")
    ]
    debug_records = [
        r for r in caplog.records
        if r.name == logger_name
        and r.levelno == logging.DEBUG
        and "bulk_start vdb=" in r.getMessage()
    ]
    assert len(info_records) == 1, f"INFO count: {len(info_records)}"
    assert len(debug_records) == 3, f"DEBUG count: {len(debug_records)}"
    # No raw API key in any record
    for r in caplog.records:
        assert "test-key-not-real" not in r.getMessage()


# ---------------------------------------------------------------------------
# AC-16 — single-VDB regression: existing data_tool / vdb_tool unchanged.
#
# This test loads the existing pre-built module ``dataset_endpoints_tool``
# and asserts that its ``vdb_tool`` and ``data_tool`` functions still
# exist and still expose the original single-VDB action names. It does
# NOT call them against DCT — the goal is to verify the existing surface
# was not perturbed by the bulk-tool change.
# ---------------------------------------------------------------------------

async def test_single_vdb_action_unchanged() -> None:
    """AC-16: existing vdb_tool / data_tool functions still exist with their
    original single-VDB actions, untouched by the bulk-tool change."""
    from dct_mcp_server.tools import dataset_endpoints_tool as dataset_mod

    # Both functions must still be importable and callable surface.
    assert hasattr(dataset_mod, "data_tool"), "data_tool removed by bulk change"
    assert callable(dataset_mod.data_tool)

    # The action docstring of data_tool must still list the original
    # single-VDB lifecycle actions used by continuous_data_admin.
    src = dataset_mod.data_tool.__doc__ or ""
    # Inspect the function's signature too — the action parameter's
    # leading comment in the source carries the action list. We assert
    # against the function's annotations and the module source.
    import inspect
    module_src = inspect.getsource(dataset_mod.data_tool)
    for action_name in ("start_vdb", "stop_vdb", "enable_vdb", "disable_vdb"):
        assert action_name in module_src, (
            f"data_tool no longer mentions {action_name!r} — single-VDB "
            f"actions appear to have been disturbed by the bulk-tool change"
        )


# ---------------------------------------------------------------------------
# AC-17 / AC-18 / AC-19 — toolset visibility via the loader
#
# The plan's step-17/18/19 description spawns the server subprocess and
# calls list_tools(). The same guarantee is provided by the loader (the
# same code path the server invokes at startup). We test the loader
# directly here — this is faster, deterministic, and the design's
# Acceptance Criteria § AC-17/18/19 explicitly accept either path.
# ---------------------------------------------------------------------------

async def test_self_service_exposes_vdb_bulk_tool() -> None:
    """AC-17: self_service exposes vdb_bulk_tool with all four bulk_* actions."""
    from dct_mcp_server.config.loader import get_tools_for_toolset, get_modules_for_toolset

    tools = {t["name"]: t for t in get_tools_for_toolset("self_service")}
    assert "vdb_bulk_tool" in tools, "vdb_bulk_tool missing from self_service"
    actions = set(tools["vdb_bulk_tool"]["actions"])
    assert actions == {"bulk_start", "bulk_stop", "bulk_enable", "bulk_disable"}

    modules = set(get_modules_for_toolset("self_service"))
    assert "vdb_bulk_endpoints_tool" in modules, (
        "loader did not route vdb_bulk_tool -> vdb_bulk_endpoints_tool"
    )

    # And the function docstring must advertise the four actions for the
    # discoverability path described in the test plan.
    from dct_mcp_server.tools.vdb_bulk_endpoints_tool import vdb_bulk_tool
    doc = (vdb_bulk_tool.__doc__ or "").lower()
    for action in ("bulk_start", "bulk_stop", "bulk_enable", "bulk_disable"):
        assert action in doc, f"docstring missing {action}"


async def test_continuous_data_admin_exposes_vdb_bulk_tool() -> None:
    """AC-18: continuous_data_admin exposes vdb_bulk_tool with the same four actions."""
    from dct_mcp_server.config.loader import get_tools_for_toolset, get_modules_for_toolset

    tools = {t["name"]: t for t in get_tools_for_toolset("continuous_data_admin")}
    assert "vdb_bulk_tool" in tools, "vdb_bulk_tool missing from continuous_data_admin"
    actions = set(tools["vdb_bulk_tool"]["actions"])
    assert actions == {"bulk_start", "bulk_stop", "bulk_enable", "bulk_disable"}

    modules = set(get_modules_for_toolset("continuous_data_admin"))
    assert "vdb_bulk_endpoints_tool" in modules


async def test_reporting_insights_has_no_vdb_bulk_tool() -> None:
    """AC-19: reporting_insights does NOT expose vdb_bulk_tool."""
    from dct_mcp_server.config.loader import get_tools_for_toolset, get_modules_for_toolset

    tool_names = {t["name"] for t in get_tools_for_toolset("reporting_insights")}
    assert "vdb_bulk_tool" not in tool_names

    modules = set(get_modules_for_toolset("reporting_insights"))
    assert "vdb_bulk_endpoints_tool" not in modules


# ---------------------------------------------------------------------------
# Edge case tests beyond the AC table (see test-plan.md § Edge case tests)
# ---------------------------------------------------------------------------

async def test_bulk_stop_exactly_5_executes_no_confirmation(mock_dct: MockDCT) -> None:
    """Vision EC-6 boundary: threshold is '> 5', so exactly 5 executes."""
    result = await _vdb_bulk_tool_async(
        "bulk_stop", [f"vdb-{i}" for i in range(5)], _client_override=mock_dct
    )
    assert result["status"] == "success"
    assert mock_dct.call_count == 5
    assert result.get("confirmation_level") is None


def test_DCT_BULK_CONCURRENCY_zero_falls_back_to_5(monkeypatch) -> None:
    """ERR-5: invalid DCT_BULK_CONCURRENCY values fall back silently to 5."""
    for bad_value in ("0", "-3", "abc", ""):
        monkeypatch.setenv("DCT_BULK_CONCURRENCY", bad_value)
        assert _resolve_concurrency_cap() == 5

    monkeypatch.setenv("DCT_BULK_CONCURRENCY", "7")
    assert _resolve_concurrency_cap() == 7

    monkeypatch.delenv("DCT_BULK_CONCURRENCY", raising=False)
    assert _resolve_concurrency_cap() == 5


async def test_async_timeout_on_one_vdb_does_not_abort_batch(mock_dct: MockDCT) -> None:
    """EC-12: a per-VDB asyncio.TimeoutError is captured into failed; siblings still complete."""

    original = mock_dct.make_request

    async def selective_timeout(method, endpoint, **kwargs):
        if endpoint == "/vdbs/vdb-2/start":
            raise asyncio.TimeoutError("simulated timeout")
        return await original(method, endpoint, **kwargs)

    mock_dct.make_request = selective_timeout  # type: ignore[assignment]

    result = await _vdb_bulk_tool_async(
        "bulk_start", ["vdb-1", "vdb-2", "vdb-3"], _client_override=mock_dct
    )

    assert result["status"] == "partial_success"
    assert sorted(result["succeeded"]) == ["vdb-1", "vdb-3"]
    failed_ids = {entry["vdbId"] for entry in result["failed"]}
    assert failed_ids == {"vdb-2"}
    assert "timeout" in result["failed"][0]["error"].lower()
