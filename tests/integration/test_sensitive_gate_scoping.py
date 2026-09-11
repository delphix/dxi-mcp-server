"""Integration tests for scoping the sensitive-input gate (DLPXECO-14642).

Drives the real gate wiring in ``tools/core/dynamic.py``; only the DCT API
dispatch and the cached spec are stubbed.

The gate asks an embedding host to capture a secret out-of-band and re-call.
Only the DCT AI Assistant does that. In Claude Desktop, Claude Code and
third-party MCP clients nothing can, so raising the gate there deadlocks the
operation rather than protecting anything: the model relays the request into
chat, the value lands in ``body``, rule 1 re-flags it, and the call never
dispatches.

All functions in this module were AI-generated.
"""

import pytest

import dct_mcp_server.tools.core.dynamic as dynamic
from dct_mcp_server.tools.core.dynamic import _SENSITIVE_NONCE_ENV
from tests.integration._gate_helpers import make_execute

NONCE = "host-nonce-14642"

# A credentialed create: `password` is annotated, which is the only thing that
# makes a field a secret here (DLPXECO-14641).
SECRET_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "sensitive-scope-test", "version": "1.0.0"},
    "paths": {
        "/environments": {
            "post": {
                "operationId": "createEnvironment",
                "summary": "Create environment",
                "tags": ["Environments"],
            },
        },
    },
    "components": {
        "schemas": {
            "EnvironmentCreateParameters": {
                "properties": {
                    "name": {"type": "string"},
                    "username": {"type": "string"},
                    "password": {
                        "type": "string",
                        "x-dct-toolkit-credential-field": True,
                    },
                }
            }
        }
    },
}

_PATH = "/environments"

# `password` is annotated, so an inline value is what the gate acts on: strip
# it and have the host recapture. Detection is annotation-only (DLPXECO-14641),
# so the field has to actually be in the body for the gate to have anything to
# do -- an absent credential is left to the API's own validation.
_BODY_INLINE_SECRET = {
    "name": "r92t",
    "username": "dlpxqa",
    "hostname": "r92.dlpxdc.co",
    "password": "typed-in-chat",
}


@pytest.fixture
def spec_loaded(monkeypatch):
    monkeypatch.setattr(dynamic, "get_cached_spec", lambda: SECRET_SPEC)
    monkeypatch.setattr(dynamic, "get_process_identity", lambda: "identity-14642")


def _as_host(monkeypatch, *, nonce=True, auth_mode="embedded"):
    """Configure (or deliberately half-configure) a capture-capable host."""
    if nonce:
        monkeypatch.setenv(_SENSITIVE_NONCE_ENV, NONCE)
    else:
        monkeypatch.delenv(_SENSITIVE_NONCE_ENV, raising=False)
    monkeypatch.setattr(dynamic, "get_dct_config", lambda **_: {"auth_mode": auth_mode})


async def test_DLPXECO14642_embedded_host_still_gets_the_gate(
    spec_loaded, monkeypatch
):  # AI-generated
    """AC-3: inside the DCT AI Assistant the gate is unchanged."""
    _as_host(monkeypatch)
    execute, client = make_execute()

    result = await execute(path=_PATH, method="POST", body=dict(_BODY_INLINE_SECRET))

    assert result["status"] == "sensitive_input_required", result
    assert result["required_sensitive_fields"] == ["password"]
    client.make_request.assert_not_awaited()


async def test_DLPXECO14642_standalone_client_is_not_gated(
    spec_loaded, monkeypatch
):  # AI-generated
    """AC-1: the reproduction — a standalone MCP client must not be asked for
    a secret it has no way to supply."""
    _as_host(monkeypatch, nonce=False, auth_mode="standalone")
    execute, client = make_execute()

    result = await execute(path=_PATH, method="POST", body=dict(_BODY_INLINE_SECRET))

    assert result.get("status") != "sensitive_input_required", result


async def test_DLPXECO14642_standalone_dispatches_the_inline_credential(
    spec_loaded, monkeypatch
):  # AI-generated
    """AC-1: the body reaches the API as supplied, secret included."""
    _as_host(monkeypatch, nonce=False, auth_mode="standalone")
    execute, client = make_execute()

    result = await execute(path=_PATH, method="POST", body=dict(_BODY_INLINE_SECRET))

    assert result["status"] == "success", result
    client.make_request.assert_awaited_once()
    sent = client.make_request.await_args.kwargs["json"]
    assert sent["password"] == "typed-in-chat"


async def test_DLPXECO14642_nonce_without_embedded_mode_is_not_gated(
    spec_loaded, monkeypatch
):  # AI-generated
    """AC-2: both markers are required — a stray nonce is not a host."""
    _as_host(monkeypatch, nonce=True, auth_mode="standalone")
    execute, _ = make_execute()

    result = await execute(path=_PATH, method="POST", body=dict(_BODY_INLINE_SECRET))

    assert result.get("status") != "sensitive_input_required", result


async def test_DLPXECO14642_embedded_mode_without_nonce_is_not_gated(
    spec_loaded, monkeypatch
):  # AI-generated
    """AC-2: embedded auth alone does not imply a masked-input UI."""
    _as_host(monkeypatch, nonce=False, auth_mode="embedded")
    execute, _ = make_execute()

    result = await execute(path=_PATH, method="POST", body=dict(_BODY_INLINE_SECRET))

    assert result.get("status") != "sensitive_input_required", result


async def test_DLPXECO14642_config_failure_with_nonce_keeps_the_gate(
    spec_loaded, monkeypatch
):  # AI-generated
    """AC-4: a host set the nonce, so an unreadable config must cost a blocked
    operation rather than a secret travelling inline."""
    monkeypatch.setenv(_SENSITIVE_NONCE_ENV, NONCE)

    def _boom(**_):
        raise RuntimeError("config unreadable")

    monkeypatch.setattr(dynamic, "get_dct_config", _boom)
    execute, client = make_execute()

    result = await execute(path=_PATH, method="POST", body=dict(_BODY_INLINE_SECRET))

    assert result["status"] == "sensitive_input_required", result
    client.make_request.assert_not_awaited()


async def test_DLPXECO14642_read_operations_unaffected(
    spec_loaded, monkeypatch
):  # AI-generated
    """AC-5: the gate never applied to GET, in either mode."""
    _as_host(monkeypatch)
    execute, _ = make_execute()

    result = await execute(path=_PATH, method="GET")

    assert result.get("status") != "sensitive_input_required", result
