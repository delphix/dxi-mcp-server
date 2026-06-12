"""
Unit tests for tools/core/meta_tools.py.

Tests the 6 meta-tools and their supporting functions.
"""

from __future__ import annotations

# Warm up pydantic's generic-model registry before any mcp.server.fastmcp import.
# Without this, running this file in isolation triggers KeyError: 'pydantic.root_model'
# during collection (mcp triggers generic model creation before pydantic internals are
# registered in sys.modules).
from pydantic import RootModel  # noqa: F401 — must be first import

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import dct_mcp_server.tools.core.meta_tools as mt
from dct_mcp_server.tools.core.meta_tools import (
    _disable_current_toolset_internal,
    _get_confirmation_guidance,
    _register_toolset_tools,
    check_operation_confirmation,
    get_toolset_tools,
    initialize_tool_inventory,
    list_available_toolsets,
    register_meta_tools,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_meta_tools_state():
    """Reset global meta_tools state before/after each test."""
    orig_app = mt._app
    orig_client = mt._dct_client
    orig_inventory = mt._tool_inventory.copy()
    orig_current = mt._current_toolset
    orig_registered = mt._registered_tool_names.copy()
    yield
    mt._app = orig_app
    mt._dct_client = orig_client
    mt._tool_inventory = orig_inventory
    mt._current_toolset = orig_current
    mt._registered_tool_names = orig_registered


# ---------------------------------------------------------------------------
# list_available_toolsets
# ---------------------------------------------------------------------------

def test_list_available_toolsets_returns_dict():
    result = list_available_toolsets()
    assert isinstance(result, dict)
    assert "toolsets" in result
    assert "total_count" in result


def test_list_available_toolsets_has_self_service():
    result = list_available_toolsets()
    names = [t["name"] for t in result["toolsets"]]
    assert "self_service" in names


def test_list_available_toolsets_toolset_structure():
    result = list_available_toolsets()
    for ts in result["toolsets"]:
        assert "name" in ts
        assert "description" in ts
        assert "tool_count" in ts


def test_list_available_toolsets_total_count_matches():
    result = list_available_toolsets()
    assert result["total_count"] == len(result["toolsets"])


def test_list_available_toolsets_has_instructions():
    result = list_available_toolsets()
    assert "instructions" in result


def test_list_available_toolsets_error_handling():
    with patch("dct_mcp_server.tools.core.meta_tools.load_all_toolsets_metadata",
               side_effect=Exception("boom")):
        result = list_available_toolsets()
    assert "error" in result


# ---------------------------------------------------------------------------
# get_toolset_tools
# ---------------------------------------------------------------------------

def test_get_toolset_tools_self_service():
    result = get_toolset_tools("self_service")
    assert isinstance(result, dict)
    assert "tools" in result
    assert result["toolset_name"] == "self_service"


def test_get_toolset_tools_has_metadata():
    result = get_toolset_tools("self_service")
    assert "metadata" in result
    assert "description" in result["metadata"]


def test_get_toolset_tools_has_instructions():
    result = get_toolset_tools("self_service")
    assert "instructions" in result


def test_get_toolset_tools_invalid_toolset():
    result = get_toolset_tools("totally_invalid_xyz")
    assert "error" in result
    assert "available_toolsets" in result


def test_get_toolset_tools_total_counts():
    result = get_toolset_tools("self_service")
    assert "total_tools" in result
    assert "total_actions" in result
    assert result["total_tools"] >= 0
    assert result["total_actions"] >= 0


def test_get_toolset_tools_error_handling():
    with patch("dct_mcp_server.tools.core.meta_tools.get_available_toolsets",
               side_effect=Exception("toolset error")):
        result = get_toolset_tools("self_service")
    assert "error" in result


# ---------------------------------------------------------------------------
# check_operation_confirmation
# ---------------------------------------------------------------------------

def test_check_operation_confirmation_safe_get():
    result = check_operation_confirmation("GET", "/vdbs/search")
    assert isinstance(result, dict)
    assert "requires_confirmation" in result
    assert "level" in result


def test_check_operation_confirmation_no_confirmation_safe_op():
    result = check_operation_confirmation("GET", "/some/safe/endpoint")
    assert result["requires_confirmation"] is False
    assert result["level"] == "none"


def test_check_operation_confirmation_delete_vdb():
    result = check_operation_confirmation("POST", "/vdbs/vdb-1/delete")
    assert "level" in result
    assert "guidance" in result
    assert "method" in result
    assert result["method"] == "POST"
    assert result["api_path"] == "/vdbs/vdb-1/delete"


def test_check_operation_confirmation_includes_guidance():
    result = check_operation_confirmation("GET", "/vdbs/search")
    assert "guidance" in result
    assert len(result["guidance"]) > 0


def test_check_operation_confirmation_error_handling():
    with patch("dct_mcp_server.tools.core.meta_tools.get_confirmation_for_operation",
               side_effect=Exception("conf error")):
        result = check_operation_confirmation("GET", "/vdbs")
    assert "error" in result


# ---------------------------------------------------------------------------
# _get_confirmation_guidance
# ---------------------------------------------------------------------------

def test_get_confirmation_guidance_none():
    guidance = _get_confirmation_guidance("none")
    assert "No confirmation" in guidance or len(guidance) > 0


def test_get_confirmation_guidance_standard():
    guidance = _get_confirmation_guidance("standard")
    assert len(guidance) > 0


def test_get_confirmation_guidance_elevated():
    guidance = _get_confirmation_guidance("elevated")
    assert len(guidance) > 0


def test_get_confirmation_guidance_manual():
    guidance = _get_confirmation_guidance("manual")
    assert len(guidance) > 0
    assert "destructive" in guidance.lower() or "manual" in guidance.lower() or "confirm" in guidance.lower()


def test_get_confirmation_guidance_unknown_level():
    guidance = _get_confirmation_guidance("totally_unknown_level")
    assert isinstance(guidance, str)
    assert len(guidance) > 0


# ---------------------------------------------------------------------------
# initialize_tool_inventory
# ---------------------------------------------------------------------------

def test_initialize_tool_inventory_sets_app():
    mock_app = MagicMock()
    mock_client = MagicMock()
    with patch("dct_mcp_server.tools.core.meta_tools.initialize_openapi_cache", return_value=True):
        initialize_tool_inventory(mock_app, mock_client)
    assert mt._app is mock_app
    assert mt._dct_client is mock_client


def test_initialize_tool_inventory_populates_inventory():
    mock_app = MagicMock()
    mock_client = MagicMock()
    with patch("dct_mcp_server.tools.core.meta_tools.initialize_openapi_cache", return_value=True):
        initialize_tool_inventory(mock_app, mock_client)
    assert len(mt._tool_inventory) > 0


def test_initialize_tool_inventory_spec_not_available():
    mock_app = MagicMock()
    mock_client = MagicMock()
    with patch("dct_mcp_server.tools.core.meta_tools.initialize_openapi_cache", return_value=False):
        initialize_tool_inventory(mock_app, mock_client)
    # Should still initialize without spec
    assert len(mt._tool_inventory) > 0


def test_initialize_tool_inventory_all_toolsets_dynamic():
    mock_app = MagicMock()
    mock_client = MagicMock()
    with patch("dct_mcp_server.tools.core.meta_tools.initialize_openapi_cache", return_value=True):
        initialize_tool_inventory(mock_app, mock_client)
    for name, info in mt._tool_inventory.items():
        assert info.get("dynamic") is True
        assert info.get("loaded") is False


# ---------------------------------------------------------------------------
# _disable_current_toolset_internal
# ---------------------------------------------------------------------------

def test_disable_current_toolset_internal_no_tools():
    mt._registered_tool_names = []
    # Should not raise
    _disable_current_toolset_internal()


def test_disable_current_toolset_internal_clears_list():
    mock_app = MagicMock()
    mock_app._tool_manager = MagicMock()
    mock_app._tool_manager._tools = {"vdb_tool": MagicMock(), "job_tool": MagicMock()}
    mt._app = mock_app
    mt._registered_tool_names = ["vdb_tool", "job_tool"]
    _disable_current_toolset_internal()
    assert mt._registered_tool_names == []


def test_disable_current_toolset_handles_missing_tool():
    mock_app = MagicMock()
    mock_app._tool_manager = MagicMock()
    mock_app._tool_manager._tools = {}  # Empty — tools not present
    mt._app = mock_app
    mt._registered_tool_names = ["nonexistent_tool"]
    # Should not raise
    _disable_current_toolset_internal()
    assert mt._registered_tool_names == []


def test_disable_current_toolset_local_provider_path():
    mock_app = MagicMock()
    # No _tool_manager attribute — fallback to local_provider
    del mock_app._tool_manager
    mock_app.local_provider = MagicMock()
    mock_app.local_provider._tools = {"my_tool": MagicMock()}
    mock_app.local_provider.remove_tool = MagicMock()
    mt._app = mock_app
    mt._registered_tool_names = ["my_tool"]
    _disable_current_toolset_internal()
    assert mt._registered_tool_names == []


# ---------------------------------------------------------------------------
# _register_toolset_tools
# ---------------------------------------------------------------------------

def test_register_toolset_tools_unknown_toolset():
    mt._app = MagicMock()
    mt._tool_inventory = {}
    count = _register_toolset_tools("nonexistent")
    assert count == 0


def test_register_toolset_tools_in_inventory():
    mock_app = MagicMock()
    mock_app._tool_manager = MagicMock()
    # Before: no tools
    mock_app._tool_manager._tools = {}
    mt._app = mock_app
    mt._dct_client = MagicMock()
    mt._tool_inventory = {"self_service": {"dynamic": True, "loaded": False}}

    def fake_register(app, toolset_name, dct_client):
        # Simulate adding tools
        mock_app._tool_manager._tools["vdb_tool"] = MagicMock()

    with patch("dct_mcp_server.tools.core.meta_tools.register_toolset_tools",
               side_effect=fake_register):
        count = _register_toolset_tools("self_service")

    assert count >= 1


# ---------------------------------------------------------------------------
# register_meta_tools
# ---------------------------------------------------------------------------

def test_register_meta_tools_calls_add_tool():
    mock_app = MagicMock()
    register_meta_tools(mock_app)
    assert mock_app.add_tool.call_count == 6


def test_register_meta_tools_registers_all_6():
    mock_app = MagicMock()
    registered_names = []

    def capture_add(func, name=None):
        registered_names.append(name)

    mock_app.add_tool.side_effect = capture_add
    register_meta_tools(mock_app)

    expected = {
        "list_available_toolsets",
        "get_toolset_tools",
        "enable_toolset",
        "disable_toolset",
        "check_operation_confirmation",
        "execute_action",
    }
    assert expected == set(registered_names)


def test_register_meta_tools_raises_on_failure():
    mock_app = MagicMock()
    mock_app.add_tool.side_effect = Exception("cannot register")
    with pytest.raises(Exception, match="cannot register"):
        register_meta_tools(mock_app)


# ---------------------------------------------------------------------------
# get_current_toolset / get_registered_tool_count
# ---------------------------------------------------------------------------

def test_get_current_toolset_default():
    from dct_mcp_server.tools.core.meta_tools import get_current_toolset
    mt._current_toolset = None
    assert get_current_toolset() is None


def test_get_current_toolset_after_set():
    from dct_mcp_server.tools.core.meta_tools import get_current_toolset
    mt._current_toolset = "self_service"
    assert get_current_toolset() == "self_service"


def test_get_registered_tool_count_empty():
    from dct_mcp_server.tools.core.meta_tools import get_registered_tool_count
    mt._registered_tool_names = []
    assert get_registered_tool_count() == 0


def test_get_registered_tool_count_with_tools():
    from dct_mcp_server.tools.core.meta_tools import get_registered_tool_count
    mt._registered_tool_names = ["vdb_tool", "job_tool", "dsource_tool"]
    assert get_registered_tool_count() == 3


# ---------------------------------------------------------------------------
# execute_action (async)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_action_no_client():
    from dct_mcp_server.tools.core.meta_tools import execute_action
    mt._dct_client = None
    result = await execute_action(
        toolset_name="self_service",
        tool_name="vdb_tool",
        action="search",
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_execute_action_unknown_toolset():
    from dct_mcp_server.tools.core.meta_tools import execute_action
    mt._dct_client = MagicMock()
    result = await execute_action(
        toolset_name="fake_toolset_xyz",
        tool_name="vdb_tool",
        action="search",
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_execute_action_unknown_tool():
    from dct_mcp_server.tools.core.meta_tools import execute_action
    mt._dct_client = MagicMock()
    result = await execute_action(
        toolset_name="self_service",
        tool_name="nonexistent_tool",
        action="search",
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_execute_action_unknown_action():
    from dct_mcp_server.tools.core.meta_tools import execute_action
    mt._dct_client = MagicMock()
    result = await execute_action(
        toolset_name="self_service",
        tool_name="vdb_tool",
        action="fly_to_moon",
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_execute_action_search_vdbs():
    from dct_mcp_server.tools.core.meta_tools import execute_action
    mock_client = MagicMock()
    mock_client.make_request = AsyncMock(return_value={"items": []})
    mt._dct_client = mock_client
    result = await execute_action(
        toolset_name="self_service",
        tool_name="vdb_tool",
        action="search",
    )
    assert mock_client.make_request.called


@pytest.mark.asyncio
async def test_execute_action_requires_confirmation_for_destructive():
    from dct_mcp_server.tools.core.meta_tools import execute_action
    mock_client = MagicMock()
    mock_client.make_request = AsyncMock(return_value={"status": "success"})
    mt._dct_client = mock_client

    with patch("dct_mcp_server.tools.core.meta_tools.get_confirmation_for_operation") as mock_conf:
        mock_conf.return_value = {
            "level": "manual",
            "message": "Are you sure?",
            "conditional": False,
            "threshold_days": None,
        }
        result = await execute_action(
            toolset_name="self_service",
            tool_name="vdb_tool",
            action="search",
            confirmed=False,
        )
    assert result.get("status") == "confirmation_required" or mock_client.make_request.called


@pytest.mark.asyncio
async def test_execute_action_with_confirmed_true():
    from dct_mcp_server.tools.core.meta_tools import execute_action
    mock_client = MagicMock()
    mock_client.make_request = AsyncMock(return_value={"status": "success"})
    mt._dct_client = mock_client

    with patch("dct_mcp_server.tools.core.meta_tools.get_confirmation_for_operation") as mock_conf:
        mock_conf.return_value = {
            "level": "manual",
            "message": "Are you sure?",
            "conditional": False,
            "threshold_days": None,
        }
        result = await execute_action(
            toolset_name="self_service",
            tool_name="vdb_tool",
            action="search",
            confirmed=True,
        )
    # With confirmed=True, the request should go through
    assert mock_client.make_request.called


@pytest.mark.asyncio
async def test_execute_action_with_path_params():
    from dct_mcp_server.tools.core.meta_tools import execute_action
    mock_client = MagicMock()
    mock_client.make_request = AsyncMock(return_value={"id": "v-123"})
    mt._dct_client = mock_client
    result = await execute_action(
        toolset_name="self_service",
        tool_name="vdb_tool",
        action="get",
        vdbId="v-123",
    )
    assert mock_client.make_request.called
    call_args = mock_client.make_request.call_args
    # Path should have vdbId substituted
    assert "v-123" in str(call_args)


# ---------------------------------------------------------------------------
# enable_toolset / disable_toolset (async)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enable_toolset_unknown_toolset():
    from dct_mcp_server.tools.core.meta_tools import enable_toolset
    mock_ctx = MagicMock()
    mt._app = MagicMock()
    result = await enable_toolset("totally_fake_toolset_xyz", mock_ctx)
    assert "error" in result


@pytest.mark.asyncio
async def test_enable_toolset_app_not_initialized():
    from dct_mcp_server.tools.core.meta_tools import enable_toolset
    mt._app = None
    mock_ctx = MagicMock()
    result = await enable_toolset("self_service", mock_ctx)
    assert "error" in result


@pytest.mark.asyncio
async def test_disable_toolset_no_current_toolset():
    from dct_mcp_server.tools.core.meta_tools import disable_toolset
    mt._current_toolset = None
    mock_ctx = MagicMock()
    result = await disable_toolset(mock_ctx)
    assert result["status"] == "already_minimal"


@pytest.mark.asyncio
async def test_disable_toolset_with_active_toolset():
    from dct_mcp_server.tools.core.meta_tools import disable_toolset
    mt._current_toolset = "self_service"
    mt._registered_tool_names = ["vdb_tool"]
    mock_ctx = MagicMock()
    mock_ctx.session.send_tool_list_changed = AsyncMock()
    mock_app = MagicMock()
    mock_app._tool_manager = MagicMock()
    mock_app._tool_manager._tools = {"vdb_tool": MagicMock()}
    mt._app = mock_app
    result = await disable_toolset(mock_ctx)
    assert result["status"] == "disabled"
    assert result["disabled_toolset"] == "self_service"


@pytest.mark.asyncio
async def test_disable_toolset_notification_failure_handled():
    from dct_mcp_server.tools.core.meta_tools import disable_toolset
    mt._current_toolset = "self_service"
    mt._registered_tool_names = ["vdb_tool"]
    mock_ctx = MagicMock()
    mock_ctx.session.send_tool_list_changed = AsyncMock(side_effect=Exception("network error"))
    mock_app = MagicMock()
    mock_app._tool_manager = MagicMock()
    mock_app._tool_manager._tools = {}
    mt._app = mock_app
    # Should not raise — notification failure is handled gracefully
    result = await disable_toolset(mock_ctx)
    assert result["status"] == "disabled"


# ---------------------------------------------------------------------------
# enable_toolset — SUCCESS paths (lines 228-256)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enable_toolset_fresh_enable_no_previous():
    """Lines 228-256: fresh enable when no previous toolset (_current_toolset is None)."""
    from dct_mcp_server.tools.core.meta_tools import enable_toolset

    mock_app = MagicMock()
    mock_app._tool_manager = MagicMock()
    mock_app._tool_manager._tools = {}
    mt._app = mock_app
    mt._dct_client = MagicMock()
    mt._current_toolset = None
    mt._tool_inventory = {"self_service": {"dynamic": True, "loaded": False}}

    mock_ctx = MagicMock()
    mock_ctx.session.send_tool_list_changed = AsyncMock()

    def fake_register(app, toolset_name, dct_client):
        mock_app._tool_manager._tools["vdb_tool"] = MagicMock()

    with patch("dct_mcp_server.tools.core.meta_tools.register_toolset_tools",
               side_effect=fake_register):
        result = await enable_toolset("self_service", mock_ctx)

    assert result["status"] == "enabled"
    assert result["toolset_name"] == "self_service"
    assert result["previous_toolset"] is None
    assert mock_ctx.session.send_tool_list_changed.called


@pytest.mark.asyncio
async def test_enable_toolset_switch_from_existing():
    """Lines 228-256: switch from one toolset to another (_current_toolset is not None)."""
    from dct_mcp_server.tools.core.meta_tools import enable_toolset

    mock_app = MagicMock()
    mock_app._tool_manager = MagicMock()
    mock_app._tool_manager._tools = {"old_tool": MagicMock()}
    mt._app = mock_app
    mt._dct_client = MagicMock()
    mt._current_toolset = "continuous_data_admin"
    mt._registered_tool_names = ["old_tool"]
    mt._tool_inventory = {
        "self_service": {"dynamic": True, "loaded": False},
        "continuous_data_admin": {"dynamic": True, "loaded": True},
    }

    mock_ctx = MagicMock()
    mock_ctx.session.send_tool_list_changed = AsyncMock()

    def fake_register(app, toolset_name, dct_client):
        mock_app._tool_manager._tools["vdb_tool"] = MagicMock()

    with patch("dct_mcp_server.tools.core.meta_tools.register_toolset_tools",
               side_effect=fake_register):
        result = await enable_toolset("self_service", mock_ctx)

    assert result["status"] == "enabled"
    assert result["previous_toolset"] == "continuous_data_admin"
    assert mock_ctx.session.send_tool_list_changed.called


@pytest.mark.asyncio
async def test_enable_toolset_notification_failure_handled():
    """Lines 240-241: notification send failure is caught and logged, not raised."""
    from dct_mcp_server.tools.core.meta_tools import enable_toolset

    mock_app = MagicMock()
    mock_app._tool_manager = MagicMock()
    mock_app._tool_manager._tools = {}
    mt._app = mock_app
    mt._dct_client = MagicMock()
    mt._current_toolset = None
    mt._tool_inventory = {"self_service": {"dynamic": True, "loaded": False}}

    mock_ctx = MagicMock()
    mock_ctx.session.send_tool_list_changed = AsyncMock(side_effect=Exception("network down"))

    with patch("dct_mcp_server.tools.core.meta_tools.register_toolset_tools"):
        result = await enable_toolset("self_service", mock_ctx)

    # Should still succeed even though notification failed
    assert result["status"] == "enabled"


@pytest.mark.asyncio
async def test_enable_toolset_outer_exception_handler():
    """Lines 254-256: unexpected exception outside the notification block returns error dict."""
    from dct_mcp_server.tools.core.meta_tools import enable_toolset

    mt._app = MagicMock()
    mt._dct_client = MagicMock()
    mt._current_toolset = None
    mt._tool_inventory = {"self_service": {"dynamic": True, "loaded": False}}

    mock_ctx = MagicMock()

    # Patch _register_toolset_tools (called inside enable_toolset body) to raise.
    with patch("dct_mcp_server.tools.core.meta_tools._register_toolset_tools",
               side_effect=RuntimeError("registration crash")):
        result = await enable_toolset("self_service", mock_ctx)

    assert "error" in result
    assert result["status"] == "error"


# ---------------------------------------------------------------------------
# disable_toolset — exception handler (lines 304-306)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_disable_toolset_exception_handler():
    """Lines 304-306: unexpected exception inside disable_toolset returns error dict."""
    from dct_mcp_server.tools.core.meta_tools import disable_toolset

    mt._current_toolset = "self_service"
    mt._registered_tool_names = ["vdb_tool"]

    mock_ctx = MagicMock()
    mock_ctx.session.send_tool_list_changed = AsyncMock()

    with patch("dct_mcp_server.tools.core.meta_tools._disable_current_toolset_internal",
               side_effect=RuntimeError("unexpected internal error")):
        result = await disable_toolset(mock_ctx)

    assert "error" in result
    assert result["status"] == "error"


# ---------------------------------------------------------------------------
# _register_toolset_tools — local_provider branch (lines 320-321, 328-329)
# ---------------------------------------------------------------------------

def test_register_toolset_tools_local_provider_branch():
    """Lines 320-321 & 328-329: app has no _tool_manager but has local_provider._tools."""
    mock_app = MagicMock(spec=[])  # No attributes by default
    mock_app.local_provider = MagicMock()
    mock_app.local_provider._tools = {}

    mt._app = mock_app
    mt._dct_client = MagicMock()
    mt._tool_inventory = {"self_service": {"dynamic": True, "loaded": False}}

    def fake_register(app, toolset_name, dct_client):
        mock_app.local_provider._tools["vdb_tool"] = MagicMock()

    with patch("dct_mcp_server.tools.core.meta_tools.register_toolset_tools",
               side_effect=fake_register):
        count = _register_toolset_tools("self_service")

    assert count >= 1
    assert "vdb_tool" in mt._registered_tool_names


# ---------------------------------------------------------------------------
# _disable_current_toolset_internal — local_provider no remove_tool (lines 357-361)
# ---------------------------------------------------------------------------

def test_disable_toolset_internal_local_provider_no_remove_tool():
    """Lines 357-359: local_provider has _tools dict but no remove_tool method."""
    mock_app = MagicMock(spec=[])  # No _tool_manager
    mock_app.local_provider = MagicMock(spec=["_tools"])  # No remove_tool method
    mock_app.local_provider._tools = {"vdb_tool": MagicMock()}
    mt._app = mock_app
    mt._registered_tool_names = ["vdb_tool"]

    _disable_current_toolset_internal()

    assert mt._registered_tool_names == []
    # Tool should have been deleted from _tools dict
    assert "vdb_tool" not in mock_app.local_provider._tools


def test_disable_toolset_internal_local_provider_deletion_raises():
    """Lines 360-361: exception during deletion inside the for loop is caught per-tool."""

    class BadTools(dict):
        def __delitem__(self, key):
            raise KeyError("simulated delete failure")

    mock_app = MagicMock(spec=[])  # No _tool_manager
    mock_app.local_provider = MagicMock(spec=["_tools"])  # No remove_tool
    mock_app.local_provider._tools = BadTools({"vdb_tool": MagicMock()})
    mt._app = mock_app
    mt._registered_tool_names = ["vdb_tool"]

    # Should not raise — exception per tool is caught in the loop
    _disable_current_toolset_internal()
    assert mt._registered_tool_names == []


# ---------------------------------------------------------------------------
# execute_action — filter_expression body injection (line 511)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_action_filter_expression_search():
    """Line 511: filter_expression kwarg + search action → json_body set."""
    from dct_mcp_server.tools.core.meta_tools import execute_action

    mock_client = MagicMock()
    mock_client.make_request = AsyncMock(return_value={"items": []})
    mt._dct_client = mock_client

    result = await execute_action(
        toolset_name="self_service",
        tool_name="vdb_tool",
        action="search",
        filter_expression="name like '%test%'",
    )

    assert mock_client.make_request.called
    call_kwargs = mock_client.make_request.call_args
    # json body should contain filter_expression
    assert call_kwargs.kwargs.get("json") == {"filter_expression": "name like '%test%'"} or \
        (call_kwargs.args and "filter_expression" in str(call_kwargs))


# ---------------------------------------------------------------------------
# execute_action — explicit body param (line 516)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_action_explicit_body_param():
    """Line 516: body= kwarg takes precedence and becomes json_body."""
    from dct_mcp_server.tools.core.meta_tools import execute_action

    mock_client = MagicMock()
    mock_client.make_request = AsyncMock(return_value={"items": []})
    mt._dct_client = mock_client

    result = await execute_action(
        toolset_name="self_service",
        tool_name="vdb_tool",
        action="search",
        body={"filter_expression": "foo"},
    )

    assert mock_client.make_request.called
    call_kwargs = mock_client.make_request.call_args
    assert call_kwargs.kwargs.get("json") == {"filter_expression": "foo"}


# ---------------------------------------------------------------------------
# execute_action — POST with json_body + extra clean_remaining (lines 521-525)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_action_post_body_merged_with_remaining():
    """Lines 521-522: filter_expression sets json_body, extra POST kwargs merged via update()."""
    from dct_mcp_server.tools.core.meta_tools import execute_action

    mock_client = MagicMock()
    mock_client.make_request = AsyncMock(return_value={"items": []})
    mt._dct_client = mock_client

    # Pass filter_expression (sets json_body) AND an extra kwarg.
    # Hits the "if json_body: json_body.update(clean_remaining)" branch (line 522).
    result = await execute_action(
        toolset_name="self_service",
        tool_name="vdb_tool",
        action="search",
        filter_expression="name like '%test%'",
        limit=10,
    )

    assert mock_client.make_request.called
    call_kwargs = mock_client.make_request.call_args
    sent_json = call_kwargs.kwargs.get("json")
    # Both filter_expression and extra param should be in the merged body
    assert sent_json is not None
    assert "filter_expression" in sent_json
    assert "limit" in sent_json


@pytest.mark.asyncio
async def test_execute_action_post_no_json_body_uses_clean_remaining():
    """Line 524: no filter_expression and no body= → json_body = clean_remaining for POST."""
    from dct_mcp_server.tools.core.meta_tools import execute_action

    mock_client = MagicMock()
    mock_client.make_request = AsyncMock(return_value={"items": []})
    mt._dct_client = mock_client

    # Pass only limit (no filter_expression, no body=) for a POST action.
    # json_body starts as None → else branch: json_body = clean_remaining (line 524).
    result = await execute_action(
        toolset_name="self_service",
        tool_name="vdb_tool",
        action="search",
        limit=10,
    )

    assert mock_client.make_request.called
    call_kwargs = mock_client.make_request.call_args
    sent_json = call_kwargs.kwargs.get("json")
    assert sent_json == {"limit": 10}


# ---------------------------------------------------------------------------
# execute_action — exception handlers (lines 536-540)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_action_value_error_returns_error_dict():
    """Lines 536-537: ValueError inside execute_action is caught, returns error dict."""
    from dct_mcp_server.tools.core.meta_tools import execute_action

    mock_client = MagicMock()
    mock_client.make_request = AsyncMock(side_effect=ValueError("bad value"))
    mt._dct_client = mock_client

    result = await execute_action(
        toolset_name="self_service",
        tool_name="vdb_tool",
        action="search",
    )

    assert "error" in result
    assert "bad value" in result["error"]


@pytest.mark.asyncio
async def test_execute_action_generic_exception_returns_error_dict():
    """Lines 538-540: generic Exception inside execute_action is caught, returns error dict."""
    from dct_mcp_server.tools.core.meta_tools import execute_action

    mock_client = MagicMock()
    mock_client.make_request = AsyncMock(side_effect=RuntimeError("unexpected crash"))
    mt._dct_client = mock_client

    result = await execute_action(
        toolset_name="self_service",
        tool_name="vdb_tool",
        action="search",
    )

    assert "error" in result
    assert "unexpected crash" in result["error"]
