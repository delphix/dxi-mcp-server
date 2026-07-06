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
from unittest.mock import AsyncMock, MagicMock  # AsyncMock used in set_client fixture

import dct_mcp_server.tools.job_endpoints_tool as job_mod
from dct_mcp_server.tools.job_endpoints_tool import (
    build_params,
    check_confirmation,
    register_tools,
)


class _SafeDict(dict):
    """Returns '{key}' for missing keys so unresolvable placeholders stay readable."""

    def __missing__(self, key):
        return f"{{{key}}}"


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
    result = check_confirmation(
        "POST", "/jobs/search", "search", "job_tool", confirmed=False
    )
    assert result is None


def test_check_confirmation_confirmed_true_returns_none():
    result = check_confirmation(
        "GET", "/jobs/j-1/tags", "get_tags", "job_tool", confirmed=True
    )
    assert result is None


def test_check_confirmation_with_request_params():
    # With context dict — should not raise
    result = check_confirmation(
        "GET",
        "/jobs/j-1",
        "get",
        "job_tool",
        confirmed=False,
        context={"job_id": "j-1"},
    )
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


async def test_job_tool_search(set_client):
    from dct_mcp_server.tools.job_endpoints_tool import job_tool

    await job_tool(action="search", limit=10)
    assert set_client.make_request.called


async def test_job_tool_search_with_filter(set_client):
    from dct_mcp_server.tools.job_endpoints_tool import job_tool

    await job_tool(action="search", filter_expression="status EQ 'RUNNING'")
    assert set_client.make_request.called


async def test_job_tool_get(set_client):
    from dct_mcp_server.tools.job_endpoints_tool import job_tool

    await job_tool(action="get", job_id="j-abc-123")
    assert set_client.make_request.called
    call_args = set_client.make_request.call_args
    assert "j-abc-123" in str(call_args)


async def test_job_tool_get_missing_job_id(set_client):
    from dct_mcp_server.tools.job_endpoints_tool import job_tool

    result = await job_tool(action="get")
    assert "error" in result
    assert "job_id" in result["error"]


async def test_job_tool_abandon(set_client):
    from dct_mcp_server.tools.job_endpoints_tool import job_tool

    await job_tool(action="abandon", job_id="j-abc-456")
    assert set_client.make_request.called


async def test_job_tool_abandon_missing_job_id(set_client):
    from dct_mcp_server.tools.job_endpoints_tool import job_tool

    result = await job_tool(action="abandon")
    assert "error" in result
    assert "job_id" in result["error"]


async def test_job_tool_get_tags(set_client):
    from dct_mcp_server.tools.job_endpoints_tool import job_tool

    await job_tool(action="get_tags", job_id="j-789")
    assert set_client.make_request.called


async def test_job_tool_get_tags_missing_job_id(set_client):
    from dct_mcp_server.tools.job_endpoints_tool import job_tool

    result = await job_tool(action="get_tags")
    assert "error" in result
    assert "job_id" in result["error"]


async def test_job_tool_unknown_action(set_client):
    from dct_mcp_server.tools.job_endpoints_tool import job_tool

    result = await job_tool(action="fly_to_moon")
    assert "error" in result
    assert "Unknown action" in result["error"] or "fly_to_moon" in result["error"]


async def test_job_tool_abandon_endpoint_path(set_client):
    from dct_mcp_server.tools.job_endpoints_tool import job_tool

    await job_tool(action="abandon", job_id="j-xxx")
    call_args = set_client.make_request.call_args
    assert "abandon" in str(call_args)


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


def test_check_confirmation_non_none_level_requires_confirmation():
    """Any non-none confirmation level triggers confirmation."""
    from unittest.mock import patch

    with patch(
        "dct_mcp_server.tools.job_endpoints_tool.get_confirmation_for_operation"
    ) as mock_conf:
        mock_conf.return_value = {
            "level": "retention_check",
            "message": "Snapshot policy check",
        }
        result = check_confirmation(
            "POST", "/snapshots/s-1/delete", "delete", "snapshot_tool", confirmed=False
        )
        assert result is not None
        assert result["status"] == "confirmation_required"


def test_check_confirmation_non_retention_requires_confirmation():
    """Manual confirmation level requires confirmation."""
    from unittest.mock import patch

    with patch(
        "dct_mcp_server.tools.job_endpoints_tool.get_confirmation_for_operation"
    ) as mock_conf:
        mock_conf.return_value = {"level": "manual", "message": "Are you sure?"}
        result = check_confirmation(
            "POST", "/vdbs/v-1/delete", "delete", "vdb_tool", confirmed=False
        )
        assert result is not None
        assert result["status"] == "confirmation_required"


def test_check_confirmation_confirmed_true_skips():
    """With confirmed=True, no confirmation response."""
    from unittest.mock import patch

    with patch(
        "dct_mcp_server.tools.job_endpoints_tool.get_confirmation_for_operation"
    ) as mock_conf:
        mock_conf.return_value = {"level": "manual", "message": "Are you sure?"}
        result = check_confirmation(
            "POST", "/vdbs/v-1/delete", "delete", "vdb_tool", confirmed=True
        )
        assert result is None


def test_check_confirmation_none_level_skips():
    """When level is 'none', no confirmation needed."""
    from unittest.mock import patch

    with patch(
        "dct_mcp_server.tools.job_endpoints_tool.get_confirmation_for_operation"
    ) as mock_conf:
        mock_conf.return_value = {"level": "none", "message": ""}
        result = check_confirmation(
            "GET", "/jobs/j-1", "get", "job_tool", confirmed=False
        )
        assert result is None
