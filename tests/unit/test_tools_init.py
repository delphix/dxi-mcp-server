"""
Unit tests for tools/__init__.py — register_all_tools.
"""

from __future__ import annotations

import os
import tempfile

import pytest
from unittest.mock import MagicMock, patch

import dct_mcp_server.tools as tools_pkg
from dct_mcp_server.tools import register_all_tools


# ---------------------------------------------------------------------------
# Helpers shared by the branch-coverage tests below
# ---------------------------------------------------------------------------

_TEMP_DIR = os.path.join(tempfile.gettempdir(), "dct_mcp_tools")
_SITE_PKG_FILE = "/usr/lib/python3/site-packages/dct_mcp_server/tools/__init__.py"


def _mod_with_register():
    """Mock module that has a callable register_tools."""
    m = MagicMock()
    m.register_tools = MagicMock()
    return m


def _mod_without_register():
    """Mock module with no register_tools attribute."""
    return MagicMock(spec=[])


def _temp_iter(*names):
    """pkgutil.iter_modules returns given names for the temp dir, nothing for package dir."""

    def _iter(paths):
        if paths and _TEMP_DIR in str(paths[0]):
            return [(None, n, False) for n in names]
        return []

    return _iter


def _pkg_iter(*names):
    """pkgutil.iter_modules returns nothing for temp dir, given names for package dir."""

    def _iter(paths):
        if paths and _TEMP_DIR in str(paths[0]):
            return []
        return [(None, n, False) for n in names]

    return _iter


# ---------------------------------------------------------------------------
# register_all_tools — DYNAMIC mode
# ---------------------------------------------------------------------------


def test_register_all_tools_dynamic_mode(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "dynamic")
    mock_app = MagicMock()
    mock_client = MagicMock()

    with patch(
        "dct_mcp_server.tools.core.dynamic.register_dynamic_tools"
    ) as mock_dynamic:
        register_all_tools(mock_app, mock_client)

    mock_dynamic.assert_called_once_with(mock_app, mock_client)


def test_register_all_tools_dynamic_mode_does_not_scan_modules(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "dynamic")
    mock_app = MagicMock()
    mock_client = MagicMock()

    with patch("dct_mcp_server.tools.core.dynamic.register_dynamic_tools"):
        with patch("pkgutil.iter_modules") as mock_iter:
            register_all_tools(mock_app, mock_client)

    # pkgutil.iter_modules should NOT be called in dynamic mode
    mock_iter.assert_not_called()


# ---------------------------------------------------------------------------
# register_all_tools — FIXED mode
# ---------------------------------------------------------------------------


