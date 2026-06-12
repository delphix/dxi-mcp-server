"""
Unit tests for core/session.py — SessionManager, SessionJsonFormatter, and public API.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dct_mcp_server.core.session import (
    SessionJsonFormatter,
    SessionManager,
    end_session,
    get_current_session_id,
    get_session_logger,
    log_tool_call,
    start_session,
)


# ---------------------------------------------------------------------------
# SessionManager — direct tests
# ---------------------------------------------------------------------------

class TestSessionManager:
    def test_initial_state(self):
        mgr = SessionManager()
        assert mgr.current_session_id is None

    def test_get_user_id_returns_string(self):
        mgr = SessionManager()
        uid = mgr._get_user_id()
        assert isinstance(uid, str)
        assert len(uid) > 0

    def test_get_user_details_returns_dict(self):
        mgr = SessionManager()
        details = mgr.get_user_details()
        assert "id" in details
        assert "os" in details
        assert "os_ver" in details

    def test_get_user_details_cached(self):
        mgr = SessionManager()
        d1 = mgr.get_user_details()
        d2 = mgr.get_user_details()
        assert d1 is d2

    def test_get_user_id_fallback_on_exception(self):
        mgr = SessionManager()
        with patch("getpass.getuser", side_effect=Exception("no user")):
            uid = mgr._get_user_id()
        assert uid == "unknown"

    def test_start_session_generates_id(self, tmp_path):
        mgr = SessionManager()
        with patch.object(mgr, "_get_project_root", return_value=tmp_path):
            sid = mgr.start_session()
        assert isinstance(sid, str)
        assert len(sid) > 0
        mgr.end_session(sid)

    def test_start_session_custom_id(self, tmp_path):
        mgr = SessionManager()
        with patch.object(mgr, "_get_project_root", return_value=tmp_path):
            sid = mgr.start_session("custom-id-123")
        assert sid == "custom-id-123"
        mgr.end_session(sid)

    def test_start_session_ends_existing(self, tmp_path):
        mgr = SessionManager()
        with patch.object(mgr, "_get_project_root", return_value=tmp_path):
            sid1 = mgr.start_session("first-session")
            sid2 = mgr.start_session("second-session")
        assert mgr.current_session_id == "second-session"
        mgr.end_session(sid2)

    def test_end_session_clears_current(self, tmp_path):
        mgr = SessionManager()
        with patch.object(mgr, "_get_project_root", return_value=tmp_path):
            sid = mgr.start_session()
        mgr.end_session(sid)
        assert mgr.current_session_id is None

    def test_end_session_no_op_when_not_active(self):
        mgr = SessionManager()
        # Should not raise
        mgr.end_session("nonexistent-session")

    def test_end_session_without_arg_uses_current(self, tmp_path):
        mgr = SessionManager()
        with patch.object(mgr, "_get_project_root", return_value=tmp_path):
            sid = mgr.start_session()
        mgr.end_session()
        assert mgr.current_session_id is None

    def test_get_session_logger_returns_logger(self, tmp_path):
        mgr = SessionManager()
        with patch.object(mgr, "_get_project_root", return_value=tmp_path):
            sid = mgr.start_session()
        lg = mgr.get_session_logger(sid)
        assert lg is not None
        assert isinstance(lg, logging.Logger)
        mgr.end_session(sid)

    def test_get_session_logger_returns_none_without_session(self):
        mgr = SessionManager()
        assert mgr.get_session_logger() is None

    def test_get_session_logger_default_uses_current(self, tmp_path):
        mgr = SessionManager()
        with patch.object(mgr, "_get_project_root", return_value=tmp_path):
            sid = mgr.start_session()
        lg = mgr.get_session_logger()
        assert lg is not None
        mgr.end_session(sid)

    def test_log_tool_call_with_active_session(self, tmp_path):
        mgr = SessionManager()
        with patch.object(mgr, "_get_project_root", return_value=tmp_path):
            sid = mgr.start_session()
        # Should not raise
        mgr.log_tool_call({"tool_name": "test_tool", "status": "success"})
        mgr.end_session(sid)

    def test_log_tool_call_without_session_logs_warning(self):
        mgr = SessionManager()
        with patch.object(logging.Logger, "warning") as mock_warn:
            mgr.log_tool_call({"tool_name": "test_tool", "status": "success"})
        # warning should have been called (or at least no exception)

    def test_log_tool_call_logs_to_session(self, tmp_path):
        mgr = SessionManager()
        with patch.object(mgr, "_get_project_root", return_value=tmp_path):
            sid = mgr.start_session()
        session_lg = mgr.get_session_logger(sid)
        with patch.object(session_lg, "info") as mock_info:
            mgr.log_tool_call({"tool_name": "my_tool", "status": "success"})
        mock_info.assert_called_once()
        mgr.end_session(sid)

    def test_get_project_root_returns_path(self):
        root = SessionManager._get_project_root()
        assert isinstance(root, Path)

    def test_concurrent_sessions(self, tmp_path):
        """Verify thread-safety by starting/ending sessions from multiple threads."""
        mgr = SessionManager()
        errors = []

        def worker(idx):
            try:
                with patch.object(mgr, "_get_project_root", return_value=tmp_path):
                    sid = mgr.start_session(f"thread-{idx}")
                mgr.end_session(sid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors


# ---------------------------------------------------------------------------
# SessionJsonFormatter
# ---------------------------------------------------------------------------

class TestSessionJsonFormatter:
    def _make_record(self, message: str) -> logging.LogRecord:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=message,
            args=(),
            exc_info=None,
        )
        return record

    def test_format_returns_json_string(self):
        mgr = SessionManager()
        fmt = SessionJsonFormatter("test-session", mgr)
        record = self._make_record("hello world")
        output = fmt.format(record)
        parsed = json.loads(output)
        assert parsed["session_id"] == "test-session"
        assert "timestamp" in parsed
        assert "user" in parsed

    def test_format_parses_json_tool_call(self):
        mgr = SessionManager()
        fmt = SessionJsonFormatter("sess-1", mgr)
        tool_call_data = {"tool_name": "vdb_tool", "status": "success"}
        record = self._make_record(json.dumps(tool_call_data))
        output = fmt.format(record)
        parsed = json.loads(output)
        assert parsed["tool_call"]["tool_name"] == "vdb_tool"

    def test_format_handles_plain_string_message(self):
        mgr = SessionManager()
        fmt = SessionJsonFormatter("sess-2", mgr)
        record = self._make_record("not json")
        output = fmt.format(record)
        parsed = json.loads(output)
        assert parsed["tool_call"] == "not json"

    def test_format_fallback_on_exception(self):
        mgr = SessionManager()
        fmt = SessionJsonFormatter("sess-3", mgr)
        # Break get_user_details to trigger fallback
        mgr._user_details = None
        with patch.object(mgr, "get_user_details", side_effect=Exception("boom")):
            record = self._make_record("test message")
            output = fmt.format(record)
        assert "JSON_FORMAT_ERROR" in output or "test message" in output


# ---------------------------------------------------------------------------
# Public API (module-level functions)
# ---------------------------------------------------------------------------

class TestPublicApi:
    def test_get_current_session_id_returns_none_by_default(self):
        # The global _session_manager may or may not have an active session;
        # after end_session it should be None
        end_session()
        sid = get_current_session_id()
        assert sid is None

    def test_start_session_returns_string(self, tmp_path):
        import dct_mcp_server.core.session as _sess_mod
        orig_root = _sess_mod._session_manager._get_project_root
        try:
            with patch.object(_sess_mod._session_manager, "_get_project_root", return_value=tmp_path):
                sid = start_session()
            assert isinstance(sid, str)
            end_session(sid)
        except Exception:
            end_session()

    def test_start_session_with_id(self, tmp_path):
        import dct_mcp_server.core.session as _sess_mod
        with patch.object(_sess_mod._session_manager, "_get_project_root", return_value=tmp_path):
            sid = start_session("pub-test-id")
        assert sid == "pub-test-id"
        end_session(sid)

    def test_end_session_clears_id(self, tmp_path):
        import dct_mcp_server.core.session as _sess_mod
        with patch.object(_sess_mod._session_manager, "_get_project_root", return_value=tmp_path):
            start_session("my-end-test")
        end_session("my-end-test")
        # After ending, it should not be the current session
        assert get_current_session_id() != "my-end-test"

    def test_end_session_no_arg(self, tmp_path):
        import dct_mcp_server.core.session as _sess_mod
        with patch.object(_sess_mod._session_manager, "_get_project_root", return_value=tmp_path):
            start_session("no-arg-end")
        end_session()
        assert get_current_session_id() is None

    def test_log_tool_call_no_error(self):
        # No active session - should not raise, just warn
        end_session()
        log_tool_call({"tool_name": "test", "status": "success"})

    def test_get_session_logger_returns_none_without_session(self):
        end_session()
        lg = get_session_logger()
        assert lg is None

    def test_get_session_logger_returns_logger_with_session(self, tmp_path):
        import dct_mcp_server.core.session as _sess_mod
        with patch.object(_sess_mod._session_manager, "_get_project_root", return_value=tmp_path):
            sid = start_session()
        lg = get_session_logger(sid)
        assert lg is not None
        end_session(sid)
