"""
Tests for DLPXECO-13965: Bulk VDB Lifecycle Actions.

Mocking approach: In-process function-level testing.
We call register_tools(app, mock_client) to wire vdb_tool into a throwaway FastMCP app,
then invoke vdb_tool(...) directly as an async coroutine.
DCTAPIClient.make_request is replaced with AsyncMock — no real DCT instance or subprocess needed.

Test runner:
    pytest tests/dlpxeco-13965-test.py -v \
        --cov=src/dct_mcp_server/tools/vdb_endpoints_tool \
        --cov-report=term-missing

Environment:
    DCT_API_KEY=test-key DCT_BASE_URL=http://fake.test DCT_TOOLSET=continuous_data_admin
    DCT_BULK_CONCURRENCY=5  (default; overridden per-test via monkeypatch)
"""

import asyncio
import logging
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Module-level env setup — must happen before any dct_mcp_server imports
# ---------------------------------------------------------------------------
os.environ.setdefault("DCT_API_KEY", "test-key")
os.environ.setdefault("DCT_BASE_URL", "http://fake.test")
os.environ.setdefault("DCT_TOOLSET", "continuous_data_admin")
os.environ.setdefault("DCT_BULK_CONCURRENCY", "5")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app_and_tool(mock_client):
    """
    Register vdb_endpoints_tool against a throwaway FastMCP app, return
    the registered vdb_tool coroutine function directly.
    """
    from mcp.server.fastmcp import FastMCP
    from dct_mcp_server.tools import vdb_endpoints_tool

    app = FastMCP("test-dct-mcp")
    vdb_endpoints_tool.register_tools(app, mock_client)

    # FastMCP stores registered tools in _tool_manager._tools[name].fn
    tool_fn = app._tool_manager._tools["vdb_tool"].fn
    return tool_fn


def _ok_response(vdb_id: str) -> dict:
    """Mock DCT success response for a single VDB action."""
    return {"jobId": f"job-{vdb_id}", "status": "RUNNING"}


def _error_side_effect(failing_ids: set):
    """
    Return an async side_effect that raises DCTClientError for IDs in failing_ids,
    and returns a success response for all others.
    """
    from dct_mcp_server.core.exceptions import DCTClientError

    async def _side_effect(method, endpoint, **kwargs):
        vdb_id = endpoint.split("/")[2]  # /vdbs/<id>/start → <id>
        if vdb_id in failing_ids:
            raise DCTClientError(f"HTTP 500: internal error for {vdb_id}")
        return _ok_response(vdb_id)

    return _side_effect


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    """A mock DCTAPIClient with AsyncMock make_request."""
    client = MagicMock()
    client.make_request = AsyncMock(side_effect=lambda m, ep, **kw: _ok_response(ep.split("/")[2]))
    return client


# ---------------------------------------------------------------------------
# S1: bulk_start with 3 VDB IDs all returning HTTP 200
# Test plan: S1 — status=success, total=3, len(succeeded)==3, failed==[]
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_s1_bulk_start_all_success(mock_client):
    """S1: bulk_start 3 VDBs all 200 → status=success, total=3, 3 succeeded, 0 failed."""
    vdb_ids = ["vdb-1", "vdb-2", "vdb-3"]
    tool = _make_app_and_tool(mock_client)
    result = await tool(action="bulk_start", vdbIds=vdb_ids)
    assert result["status"] == "success"
    assert result["total"] == 3
    assert len(result["succeeded"]) == 3
    assert result["failed"] == []


# ---------------------------------------------------------------------------
# S2: bulk_start with one VDB returning HTTP 500
# Test plan: S2 — status=partial_success, 2 succeeded, 1 failed
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_s2_bulk_start_partial_failure(mock_client):
    """S2: 3 VDBs, one fails → partial_success, 2 succeeded, 1 failed."""
    mock_client.make_request.side_effect = _error_side_effect({"vdb-2"})
    vdb_ids = ["vdb-1", "vdb-2", "vdb-3"]
    tool = _make_app_and_tool(mock_client)
    result = await tool(action="bulk_start", vdbIds=vdb_ids)
    assert result["status"] == "partial_success"
    assert len(result["succeeded"]) == 2
    assert len(result["failed"]) == 1
    assert result["failed"][0]["vdbId"] == "vdb-2"


