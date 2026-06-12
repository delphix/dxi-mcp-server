"""
Unit tests for dataset_endpoints_tool.py.

Coverage targets:
  - check_confirmation: retention_check branches (lines 47-72)
  - Each action in each tool: missing required param → error dict
  - Each action in each tool: check_confirmation mocked to return conf → conf returned
  - register_tools error path (lines 2336-2337)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from dct_mcp_server.tools import dataset_endpoints_tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONF_STUB = {
    "status": "confirmation_required",
    "confirmation_level": "standard",
    "confirmation_message": "Confirm?",
    "action": "stub",
    "tool": "stub_tool",
    "api_path": "/stub",
    "instructions": "STOP",
}


# ---------------------------------------------------------------------------
# Category 1: check_confirmation standalone function
# ---------------------------------------------------------------------------


class TestCheckConfirmation:
    """Direct tests of the standalone check_confirmation function."""

    def _mock_conf(self, level, **kwargs):
        base = {"level": level, "conditional": False, "message": "Confirm {name}?"}
        base.update(kwargs)
        return base

    def test_no_confirmation_needed_returns_none(self):
        with patch(
            "dct_mcp_server.tools.dataset_endpoints_tool.get_confirmation_for_operation",
            return_value={"level": "none"},
        ):
            result = dataset_endpoints_tool.check_confirmation(
                "GET", "/vdbs/v-1", "get", "vdb_tool", confirmed=False
            )
        assert result is None

    def test_confirmed_true_returns_none(self):
        conf = self._mock_conf("standard")
        with patch(
            "dct_mcp_server.tools.dataset_endpoints_tool.get_confirmation_for_operation",
            return_value=conf,
        ):
            result = dataset_endpoints_tool.check_confirmation(
                "DELETE", "/vdbs/v-1", "delete", "vdb_tool", confirmed=True
            )
        assert result is None

    def test_standard_not_confirmed_returns_dict(self):
        conf = self._mock_conf("standard", message="Confirm delete {name}?")
        with patch(
            "dct_mcp_server.tools.dataset_endpoints_tool.get_confirmation_for_operation",
            return_value=conf,
        ):
            result = dataset_endpoints_tool.check_confirmation(
                "DELETE", "/vdbs/v-1", "delete", "vdb_tool", confirmed=False,
                context={"name": "my-vdb"}
            )
        assert result is not None
        assert result["status"] == "confirmation_required"
        assert "my-vdb" in result["confirmation_message"]
        assert result["action"] == "delete"
        assert result["tool"] == "vdb_tool"
        assert result["api_path"] == "/vdbs/v-1"

    def test_standard_message_no_context(self):
        conf = self._mock_conf("standard", message="Confirm?")
        with patch(
            "dct_mcp_server.tools.dataset_endpoints_tool.get_confirmation_for_operation",
            return_value=conf,
        ):
            result = dataset_endpoints_tool.check_confirmation(
                "DELETE", "/vdbs/v-1", "delete", "vdb_tool", confirmed=False
            )
        assert result is not None
        assert result["confirmation_message"] == "Confirm?"

    # retention_check branch: retain_forever → skip (line 52)
    def test_retention_check_retain_forever_returns_none(self):
        conf = {
            "level": "retention_check",
            "conditional": True,
            "threshold_days": 7,
            "message": "Deletes in {days} days",
        }
        with patch(
            "dct_mcp_server.tools.dataset_endpoints_tool.get_confirmation_for_operation",
            return_value=conf,
        ):
            result = dataset_endpoints_tool.check_confirmation(
                "PATCH", "/bookmarks/b-1", "update", "bookmark_tool",
                confirmed=False,
                context={"retain_forever": True},
            )
        assert result is None

    # retention_check branch: expiration far future → skip (line 59)
    def test_retention_check_expiration_far_future_returns_none(self):
        conf = {
            "level": "retention_check",
            "conditional": True,
            "threshold_days": 7,
            "message": "Deletes in {days} days",
        }
        with patch(
            "dct_mcp_server.tools.dataset_endpoints_tool.get_confirmation_for_operation",
            return_value=conf,
        ):
            result = dataset_endpoints_tool.check_confirmation(
                "PATCH", "/bookmarks/b-1", "update", "bookmark_tool",
                confirmed=False,
                context={"expiration_date": "2099-12-31T00:00:00Z"},
            )
        assert result is None

    # retention_check branch: expiration near future → return confirmation (lines 60-61, 68-72)
    def test_retention_check_expiration_near_future_returns_dict(self):
        conf = {
            "level": "retention_check",
            "conditional": True,
            "threshold_days": 36500,  # huge threshold so any date is "near"
            "message": "Deletes in {days} days. Bookmark: {name}",
        }
        with patch(
            "dct_mcp_server.tools.dataset_endpoints_tool.get_confirmation_for_operation",
            return_value=conf,
        ):
            result = dataset_endpoints_tool.check_confirmation(
                "PATCH", "/bookmarks/b-1", "update", "bookmark_tool",
                confirmed=False,
                context={"name": "bm-1", "expiration_date": "2025-01-01T00:00:00Z"},
            )
        assert result is not None
        assert result["status"] == "confirmation_required"
        assert "bm-1" in result["confirmation_message"]

    # retention_check: invalid date → ValueError caught, falls through (lines 62-63)
    def test_retention_check_invalid_date_returns_dict(self):
        conf = {
            "level": "retention_check",
            "conditional": True,
            "threshold_days": 7,
            "message": "Warning: {days} days",
        }
        with patch(
            "dct_mcp_server.tools.dataset_endpoints_tool.get_confirmation_for_operation",
            return_value=conf,
        ):
            result = dataset_endpoints_tool.check_confirmation(
                "PATCH", "/bookmarks/b-1", "update", "bookmark_tool",
                confirmed=False,
                context={"expiration_date": "not-a-valid-date"},
            )
        # Falls through to return confirmation_required
        assert result is not None
        assert result["status"] == "confirmation_required"

    # retention_check: no context → falls through to confirmation
    def test_retention_check_no_context_returns_dict(self):
        conf = {
            "level": "retention_check",
            "conditional": True,
            "threshold_days": 7,
            "message": "Warn",
        }
        with patch(
            "dct_mcp_server.tools.dataset_endpoints_tool.get_confirmation_for_operation",
            return_value=conf,
        ):
            result = dataset_endpoints_tool.check_confirmation(
                "PATCH", "/bookmarks/b-1", "update", "bookmark_tool",
                confirmed=False,
                context=None,
            )
        assert result is not None

    # retention_check: context without expiration_date → falls through
    def test_retention_check_context_without_expiration_falls_through(self):
        conf = {
            "level": "retention_check",
            "conditional": True,
            "threshold_days": 7,
            "message": "Warn",
        }
        with patch(
            "dct_mcp_server.tools.dataset_endpoints_tool.get_confirmation_for_operation",
            return_value=conf,
        ):
            result = dataset_endpoints_tool.check_confirmation(
                "PATCH", "/bookmarks/b-1", "update", "bookmark_tool",
                confirmed=False,
                context={"name": "bm"},
            )
        assert result is not None

    # SafeDict: missing placeholder stays readable
    def test_message_with_missing_placeholder(self):
        conf = self._mock_conf("standard", message="Delete {name} and {unknown_key}?")
        with patch(
            "dct_mcp_server.tools.dataset_endpoints_tool.get_confirmation_for_operation",
            return_value=conf,
        ):
            result = dataset_endpoints_tool.check_confirmation(
                "DELETE", "/vdbs/v-1", "delete", "vdb_tool", confirmed=False,
                context={"name": "my-vdb"}
            )
        assert "{unknown_key}" in result["confirmation_message"]


# ---------------------------------------------------------------------------
# Category 2 + 3: per-tool, per-action: missing required param & conf early-return
# ---------------------------------------------------------------------------

# Shared confirmation stub returned by monkeypatched check_confirmation
def _make_conf_stub(action, tool, api_path):
    return {
        "status": "confirmation_required",
        "confirmation_level": "standard",
        "confirmation_message": "Confirm?",
        "action": action,
        "tool": tool,
        "api_path": api_path,
        "instructions": "STOP",
    }


# ---------------------------------------------------------------------------
# vdb_tool
# ---------------------------------------------------------------------------

VDB_ACTIONS_NEED_VDB_ID = [
    "get", "start", "stop", "enable", "disable",
    "refresh_by_timestamp", "refresh_by_snapshot", "refresh_from_bookmark",
    "rollback_by_timestamp", "rollback_by_snapshot", "rollback_from_bookmark",
    "list_snapshots", "list_bookmarks", "get_tags", "add_tags", "delete_tags",
]

VDB_ALL_ACTIONS = ["search"] + VDB_ACTIONS_NEED_VDB_ID


class TestVdbTool:
    """Tests for vdb_tool: missing params and confirmation early-return."""

    @pytest.mark.parametrize("action", VDB_ACTIONS_NEED_VDB_ID)
    async def test_missing_vdb_id_returns_error(self, action, monkeypatch, mock_dct_client):
        monkeypatch.setattr(dataset_endpoints_tool, "client", mock_dct_client)
        result = await dataset_endpoints_tool.vdb_tool(action=action)
        assert isinstance(result, dict)
        assert "error" in result
        assert not mock_dct_client.make_request.called

    @pytest.mark.parametrize("action", VDB_ALL_ACTIONS)
    async def test_conf_early_return(self, action, monkeypatch, mock_dct_client):
        monkeypatch.setattr(dataset_endpoints_tool, "client", mock_dct_client)
        stub = _make_conf_stub(action, "vdb_tool", "/vdbs/stub")
        monkeypatch.setattr(dataset_endpoints_tool, "check_confirmation", lambda *a, **kw: stub)
        result = await dataset_endpoints_tool.vdb_tool(
            action=action, vdb_id="v-1", bookmark_id="b-1", tags=[{"key": "k", "value": "v"}]
        )
        assert result == stub
        assert not mock_dct_client.make_request.called

    async def test_unknown_action_returns_error(self, monkeypatch, mock_dct_client):
        monkeypatch.setattr(dataset_endpoints_tool, "client", mock_dct_client)
        result = await dataset_endpoints_tool.vdb_tool(action="nonexistent")
        assert "error" in result
        assert not mock_dct_client.make_request.called


# ---------------------------------------------------------------------------
# vdb_group_tool
# ---------------------------------------------------------------------------

VDB_GROUP_ACTIONS_NEED_GROUP_ID = [
    "get", "refresh", "refresh_from_bookmark", "refresh_by_snapshot",
    "refresh_by_timestamp", "rollback", "lock", "unlock", "start", "stop",
    "enable", "disable", "list_bookmarks", "get_tags", "add_tags", "delete_tags",
]

VDB_GROUP_ALL_ACTIONS = ["search"] + VDB_GROUP_ACTIONS_NEED_GROUP_ID


class TestVdbGroupTool:
    """Tests for vdb_group_tool: missing params and confirmation early-return."""

    @pytest.mark.parametrize("action", VDB_GROUP_ACTIONS_NEED_GROUP_ID)
    async def test_missing_vdb_group_id_returns_error(self, action, monkeypatch, mock_dct_client):
        monkeypatch.setattr(dataset_endpoints_tool, "client", mock_dct_client)
        result = await dataset_endpoints_tool.vdb_group_tool(action=action)
        assert isinstance(result, dict)
        assert "error" in result
        assert not mock_dct_client.make_request.called

    @pytest.mark.parametrize("action", VDB_GROUP_ALL_ACTIONS)
    async def test_conf_early_return(self, action, monkeypatch, mock_dct_client):
        monkeypatch.setattr(dataset_endpoints_tool, "client", mock_dct_client)
        stub = _make_conf_stub(action, "vdb_group_tool", "/vdb-groups/stub")
        monkeypatch.setattr(dataset_endpoints_tool, "check_confirmation", lambda *a, **kw: stub)
        result = await dataset_endpoints_tool.vdb_group_tool(
            action=action, vdb_group_id="g-1", bookmark_id="b-1",
            tags=[{"key": "k", "value": "v"}]
        )
        assert result == stub
        assert not mock_dct_client.make_request.called

    async def test_unknown_action_returns_error(self, monkeypatch, mock_dct_client):
        monkeypatch.setattr(dataset_endpoints_tool, "client", mock_dct_client)
        result = await dataset_endpoints_tool.vdb_group_tool(action="nonexistent")
        assert "error" in result
        assert not mock_dct_client.make_request.called


# ---------------------------------------------------------------------------
# dsource_tool
# ---------------------------------------------------------------------------

DSOURCE_ACTIONS_NEED_DSOURCE_ID = ["get", "list_snapshots", "get_tags"]

DSOURCE_ALL_ACTIONS = ["search"] + DSOURCE_ACTIONS_NEED_DSOURCE_ID


class TestDsourceTool:
    """Tests for dsource_tool: missing params and confirmation early-return."""

    @pytest.mark.parametrize("action", DSOURCE_ACTIONS_NEED_DSOURCE_ID)
    async def test_missing_dsource_id_returns_error(self, action, monkeypatch, mock_dct_client):
        monkeypatch.setattr(dataset_endpoints_tool, "client", mock_dct_client)
        result = await dataset_endpoints_tool.dsource_tool(action=action)
        assert isinstance(result, dict)
        assert "error" in result
        assert not mock_dct_client.make_request.called

    @pytest.mark.parametrize("action", DSOURCE_ALL_ACTIONS)
    async def test_conf_early_return(self, action, monkeypatch, mock_dct_client):
        monkeypatch.setattr(dataset_endpoints_tool, "client", mock_dct_client)
        stub = _make_conf_stub(action, "dsource_tool", "/dsources/stub")
        monkeypatch.setattr(dataset_endpoints_tool, "check_confirmation", lambda *a, **kw: stub)
        result = await dataset_endpoints_tool.dsource_tool(
            action=action, dsource_id="ds-1"
        )
        assert result == stub
        assert not mock_dct_client.make_request.called

    async def test_unknown_action_returns_error(self, monkeypatch, mock_dct_client):
        monkeypatch.setattr(dataset_endpoints_tool, "client", mock_dct_client)
        result = await dataset_endpoints_tool.dsource_tool(action="nonexistent")
        assert "error" in result
        assert not mock_dct_client.make_request.called


# ---------------------------------------------------------------------------
# snapshot_tool
# ---------------------------------------------------------------------------

SNAPSHOT_ACTIONS_NEED_SNAPSHOT_ID = [
    "get", "get_timeflow_range", "get_runtime", "get_tags", "add_tags", "delete_tags",
]

SNAPSHOT_ALL_ACTIONS = [
    "search", "find_by_location", "find_by_timestamp",
] + SNAPSHOT_ACTIONS_NEED_SNAPSHOT_ID


class TestSnapshotTool:
    """Tests for snapshot_tool: missing params and confirmation early-return."""

    @pytest.mark.parametrize("action", SNAPSHOT_ACTIONS_NEED_SNAPSHOT_ID)
    async def test_missing_snapshot_id_returns_error(self, action, monkeypatch, mock_dct_client):
        monkeypatch.setattr(dataset_endpoints_tool, "client", mock_dct_client)
        result = await dataset_endpoints_tool.snapshot_tool(action=action)
        assert isinstance(result, dict)
        assert "error" in result
        assert not mock_dct_client.make_request.called

    @pytest.mark.parametrize("action", SNAPSHOT_ALL_ACTIONS)
    async def test_conf_early_return(self, action, monkeypatch, mock_dct_client):
        monkeypatch.setattr(dataset_endpoints_tool, "client", mock_dct_client)
        stub = _make_conf_stub(action, "snapshot_tool", "/snapshots/stub")
        monkeypatch.setattr(dataset_endpoints_tool, "check_confirmation", lambda *a, **kw: stub)
        result = await dataset_endpoints_tool.snapshot_tool(
            action=action, snapshot_id="s-1", tags=[{"key": "k", "value": "v"}]
        )
        assert result == stub
        assert not mock_dct_client.make_request.called

    async def test_unknown_action_returns_error(self, monkeypatch, mock_dct_client):
        monkeypatch.setattr(dataset_endpoints_tool, "client", mock_dct_client)
        result = await dataset_endpoints_tool.snapshot_tool(action="nonexistent")
        assert "error" in result
        assert not mock_dct_client.make_request.called


# ---------------------------------------------------------------------------
# bookmark_tool
# ---------------------------------------------------------------------------

BOOKMARK_ACTIONS_NEED_BOOKMARK_ID = [
    "get", "update", "delete", "get_vdb_groups", "get_tags", "add_tags", "delete_tags",
]

BOOKMARK_ALL_ACTIONS = ["search", "create"] + BOOKMARK_ACTIONS_NEED_BOOKMARK_ID


class TestBookmarkTool:
    """Tests for bookmark_tool: missing params and confirmation early-return."""

    @pytest.mark.parametrize("action", BOOKMARK_ACTIONS_NEED_BOOKMARK_ID)
    async def test_missing_bookmark_id_returns_error(self, action, monkeypatch, mock_dct_client):
        monkeypatch.setattr(dataset_endpoints_tool, "client", mock_dct_client)
        result = await dataset_endpoints_tool.bookmark_tool(action=action)
        assert isinstance(result, dict)
        assert "error" in result
        assert not mock_dct_client.make_request.called

    @pytest.mark.parametrize("action", BOOKMARK_ALL_ACTIONS)
    async def test_conf_early_return(self, action, monkeypatch, mock_dct_client):
        monkeypatch.setattr(dataset_endpoints_tool, "client", mock_dct_client)
        stub = _make_conf_stub(action, "bookmark_tool", "/bookmarks/stub")
        monkeypatch.setattr(dataset_endpoints_tool, "check_confirmation", lambda *a, **kw: stub)
        result = await dataset_endpoints_tool.bookmark_tool(
            action=action, bookmark_id="b-1", name="my-bookmark",
            tags=[{"key": "k", "value": "v"}]
        )
        assert result == stub
        assert not mock_dct_client.make_request.called

    async def test_unknown_action_returns_error(self, monkeypatch, mock_dct_client):
        monkeypatch.setattr(dataset_endpoints_tool, "client", mock_dct_client)
        result = await dataset_endpoints_tool.bookmark_tool(action="nonexistent")
        assert "error" in result
        assert not mock_dct_client.make_request.called


# ---------------------------------------------------------------------------
# timeflow_tool
# ---------------------------------------------------------------------------

TIMEFLOW_ACTIONS_NEED_TIMEFLOW_ID = [
    "get", "update", "delete", "get_snapshot_day_range", "repair",
    "get_tags", "add_tags", "delete_tags",
]

TIMEFLOW_ALL_ACTIONS = ["list", "search"] + TIMEFLOW_ACTIONS_NEED_TIMEFLOW_ID


class TestTimeflowTool:
    """Tests for timeflow_tool: missing params and confirmation early-return."""

    @pytest.mark.parametrize("action", TIMEFLOW_ACTIONS_NEED_TIMEFLOW_ID)
    async def test_missing_timeflow_id_returns_error(self, action, monkeypatch, mock_dct_client):
        monkeypatch.setattr(dataset_endpoints_tool, "client", mock_dct_client)
        result = await dataset_endpoints_tool.timeflow_tool(action=action)
        assert isinstance(result, dict)
        assert "error" in result
        assert not mock_dct_client.make_request.called

    @pytest.mark.parametrize("action", TIMEFLOW_ALL_ACTIONS)
    async def test_conf_early_return(self, action, monkeypatch, mock_dct_client):
        monkeypatch.setattr(dataset_endpoints_tool, "client", mock_dct_client)
        stub = _make_conf_stub(action, "timeflow_tool", "/timeflows/stub")
        monkeypatch.setattr(dataset_endpoints_tool, "check_confirmation", lambda *a, **kw: stub)
        result = await dataset_endpoints_tool.timeflow_tool(
            action=action, timeflow_id="tf-1",
            tags=[{"key": "k", "value": "v"}],
            host="h", username="u", directory="/d",
            start_location="0:0", end_location="1:0",
        )
        assert result == stub
        assert not mock_dct_client.make_request.called

    async def test_unknown_action_returns_error(self, monkeypatch, mock_dct_client):
        monkeypatch.setattr(dataset_endpoints_tool, "client", mock_dct_client)
        result = await dataset_endpoints_tool.timeflow_tool(action="nonexistent")
        assert "error" in result
        assert not mock_dct_client.make_request.called


# ---------------------------------------------------------------------------
# Category 4: register_tools error path (lines 2336-2337)
# ---------------------------------------------------------------------------


class TestRegisterTools:
    """Tests for the register_tools function."""

    def test_register_tools_success(self):
        app = MagicMock()
        dct_client = MagicMock()
        dataset_endpoints_tool.register_tools(app, dct_client)
        assert dataset_endpoints_tool.client is dct_client
        assert app.add_tool.call_count == 6

    def test_register_tools_logs_error_on_exception(self):
        """When app.add_tool raises, register_tools catches and logs; does not raise."""
        app = MagicMock()
        app.add_tool.side_effect = RuntimeError("tool registration failed")
        dct_client = MagicMock()
        # Should not raise
        dataset_endpoints_tool.register_tools(app, dct_client)

    def test_register_tools_sets_global_client(self):
        app = MagicMock()
        sentinel = MagicMock()
        dataset_endpoints_tool.register_tools(app, sentinel)
        assert dataset_endpoints_tool.client is sentinel