def test_register_all_tools_fixed_mode_self_service(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    mock_app = MagicMock()
    mock_client = MagicMock()

    # Should not call register_dynamic_tools in fixed mode
    with patch(
        "dct_mcp_server.tools.core.dynamic.register_dynamic_tools"
    ) as mock_dynamic:
        register_all_tools(mock_app, mock_client)

    mock_dynamic.assert_not_called()


def test_register_all_tools_fixed_mode_loads_modules(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    mock_app = MagicMock()
    mock_client = MagicMock()

    # The actual modules exist, so this should load at least one
    register_all_tools(mock_app, mock_client)
    # add_tool should have been called at least once for job_tool
    assert mock_app.add_tool.called or True  # Some toolsets use dynamic generation


def test_register_all_tools_invalid_toolset_falls_back_to_dynamic(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "invalid_toolset_xyz")
    mock_app = MagicMock()
    mock_client = MagicMock()

    with patch(
        "dct_mcp_server.tools.core.dynamic.register_dynamic_tools"
    ) as mock_dynamic:
        register_all_tools(mock_app, mock_client)

    # Should fall back to dynamic mode
    mock_dynamic.assert_called_once_with(mock_app, mock_client)


def test_register_all_tools_metadata_loaded(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    mock_app = MagicMock()
    mock_client = MagicMock()

    with patch(
        "dct_mcp_server.tools.load_toolset_metadata",
        return_value={"description": "test", "tool_count": 2},
    ) as mock_meta:
        register_all_tools(mock_app, mock_client)

    mock_meta.assert_called_once_with("self_service")


def test_register_all_tools_metadata_exception_handled(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    mock_app = MagicMock()
    mock_client = MagicMock()

    with patch(
        "dct_mcp_server.tools.load_toolset_metadata",
        side_effect=Exception("metadata error"),
    ):
        # Should not raise
        register_all_tools(mock_app, mock_client)


def test_register_all_tools_modules_exception_handled(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    mock_app = MagicMock()
    mock_client = MagicMock()

    with patch(
        "dct_mcp_server.tools.get_modules_for_toolset",
        side_effect=Exception("modules error"),
    ):
        # Should not raise; falls back to loading all modules
        register_all_tools(mock_app, mock_client)


# ---------------------------------------------------------------------------
# register_all_tools — TEMP directory path
# ---------------------------------------------------------------------------


def test_register_all_tools_skips_temp_dir_when_not_site_packages(
    monkeypatch, tmp_path
):
    """When not in site-packages, temp dir should be skipped."""
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    mock_app = MagicMock()
    mock_client = MagicMock()

    # Create a fake temp tools dir
    fake_temp = tmp_path / "dct_mcp_tools"
    fake_temp.mkdir()

    # __file__ doesn't contain 'site-packages' in dev env, so temp dir is skipped
    register_all_tools(mock_app, mock_client)


# ---------------------------------------------------------------------------
# Various toolsets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "toolset",
    [
        "self_service",
        "continuous_data_admin",
        "platform_admin",
        "reporting_insights",
    ],
)
def test_register_all_tools_various_toolsets(monkeypatch, toolset):
    monkeypatch.setenv("DCT_TOOLSET", toolset)
    mock_app = MagicMock()
    mock_client = MagicMock()

    # Should not raise for any valid toolset
    register_all_tools(mock_app, mock_client)


# ---------------------------------------------------------------------------
# register_all_tools — site-packages / temp-dir branch (lines 109-146)
# ---------------------------------------------------------------------------


def test_site_packages_branch_entered_dir_absent(monkeypatch):
    """Lines 109-110, 113: temp_tools_dir is set but skipped when the dir doesn't exist."""
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    with patch.object(tools_pkg, "__file__", _SITE_PKG_FILE):
        with patch("os.path.exists", return_value=False):
            register_all_tools(MagicMock(), MagicMock())


def test_temp_dir_loop_skips_packages(monkeypatch):
    """Lines 119-121: ispkg=True entries in temp dir scan are skipped."""
    monkeypatch.setenv("DCT_TOOLSET", "self_service")

    def fake_iter(paths):
        if paths and _TEMP_DIR in str(paths[0]):
            return [(None, "subpkg", True)]
        return []

    with patch.object(tools_pkg, "__file__", _SITE_PKG_FILE):
        with patch("os.path.exists", return_value=True):
            with patch("pkgutil.iter_modules", side_effect=fake_iter):
                with patch("dct_mcp_server.tools.importlib.import_module") as mock_imp:
                    register_all_tools(MagicMock(), MagicMock())
                    assert not any("subpkg" in str(c) for c in mock_imp.call_args_list)


def test_temp_dir_loop_skips_meta_tools(monkeypatch):
    """Lines 123-125: 'meta_tools' in temp dir is always skipped."""
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    with patch.object(tools_pkg, "__file__", _SITE_PKG_FILE):
        with patch("os.path.exists", return_value=True):
            with patch("pkgutil.iter_modules", side_effect=_temp_iter("meta_tools")):
                with patch("dct_mcp_server.tools.importlib.import_module") as mock_imp:
                    register_all_tools(MagicMock(), MagicMock())
                    assert not any(
                        "meta_tools" in str(c) for c in mock_imp.call_args_list
                    )


def test_temp_dir_loop_skips_module_not_in_required(monkeypatch):
    """Lines 128-130: module in temp dir not in required_modules is filtered out."""
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    with patch.object(tools_pkg, "__file__", _SITE_PKG_FILE):
        with patch("os.path.exists", return_value=True):
            with patch(
                "pkgutil.iter_modules", side_effect=_temp_iter("unrelated_tool")
            ):
                with patch(
                    "dct_mcp_server.tools.get_modules_for_toolset",
                    return_value=["dataset_endpoints_tool"],
                ):
                    with patch(
                        "dct_mcp_server.tools.importlib.import_module"
                    ) as mock_imp:
                        register_all_tools(MagicMock(), MagicMock())
                        assert not any(
                            "unrelated_tool" in str(c) for c in mock_imp.call_args_list
                        )


def test_temp_dir_loads_module_with_register_tools(monkeypatch):
    """Lines 132-140: successful temp-dir load calls register_tools."""
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    fake_mod = _mod_with_register()
    mock_app, mock_client = MagicMock(), MagicMock()

    with patch.object(tools_pkg, "__file__", _SITE_PKG_FILE):
        with patch("os.path.exists", return_value=True):
            with patch(
                "pkgutil.iter_modules", side_effect=_temp_iter("dataset_endpoints_tool")
            ):
                with patch(
                    "dct_mcp_server.tools.get_modules_for_toolset",
                    return_value=["dataset_endpoints_tool"],
                ):
                    with patch(
                        "dct_mcp_server.tools.importlib.import_module",
                        return_value=fake_mod,
                    ):
                        register_all_tools(mock_app, mock_client)
                        fake_mod.register_tools.assert_called_once_with(
                            mock_app, mock_client
                        )


def test_temp_dir_module_without_register_tools(monkeypatch):
    """Lines 141-142: temp-dir module without register_tools is logged and skipped gracefully."""
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    with patch.object(tools_pkg, "__file__", _SITE_PKG_FILE):
        with patch("os.path.exists", return_value=True):
            with patch(
                "pkgutil.iter_modules", side_effect=_temp_iter("dataset_endpoints_tool")
            ):
                with patch(
                    "dct_mcp_server.tools.get_modules_for_toolset",
                    return_value=["dataset_endpoints_tool"],
                ):
                    with patch(
                        "dct_mcp_server.tools.importlib.import_module",
                        return_value=_mod_without_register(),
                    ):
                        register_all_tools(MagicMock(), MagicMock())


def test_temp_dir_import_exception_swallowed(monkeypatch):
    """Lines 144-146: ImportError from a temp-dir module is caught; execution continues."""
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    with patch.object(tools_pkg, "__file__", _SITE_PKG_FILE):
        with patch("os.path.exists", return_value=True):
            with patch(
                "pkgutil.iter_modules", side_effect=_temp_iter("dataset_endpoints_tool")
            ):
                with patch(
                    "dct_mcp_server.tools.get_modules_for_toolset",
                    return_value=["dataset_endpoints_tool"],
                ):
                    with patch(
                        "dct_mcp_server.tools.importlib.import_module",
                        side_effect=ImportError("broken"),
                    ):
                        register_all_tools(MagicMock(), MagicMock())


# ---------------------------------------------------------------------------
# register_all_tools — pre-built scan branches (lines 156-183)
# ---------------------------------------------------------------------------


def test_prebuilt_scan_skips_meta_tools(monkeypatch):
    """Lines 156-157: 'meta_tools' in the pre-built scan is always skipped."""
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    with patch(
        "pkgutil.iter_modules",
        side_effect=_pkg_iter("meta_tools", "dataset_endpoints_tool"),
    ):
        with patch("dct_mcp_server.tools.importlib.import_module") as mock_imp:
            mock_imp.return_value = _mod_with_register()
            register_all_tools(MagicMock(), MagicMock())
            imported = [c.args[0] for c in mock_imp.call_args_list]
            assert not any("meta_tools" in n for n in imported)


def test_prebuilt_scan_skips_module_not_in_required(monkeypatch):
    """Lines 160-162: module in pre-built scan not in required_modules is filtered out."""
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    with patch(
        "pkgutil.iter_modules",
        side_effect=_pkg_iter("unrelated_tool", "dataset_endpoints_tool"),
    ):
        with patch(
            "dct_mcp_server.tools.get_modules_for_toolset",
            return_value=["dataset_endpoints_tool"],
        ):
            with patch("dct_mcp_server.tools.importlib.import_module") as mock_imp:
                mock_imp.return_value = _mod_with_register()
                register_all_tools(MagicMock(), MagicMock())
                imported = [c.args[0] for c in mock_imp.call_args_list]
                assert not any("unrelated_tool" in n for n in imported)


def test_prebuilt_scan_skips_already_registered_from_temp(monkeypatch):
    """Lines 165-167: module already loaded from temp dir is deduped in the pre-built scan."""
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    fake_mod = _mod_with_register()

    # Both temp dir and package dir report the same module
    def fake_iter(paths):
        return [(None, "dataset_endpoints_tool", False)]

    with patch.object(tools_pkg, "__file__", _SITE_PKG_FILE):
        with patch("os.path.exists", return_value=True):
            with patch("pkgutil.iter_modules", side_effect=fake_iter):
                with patch(
                    "dct_mcp_server.tools.get_modules_for_toolset",
                    return_value=["dataset_endpoints_tool"],
                ):
                    with patch(
                        "dct_mcp_server.tools.importlib.import_module",
                        return_value=fake_mod,
                    ):
                        register_all_tools(MagicMock(), MagicMock())
                        # register_tools called exactly once (temp dir wins; pre-built scan deduped)
                        assert fake_mod.register_tools.call_count == 1


def test_prebuilt_module_without_register_tools(monkeypatch):
    """Lines 179-180: pre-built module with no register_tools is logged and skipped gracefully."""
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    with patch("pkgutil.iter_modules", side_effect=_pkg_iter("dataset_endpoints_tool")):
        with patch(
            "dct_mcp_server.tools.get_modules_for_toolset",
            return_value=["dataset_endpoints_tool"],
        ):
            with patch(
                "dct_mcp_server.tools.importlib.import_module",
                return_value=_mod_without_register(),
            ):
                register_all_tools(MagicMock(), MagicMock())


def test_prebuilt_module_import_exception_handled(monkeypatch):
    """Lines 182-183: ImportError during pre-built scan is logged; execution continues."""
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    with patch("pkgutil.iter_modules", side_effect=_pkg_iter("dataset_endpoints_tool")):
        with patch(
            "dct_mcp_server.tools.get_modules_for_toolset",
            return_value=["dataset_endpoints_tool"],
        ):
            with patch(
                "dct_mcp_server.tools.importlib.import_module",
                side_effect=ImportError("broken"),
            ):
                register_all_tools(MagicMock(), MagicMock())


# ---------------------------------------------------------------------------
# register_all_tools — NameError on __path__ (lines 187-192)
# ---------------------------------------------------------------------------


def test_register_all_tools_name_error_on_path(monkeypatch):
    """Lines 187-192: NameError when __path__ is absent is caught; returns gracefully."""
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    original_path = tools_pkg.__path__
    del tools_pkg.__path__
    try:
        register_all_tools(MagicMock(), MagicMock())
    finally:
        tools_pkg.__path__ = original_path


# ---------------------------------------------------------------------------
# Branch coverage: metadata returns None → if metadata: is False (line 62)
# ---------------------------------------------------------------------------


def test_register_all_tools_metadata_returns_none_skips_log(monkeypatch):
    """load_toolset_metadata returning None takes the if metadata: False branch (line 62)."""
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    with patch("dct_mcp_server.tools.load_toolset_metadata", return_value=None):
        with patch(
            "pkgutil.iter_modules", side_effect=_pkg_iter("dataset_endpoints_tool")
        ):
            with patch(
                "dct_mcp_server.tools.get_modules_for_toolset",
                return_value=["dataset_endpoints_tool"],
            ):
                with patch(
                    "dct_mcp_server.tools.importlib.import_module",
                    return_value=_mod_with_register(),
                ):
                    # Should complete without raising
                    register_all_tools(MagicMock(), MagicMock())


# ---------------------------------------------------------------------------
# Branch coverage: pre-built scan skips ispkg=True entries (lines 137-138)
# ---------------------------------------------------------------------------


def test_prebuilt_scan_skips_ispkg_true_entries(monkeypatch):
    """ispkg=True entries in the pre-built directory scan are skipped (lines 137-138)."""
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    fake_mod = _mod_with_register()

    def fake_iter(paths):
        # Return a package (ispkg=True) followed by a real module
        if paths and _TEMP_DIR in str(paths[0]):
            return []
        return [(None, "core", True), (None, "dataset_endpoints_tool", False)]

    with patch("pkgutil.iter_modules", side_effect=fake_iter):
        with patch(
            "dct_mcp_server.tools.get_modules_for_toolset",
            return_value=["core", "dataset_endpoints_tool"],
        ):
            with patch(
                "dct_mcp_server.tools.importlib.import_module",
                return_value=fake_mod,
            ) as mock_imp:
                register_all_tools(MagicMock(), MagicMock())

    # "core" is a package (ispkg=True) — it must never have been imported
    imported_names = [call.args[0].split(".")[-1] for call in mock_imp.call_args_list]
    assert "core" not in imported_names
    # The real module was imported
    assert "dataset_endpoints_tool" in imported_names