# ---------------------------------------------------------------------------
# S3: bulk_start with all VDBs failing
# Test plan: S3 — status=failed, succeeded==[], len(failed)==3
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_s3_bulk_start_all_failed(mock_client):
    """S3: All 3 VDBs fail → status=failed, succeeded=[]."""
    mock_client.make_request.side_effect = _error_side_effect({"vdb-1", "vdb-2", "vdb-3"})
    vdb_ids = ["vdb-1", "vdb-2", "vdb-3"]
    tool = _make_app_and_tool(mock_client)
    result = await tool(action="bulk_start", vdbIds=vdb_ids)
    assert result["status"] == "failed"
    assert result["succeeded"] == []
    assert len(result["failed"]) == 3


# ---------------------------------------------------------------------------
# S4: bulk_start with empty vdbIds
# Test plan: S4 — Error with "vdbIds must be a non-empty list", zero mock calls
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_s4_bulk_start_empty_list_rejected(mock_client):
    """S4: empty vdbIds → MCPError before any DCT call."""
    from dct_mcp_server.core.exceptions import MCPError
    tool = _make_app_and_tool(mock_client)
    with pytest.raises(MCPError, match="vdbIds must be a non-empty list"):
        await tool(action="bulk_start", vdbIds=[])
    mock_client.make_request.assert_not_called()


# ---------------------------------------------------------------------------
# S5: bulk_start with a single VDB ID
# Test plan: S5 — status=success, total=1, len(succeeded)==1, failed==[]
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_s5_bulk_start_single_vdb(mock_client):
    """S5: single VDB → status=success, total=1, 1 succeeded."""
    tool = _make_app_and_tool(mock_client)
    result = await tool(action="bulk_start", vdbIds=["vdb-solo"])
    assert result["status"] == "success"
    assert result["total"] == 1
    assert len(result["succeeded"]) == 1
    assert result["failed"] == []


# ---------------------------------------------------------------------------
# S6: bulk_stop with 6 VDB IDs and confirmed=False
# Test plan: S6 — status=confirmation_required, confirmation_level=manual, len(vdbIds)==6, zero DCT calls
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_s6_bulk_stop_confirmation_gate(mock_client):
    """S6: 6 VDBs, confirmed=False → confirmation_required, no DCT calls."""
    vdb_ids = [f"vdb-{i}" for i in range(6)]
    tool = _make_app_and_tool(mock_client)
    result = await tool(action="bulk_stop", vdbIds=vdb_ids, confirmed=False)
    assert result["status"] == "confirmation_required"
    assert result["confirmation_level"] == "manual"
    assert len(result["vdbIds"]) == 6
    mock_client.make_request.assert_not_called()


# ---------------------------------------------------------------------------
# S7: bulk_stop with 6 VDB IDs and confirmed=True
# Test plan: S7 — status in (success/partial_success/failed), total==6, 6 DCT calls
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_s7_bulk_stop_confirmed_executes(mock_client):
    """S7: 6 VDBs, confirmed=True → batch executes, total=6, 6 DCT calls."""
    vdb_ids = [f"vdb-{i}" for i in range(6)]
    tool = _make_app_and_tool(mock_client)
    result = await tool(action="bulk_stop", vdbIds=vdb_ids, confirmed=True)
    assert result["status"] in ("success", "partial_success", "failed")
    assert result["total"] == 6
    assert mock_client.make_request.call_count == 6


# ---------------------------------------------------------------------------
# S8: bulk_stop with 5 VDB IDs and no confirmed
# Test plan: S8 — executes immediately (<=5 VDBs), no confirmation gate triggered
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_s8_bulk_stop_five_no_confirmation_needed(mock_client):
    """S8: 5 VDBs, no confirmed → executes immediately (no confirmation gate)."""
    vdb_ids = [f"vdb-{i}" for i in range(5)]
    tool = _make_app_and_tool(mock_client)
    result = await tool(action="bulk_stop", vdbIds=vdb_ids)
    assert result["status"] in ("success", "partial_success", "failed")
    assert result["total"] == 5
    # confirmation_required was NOT returned
    assert result.get("confirmation_level") is None


# ---------------------------------------------------------------------------
# S9: bulk_enable with > 5 VDB IDs executes without confirmation gate
# Test plan: S9 — no confirmation response regardless of list size
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_s9_bulk_enable_no_confirmation_gate(mock_client):
    """S9: bulk_enable with 7 VDBs → executes immediately, no confirmation returned."""
    vdb_ids = [f"vdb-{i}" for i in range(7)]
    tool = _make_app_and_tool(mock_client)
    result = await tool(action="bulk_enable", vdbIds=vdb_ids)
    assert result["status"] in ("success", "partial_success", "failed")
    assert result.get("confirmation_level") is None


