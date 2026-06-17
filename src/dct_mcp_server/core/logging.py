"""
Global logging configuration for the MCP server.
"""

import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional


class LoggingConfig:
    """Configuration constants for logging."""

    DEFAULT_LOG_LEVEL = "INFO"
    WHEN = "midnight"
    DAY_INTERVAL = 1  # Rotate logs daily
    BACKUP_COUNT = 7
    ENCODING = "utf-8"

    NOISY_LOGGERS = [
        "urllib3",
        "httpx",
        "asyncio",
        "fastmcp",
        "mcp.server.lowlevel.server",
    ]


class GlobalLogger:
    """Handles global application logging."""

    def __init__(self):
        self._logger = logging.getLogger("dct_mcp_server")
        self._setup_complete = False

    def setup(
        self,
        log_level: str = LoggingConfig.DEFAULT_LOG_LEVEL,
        log_file: Optional[str] = None,
        disable_logging: bool = False,
    ) -> None:
        """Setup global logging configuration."""
        if self._setup_complete or disable_logging or log_level.upper() == "OFF":
            if disable_logging or log_level.upper() == "OFF":
                logging.disable(logging.CRITICAL)
            return

        if log_level.upper() == "QUIET":
            log_level = "CRITICAL"

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        numeric_level = getattr(logging, log_level.upper(), logging.INFO)
        root_logger.setLevel(numeric_level)

        # Setup global logging handlers
        self._setup_global_handlers(root_logger, log_file)
        self._suppress_noisy_loggers()
        self._setup_complete = True

    def _setup_global_handlers(
        self, root_logger: logging.Logger, log_file: Optional[str]
    ) -> None:
        """Setup global logging handlers."""
        global_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        )

        # Determine log file path
        if log_file is None:
            project_root = self._get_project_root()
            logs_dir = project_root / "logs"
            log_file_path = logs_dir / "dct_mcp_server.log"
        else:
            log_file_path = Path(log_file)
            logs_dir = log_file_path.parent

        # Create logs directory and add rotating file handler.
        # When running from a read-only location (e.g. restricted container mount),
        # degrade gracefully: emit a warning and skip the file handler.
        try:
            logs_dir.mkdir(exist_ok=True)
            global_handler = TimedRotatingFileHandler(
                log_file_path,
                when=LoggingConfig.WHEN,
                interval=LoggingConfig.DAY_INTERVAL,
                backupCount=LoggingConfig.BACKUP_COUNT,
                encoding=LoggingConfig.ENCODING,
            )
            self._add_handler(root_logger, global_handler, global_formatter)
        except PermissionError as e:
            print(
                f"Warning: Cannot create log directory {logs_dir}: {e}",
                file=sys.stderr,
            )
        except Exception as e:
            print(
                f"Warning: Failed to create global log file {log_file_path}: {e}",
                file=sys.stderr,
            )

        # Add console handler for global logs
        console_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )
        self._add_handler(
            root_logger, logging.StreamHandler(sys.stderr), console_formatter
        )

    def _suppress_noisy_loggers(self) -> None:
        """Suppress commonly noisy third-party loggers."""
        for logger_name in LoggingConfig.NOISY_LOGGERS:
            logging.getLogger(logger_name).setLevel(logging.WARNING)

    def _add_handler(
        self,
        logger: logging.Logger,
        handler: logging.Handler,
        formatter: logging.Formatter,
    ) -> None:
        """Helper function to configure and add a handler to the logger."""
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        """Get a logger instance."""
        if not self._setup_complete:
            self.setup()  # Auto-setup with defaults if not already done
        if name:
            return logging.getLogger(name)
        return self._logger

    @staticmethod
    def _get_project_root() -> Path:
        """Get project root directory.

        Returns Path.cwd() when running from an installed package (site-packages),
        so log files are written relative to the working directory rather than
        into the Python library tree. Falls back to cwd when the candidate path
        is not writable (secondary guard).

        In development (cloned repo or editable install) returns the repo root,
        which is four directory levels above this file:
        src/dct_mcp_server/core/logging.py → parents[3] = repo root.
        """
        if getattr(sys, "frozen", False):
            return Path(os.path.dirname(sys.executable))

        resolved_file = Path(__file__).resolve()

        # Primary guard: installed package path always contains "site-packages"
        if "site-packages" in str(resolved_file):
            return Path.cwd()

        # Dev clone / editable install: file lives inside the source tree
        candidate = resolved_file.parents[3]

        # Secondary guard: if the candidate is unwritable (e.g. a path that
        # coincidentally contains "site-packages" in an ancestor dir name but
        # was caught above, or a read-only mount), fall back to cwd.
        if not os.access(str(candidate), os.W_OK):
            return Path.cwd()

        return candidate


# Global instance
_global_logger = GlobalLogger()


# Public API
def setup_logging(
    log_level: str = LoggingConfig.DEFAULT_LOG_LEVEL,
    log_file: Optional[str] = None,
    disable_logging: bool = False,
) -> None:
    """Setup global logging configuration."""
    _global_logger.setup(log_level, log_file, disable_logging)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance."""
    return _global_logger.get_logger(name)
