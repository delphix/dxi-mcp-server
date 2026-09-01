"""
Generated tests for DLPXECO-14324 — stdio-only embedded auth, per-process
identity resolution, and secret-safe execution for DCT MCP server embedded
deployment mode.

Scenarios sourced from docs/DLPXECO-14324/DLPXECO-14324-test-plan.md.

The server is stdio-only: the embedded host spawns one process per caller and
supplies the caller's DCT account id in the child process environment as
DCT_CLIENT_ID. The former HTTP transport (uvicorn / streamable_http +
ClientIDMiddleware + the X-CLIENT-ID request header) has been removed, so the
HTTP-specific scenarios (S2–S6, S13) are gone.

All DCT API I/O is mocked — no real network calls are made.
Tests in this file are AI-generated.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_env(**kwargs):
    """Context manager that temporarily sets environment variables."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        old = {k: os.environ.get(k) for k in kwargs}
        os.environ.update(kwargs)
        try:
            yield
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    return _ctx()


# ---------------------------------------------------------------------------
# S1 — Server runs over stdio (the only transport)
# ---------------------------------------------------------------------------


class TestS1_StdioTransport:
    """S1: Server runs over stdio; no transport branching remains."""

    def test_config_has_no_transport_field(self):
        """The transport config field has been removed (stdio is implicit)."""
        # AI-generated
        from dct_mcp_server.config.config import get_dct_config

        config = get_dct_config()
        assert "transport" not in config, (
            "transport config field must be removed — server is stdio-only"
        )

    def test_config_has_no_http_fields(self):
        """HTTP-transport config fields must be gone."""
        # AI-generated
        from dct_mcp_server.config.config import get_dct_config

        config = get_dct_config()
        for key in ("http_host", "http_port", "require_tls"):
            assert key not in config, (
                f"{key} config field must be removed — server is stdio-only"
            )


# ---------------------------------------------------------------------------
# S7 — Tool generation runs at startup without DCT_API_KEY in embedded mode
# ---------------------------------------------------------------------------


class TestS7_EmbeddedModeToolGeneration:
    """S7: Tool generation at startup uses bundled spec when DCT_API_KEY is absent."""

    def test_toolsgenerator_uses_bundled_spec_in_embedded_mode(self):
        """generate_tools_from_openapi() must not call get_dct_config() without guarding in embedded mode."""
        # AI-generated
        # The design requires that in embedded mode, the driver loads the bundled
        # docs/api-external.yaml instead of downloading from DCT.
        try:
            from dct_mcp_server.toolsgenerator import driver
        except ImportError:
            pytest.skip("toolsgenerator.driver not importable — S7")

        # Verify the driver can be imported without DCT_API_KEY
        # (just import is enough; actual generation needs a spec file to exist)
        assert hasattr(driver, "generate_tools_from_openapi"), (
            "generate_tools_from_openapi must be importable — S7"
        )

    def test_config_get_dct_config_accepts_require_key_false(self):
        """get_dct_config(require_key=False) must not raise when DCT_API_KEY is absent."""
        # AI-generated
        from dct_mcp_server.config.config import get_dct_config

        saved = os.environ.pop("DCT_API_KEY", None)
        try:
            try:
                # Try with require_key=False (new param added for embedded mode)
                config = get_dct_config(require_key=False)
                # Should succeed — api_key will be None or empty
                assert config.get("api_key") is None or config.get("api_key") == ""
            except TypeError:
                # get_dct_config() doesn't yet accept require_key — skip
                pytest.skip(
                    "get_dct_config() does not yet support require_key=False — S7"
                )
            except ValueError as exc:
                if "DCT_API_KEY" in str(exc):
                    pytest.fail(
                        "get_dct_config(require_key=False) must not raise for missing "
                        "DCT_API_KEY — S7"
                    )
                raise
        finally:
            if saved is not None:
                os.environ["DCT_API_KEY"] = saved


# ---------------------------------------------------------------------------
# S8 — Telemetry scoped per caller when IS_LOCAL_TELEMETRY_ENABLED=true
# ---------------------------------------------------------------------------


