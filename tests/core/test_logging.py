"""Unit tests for GlobalLogger._get_project_root() — DLPXECO-13635."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from dct_mcp_server.core.logging import GlobalLogger


class TestGetProjectRoot:
    def test_site_packages_returns_cwd(self, tmp_path):
        """S1/S4: primary guard fires when __file__ contains site-packages."""
        fake_file = "/usr/local/lib/python3.11/site-packages/dct_mcp_server/core/logging.py"
        with patch.object(
            sys.modules["dct_mcp_server.core.logging"],
            "__file__",
            fake_file,
        ):
            result = GlobalLogger._get_project_root()
        assert result == Path.cwd()

    def test_dev_clone_returns_repo_root(self, tmp_path):
        """S2: dev-clone path (no site-packages) returns parents[3]."""
        fake_root = tmp_path / "dxi-mcp-server"
        fake_file = fake_root / "src" / "dct_mcp_server" / "core" / "logging.py"
        fake_file.parent.mkdir(parents=True, exist_ok=True)
        fake_file.touch()
        with patch.object(
            sys.modules["dct_mcp_server.core.logging"],
            "__file__",
            str(fake_file),
        ):
            result = GlobalLogger._get_project_root()
        assert result == fake_root

    def test_editable_install_returns_repo_root(self, tmp_path):
        """S3: editable install (__file__ resolves into source tree, no site-packages)."""
        fake_root = tmp_path / "dxi-mcp-server"
        fake_file = fake_root / "src" / "dct_mcp_server" / "core" / "logging.py"
        fake_file.parent.mkdir(parents=True, exist_ok=True)
        fake_file.touch()
        with patch.object(
            sys.modules["dct_mcp_server.core.logging"],
            "__file__",
            str(fake_file),
        ):
            result = GlobalLogger._get_project_root()
        assert result == fake_root

    def test_site_packages_primary_guard_takes_precedence(self, tmp_path):
        """S4: primary guard fires even when the candidate path would be writable."""
        fake_file = "/usr/local/lib/python3.11/site-packages/dct_mcp_server/core/logging.py"
        with patch.object(
            sys.modules["dct_mcp_server.core.logging"],
            "__file__",
            fake_file,
        ), patch("os.access", return_value=True):
            result = GlobalLogger._get_project_root()
        assert result == Path.cwd()

    def test_setup_global_handlers_survives_permission_error(self, tmp_path):
        """S5: server does not crash when log dir creation raises PermissionError."""
        logger_instance = GlobalLogger()
        import logging as stdlib_logging
        import io

        root = stdlib_logging.getLogger("test_permission_root_unique")
        original_handlers = root.handlers[:]

        captured = io.StringIO()
        with patch.object(
            GlobalLogger,
            "_get_project_root",
            return_value=tmp_path / "no-write",
        ), patch("pathlib.Path.mkdir", side_effect=PermissionError("no write")), patch(
            "sys.stderr", captured
        ):
            logger_instance._setup_global_handlers(root, None)

        stderr_output = captured.getvalue()
        assert "Warning" in stderr_output

        root.handlers = original_handlers
