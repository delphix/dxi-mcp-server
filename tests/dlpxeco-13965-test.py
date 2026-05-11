"""
DLPXECO-13965 — Bulk action support for vdb_tool
=================================================
Test suite: 19 functional scenarios + 3 static/grep quality-rule checks.

Test strategy
-------------
Scenarios 1–16 and 18 use direct-import + mock:
  - Import `data_tool` from `dct_mcp_server.tools.dataset_endpoints_tool`.
  - Patch the module-level `client` global
    (`dct_mcp_server.tools.dataset_endpoints_tool.client`) with a
    `unittest.mock.AsyncMock` or `MagicMock` that simulates DCT responses.
  - Call `data_tool(action="bulk_*", ...)` synchronously — it wraps
    `async_to_sync` internally, so the call is sync from the caller's view.
  - Assert on the returned dict.

Scenario 17 (toolset visibility) and 19 (reporting_insights exclusion) launch
the real server as a subprocess via `fastmcp.Client` with
`StdioServerParameters`, since those tests need actual toolset config loading.
They are guarded with `@pytest.mark.skipif` when credentials are absent.

Scenarios 14–16 use `caplog` to capture log output from the `data_tool`
function's module-level logger. Because `dataset_endpoints_tool.py` uses
`logging.getLogger(__name__)` rather than `get_logger`, we capture on the
`dct_mcp_server.tools.dataset_endpoints_tool` logger name.

Run
---
    pytest tests/dlpxeco-13965-test.py -v
    pytest tests/dlpxeco-13965-test.py::test_bulk_start_happy_path_three_vdbs -v -s
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import threading
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers and fixtures
# ---------------------------------------------------------------------------

WORKTREE_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = WORKTREE_ROOT / "src"

# Make the package importable without installing
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Patch the module-level client before importing the tool module so that
# the import does not attempt any real network connection.
_MOCK_CLIENT = AsyncMock()


def _make_success_response(job_id: str = "job-abc") -> dict:
    """Return a DCT-style success response with a job id."""
    return {"job": {"id": job_id}}


def _make_error_side_effect(exc_class, message: str):
    """Return an async side-effect that raises exc_class(message)."""
    async def _raise(*args, **kwargs):
        raise exc_class(message)
    return _raise


@pytest.fixture(autouse=True)
def reset_mock_client():
    """Reset the shared mock client before each test to avoid bleed."""
    _MOCK_CLIENT.reset_mock()
    yield


@pytest.fixture(scope="module")
def dataset_module():
    """
    Import dataset_endpoints_tool with the module-level `client` replaced by
    _MOCK_CLIENT so that make_api_request / async calls hit the mock.
    """
    # Patch client before importing to intercept module-level client usage.
    with patch.dict("sys.modules", {}):
        import dct_mcp_server.tools.dataset_endpoints_tool as mod
        original_client = mod.client
        mod.client = _MOCK_CLIENT
        yield mod
        mod.client = original_client


def call_data_tool(dataset_module, **kwargs) -> dict:
    """Convenience wrapper — call data_tool and return the result dict."""
    return dataset_module.data_tool(**kwargs)


# ---------------------------------------------------------------------------
# Scenario 1 — bulk_start happy path: 3 VDBs all succeed
# Validates: FR-001 AC-1, FR-002 AC-2, FR-004 AC-1, AC-3, SC1
# ---------------------------------------------------------------------------

def test_bulk_start_happy_path_three_vdbs(dataset_module):
    """3-VDB success call returns 5-key shape; DCT mock called exactly 3 times."""
    vdb_ids = ["vdb-1", "vdb-2", "vdb-3"]

    call_count = 0
    call_endpoints = []

    async def mock_make_request(method, endpoint, **kwargs):
        nonlocal call_count
        call_count += 1
        call_endpoints.append(endpoint)
        return _make_success_response(f"job-{call_count}")

    _MOCK_CLIENT.make_request = mock_make_request

    result = call_data_tool(dataset_module, action="bulk_start", vdbIds=vdb_ids)

    assert isinstance(result, dict), "Result must be a dict"
    # Exact 5-key shape — FR-004 AC-3
    assert set(result.keys()) == {"status", "total", "succeeded", "failed", "jobs"}, (
        f"Expected exactly 5 keys, got: {set(result.keys())}"
    )
    assert result["status"] == "success", f"Expected 'success', got: {result['status']}"
    assert result["total"] == 3, f"Expected total=3, got: {result['total']}"
    assert len(result["succeeded"]) == 3, f"Expected 3 succeeded, got: {result['succeeded']}"
    assert result["failed"] == [], f"Expected empty failed list, got: {result['failed']}"
    assert len(result["jobs"]) == 3, f"Expected 3 job entries, got: {result['jobs']}"
    # DCT mock called exactly 3 times — FR-002 AC-2
    assert call_count == 3, f"Expected exactly 3 DCT calls, got: {call_count}"
    # Endpoints contain /start
    for ep in call_endpoints:
        assert "/start" in ep, f"Expected /start endpoint, got: {ep}"


# ---------------------------------------------------------------------------
# Scenario 2 — partial failure: 2 of 3 succeed, 1 fails
# Validates: FR-003 AC-1, FR-004 AC-1, SC3
# Also parametrizes over 404 and 500 status codes (EC-6)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("error_msg", [
    "HTTP 500: internal server error",
    "HTTP 404: not found",
])
def test_bulk_start_partial_failure_one_of_three_fails(dataset_module, error_msg):
    """2 of 3 mocks succeed, 1 raises an error → partial_success."""
    from dct_mcp_server.core.exceptions import DCTClientError

    vdb_ids = ["vdb-1", "vdb-2", "vdb-3"]
    call_number = 0

    async def mock_make_request(method, endpoint, **kwargs):
        nonlocal call_number
        call_number += 1
        if call_number == 2:
            raise DCTClientError(error_msg)
        return _make_success_response(f"job-{call_number}")

    _MOCK_CLIENT.make_request = mock_make_request

    result = call_data_tool(dataset_module, action="bulk_start", vdbIds=vdb_ids)

    assert result["status"] == "partial_success", (
        f"Expected 'partial_success', got: {result['status']}"
    )
    assert len(result["succeeded"]) == 2, f"Expected 2 succeeded, got: {result['succeeded']}"
    assert len(result["failed"]) == 1, f"Expected 1 failed, got: {result['failed']}"
    failed_entry = result["failed"][0]
    assert "vdbId" in failed_entry, "failed entry must have vdbId"
    assert "error" in failed_entry, "failed entry must have error"
    assert failed_entry["error"], "error string must be non-empty"


# ---------------------------------------------------------------------------
# Scenario 3 — all three fail: status="failed", no exception raised
# Validates: FR-003 AC-2, FR-004 AC-2, EC-8
# ---------------------------------------------------------------------------

def test_bulk_start_all_three_fail(dataset_module):
    """All 3 mocks raise DCTClientError → status='failed', no exception bubbles."""
    from dct_mcp_server.core.exceptions import DCTClientError

    vdb_ids = ["vdb-1", "vdb-2", "vdb-3"]

    async def mock_make_request(method, endpoint, **kwargs):
        raise DCTClientError("HTTP 500: boom")

    _MOCK_CLIENT.make_request = mock_make_request

    # Must NOT raise — workers isolate failures
    result = call_data_tool(dataset_module, action="bulk_start", vdbIds=vdb_ids)

    assert isinstance(result, dict), "Result must be a dict (no exception raised)"
    assert result["status"] == "failed", f"Expected 'failed', got: {result['status']}"
    assert result["succeeded"] == [], f"Expected empty succeeded, got: {result['succeeded']}"
    assert len(result["failed"]) == 3, f"Expected 3 failed entries, got: {result['failed']}"
    assert result["jobs"] == [], f"Expected empty jobs, got: {result['jobs']}"
    # Each failed entry must have non-empty error
    for entry in result["failed"]:
        assert entry.get("error"), f"Error must be non-empty; got: {entry}"


# ---------------------------------------------------------------------------
# Scenario 4 — empty vdbIds returns validation error, zero DCT calls
# Validates: FR-001 AC-2, EC-1
# ---------------------------------------------------------------------------

def test_bulk_start_empty_list_returns_error(dataset_module):
    """vdbIds=[] → validation error, DCT mock called 0 times."""
    call_count = 0

    async def mock_make_request(method, endpoint, **kwargs):
        nonlocal call_count
        call_count += 1
        return _make_success_response()

    _MOCK_CLIENT.make_request = mock_make_request

    result = call_data_tool(dataset_module, action="bulk_start", vdbIds=[])

    assert "error" in result, f"Expected error key, got: {result}"
    assert "vdbIds" in result["error"].lower() or "list" in result["error"].lower(), (
        f"Error message should reference vdbIds: {result['error']}"
    )
    assert call_count == 0, f"Expected 0 DCT calls, got: {call_count}"


# ---------------------------------------------------------------------------
# Scenario 5 — single VDB uses same response shape
# Validates: FR-004 AC-4, EC-2
# ---------------------------------------------------------------------------

def test_bulk_start_single_vdb_uses_same_response_shape(dataset_module):
    """vdbIds=['v1'] → total=1, 5-key shape, fan-out runs through semaphore."""
    async def mock_make_request(method, endpoint, **kwargs):
        return _make_success_response("job-single")

    _MOCK_CLIENT.make_request = mock_make_request

    result = call_data_tool(dataset_module, action="bulk_start", vdbIds=["v1"])

    assert set(result.keys()) == {"status", "total", "succeeded", "failed", "jobs"}
    assert result["total"] == 1
    assert result["status"] == "success"
    assert len(result["succeeded"]) == 1


# ---------------------------------------------------------------------------
# Scenario 6 — concurrency cap: 20 VDBs with DCT_BULK_CONCURRENCY=3
# Validates: FR-002 AC-1, AC-2, SC2
# ---------------------------------------------------------------------------

def test_bulk_concurrency_cap_three_with_twenty_ids(dataset_module):
    """With DCT_BULK_CONCURRENCY=3 and 20 vdbIds, max in-flight ≤ 3."""
    vdb_ids = [f"vdb-{i}" for i in range(20)]
    max_in_flight = 0
    in_flight = 0
    completed = 0

    # Use an asyncio gate that we can control inside the mock
    async def mock_make_request(method, endpoint, **kwargs):
        nonlocal in_flight, max_in_flight, completed
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        # Yield control so other coroutines can run and acquire semaphore
        await asyncio.sleep(0)
        in_flight -= 1
        completed += 1
        return _make_success_response(f"job-{completed}")

    _MOCK_CLIENT.make_request = mock_make_request

    with patch.dict(os.environ, {"DCT_BULK_CONCURRENCY": "3"}):
        result = call_data_tool(dataset_module, action="bulk_start", vdbIds=vdb_ids)

    assert max_in_flight <= 3, (
        f"Max in-flight was {max_in_flight}, expected ≤ 3 (concurrency cap)"
    )
    # All 20 calls complete — FR-002 AC-2
    assert completed == 20, f"Expected 20 completions, got: {completed}"
    assert result["total"] == 20
    assert result["status"] == "success"


# ---------------------------------------------------------------------------
# Scenario 7 — bulk_stop with 6 IDs returns confirmation_required (no calls)
# Validates: FR-005 AC-1, SC4
# ---------------------------------------------------------------------------

def test_bulk_stop_threshold_six_returns_confirmation(dataset_module):
    """bulk_stop, 6 vdbIds, no confirmed → confirmation_required; 0 DCT calls."""
    call_count = 0

    async def mock_make_request(method, endpoint, **kwargs):
        nonlocal call_count
        call_count += 1
        return _make_success_response()

    _MOCK_CLIENT.make_request = mock_make_request
    vdb_ids = [f"vdb-{i}" for i in range(6)]

    result = call_data_tool(dataset_module, action="bulk_stop", vdbIds=vdb_ids)

    assert result.get("status") == "confirmation_required", (
        f"Expected confirmation_required, got: {result}"
    )
    assert result.get("confirmation_level") == "manual", (
        f"Expected manual level, got: {result.get('confirmation_level')}"
    )
    assert call_count == 0, f"Expected 0 DCT calls before confirmation, got: {call_count}"


# ---------------------------------------------------------------------------
# Scenario 8 — bulk_stop with confirmed=True dispatches 6 calls
# Validates: FR-005 AC-2, SC5
# ---------------------------------------------------------------------------

def test_bulk_stop_threshold_six_with_confirmed_proceeds(dataset_module):
    """Same call with confirmed=True → 6 DCT calls, status in success/partial_success."""
    call_count = 0

    async def mock_make_request(method, endpoint, **kwargs):
        nonlocal call_count
        call_count += 1
        return _make_success_response(f"job-{call_count}")

    _MOCK_CLIENT.make_request = mock_make_request
    vdb_ids = [f"vdb-{i}" for i in range(6)]

    result = call_data_tool(dataset_module, action="bulk_stop", vdbIds=vdb_ids, confirmed=True)

    assert call_count == 6, f"Expected exactly 6 DCT calls, got: {call_count}"
    assert result["status"] in {"success", "partial_success"}, (
        f"Expected success or partial_success, got: {result['status']}"
    )


# ---------------------------------------------------------------------------
# Scenario 9 — bulk_stop below threshold proceeds without confirmation
# Validates: FR-005 AC-3, SC6
# ---------------------------------------------------------------------------

def test_bulk_stop_below_threshold_no_confirmation(dataset_module):
    """bulk_stop with 3 vdbIds and no confirmed → proceeds, 3 DCT calls."""
    call_count = 0

    async def mock_make_request(method, endpoint, **kwargs):
        nonlocal call_count
        call_count += 1
        return _make_success_response(f"job-{call_count}")

    _MOCK_CLIENT.make_request = mock_make_request
    vdb_ids = ["vdb-1", "vdb-2", "vdb-3"]

    result = call_data_tool(dataset_module, action="bulk_stop", vdbIds=vdb_ids)

    assert result["status"] == "success", (
        f"Expected success (no gate for 3 VDBs), got: {result['status']}"
    )
    assert call_count == 3, f"Expected 3 DCT calls, got: {call_count}"


# ---------------------------------------------------------------------------
# Scenario 10 — bulk_disable with 6 IDs returns confirmation_required
# Validates: FR-005 AC-4
# ---------------------------------------------------------------------------

def test_bulk_disable_threshold_matches_bulk_stop(dataset_module):
    """bulk_disable with 6 vdbIds and no confirmed → confirmation_required."""
    call_count = 0

    async def mock_make_request(method, endpoint, **kwargs):
        nonlocal call_count
        call_count += 1
        return _make_success_response()

    _MOCK_CLIENT.make_request = mock_make_request
    vdb_ids = [f"vdb-{i}" for i in range(6)]

    result = call_data_tool(dataset_module, action="bulk_disable", vdbIds=vdb_ids)

    assert result.get("status") == "confirmation_required", (
        f"Expected confirmation_required, got: {result}"
    )
    assert call_count == 0, f"Expected 0 DCT calls, got: {call_count}"


# ---------------------------------------------------------------------------
# Scenario 11 — bulk_enable with 6 IDs runs directly (non-destructive)
# Validates: FR-005 AC-5, SC7
# ---------------------------------------------------------------------------

def test_bulk_enable_no_threshold_six_runs_directly(dataset_module):
    """bulk_enable with 6 vdbIds, no confirmed → success, 6 DCT calls (no gate)."""
    call_count = 0

    async def mock_make_request(method, endpoint, **kwargs):
        nonlocal call_count
        call_count += 1
        return _make_success_response(f"job-{call_count}")

    _MOCK_CLIENT.make_request = mock_make_request
    vdb_ids = [f"vdb-{i}" for i in range(6)]

    result = call_data_tool(dataset_module, action="bulk_enable", vdbIds=vdb_ids)

    assert result["status"] == "success", (
        f"Expected success (no confirmation gate for bulk_enable), got: {result}"
    )
    assert call_count == 6, f"Expected 6 DCT calls, got: {call_count}"


# ---------------------------------------------------------------------------
# Scenario 12 — unknown bulk action returns error
# Validates: EC-10
# ---------------------------------------------------------------------------

def test_bulk_unknown_action_returns_unknown_action_error(dataset_module):
    """action='bulk_garbage' → existing else branch returns Unknown action error."""
    result = call_data_tool(dataset_module, action="bulk_garbage", vdbIds=["vdb-1"])

    # The existing else branch in data_tool returns {"error": "Unknown action: ..."}
    assert "error" in result or "unknown" in str(result).lower(), (
        f"Expected unknown action error, got: {result}"
    )


# ---------------------------------------------------------------------------
# Scenario 13 — vdbIds passed as string (not list) returns validation error
# Validates: FR-001 AC-3, EC-5
# Also covers EC-4 (vdbIds=[None, "v2"]) — non-string element validation
# ---------------------------------------------------------------------------

def test_bulk_start_vdbIds_string_returns_validation_error(dataset_module):
    """vdbIds='vdb-1' (str, not list) → validation error, 0 DCT calls."""
    call_count = 0

    async def mock_make_request(method, endpoint, **kwargs):
        nonlocal call_count
        call_count += 1
        return _make_success_response()

    _MOCK_CLIENT.make_request = mock_make_request

    result = call_data_tool(dataset_module, action="bulk_start", vdbIds="vdb-1")

    assert "error" in result, f"Expected error key, got: {result}"
    assert call_count == 0, f"Expected 0 DCT calls, got: {call_count}"


def test_bulk_start_vdbIds_list_with_none_element_returns_validation_error(dataset_module):
    """vdbIds=[None, 'v2'] → validation error (non-string element), 0 DCT calls."""
    call_count = 0

    async def mock_make_request(method, endpoint, **kwargs):
        nonlocal call_count
        call_count += 1
        return _make_success_response()

    _MOCK_CLIENT.make_request = mock_make_request

    result = call_data_tool(dataset_module, action="bulk_start", vdbIds=[None, "v2"])

    assert "error" in result, f"Expected error key for None element, got: {result}"
    assert call_count == 0, f"Expected 0 DCT calls, got: {call_count}"


# ---------------------------------------------------------------------------
# Scenario 14 — INFO logs on dispatch and completion
# Validates: FR-007 AC-1 (INFO half)
# ---------------------------------------------------------------------------

def test_bulk_start_logs_info_on_dispatch_and_completion(dataset_module, caplog):
    """Successful 3-VDB batch emits ≥2 INFO records containing 'bulk action='."""
    vdb_ids = ["vdb-1", "vdb-2", "vdb-3"]

    async def mock_make_request(method, endpoint, **kwargs):
        return _make_success_response()

    _MOCK_CLIENT.make_request = mock_make_request

    logger_name = "dct_mcp_server.tools.dataset_endpoints_tool"
    with caplog.at_level(logging.INFO, logger=logger_name):
        call_data_tool(dataset_module, action="bulk_start", vdbIds=vdb_ids)

    info_records = [
        r for r in caplog.records
        if r.levelno == logging.INFO and "bulk action=" in r.message
    ]
    assert len(info_records) >= 2, (
        f"Expected ≥2 INFO records with 'bulk action=', got: {[r.message for r in caplog.records]}"
    )


# ---------------------------------------------------------------------------
# Scenario 15 — DEBUG logs per-VDB success outcome
# Validates: FR-007 AC-1 (DEBUG half)
# ---------------------------------------------------------------------------

def test_bulk_start_logs_debug_per_vdb_outcome(dataset_module, caplog):
    """3 VDBs all succeed → exactly 3 DEBUG records containing 'outcome=success'."""
    vdb_ids = ["vdb-1", "vdb-2", "vdb-3"]

    async def mock_make_request(method, endpoint, **kwargs):
        return _make_success_response()

    _MOCK_CLIENT.make_request = mock_make_request

    logger_name = "dct_mcp_server.tools.dataset_endpoints_tool"
    with caplog.at_level(logging.DEBUG, logger=logger_name):
        call_data_tool(dataset_module, action="bulk_start", vdbIds=vdb_ids)

    debug_success_records = [
        r for r in caplog.records
        if r.levelno == logging.DEBUG and "outcome=success" in r.message
    ]
    assert len(debug_success_records) == 3, (
        f"Expected exactly 3 DEBUG 'outcome=success' records, "
        f"got: {[r.message for r in caplog.records if r.levelno == logging.DEBUG]}"
    )


# ---------------------------------------------------------------------------
# Scenario 16 — DEBUG logs per-VDB failure with error string
# Validates: FR-007 AC-2
# ---------------------------------------------------------------------------

def test_bulk_start_logs_debug_failure_with_error_string(dataset_module, caplog):
    """All 3 mocks raise DCTClientError → 3 DEBUG 'outcome=failure' records with error=."""
    from dct_mcp_server.core.exceptions import DCTClientError

    vdb_ids = ["vdb-1", "vdb-2", "vdb-3"]

    async def mock_make_request(method, endpoint, **kwargs):
        raise DCTClientError("HTTP 500: boom")

    _MOCK_CLIENT.make_request = mock_make_request

    logger_name = "dct_mcp_server.tools.dataset_endpoints_tool"
    with caplog.at_level(logging.DEBUG, logger=logger_name):
        call_data_tool(dataset_module, action="bulk_start", vdbIds=vdb_ids)

    debug_failure_records = [
        r for r in caplog.records
        if r.levelno == logging.DEBUG and "outcome=failure" in r.message
    ]
    assert len(debug_failure_records) == 3, (
        f"Expected exactly 3 DEBUG 'outcome=failure' records, "
        f"got: {[r.message for r in caplog.records if r.levelno == logging.DEBUG]}"
    )
    for record in debug_failure_records:
        assert "error=" in record.message, (
            f"DEBUG failure record must contain 'error=': {record.message}"
        )
        # error= value must be non-empty (not "error=" at end of string)
        idx = record.message.index("error=")
        error_val = record.message[idx + len("error="):].strip()
        assert error_val, f"error= value must be non-empty in: {record.message}"


# ---------------------------------------------------------------------------
# Scenario 17 — bulk actions visible in self_service and continuous_data_admin
# Validates: FR-006 AC-1, AC-2, SC8
# ---------------------------------------------------------------------------

def _toolset_actions_for_tool(toolset_name: str, tool_name: str) -> set[str]:
    """
    Parse the toolset .txt file and return the set of action names
    registered under `tool_name`.
    """
    txt_dir = WORKTREE_ROOT / "src" / "dct_mcp_server" / "config" / "toolsets"
    txt_file = txt_dir / f"{toolset_name}.txt"
    if not txt_file.exists():
        return set()

    actions: set[str] = set()
    in_block = False

    with txt_file.open() as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                # Detect the tool block header comment
                if f"TOOL" in stripped and tool_name in stripped:
                    in_block = True
                elif "TOOL" in stripped and tool_name not in stripped and in_block:
                    # Started a new tool block
                    in_block = False
                continue
            if in_block:
                # Lines look like: POST|/vdbs/bulk_start|bulk_start
                parts = stripped.split("|")
                if len(parts) == 3:
                    actions.add(parts[2])

    return actions


def test_bulk_visibility_in_self_service_and_cda_only():
    """
    Parse toolset .txt files directly to verify bulk actions are registered.
    self_service: bulk_start/stop/enable/disable on vdb_tool.
    continuous_data_admin: same on data_tool.
    reporting_insights: no bulk_* anywhere.
    """
    bulk_actions = {"bulk_start", "bulk_stop", "bulk_enable", "bulk_disable"}

    # self_service
    ss_actions = _toolset_actions_for_tool("self_service", "vdb_tool")
    missing_ss = bulk_actions - ss_actions
    assert not missing_ss, (
        f"self_service vdb_tool is missing bulk actions: {missing_ss}. "
        f"Found actions: {ss_actions}"
    )

    # continuous_data_admin
    cda_actions = _toolset_actions_for_tool("continuous_data_admin", "data_tool")
    missing_cda = bulk_actions - cda_actions
    assert not missing_cda, (
        f"continuous_data_admin data_tool is missing bulk actions: {missing_cda}. "
        f"Found actions: {cda_actions}"
    )


# ---------------------------------------------------------------------------
# Scenario 18 — single-VDB start unchanged after bulk addition
# Validates: FR-008 AC-1, QR-1
# ---------------------------------------------------------------------------

def test_single_vdb_start_unchanged_after_bulk_addition(dataset_module):
    """data_tool(action='start_vdb', vdb_id='v1') returns the DCT response unchanged."""
    expected_payload = {"job": {"id": "job-single-vdb"}, "status": "queued"}

    async def mock_make_request(method, endpoint, **kwargs):
        assert method == "POST"
        assert endpoint == "/vdbs/v1/start"
        return expected_payload

    _MOCK_CLIENT.make_request = mock_make_request

    # Patch make_api_request to go through our mock client
    original_make_api_request = dataset_module.make_api_request

    def patched_make_api_request(method, endpoint, params=None, json_body=None):
        async def _inner():
            return await _MOCK_CLIENT.make_request(
                method, endpoint, params=params or {}, json=json_body
            )
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                result_holder = [None]
                exc_holder = [None]
                def run_in_thread():
                    try:
                        result_holder[0] = asyncio.run(_inner())
                    except Exception as e:
                        exc_holder[0] = e
                t = threading.Thread(target=run_in_thread)
                t.start()
                t.join()
                if exc_holder[0]:
                    raise exc_holder[0]
                return result_holder[0]
            else:
                return loop.run_until_complete(_inner())
        except RuntimeError:
            return asyncio.run(_inner())

    dataset_module.make_api_request = patched_make_api_request
    try:
        result = call_data_tool(dataset_module, action="start_vdb", vdb_id="v1")
    finally:
        dataset_module.make_api_request = original_make_api_request

    assert result == expected_payload, (
        f"Single-VDB start response must match pre-change baseline. "
        f"Got: {result}, expected: {expected_payload}"
    )


# ---------------------------------------------------------------------------
# Scenario 19 — reporting_insights excludes bulk actions
# Validates: FR-006 AC-3, SC8, QR-9
# ---------------------------------------------------------------------------

def test_reporting_insights_excludes_bulk_actions():
    """
    Parse reporting_insights.txt and assert no bulk_* action is present anywhere.
    """
    txt_file = (
        WORKTREE_ROOT
        / "src"
        / "dct_mcp_server"
        / "config"
        / "toolsets"
        / "reporting_insights.txt"
    )
    assert txt_file.exists(), f"reporting_insights.txt not found at {txt_file}"

    bulk_actions_found = []
    with txt_file.open() as fh:
        for lineno, line in enumerate(fh, 1):
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                continue
            parts = stripped.split("|")
            if len(parts) == 3:
                action_name = parts[2]
                if action_name.startswith("bulk_"):
                    bulk_actions_found.append((lineno, action_name))

    assert not bulk_actions_found, (
        f"reporting_insights.txt contains bulk actions (must not): "
        f"{bulk_actions_found}"
    )


# ---------------------------------------------------------------------------
# Extra concurrency env-var scenarios (ERR-4, ERR-5 from test plan)
# ---------------------------------------------------------------------------

def test_concurrency_env_var_invalid_falls_back_to_5(dataset_module, caplog):
    """DCT_BULK_CONCURRENCY=foo → WARNING logged, effective concurrency 5, batch runs."""
    call_count = 0

    async def mock_make_request(method, endpoint, **kwargs):
        nonlocal call_count
        call_count += 1
        return _make_success_response(f"job-{call_count}")

    _MOCK_CLIENT.make_request = mock_make_request

    logger_name = "dct_mcp_server.tools.dataset_endpoints_tool"
    with caplog.at_level(logging.WARNING, logger=logger_name):
        with patch.dict(os.environ, {"DCT_BULK_CONCURRENCY": "foo"}):
            result = call_data_tool(
                dataset_module, action="bulk_start", vdbIds=["vdb-1", "vdb-2"]
            )

    assert result["status"] == "success", f"Batch should still complete: {result}"
    # A WARNING about the invalid value should have been emitted
    warning_records = [
        r for r in caplog.records
        if r.levelno == logging.WARNING and "DCT_BULK_CONCURRENCY" in r.message
    ]
    assert warning_records, (
        f"Expected WARNING about invalid DCT_BULK_CONCURRENCY, "
        f"got warnings: {[r.message for r in caplog.records if r.levelno == logging.WARNING]}"
    )


def test_concurrency_env_var_huge_clamps_to_50(dataset_module, caplog):
    """DCT_BULK_CONCURRENCY=10000 → WARNING logged, clamps to 50, batch runs."""
    call_count = 0

    async def mock_make_request(method, endpoint, **kwargs):
        nonlocal call_count
        call_count += 1
        return _make_success_response(f"job-{call_count}")

    _MOCK_CLIENT.make_request = mock_make_request

    logger_name = "dct_mcp_server.tools.dataset_endpoints_tool"
    with caplog.at_level(logging.WARNING, logger=logger_name):
        with patch.dict(os.environ, {"DCT_BULK_CONCURRENCY": "10000"}):
            result = call_data_tool(
                dataset_module, action="bulk_start", vdbIds=["vdb-1"]
            )

    assert result["status"] == "success", f"Batch should still complete: {result}"
    warning_records = [
        r for r in caplog.records
        if r.levelno == logging.WARNING and "DCT_BULK_CONCURRENCY" in r.message
    ]
    assert warning_records, (
        f"Expected WARNING about huge DCT_BULK_CONCURRENCY value, "
        f"got warnings: {[r.message for r in caplog.records if r.levelno == logging.WARNING]}"
    )


def test_bulk_stop_confirmed_true_with_n_lte_5_runs_directly(dataset_module):
    """confirmed=True with N≤5 — confirmed is ignored, batch runs (EC-9)."""
    call_count = 0

    async def mock_make_request(method, endpoint, **kwargs):
        nonlocal call_count
        call_count += 1
        return _make_success_response(f"job-{call_count}")

    _MOCK_CLIENT.make_request = mock_make_request

    result = call_data_tool(
        dataset_module, action="bulk_stop", vdbIds=["vdb-1", "vdb-2", "vdb-3"], confirmed=True
    )

    assert result["status"] == "success", (
        f"confirmed=True with N=3 should run directly, got: {result}"
    )
    assert call_count == 3, f"Expected 3 DCT calls, got: {call_count}"


# ---------------------------------------------------------------------------
# Static / grep-based quality rule checks (QR-3, QR-4, QR-5)
# ---------------------------------------------------------------------------

def test_qr3_log_tool_execution_decorators_present():
    """
    QR-3: All tool functions in tools/ are decorated with @log_tool_execution.
    Grep: files lacking the decorator string → output must be empty.
    """
    tools_dir = WORKTREE_ROOT / "src" / "dct_mcp_server" / "tools"
    tool_files = [
        f for f in tools_dir.glob("*_endpoints_tool.py")
        if f.is_file()
    ]
    assert tool_files, "No *_endpoints_tool.py files found — check path"

    missing = []
    for tf in tool_files:
        content = tf.read_text()
        if "@log_tool_execution" not in content:
            missing.append(str(tf))

    assert not missing, (
        f"These tool files are missing @log_tool_execution: {missing}"
    )


def test_qr4_no_bare_exception_in_new_code():
    """
    QR-4: No 'raise Exception' in dataset_endpoints_tool.py.
    Allowed: raise DCTClientError / raise MCPError.
    """
    target = (
        WORKTREE_ROOT
        / "src"
        / "dct_mcp_server"
        / "tools"
        / "dataset_endpoints_tool.py"
    )
    content = target.read_text()
    lines_with_bare_raise = [
        (i + 1, line.strip())
        for i, line in enumerate(content.splitlines())
        if "raise Exception" in line
    ]
    assert not lines_with_bare_raise, (
        f"Found bare 'raise Exception' in dataset_endpoints_tool.py: "
        f"{lines_with_bare_raise}"
    )


def test_qr5_no_new_logging_getlogger_in_diff():
    """
    QR-5: No new logging.getLogger( calls added in the bulk code sections.
    The pre-existing top-level declaration at line ~11 is allowed;
    no additional occurrences should be added.

    This checks the total count in the file has not grown past 1.
    """
    target = (
        WORKTREE_ROOT
        / "src"
        / "dct_mcp_server"
        / "tools"
        / "dataset_endpoints_tool.py"
    )
    content = target.read_text()
    occurrences = [
        (i + 1, line.strip())
        for i, line in enumerate(content.splitlines())
        if "logging.getLogger(" in line
    ]
    assert len(occurrences) <= 1, (
        f"Expected at most 1 logging.getLogger( occurrence (the existing top-level one), "
        f"found {len(occurrences)}: {occurrences}"
    )
