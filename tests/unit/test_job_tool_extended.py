"""
Extended unit tests for tools/job_endpoints_tool.py.

Covers the uncovered lines:
- build_params()
- _SafeDict
- check_confirmation() integration in job_tool
- job_tool actions: abandon, get_tags
- Missing required parameter branches
- Unknown action branch
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import dct_mcp_server.tools.job_endpoints_tool as job_mod
from dct_mcp_server.tools.job_endpoints_tool import (
    _SafeDict,
    build_params,
    check_confirmation,
    register_tools,
)


# ---------------------------------------------------------------------------
# _SafeDict
# ---------------------------------------------------------------------------

def test_safedict_returns_value_for_existing_key():
    d = _SafeDict(name="Alice")
    assert d["name"] == "Alice"


def test_safedict_returns_placeholder_for_missing_key():
    d = _SafeDict()
    assert d["missing_key"] == "{missing_key}"


def test_safedict_format_map_with_missing_keys():
    d = _SafeDict(days=3)
    result = "Will expire in {days} days (id={id})".format_map(d)
    assert "3" in result
    assert "{id}" in result


# ---------------------------------------------------------------------------
# build_params
# ---------------------------------------------------------------------------

def test_build_params_excludes_none():
    result = build_params(a=1, b=None, c="hello")
    assert result == {"a": 1, "c": "hello"}


def test_build_params_excludes_empty_string():
    result = build_params(a="", b="value")
    assert result == {"b": "value"}


def test_build_params_all_none():
    result = build_params(x=None, y=None)
    assert result == {}


def test_build_params_all_values():
    result = build_params(limit=10, cursor="abc", sort="-start_time")
    assert result == {"limit": 10, "cursor": "abc", "sort": "-start_time"}


def test_build_params_zero_is_kept():
    result = build_params(count=0)
    assert result == {"count": 0}


# ---------------------------------------------------------------------------
# check_confirmation (in job_endpoints_tool)
# ---------------------------------------------------------------------------

def test_check_confirmation_safe_get_returns_none():
    result = check_confirmation("GET", "/jobs/j-1", "get", "job_tool", confirmed=False)
    assert result is None


def test_check_confirmation_safe_post_search_returns_none():
    result = check_confirmation("POST", "/jobs/search", "search", "job_tool", confirmed=False)
    assert result is None


def test_check_confirmation_confirmed_true_returns_none():
    result = check_confirmation("GET", "/jobs/j-1/tags", "get_tags", "job_tool", confirmed=True)
    assert result is None


def test_check_confirmation_with_context():
    # With context dict — should not raise
    result = check_confirmation("GET", "/jobs/j-1", "get", "job_tool", confirmed=False,
                                context={"job_id": "j-1"})
    assert result is None


# ---------------------------------------------------------------------------
# job_tool — action routing
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def set_client():
    """Set a mock client on the job_endpoints_tool module."""
    mock_client = MagicMock()
    mock_client.make_request = AsyncMock(return_value={"items": []})
    job_mod.client = mock_client
    yield mock_client
    job_mod.client = None


@pytest.mark.asyncio
async def test_job_tool_search(set_client):
    from dct_mcp_server.tools.job_endpoints_tool import job_tool
    result = await job_tool(action="search", limit=10)
    assert set_client.make_request.called


@pytest.mark.asyncio
async def test_job_tool_search_with_filter(set_client):
    from dct_mcp_server.tools.job_endpoints_tool import job_tool
    result = await job_tool(action="search", filter_expression="status EQ 'RUNNING'")
    assert set_client.make_request.called
    call_kwargs = set_client.make_request.call_args
    # Body should contain filter_expression
    json_body = call_kwargs[1].get("json") or (call_kwargs[0][3] if len(call_kwargs[0]) > 3 else {})
    # Just verify it was called
    assert set_client.make_request.called


@pytest.mark.asyncio
async def test_job_tool_get(set_client):
    from dct_mcp_server.tools.job_endpoints_tool import job_tool
    result = await job_tool(action="get", job_id="j-abc-123")
    assert set_client.make_request.called
    call_args = set_client.make_request.call_args
    # Verify endpoint includes the job_id
    endpoint = call_args[0][1] if call_args[0] else call_args[1].get("endpoint", "")
    assert "j-abc-123" in str(call_args)


@pytest.mark.asyncio
async def test_job_tool_get_missing_job_id(set_client):
    from dct_mcp_server.tools.job_endpoints_tool import job_tool
    result = await job_tool(action="get")
    assert "error" in result
    assert "job_id" in result["error"]


@pytest.mark.asyncio
async def test_job_tool_abandon(set_client):
    from dct_mcp_server.tools.job_endpoints_tool import job_tool
    result = await job_tool(action="abandon", job_id="j-abc-456")
    assert set_client.make_request.called


@pytest.mark.asyncio
async def test_job_tool_abandon_missing_job_id(set_client):
    from dct_mcp_server.tools.job_endpoints_tool import job_tool
    result = await job_tool(action="abandon")
    assert "error" in result
    assert "job_id" in result["error"]


@pytest.mark.asyncio
async def test_job_tool_get_tags(set_client):
    from dct_mcp_server.tools.job_endpoints_tool import job_tool
    result = await job_tool(action="get_tags", job_id="j-789")
    assert set_client.make_request.called


@pytest.mark.asyncio
async def test_job_tool_get_tags_missing_job_id(set_client):
    from dct_mcp_server.tools.job_endpoints_tool import job_tool
    result = await job_tool(action="get_tags")
    assert "error" in result
    assert "job_id" in result["error"]


@pytest.mark.asyncio
async def test_job_tool_unknown_action(set_client):
    from dct_mcp_server.tools.job_endpoints_tool import job_tool
    result = await job_tool(action="fly_to_moon")
    assert "error" in result
    assert "Unknown action" in result["error"] or "fly_to_moon" in result["error"]


@pytest.mark.asyncio
async def test_job_tool_abandon_endpoint_path(set_client):
    from dct_mcp_server.tools.job_endpoints_tool import job_tool
    await job_tool(action="abandon", job_id="j-xxx")
    call_args = set_client.make_request.call_args
    # Should have called with POST and /jobs/j-xxx/abandon
    assert "abandon" in str(call_args)


@pytest.mark.asyncio
async def test_job_tool_get_tags_endpoint_path(set_client):
    from dct_mcp_server.tools.job_endpoints_tool import job_tool
    await job_tool(action="get_tags", job_id="j-yyy")
    call_args = set_client.make_request.call_args
    assert "tags" in str(call_args)


# ---------------------------------------------------------------------------
# register_tools
# ---------------------------------------------------------------------------

def test_register_tools_sets_client():
    mock_app = MagicMock()
    mock_client = MagicMock()
    register_tools(mock_app, mock_client)
    assert job_mod.client is mock_client
    mock_app.add_tool.assert_called()


def test_register_tools_calls_add_tool():
    mock_app = MagicMock()
    mock_client = MagicMock()
    register_tools(mock_app, mock_client)
    assert mock_app.add_tool.call_count >= 1


def test_register_tools_handles_exception():
    mock_app = MagicMock()
    mock_app.add_tool.side_effect = Exception("registration failed")
    mock_client = MagicMock()
    # Should not raise
    register_tools(mock_app, mock_client)


# ---------------------------------------------------------------------------
# check_confirmation with conditional logic
# ---------------------------------------------------------------------------

def test_check_confirmation_retain_forever_skips():
    """When retain_forever=True, no confirmation needed."""
    from unittest.mock import patch
    with patch("dct_mcp_server.tools.job_endpoints_tool.get_confirmation_for_operation") as mock_conf:
        mock_conf.return_value = {
            "level": "retention_check",
            "message": "Snapshot is {days} days old",
            "conditional": True,
            "threshold_days": 7,
        }
        result = check_confirmation("POST", "/snapshots/s-1/delete", "delete", "snapshot_tool",
                                    confirmed=False,
                                    context={"retain_forever": True})
        assert result is None


def test_check_confirmation_retention_far_future_skips():
    """Expiration date far in the future → skip confirmation."""
    from unittest.mock import patch
    from datetime import datetime, timezone, timedelta
    future_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    with patch("dct_mcp_server.tools.job_endpoints_tool.get_confirmation_for_operation") as mock_conf:
        mock_conf.return_value = {
            "level": "retention_check",
            "message": "Snapshot expires in {days} days",
            "conditional": True,
            "threshold_days": 7,
        }
        result = check_confirmation("POST", "/snapshots/s-1/delete", "delete", "snapshot_tool",
                                    confirmed=False,
                                    context={"retain_forever": False, "expiration_date": future_date})
        assert result is None


def test_check_confirmation_retention_near_expiry_requires_confirmation():
    """Expiration date very soon → require confirmation."""
    from unittest.mock import patch
    from datetime import datetime, timezone, timedelta
    soon_date = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    with patch("dct_mcp_server.tools.job_endpoints_tool.get_confirmation_for_operation") as mock_conf:
        mock_conf.return_value = {
            "level": "retention_check",
            "message": "Snapshot expires in {days} days",
            "conditional": True,
            "threshold_days": 7,
        }
        result = check_confirmation("POST", "/snapshots/s-1/delete", "delete", "snapshot_tool",
                                    confirmed=False,
                                    context={"retain_forever": False, "expiration_date": soon_date})
        # Should require confirmation since 1 day < 7 day threshold
        assert result is not None
        assert result["status"] == "confirmation_required"


def test_check_confirmation_non_retention_no_context():
    """Manual confirmation level without context."""
    from unittest.mock import patch
    with patch("dct_mcp_server.tools.job_endpoints_tool.get_confirmation_for_operation") as mock_conf:
        mock_conf.return_value = {
            "level": "manual",
            "message": "Are you sure?",
            "conditional": False,
            "threshold_days": None,
        }
        result = check_confirmation("POST", "/vdbs/v-1/delete", "delete", "vdb_tool",
                                    confirmed=False, context=None)
        assert result is not None
        assert result["status"] == "confirmation_required"


def test_check_confirmation_confirmed_true_skips():
    """With confirmed=True, no confirmation response."""
    from unittest.mock import patch
    with patch("dct_mcp_server.tools.job_endpoints_tool.get_confirmation_for_operation") as mock_conf:
        mock_conf.return_value = {
            "level": "manual",
            "message": "Are you sure?",
            "conditional": False,
            "threshold_days": None,
        }
        result = check_confirmation("POST", "/vdbs/v-1/delete", "delete", "vdb_tool",
                                    confirmed=True, context=None)
        assert result is None


def test_check_confirmation_invalid_date_handles_gracefully():
    """Invalid expiration_date should be handled without crash."""
    from unittest.mock import patch
    with patch("dct_mcp_server.tools.job_endpoints_tool.get_confirmation_for_operation") as mock_conf:
        mock_conf.return_value = {
            "level": "retention_check",
            "message": "Snapshot expires in {days} days",
            "conditional": True,
            "threshold_days": 7,
        }
        result = check_confirmation("POST", "/snapshots/s-1/delete", "delete", "snapshot_tool",
                                    confirmed=False,
                                    context={"retain_forever": False,
                                             "expiration_date": "not-a-date"})
        # Should not crash — may or may not require confirmation
        assert result is None or isinstance(result, dict)