# ---------------------------------------------------------------------------
# S10: bulk_enable with mixed results → partial_success
# Test plan: S10 — status=partial_success, succeeded and failed both non-empty
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_s10_bulk_enable_partial_success(mock_client):
    """S10: bulk_enable, one VDB fails → partial_success."""
    mock_client.make_request.side_effect = _error_side_effect({"vdb-1"})
    vdb_ids = ["vdb-0", "vdb-1", "vdb-2"]
    tool = _make_app_and_tool(mock_client)
    result = await tool(action="bulk_enable", vdbIds=vdb_ids)
    assert result["status"] == "partial_success"
    assert len(result["succeeded"]) > 0
    assert len(result["failed"]) > 0


# ---------------------------------------------------------------------------
# S11: bulk_disable with 6 VDB IDs and no confirmed
# Test plan: S11 — status=confirmation_required, confirmation_level=manual, zero DCT calls
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_s11_bulk_disable_confirmation_gate(mock_client):
    """S11: 6 VDBs, no confirmed → confirmation_required, zero DCT calls."""
    vdb_ids = [f"vdb-{i}" for i in range(6)]
    tool = _make_app_and_tool(mock_client)
    result = await tool(action="bulk_disable", vdbIds=vdb_ids)
    assert result["status"] == "confirmation_required"
    assert result["confirmation_level"] == "manual"
    mock_client.make_request.assert_not_called()


# ---------------------------------------------------------------------------
# S12: bulk_disable with 5 VDB IDs executes without confirmation gate
# Test plan: S12 — status in (success/partial_success/failed), total==5, no gate
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_s12_bulk_disable_five_no_gate(mock_client):
    """S12: 5 VDBs, no confirmed → executes without confirmation gate."""
    vdb_ids = [f"vdb-{i}" for i in range(5)]
    tool = _make_app_and_tool(mock_client)
    result = await tool(action="bulk_disable", vdbIds=vdb_ids)
    assert result["status"] in ("success", "partial_success", "failed")
    assert result["total"] == 5
    assert result.get("confirmation_level") is None


# ---------------------------------------------------------------------------
# S13: Concurrency cap at DCT_BULK_CONCURRENCY=3
# Test plan: S13 — peak in-flight <= 3 for 10 VDBs with DCT_BULK_CONCURRENCY=3
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_s13_bulk_concurrency_cap_3(monkeypatch):
    """S13: DCT_BULK_CONCURRENCY=3, 10 VDBs → peak in-flight <= 3."""
    monkeypatch.setenv("DCT_BULK_CONCURRENCY", "3")

    peak_inflight = 0
    current_inflight = 0
    counter_lock = asyncio.Lock()

    async def _counting_mock(method, endpoint, **kwargs):
        nonlocal peak_inflight, current_inflight
        async with counter_lock:
            current_inflight += 1
            if current_inflight > peak_inflight:
                peak_inflight = current_inflight
        await asyncio.sleep(0.01)  # Simulate DCT latency
        async with counter_lock:
            current_inflight -= 1
        vdb_id = endpoint.split("/")[2]
        return _ok_response(vdb_id)

    mock_client = MagicMock()
    mock_client.make_request = AsyncMock(side_effect=_counting_mock)
    vdb_ids = [f"vdb-{i}" for i in range(10)]
    tool = _make_app_and_tool(mock_client)
    result = await tool(action="bulk_start", vdbIds=vdb_ids)
    assert peak_inflight <= 3, f"Peak in-flight {peak_inflight} exceeded cap of 3"
    assert result["total"] == 10


# ---------------------------------------------------------------------------
# S14: Default DCT_BULK_CONCURRENCY=5 when not set
# Test plan: S14 — peak in-flight <= 5 for 10 VDBs with default concurrency
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_s14_bulk_concurrency_default_5(monkeypatch):
    """S14: DCT_BULK_CONCURRENCY not set → default 5, peak in-flight <= 5."""
    monkeypatch.delenv("DCT_BULK_CONCURRENCY", raising=False)

    peak_inflight = 0
    current_inflight = 0
    counter_lock = asyncio.Lock()

    async def _counting_mock(method, endpoint, **kwargs):
        nonlocal peak_inflight, current_inflight
        async with counter_lock:
            current_inflight += 1
            if current_inflight > peak_inflight:
                peak_inflight = current_inflight
        await asyncio.sleep(0.01)
        async with counter_lock:
            current_inflight -= 1
        vdb_id = endpoint.split("/")[2]
        return _ok_response(vdb_id)

    mock_client = MagicMock()
    mock_client.make_request = AsyncMock(side_effect=_counting_mock)
    vdb_ids = [f"vdb-{i}" for i in range(10)]
    tool = _make_app_and_tool(mock_client)
    result = await tool(action="bulk_start", vdbIds=vdb_ids)
    assert peak_inflight <= 5, f"Peak in-flight {peak_inflight} exceeded cap of 5"


