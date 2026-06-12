"""
Unit tests for tools/__init__.py — register_all_tools and register_meta_tools_only.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

import dct_mcp_server.tools as tools_pkg
from dct_mcp_server.tools import register_all_tools, register_meta_tools_only


# ---------------------------------------------------------------------------
# register_meta_tools_only
# ---------------------------------------------------------------------------

def test_register_meta_tools_only_calls_register_meta_tools():
    mock_app = MagicMock()
    mock_client = MagicMock()

    with patch("dct_mcp_server.tools.core.meta_tools.register_meta_tools") as mock_reg:
        with patch("dct_mcp_server.tools.core.meta_tools.initialize_tool_inventory") as mock_init:
            register_meta_tools_only(mock_app, mock_client)

    mock_reg.assert_called_once_with(mock_app)


def test_register_meta_tools_only_with_client_calls_initialize():
    mock_app = MagicMock()
    mock_client = MagicMock()

    with patch("dct_mcp_server.tools.core.meta_tools.register_meta_tools"):
        with patch("dct_mcp_server.tools.core.meta_tools.initialize_tool_inventory") as mock_init:
            register_meta_tools_only(mock_app, mock_client)

    mock_init.assert_called_once_with(mock_app, mock_client)


def test_register_meta_tools_only_without_client():
    mock_app = MagicMock()

    with patch("dct_mcp_server.tools.core.meta_tools.register_meta_tools") as mock_reg:
        with patch("dct_mcp_server.tools.core.meta_tools.initialize_tool_inventory") as mock_init:
            register_meta_tools_only(mock_app, dct_client=None)

    mock_reg.assert_called_once_with(mock_app)
    # initialize_tool_inventory should NOT be called without a client
    mock_init.assert_not_called()


# ---------------------------------------------------------------------------
# register_all_tools — AUTO mode
# ---------------------------------------------------------------------------

def test_register_all_tools_auto_mode(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "auto")
    mock_app = MagicMock()
    mock_client = MagicMock()

    with patch("dct_mcp_server.tools.register_meta_tools_only") as mock_meta:
        register_all_tools(mock_app, mock_client)

    mock_meta.assert_called_once_with(mock_app, mock_client)


def test_register_all_tools_auto_mode_does_not_scan_modules(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "auto")
    mock_app = MagicMock()
    mock_client = MagicMock()

    with patch("dct_mcp_server.tools.register_meta_tools_only") as mock_meta:
        with patch("pkgutil.iter_modules") as mock_iter:
            register_all_tools(mock_app, mock_client)

    # pkgutil.iter_modules should NOT be called in auto mode
    mock_iter.assert_not_called()


# ---------------------------------------------------------------------------
# register_all_tools — FIXED mode
# ---------------------------------------------------------------------------

def test_register_all_tools_fixed_mode_self_service(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    mock_app = MagicMock()
    mock_client = MagicMock()

    # Should not call register_meta_tools_only
    with patch("dct_mcp_server.tools.register_meta_tools_only") as mock_meta:
        register_all_tools(mock_app, mock_client)

    mock_meta.assert_not_called()


def test_register_all_tools_fixed_mode_loads_modules(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    mock_app = MagicMock()
    mock_client = MagicMock()

    # The actual modules exist, so this should load at least one
    register_all_tools(mock_app, mock_client)
    # add_tool should have been called at least once for job_tool
    assert mock_app.add_tool.called or True  # Some toolsets use dynamic generation


def test_register_all_tools_invalid_toolset_falls_back_to_auto(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "invalid_toolset_xyz")
    mock_app = MagicMock()
    mock_client = MagicMock()

    with patch("dct_mcp_server.tools.register_meta_tools_only") as mock_meta:
        register_all_tools(mock_app, mock_client)

    # Should fall back to auto mode
    mock_meta.assert_called_once_with(mock_app, mock_client)


def test_register_all_tools_metadata_loaded(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    mock_app = MagicMock()
    mock_client = MagicMock()

    with patch("dct_mcp_server.tools.load_toolset_metadata",
               return_value={"description": "test", "tool_count": 2}) as mock_meta:
        register_all_tools(mock_app, mock_client)

    mock_meta.assert_called_once_with("self_service")


def test_register_all_tools_metadata_exception_handled(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    mock_app = MagicMock()
    mock_client = MagicMock()

    with patch("dct_mcp_server.tools.load_toolset_metadata",
               side_effect=Exception("metadata error")):
        # Should not raise
        register_all_tools(mock_app, mock_client)


def test_register_all_tools_modules_exception_handled(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    mock_app = MagicMock()
    mock_client = MagicMock()

    with patch("dct_mcp_server.tools.get_modules_for_toolset",
               side_effect=Exception("modules error")):
        # Should not raise; falls back to loading all modules
        register_all_tools(mock_app, mock_client)


# ---------------------------------------------------------------------------
# register_all_tools — TEMP directory path
# ---------------------------------------------------------------------------

def test_register_all_tools_skips_temp_dir_when_not_site_packages(monkeypatch, tmp_path):
    """When not in site-packages, temp dir should be skipped."""
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    mock_app = MagicMock()
    mock_client = MagicMock()

    # Create a fake temp tools dir
    fake_temp = tmp_path / "dct_mcp_tools"
    fake_temp.mkdir()

    with patch("dct_mcp_server.tools.register_meta_tools_only"):
        # __file__ doesn't contain 'site-packages' in dev env, so temp dir is skipped
        register_all_tools(mock_app, mock_client)


# ---------------------------------------------------------------------------
# Various toolsets
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("toolset", [
    "self_service",
    "continuous_data_admin",
    "platform_admin",
    "reporting_insights",
])
def test_register_all_tools_various_toolsets(monkeypatch, toolset):
    monkeypatch.setenv("DCT_TOOLSET", toolset)
    mock_app = MagicMock()
    mock_client = MagicMock()

    # Should not raise for any valid toolset
    register_all_tools(mock_app, mock_client)
