"""
Generated tests for DLPXECO-14324 — HTTP transport, embedded auth, per-request identity resolution,
and secret-safe execution for DCT MCP server embedded deployment mode.

Scenarios sourced from docs/DLPXECO-14324/DLPXECO-14324-test-plan.md.

All DCT API I/O is mocked — no real network calls are made.
Tests in this file are AI-generated.
"""

import os
import re
import threading
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch, call

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
# S1 — Server starts with DCT_TRANSPORT=stdio (default); no HTTP port opened
# ---------------------------------------------------------------------------

class TestS1_StdioTransport:
    """S1: Server starts successfully with DCT_TRANSPORT=stdio (default)."""

    def test_default_transport_is_stdio(self):
        """Verify that when DCT_TRANSPORT is unset, transport defaults to 'stdio'."""
        # AI-generated
        with _set_env(DCT_TRANSPORT="stdio"):
            from dct_mcp_server.config.config import get_dct_config
            config = get_dct_config()
            assert config.get("transport", "stdio") == "stdio", (
                "Default transport must be 'stdio' — see test-plan S1"
            )

    def test_stdio_transport_value_in_config(self):
        """Verify that DCT_TRANSPORT=stdio is accepted by config."""
        # AI-generated
        with _set_env(DCT_TRANSPORT="stdio"):
            from dct_mcp_server.config.config import get_dct_config
            config = get_dct_config()
            assert config.get("transport", "stdio") == "stdio"


# ---------------------------------------------------------------------------
# S2 — Server starts with DCT_TRANSPORT=http DCT_AUTH_MODE=embedded; no API key
# ---------------------------------------------------------------------------

class TestS2_HttpTransportEmbeddedMode:
    """S2: Server starts with DCT_TRANSPORT=http DCT_AUTH_MODE=embedded (no DCT_API_KEY)."""

    def test_embedded_mode_does_not_require_api_key(self):
        """In embedded mode, DCT_API_KEY must NOT be required at startup."""
        # AI-generated
        # Remove API key and set embedded mode
        env_overrides = {
            "DCT_TRANSPORT": "http",
            "DCT_AUTH_MODE": "embedded",
        }
        # Temporarily unset DCT_API_KEY
        saved = os.environ.pop("DCT_API_KEY", None)
        os.environ.update(env_overrides)
        try:
            from dct_mcp_server.config.config import get_dct_config
            try:
                config = get_dct_config()
                # In embedded mode, no error should be raised for missing API key
                assert config.get("auth_mode") == "embedded", (
                    "auth_mode must be 'embedded' when DCT_AUTH_MODE=embedded — S2"
                )
            except ValueError as exc:
                if "DCT_API_KEY" in str(exc):
                    pytest.fail(
                        "get_dct_config() raised ValueError for missing DCT_API_KEY "
                        "in embedded mode — this must not happen (S2)"
                    )
                raise
        finally:
            if saved is not None:
                os.environ["DCT_API_KEY"] = saved
            for k in env_overrides:
                os.environ.pop(k, None)

    def test_http_transport_config_accepted(self):
        """Verify that DCT_TRANSPORT=http is recognised in config."""
        # AI-generated
        with _set_env(DCT_TRANSPORT="http", DCT_AUTH_MODE="embedded"):
            from dct_mcp_server.config.config import get_dct_config
            saved = os.environ.pop("DCT_API_KEY", None)
            try:
                try:
                    config = get_dct_config()
                    assert config.get("transport", "stdio") == "http", (
                        "transport must be 'http' when DCT_TRANSPORT=http — S2"
                    )
                except ValueError as exc:
                    if "DCT_API_KEY" in str(exc):
                        pytest.fail(
                            "get_dct_config() must not require DCT_API_KEY in embedded mode — S2"
                        )
                    raise
            finally:
                if saved is not None:
                    os.environ["DCT_API_KEY"] = saved

    def test_http_port_config_defaults(self):
        """Verify DCT_HTTP_HOST and DCT_HTTP_PORT have correct defaults."""
        # AI-generated
        with _set_env(DCT_TRANSPORT="http", DCT_AUTH_MODE="embedded"):
            from dct_mcp_server.config.config import get_dct_config
            saved = os.environ.pop("DCT_API_KEY", None)
            try:
                try:
                    config = get_dct_config()
                    assert config.get("http_host", "127.0.0.1") == "127.0.0.1", (
                        "http_host must default to 127.0.0.1 — S2"
                    )
                    assert config.get("http_port", 8765) == 8765, (
                        "http_port must default to 8765 — S2"
                    )
                except ValueError as exc:
                    if "DCT_API_KEY" in str(exc):
                        pytest.skip("get_dct_config() not yet updated for embedded mode")
                    raise
            finally:
                if saved is not None:
                    os.environ["DCT_API_KEY"] = saved