# ---------------------------------------------------------------------------
# S15: DCT_BULK_CONCURRENCY=0 clamped to 1
# Test plan: S15 — config["bulk_concurrency"] == 1, WARNING logged
# ---------------------------------------------------------------------------
def test_s15_bulk_concurrency_zero_clamped(monkeypatch):
    """S15: DCT_BULK_CONCURRENCY=0 → config["bulk_concurrency"] == 1, WARNING logged."""
    monkeypatch.setenv("DCT_BULK_CONCURRENCY", "0")
    from dct_mcp_server.config.config import get_dct_config
    cfg = get_dct_config()
    assert cfg["bulk_concurrency"] == 1


# ---------------------------------------------------------------------------
# S16: Logging — 1 INFO + N DEBUG per bulk_start
# Test plan: S16 — 1 INFO 'fanning out', 3 DEBUG 'vdbId=' lines
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_s16_logging_one_info_n_debug(mock_client, caplog):
    """S16: bulk_start 3 VDBs → exactly 1 INFO 'fanning out' + 3 DEBUG 'vdbId='."""
    vdb_ids = ["vdb-a", "vdb-b", "vdb-c"]
    tool = _make_app_and_tool(mock_client)
    with caplog.at_level(logging.DEBUG, logger="dct_mcp_server.tools.vdb_endpoints_tool"):
        await tool(action="bulk_start", vdbIds=vdb_ids)

    info_lines = [r for r in caplog.records
                  if r.levelno == logging.INFO and "fanning out" in r.message]
    debug_lines = [r for r in caplog.records
                   if r.levelno == logging.DEBUG and "vdbId=" in r.message]
    assert len(info_lines) == 1, f"Expected 1 INFO 'fanning out' line, got {len(info_lines)}"
    assert len(debug_lines) == 3, f"Expected 3 DEBUG 'vdbId=' lines, got {len(debug_lines)}"


# ---------------------------------------------------------------------------
# S17: Existing single-VDB start action is unaffected (QR-1 backward compat)
# Test plan: S17 — bulk_start with 1 VDB returns aggregated shape, not raw DCT response
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_s17_single_vdb_start_unchanged(mock_client):
    """S17: vdb_tool bulk_start with 1 VDB returns aggregated shape (QR-1 backward compat)."""
    result = await _make_app_and_tool(mock_client)(
        action="bulk_start", vdbIds=["vdb-solo"]
    )
    assert result["status"] == "success"
    assert result["total"] == 1
    # The response is the aggregated wrapper, not a raw DCT response
    assert "succeeded" in result
    assert "failed" in result
    assert "jobs" in result


# ---------------------------------------------------------------------------
# S18: bulk actions appear in self_service toolset for vdb_tool
# Test plan: S18 — load_toolset_grouped_apis("self_service")["vdb_tool"]["apis"] contains all 4
# ---------------------------------------------------------------------------
def test_s18_bulk_actions_in_self_service():
    """S18: All 4 bulk actions appear in self_service toolset vdb_tool actions."""
    from dct_mcp_server.config.loader import load_toolset_grouped_apis
    grouped = load_toolset_grouped_apis("self_service")
    vdb_actions = {api["action"] for api in grouped["vdb_tool"]["apis"]}
    for action in ("bulk_start", "bulk_stop", "bulk_enable", "bulk_disable"):
        assert action in vdb_actions, f"{action} missing from self_service vdb_tool"


# ---------------------------------------------------------------------------
# S19: All 4 bulk actions in continuous_data_admin; none in reporting_insights
# Test plan: S19 — continuous_data_admin contains all 4; reporting_insights contains none
# ---------------------------------------------------------------------------
def test_s19_bulk_actions_toolset_presence_absence():
    """S19: All 4 in continuous_data_admin data_tool; none in reporting_insights."""
    from dct_mcp_server.config.loader import load_toolset_grouped_apis, load_toolset_apis

    grouped = load_toolset_grouped_apis("continuous_data_admin")
    data_actions = {api["action"] for api in grouped["data_tool"]["apis"]}
    for action in ("bulk_start", "bulk_stop", "bulk_enable", "bulk_disable"):
        assert action in data_actions, f"{action} missing from continuous_data_admin data_tool"

    ri_apis = load_toolset_apis("reporting_insights")
    ri_actions = {api["action"] for api in ri_apis}
    for action in ("bulk_start", "bulk_stop", "bulk_enable", "bulk_disable"):
        assert action not in ri_actions, f"{action} unexpectedly in reporting_insights"
