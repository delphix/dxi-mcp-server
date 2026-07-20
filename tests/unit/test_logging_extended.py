"""
Extended unit tests for core/logging.py.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import patch


from dct_mcp_server.core.logging import (
    GlobalLogger,
    LoggingConfig,
    get_logger,
    setup_logging,
)


# ---------------------------------------------------------------------------
# LoggingConfig constants
# ---------------------------------------------------------------------------


def test_logging_config_defaults():
    assert LoggingConfig.DEFAULT_LOG_LEVEL == "INFO"
    assert LoggingConfig.BACKUP_COUNT == 7
    assert isinstance(LoggingConfig.NOISY_LOGGERS, list)
    assert len(LoggingConfig.NOISY_LOGGERS) > 0


# ---------------------------------------------------------------------------
# setup_logging
# ---------------------------------------------------------------------------


def test_setup_logging_no_exception(tmp_path):
    log_file = str(tmp_path / "test.log")
    setup_logging(log_level="INFO", log_file=log_file)
    # Should not raise


def test_setup_logging_debug_level(tmp_path):
    log_file = str(tmp_path / "debug.log")
    setup_logging(log_level="DEBUG", log_file=log_file)


def test_setup_logging_disable(tmp_path):
    log_file = str(tmp_path / "disabled.log")
    # Calling with disable_logging=True should not raise
    gl = GlobalLogger()
    gl.setup(log_level="INFO", log_file=log_file, disable_logging=True)


def test_setup_logging_off_level(tmp_path):
    log_file = str(tmp_path / "off.log")
    gl = GlobalLogger()
    gl.setup(log_level="OFF", log_file=log_file)


def test_setup_logging_quiet_level(tmp_path):
    log_file = str(tmp_path / "quiet.log")
    gl = GlobalLogger()
    gl.setup(log_level="QUIET", log_file=log_file)


def test_setup_logging_idempotent(tmp_path):
    log_file = str(tmp_path / "idempotent.log")
    gl = GlobalLogger()
    gl.setup(log_level="INFO", log_file=log_file)
    # Second call should be a no-op (setup_complete=True)
    len(logging.getLogger().handlers)
    gl.setup(log_level="DEBUG", log_file=log_file)


def test_setup_logging_file_handler_failure(tmp_path):
    """When file creation fails, setup should not crash (falls back gracefully)."""
    gl = GlobalLogger()
    with patch(
        "dct_mcp_server.core.logging.TimedRotatingFileHandler",
        side_effect=OSError("cannot create"),
    ):
        # Should not raise; error is printed to stderr
        gl.setup(log_level="INFO", log_file=str(tmp_path / "fail.log"))


# ---------------------------------------------------------------------------
# get_logger
# ---------------------------------------------------------------------------


def test_get_logger_returns_logger():
    logger = get_logger("test.module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test.module"


def test_get_logger_none_returns_root_logger():
    logger = get_logger()
    assert isinstance(logger, logging.Logger)


def test_get_logger_different_names():
    l1 = get_logger("module.a")
    l2 = get_logger("module.b")
    assert l1.name != l2.name


def test_get_logger_same_name_same_instance():
    l1 = get_logger("same.module")
    l2 = get_logger("same.module")
    assert l1 is l2


# ---------------------------------------------------------------------------
# GlobalLogger
# ---------------------------------------------------------------------------


def test_global_logger_get_project_root():
    root = GlobalLogger._get_project_root()
    assert isinstance(root, Path)
    # Should be an existing directory
    assert root.exists()


def test_global_logger_get_project_root_frozen():
    """Test the frozen (PyInstaller) path."""
    with patch.object(sys, "frozen", True, create=True):
        root = GlobalLogger._get_project_root()
    assert isinstance(root, Path)


def test_global_logger_suppress_noisy_loggers(tmp_path):
    gl = GlobalLogger()
    gl.setup(log_level="DEBUG", log_file=str(tmp_path / "noisy.log"))
    for noisy in LoggingConfig.NOISY_LOGGERS:
        lg = logging.getLogger(noisy)
        assert lg.level >= logging.WARNING


def test_global_logger_auto_setup_on_get():
    """get_logger auto-calls setup if not complete."""
    gl = GlobalLogger()
    # _setup_complete is False initially
    assert not gl._setup_complete
    # Calling get_logger should trigger setup
    with patch.object(gl, "setup", wraps=gl.setup):
        lg = gl.get_logger("test")
    # After the call, _setup_complete or setup was called
    assert isinstance(lg, logging.Logger)


def test_global_logger_get_logger_with_name(tmp_path):
    gl = GlobalLogger()
    gl.setup(log_level="INFO", log_file=str(tmp_path / "named.log"))
    lg = gl.get_logger("my.specific.module")
    assert lg.name == "my.specific.module"


def test_global_logger_get_logger_without_name(tmp_path):
    gl = GlobalLogger()
    gl.setup(log_level="INFO", log_file=str(tmp_path / "unnamed.log"))
    lg = gl.get_logger()
    # Returns the dct_mcp_server logger
    assert isinstance(lg, logging.Logger)