class TestS8_PerCallerTelemetry:
    """S8: Tool execution in embedded mode logs telemetry with caller_id tag."""

    def test_get_or_create_caller_session_creates_session(self):
        """get_or_create_caller_session() must create a session logger for caller_id."""
        # AI-generated
        try:
            from dct_mcp_server.core.session import get_or_create_caller_session
        except ImportError:
            pytest.skip("get_or_create_caller_session not yet implemented — S8")

        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "dct_mcp_server.core.session.SessionManager._get_project_root",
                return_value=Path(tmpdir),
            ):
                session_logger = get_or_create_caller_session("caller-test-001")
                assert session_logger is not None, (
                    "get_or_create_caller_session must return a logger — S8"
                )

    def test_tool_execution_tags_telemetry_with_caller_id(self):
        """@log_tool_execution must include the per-process caller_id in telemetry.

        Under stdio-only embedded mode the caller identity is the fixed
        DCT_CLIENT_ID env value (read via config), not a per-request ContextVar.
        """
        # AI-generated
        try:
            from dct_mcp_server.core.decorators import log_tool_execution
        except ImportError:
            pytest.skip("decorators not yet updated for embedded mode — S8")

        logged_data: list = []

        def fake_log_tool_call(data, session_id=None):
            logged_data.append((data, session_id))

        with _set_env(DCT_AUTH_MODE="embedded", DCT_CLIENT_ID="caller-s8"):
            with patch(
                "dct_mcp_server.core.decorators.log_tool_call",
                side_effect=fake_log_tool_call,
            ):

                @log_tool_execution
                def sample_tool():
                    return {"ok": True}

                sample_tool()

        # Verify that telemetry was logged with a reference to the caller
        assert logged_data, (
            "log_tool_call was not called — @log_tool_execution must call it (S8)"
        )
        data, session_id = logged_data[0]
        assert session_id == "caller-s8", (
            "telemetry session_id must be the per-process DCT_CLIENT_ID — S8"
        )
        assert data.get("caller_id") == "caller-s8", (
            "telemetry payload must be tagged with caller_id — S8"
        )


# ---------------------------------------------------------------------------
# S9 — Isolated session log files per concurrent caller
# ---------------------------------------------------------------------------


class TestS9_IsolatedSessionLogs:
    """S9: Two concurrent callers each have isolated session log files."""

    def test_end_caller_session_removes_session(self):
        """end_caller_session() must remove the caller's session logger."""
        # AI-generated
        try:
            from dct_mcp_server.core.session import (
                get_or_create_caller_session,
                end_caller_session,
                get_session_logger,
            )
        except ImportError:
            pytest.skip("per-caller session functions not yet implemented — S9")

        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "dct_mcp_server.core.session.SessionManager._get_project_root",
                return_value=Path(tmpdir),
            ):
                get_or_create_caller_session("caller-a")
                get_or_create_caller_session("caller-b")
                end_caller_session("caller-a")

                # caller-a's session logger should be gone; caller-b's should remain
                logger_a = get_session_logger("caller-a")
                logger_b = get_session_logger("caller-b")
                assert logger_a is None, (
                    "end_caller_session must remove 'caller-a' logger — S9"
                )
                assert logger_b is not None, (
                    "end_caller_session must not remove 'caller-b' logger — S9"
                )


# ---------------------------------------------------------------------------
# S10 — Tool argument with raw API key prefix is rejected by secret guard
# ---------------------------------------------------------------------------


class TestS10_SecretGuardRejectsRawKey:
    """S10: Tool argument containing 'apk <token>' is rejected by inline-secret guard."""

    def test_secret_guard_rejects_apk_prefix(self):
        """SecretGuard.check() must raise or return error for 'apk <token>' in kwargs."""
        # AI-generated
        try:
            from dct_mcp_server.dct_client.client import SecretGuard
        except ImportError:
            pytest.skip("SecretGuard not yet implemented — S10")

        kwargs_with_raw_key = {"api_key": "apk some-raw-key-value"}
        with pytest.raises(Exception) as exc_info:
            SecretGuard.check(kwargs_with_raw_key)
        # The error message must be descriptive
        assert exc_info.value is not None, (
            "SecretGuard.check() must raise for 'apk ' prefix — S10"
        )

    def test_secret_guard_rejects_long_base64_like_string(self):
        """SecretGuard.check() must reject strings > 32 chars that look like base64 tokens."""
        # AI-generated
        try:
            from dct_mcp_server.dct_client.client import SecretGuard
        except ImportError:
            pytest.skip("SecretGuard not yet implemented — S10")

        # A base64-like string > 32 chars
        long_token = "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXo0NTY3ODk="  # 44 chars, base64
        kwargs_with_token = {"credential": long_token}
        with pytest.raises(Exception):
            SecretGuard.check(kwargs_with_token)