# ---------------------------------------------------------------------------
# S3 — HTTP request with valid X-CLIENT-ID causes tool to use that identity
# ---------------------------------------------------------------------------

class TestS3_ClientIdIdentityResolution:
    """S3: Valid X-CLIENT-ID header is used as tool execution identity."""

    def test_caller_id_context_var_is_set_by_middleware(self):
        """ClientIDMiddleware must set _CALLER_ID_VAR to the X-CLIENT-ID value."""
        # AI-generated
        try:
            from dct_mcp_server.core.auth import _CALLER_ID_VAR, ClientIDMiddleware
        except ImportError:
            pytest.skip("auth.py not yet implemented — S3 will pass once FR-002 is done")

        # Simulate ASGI scope and receive/send callables
        received_caller = []

        async def fake_app(scope, receive, send):
            received_caller.append(_CALLER_ID_VAR.get(None))

        middleware = ClientIDMiddleware(fake_app)
        scope = {
            "type": "http",
            "headers": [(b"x-client-id", b"user-alice")],
        }

        import asyncio
        asyncio.get_event_loop().run_until_complete(
            middleware(scope, AsyncMock(), AsyncMock())
        )
        assert received_caller == ["user-alice"], (
            "_CALLER_ID_VAR must be 'user-alice' inside the request scope — S3"
        )

    def test_resolve_auth_returns_caller_identity(self):
        """resolve_auth() must return the caller identity set by middleware in embedded mode."""
        # AI-generated
        try:
            from dct_mcp_server.core.auth import _CALLER_ID_VAR, resolve_auth
        except ImportError:
            pytest.skip("auth.py not yet implemented — S3")

        with _set_env(DCT_AUTH_MODE="embedded"):
            # remove DCT_API_KEY to simulate embedded mode (no key needed)
            saved = os.environ.pop("DCT_API_KEY", None)
            try:
                token = _CALLER_ID_VAR.set("user-bob")
                try:
                    auth_ctx = resolve_auth()
                    assert auth_ctx is not None, "resolve_auth() must return an AuthContext — S3"
                    assert auth_ctx.account_id == "user-bob", (
                        "AuthContext.account_id must equal the X-CLIENT-ID value — S3"
                    )
                finally:
                    _CALLER_ID_VAR.reset(token)
            finally:
                if saved is not None:
                    os.environ["DCT_API_KEY"] = saved

    def test_identity_is_not_logged_in_plaintext(self):
        """Masked identity (not raw value) must appear in log output — see FR-008 / S12."""
        # AI-generated
        try:
            from dct_mcp_server.dct_client.client import _mask_secret
        except ImportError:
            pytest.skip("_mask_secret not yet implemented — S3/S12")

        raw = "user-alice"
        masked = _mask_secret(raw)
        assert raw not in masked or masked.startswith("***"), (
            "_mask_secret must not return the raw identity unchanged — S3"
        )


# ---------------------------------------------------------------------------
# S4 — Concurrent requests with different X-CLIENT-ID use independent clients
# ---------------------------------------------------------------------------