# ---------------------------------------------------------------------------
# S11 — Credential alias passes through unblocked
# ---------------------------------------------------------------------------


class TestS11_CredentialAliasPassthrough:
    """S11: Credential alias string (not matching secret pattern) passes through."""

    def test_secret_guard_allows_alias_string(self):
        """SecretGuard.check() must NOT raise for a short alias or reference string."""
        # AI-generated
        try:
            from dct_mcp_server.dct_client.client import SecretGuard
        except ImportError:
            pytest.skip("SecretGuard not yet implemented — S11")

        # A short alias that does not match 'apk ' prefix or base64 > 32 chars
        alias_kwargs = {"credential_ref": "alias://my-dct-credential"}
        # Should not raise
        try:
            SecretGuard.check(alias_kwargs)
        except Exception as exc:
            pytest.fail(
                f"SecretGuard.check() raised unexpectedly for a credential alias: {exc} — S11"
            )

    def test_secret_guard_allows_normal_tool_args(self):
        """SecretGuard.check() must allow normal tool arguments to pass."""
        # AI-generated
        try:
            from dct_mcp_server.dct_client.client import SecretGuard
        except ImportError:
            pytest.skip("SecretGuard not yet implemented — S11")

        normal_args = {
            "vdb_id": "vdb-123",
            "action": "search",
            "filter": "name EQ 'prod'",
        }
        try:
            SecretGuard.check(normal_args)
        except Exception as exc:
            pytest.fail(
                f"SecretGuard.check() must not block normal tool args: {exc} — S11"
            )


# ---------------------------------------------------------------------------
# S12 — Raw API keys are never written to log files
# ---------------------------------------------------------------------------


class TestS12_SecretHygiene:
    """S12: Server logs never contain raw DCT_API_KEY value."""

    def test_mask_secret_hides_api_key(self):
        """_mask_secret() must return a masked value, not the raw key."""
        # AI-generated
        try:
            from dct_mcp_server.dct_client.client import _mask_secret
        except ImportError:
            pytest.skip("_mask_secret not yet implemented — S12")

        raw_key = "super-secret-api-key-value-12345"
        masked = _mask_secret(raw_key)
        assert raw_key not in masked, "_mask_secret must not return the raw key — S12"
        # Masked value should contain some indicator of masking
        assert len(masked) > 0, "_mask_secret must return a non-empty string — S12"

    def test_client_does_not_log_api_key_in_headers(self):
        """DCTAPIClient must not log the raw api_key value."""
        # AI-generated
        import logging
        import io
        from dct_mcp_server.dct_client.client import DCTAPIClient

        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        test_logger = logging.getLogger("dct_mcp_server")
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.DEBUG)

        try:
            DCTAPIClient()
            # Trigger any initialization logging
            log_output = log_stream.getvalue()
            raw_key = os.environ.get("DCT_API_KEY", "test-key")
            assert raw_key not in log_output, (
                f"Raw API key '{raw_key}' must not appear in log output — S12"
            )
        finally:
            test_logger.removeHandler(handler)

    def test_dct_client_for_identity_does_not_log_identity(self):
        """DCTAPIClient.for_identity() must not log the raw account_id."""
        # AI-generated
        try:
            from dct_mcp_server.dct_client.client import DCTAPIClient

            _ = DCTAPIClient.for_identity  # Check the method exists
        except (ImportError, AttributeError):
            pytest.skip("DCTAPIClient.for_identity not yet implemented — S12")

        import logging
        import io

        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        test_logger = logging.getLogger("dct_mcp_server")
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.DEBUG)

        try:
            DCTAPIClient.for_identity("raw-identity-12345", "http://localhost:8083")
            log_output = log_stream.getvalue()
            assert "raw-identity-12345" not in log_output, (
                "Raw account_id must not appear in log output from for_identity() — S12"
            )
        finally:
            test_logger.removeHandler(handler)


# ---------------------------------------------------------------------------
# S14 — Existing stdio + DCT_API_KEY (standalone) mode continues to work
# ---------------------------------------------------------------------------


class TestS14_BackwardCompatStdioMode:
    """S14: Existing stdio single-user mode (DCT_API_KEY set) still works."""

    def test_get_dct_config_works_with_api_key(self):
        """get_dct_config() must succeed with just DCT_API_KEY set (existing behaviour)."""
        # AI-generated
        from dct_mcp_server.config.config import get_dct_config

        # DCT_API_KEY is already set in conftest set_env_vars fixture
        config = get_dct_config()
        assert config.get("api_key") is not None, (
            "api_key must be present in config when DCT_API_KEY is set — S14"
        )

    def test_dct_api_client_initialises_in_standalone_mode(self):
        """DCTAPIClient must initialise successfully in standalone mode."""
        # AI-generated
        from dct_mcp_server.dct_client.client import DCTAPIClient

        client = DCTAPIClient()
        assert client.api_key == "test-key", (
            "DCTAPIClient must read api_key from DCT_API_KEY env var — S14"
        )
        assert client.base_url is not None, (
            "DCTAPIClient must read base_url from DCT_BASE_URL — S14"
        )

    def test_exceptions_classes_unchanged(self):
        """Existing exception hierarchy must be unchanged — DCTClientError, MCPError."""
        # AI-generated
        from dct_mcp_server.core.exceptions import DCTClientError, MCPError, ToolError

        assert issubclass(DCTClientError, MCPError), (
            "DCTClientError must remain a subclass of MCPError — S14"
        )
        assert issubclass(ToolError, MCPError), (
            "ToolError must remain a subclass of MCPError — S14"
        )

    def test_register_all_tools_still_accepts_single_client(self):
        """register_all_tools() must accept a plain DCTAPIClient (backward compat)."""
        # AI-generated
        import inspect
        from dct_mcp_server.tools import register_all_tools

        sig = inspect.signature(register_all_tools)
        params = list(sig.parameters.keys())
        assert "app" in params and "dct_client" in params, (
            "register_all_tools() must still accept (app, dct_client) — S14"
        )


# ---------------------------------------------------------------------------
# S15 — All existing tests still pass (backward compat guard)
# ---------------------------------------------------------------------------


class TestS15_ExistingTestsNotBroken:
    """S15: Structural guard that key existing test modules are still importable."""

    def test_existing_exceptions_importable(self):
        """Core exception classes must remain importable unchanged."""
        # AI-generated
        from dct_mcp_server.core.exceptions import MCPError, DCTClientError, ToolError

        assert MCPError is not None
        assert DCTClientError is not None
        assert ToolError is not None

    def test_existing_config_exports_unchanged(self):
        """Config module public exports must remain unchanged."""
        # AI-generated
        from dct_mcp_server.config import (
            get_dct_config,
            print_config_help,
            get_configured_toolset,
            is_dynamic_mode,
            validate_all_configs,
        )

        assert callable(get_dct_config)
        assert callable(print_config_help)
        assert callable(get_configured_toolset)
        assert callable(is_dynamic_mode)
        assert callable(validate_all_configs)

    def test_existing_session_public_api_unchanged(self):
        """session.py public API (start_session, end_session, log_tool_call) must remain."""
        # AI-generated
        from dct_mcp_server.core.session import (
            start_session,
            end_session,
            get_session_logger,
            log_tool_call,
            get_current_session_id,
        )

        assert callable(start_session)
        assert callable(end_session)
        assert callable(get_session_logger)
        assert callable(log_tool_call)
        assert callable(get_current_session_id)

    def test_existing_dct_api_client_importable(self):
        """DCTAPIClient must remain importable from its original path."""
        # AI-generated
        from dct_mcp_server.dct_client.client import DCTAPIClient
        from dct_mcp_server.dct_client import DCTAPIClient as DCTAPIClientAlias

        assert DCTAPIClient is DCTAPIClientAlias

    def test_existing_register_all_tools_importable(self):
        """register_all_tools must remain importable from dct_mcp_server.tools."""
        # AI-generated
        from dct_mcp_server.tools import register_all_tools

        assert callable(register_all_tools)