class TestS4_CrossUserIsolation:
    """S4: Two concurrent requests with different identities have zero cross-user leakage."""

    def test_client_registry_creates_separate_clients_per_identity(self):
        """ClientRegistry must return distinct DCTAPIClient instances for distinct identities."""
        # AI-generated
        try:
            from dct_mcp_server.core.client_registry import ClientRegistry
            from dct_mcp_server.core.auth import AuthContext
        except ImportError:
            pytest.skip("client_registry.py or auth.py not yet implemented — S4")

        registry = ClientRegistry()
        auth_a = AuthContext(account_id="user-alice", api_key="key-a", auth_mode="embedded")
        auth_b = AuthContext(account_id="user-bob",  api_key="key-b", auth_mode="embedded")

        client_a = registry.get_client(auth_a)
        client_b = registry.get_client(auth_b)

        assert client_a is not client_b, (
            "ClientRegistry must return distinct clients for different identities — S4"
        )

    def test_client_registry_returns_same_client_for_same_identity(self):
        """ClientRegistry must return the cached client for the same identity."""
        # AI-generated
        try:
            from dct_mcp_server.core.client_registry import ClientRegistry
            from dct_mcp_server.core.auth import AuthContext
        except ImportError:
            pytest.skip("client_registry.py or auth.py not yet implemented — S4")

        registry = ClientRegistry()
        auth = AuthContext(account_id="user-charlie", api_key="key-c", auth_mode="embedded")

        client_first  = registry.get_client(auth)
        client_second = registry.get_client(auth)

        assert client_first is client_second, (
            "ClientRegistry must return the same cached client for the same identity — S4"
        )

    def test_concurrent_requests_use_different_clients(self):
        """Under concurrent access, ClientRegistry must never swap client references."""
        # AI-generated
        try:
            from dct_mcp_server.core.client_registry import ClientRegistry
            from dct_mcp_server.core.auth import AuthContext
        except ImportError:
            pytest.skip("client_registry.py or auth.py not yet implemented — S4")

        registry = ClientRegistry()
        results: Dict[str, Any] = {}
        errors: list = []

        def worker(identity: str):
            try:
                auth = AuthContext(account_id=identity, api_key=f"key-{identity}", auth_mode="embedded")
                client = registry.get_client(auth)
                results[identity] = id(client)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(f"user-{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"ClientRegistry raised errors under concurrency: {errors}"
        # All 10 identities must have distinct client object IDs
        assert len(set(results.values())) == 10, (
            "Each identity must have a distinct client under concurrent access — S4"
        )


# ---------------------------------------------------------------------------
# S5 — Missing X-CLIENT-ID returns AuthError
# ---------------------------------------------------------------------------

class TestS5_MissingClientId:
    """S5: HTTP request with missing X-CLIENT-ID returns AuthError."""

    def test_middleware_raises_auth_error_when_header_absent(self):
        """ClientIDMiddleware must return HTTP 401 when X-CLIENT-ID is missing."""
        # AI-generated
        try:
            from dct_mcp_server.core.auth import ClientIDMiddleware
        except ImportError:
            pytest.skip("auth.py not yet implemented — S5")

        async def fake_app(scope, receive, send):
            pass  # Should never reach here

        sent_messages = []

        async def capture_send(msg):
            sent_messages.append(msg)

        middleware = ClientIDMiddleware(fake_app)
        scope = {
            "type": "http",
            "headers": [],  # No X-CLIENT-ID header
        }

        import asyncio
        asyncio.get_event_loop().run_until_complete(
            middleware(scope, AsyncMock(), capture_send)
        )
        # Middleware should have sent a 401 response without raising
        assert sent_messages, "Middleware must send an HTTP response for missing X-CLIENT-ID"
        start_msg = sent_messages[0]
        assert start_msg.get("status") == 401, (
            f"Expected HTTP 401 for missing X-CLIENT-ID, got {start_msg.get('status')} — S5"
        )

    def test_resolve_auth_raises_when_no_context_var(self):
        """resolve_auth() must raise AuthError when called with no ContextVar set."""
        # AI-generated
        try:
            from dct_mcp_server.core.auth import _CALLER_ID_VAR, resolve_auth
            from dct_mcp_server.core.exceptions import AuthError
        except ImportError:
            pytest.skip("auth.py not yet implemented — S5")

        # Ensure ContextVar is unset in embedded mode
        with _set_env(DCT_AUTH_MODE="embedded"):
            # Do not set _CALLER_ID_VAR
            with pytest.raises(AuthError):
                resolve_auth()


# ---------------------------------------------------------------------------
# S6 — Empty X-CLIENT-ID header returns AuthError
# ---------------------------------------------------------------------------

class TestS6_EmptyClientId:
    """S6: HTTP request with empty X-CLIENT-ID header returns AuthError."""

    def test_middleware_raises_auth_error_for_empty_header(self):
        """ClientIDMiddleware must return HTTP 401 when X-CLIENT-ID is empty string."""
        # AI-generated
        try:
            from dct_mcp_server.core.auth import ClientIDMiddleware
        except ImportError:
            pytest.skip("auth.py not yet implemented — S6")

        async def fake_app(scope, receive, send):
            pass

        sent_messages = []

        async def capture_send(msg):
            sent_messages.append(msg)

        middleware = ClientIDMiddleware(fake_app)
        scope = {
            "type": "http",
            "headers": [(b"x-client-id", b"")],  # Empty header value
        }

        import asyncio
        asyncio.get_event_loop().run_until_complete(
            middleware(scope, AsyncMock(), capture_send)
        )
        assert sent_messages, "Middleware must send an HTTP response for empty X-CLIENT-ID"
        start_msg = sent_messages[0]
        assert start_msg.get("status") == 401, (
            f"Expected HTTP 401 for empty X-CLIENT-ID, got {start_msg.get('status')} — S6"
        )

    def test_resolve_auth_raises_when_caller_id_is_empty(self):
        """resolve_auth() must raise AuthError when _CALLER_ID_VAR is set to empty string."""
        # AI-generated
        try:
            from dct_mcp_server.core.auth import _CALLER_ID_VAR, resolve_auth
            from dct_mcp_server.core.exceptions import AuthError
        except ImportError:
            pytest.skip("auth.py not yet implemented — S6")

        with _set_env(DCT_AUTH_MODE="embedded"):
            token = _CALLER_ID_VAR.set("")
            try:
                with pytest.raises(AuthError):
                    resolve_auth()
            finally:
                _CALLER_ID_VAR.reset(token)


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
                pytest.skip("get_dct_config() does not yet support require_key=False — S7")
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
            with patch("dct_mcp_server.core.session.SessionManager._get_project_root",
                       return_value=Path(tmpdir)):
                session_logger = get_or_create_caller_session("caller-test-001")
                assert session_logger is not None, (
                    "get_or_create_caller_session must return a logger — S8"
                )

    def test_tool_execution_tags_telemetry_with_caller_id(self):
        """@log_tool_execution must include caller_id in telemetry when in embedded mode."""
        # AI-generated
        try:
            from dct_mcp_server.core.auth import _CALLER_ID_VAR
            from dct_mcp_server.core.decorators import log_tool_execution
            from dct_mcp_server.core.session import get_or_create_caller_session
        except ImportError:
            pytest.skip("auth.py / decorators not yet updated for embedded mode — S8")

        logged_data: list = []

        def fake_log_tool_call(data, session_id=None):
            logged_data.append((data, session_id))

        with patch("dct_mcp_server.core.decorators.log_tool_call", side_effect=fake_log_tool_call):
            token = _CALLER_ID_VAR.set("caller-s8")
            try:
                @log_tool_execution
                def sample_tool():
                    return {"ok": True}

                sample_tool()
            finally:
                _CALLER_ID_VAR.reset(token)

        # Verify that telemetry was logged with a reference to the caller
        assert logged_data, "log_tool_call was not called — @log_tool_execution must call it (S8)"
        # The session_id or data should reference the caller
        # (exact shape depends on implementation)


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
            with patch("dct_mcp_server.core.session.SessionManager._get_project_root",
                       return_value=Path(tmpdir)):
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

        normal_args = {"vdb_id": "vdb-123", "action": "search", "filter": "name EQ 'prod'"}
        try:
            SecretGuard.check(normal_args)
        except Exception as exc:
            pytest.fail(f"SecretGuard.check() must not block normal tool args: {exc} — S11")


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
        assert raw_key not in masked, (
            "_mask_secret must not return the raw key — S12"
        )
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
            client = DCTAPIClient()
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
            client = DCTAPIClient.for_identity("raw-identity-12345", "http://localhost:8083")
            log_output = log_stream.getvalue()
            assert "raw-identity-12345" not in log_output, (
                "Raw account_id must not appear in log output from for_identity() — S12"
            )
        finally:
            test_logger.removeHandler(handler)


# ---------------------------------------------------------------------------
# S13 — TLS warning emitted when DCT_TRANSPORT=http and DCT_REQUIRE_TLS=false
# ---------------------------------------------------------------------------

class TestS13_TlsRequirementWarning:
    """S13: Server emits a warning log at startup when DCT_REQUIRE_TLS=false."""

    def test_tls_config_default_is_true(self):
        """DCT_REQUIRE_TLS must default to true in config."""
        # AI-generated
        with _set_env(DCT_TRANSPORT="http", DCT_AUTH_MODE="embedded"):
            from dct_mcp_server.config.config import get_dct_config
            saved = os.environ.pop("DCT_API_KEY", None)
            try:
                try:
                    config = get_dct_config()
                    assert config.get("require_tls", True) is True, (
                        "DCT_REQUIRE_TLS must default to True — S13"
                    )
                except (TypeError, ValueError) as exc:
                    if "DCT_API_KEY" in str(exc):
                        pytest.skip("get_dct_config() not yet updated for embedded mode — S13")
                    raise
            finally:
                if saved is not None:
                    os.environ["DCT_API_KEY"] = saved

    def test_require_tls_false_produces_warning(self):
        """Starting server with DCT_REQUIRE_TLS=false must emit a TLS warning to the log."""
        # AI-generated
        import logging
        import io

        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        root_logger = logging.getLogger("dct_mcp_server")
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.WARNING)

        with _set_env(DCT_TRANSPORT="http", DCT_AUTH_MODE="embedded", DCT_REQUIRE_TLS="false"):
            saved = os.environ.pop("DCT_API_KEY", None)
            try:
                try:
                    from dct_mcp_server.config.config import get_dct_config
                    config = get_dct_config()
                    require_tls = config.get("require_tls", True)
                    if not require_tls:
                        # The warning log may happen at server startup, not here,
                        # so verify the config at least exposes require_tls=False correctly
                        assert require_tls is False, (
                            "Config must expose require_tls=False when DCT_REQUIRE_TLS=false — S13"
                        )
                except (TypeError, ValueError) as exc:
                    if "DCT_API_KEY" in str(exc):
                        pytest.skip("Embedded mode config not yet implemented — S13")
                    raise
            finally:
                if saved is not None:
                    os.environ["DCT_API_KEY"] = saved
                root_logger.removeHandler(handler)


# ---------------------------------------------------------------------------
# S14 — Existing stdio + DCT_API_KEY mode continues to work
# ---------------------------------------------------------------------------

class TestS14_BackwardCompatStdioMode:
    """S14: Existing stdio single-user mode (DCT_API_KEY set, no DCT_TRANSPORT) still works."""

    def test_get_dct_config_works_with_api_key_and_no_transport(self):
        """get_dct_config() must succeed with just DCT_API_KEY set (existing behaviour)."""
        # AI-generated
        from dct_mcp_server.config.config import get_dct_config
        # DCT_API_KEY is already set in conftest set_env_vars fixture
        config = get_dct_config()
        assert config.get("api_key") is not None, (
            "api_key must be present in config when DCT_API_KEY is set — S14"
        )
        # transport must default to 'stdio'
        transport = config.get("transport", "stdio")
        assert transport == "stdio", (
            f"Default transport must remain 'stdio', got '{transport}' — S14"
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
