"""Integration tests for DCT_CONFIRMATION_HOST_APPROVAL flag (DLPXECO-14611).

Exercises the real gate wiring in tools/core/dynamic.py together with the real
confirmation stores and manual_confirmation.txt rules. Only the DCT API dispatch
(dct_client.make_request) and the cached OpenAPI spec are stubbed — everything
between the execute entry point and the wire is the production code path.

Scenarios:
  S1 — manual delete completes on token alone with required_fields==["confirmation_token"]
  S2 — flag unset: manual delete is still refused (asks for resource id + impact)
  S3 — flag unset + model sends display name instead of id → still refused
  S4 — flag ON + no token → gate still fires (token required even with host approval)
  S5 — flag ON + invalid/forged token → gate still refuses
  S6 — consumed token is not replayable (single-use even with host approval)
  S7 — confirmation_level reported as 'manual' even when host approval skips field checks
"""

import pytest

import dct_mcp_server.tools.core.dynamic as dynamic
from tests.integration._gate_helpers import make_execute

# Minimal spec that covers the DELETE /environments/{environmentId} path, which
# maps to the "manual" rule in manual_confirmation.txt.
_HOST_APPROVAL_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "host-approval-test", "version": "1.0.0"},
    "paths": {
        "/environments/{environmentId}": {
            "delete": {
                "operationId": "deleteEnvironment",
                "summary": "Delete environment",
                "tags": ["Environments"],
            },
        },
    },
}

_ENV_PATH = "/environments/env-42"
_ENV_METHOD = "DELETE"


@pytest.fixture(autouse=True)
def _reset_gate_state():
    """Clear all in-memory gate state before and after each test."""
    from dct_mcp_server.tools.core import confirmation_store as cs
    from dct_mcp_server.tools.core import velocity_counter as vc

    vc._velocity_counter._counters.clear()
    cs._grant_store._grants.clear()
    cs._consumed_token_store._pending.clear()
    yield
    vc._velocity_counter._counters.clear()
    cs._grant_store._grants.clear()
    cs._consumed_token_store._pending.clear()


@pytest.fixture
def spec_loaded(monkeypatch):
    """Patch the spec cache and process identity for all tests in this module."""
    monkeypatch.setattr(dynamic, "get_cached_spec", lambda: _HOST_APPROVAL_SPEC)
    monkeypatch.setattr(
        dynamic, "get_process_identity", lambda: "identity-host-approval"
    )


async def test_s1_manual_delete_completes_on_token_alone_with_host_approval(
    spec_loaded, monkeypatch
):
    """With DCT_CONFIRMATION_HOST_APPROVAL=true, a valid token alone passes the gate.

    required_fields must report only ["confirmation_token"] — the host's own
    human-approval UI already handled the user-intent check.
    """
    monkeypatch.setenv("DCT_CONFIRMATION_HOST_APPROVAL", "true")
    execute, client = make_execute()

    # Step 1: first call should return confirmation_required (token gate)
    first = await execute(path=_ENV_PATH, method=_ENV_METHOD)
    assert first["status"] == "confirmation_required"
    assert first["confirmation_level"] == "manual"
    assert first["required_fields"] == ["confirmation_token"]
    assert "{name}" not in (first.get("message") or "")

    token = first["confirmation_token"]

    # Step 2: re-call with the token — gate should pass without resource name / impact
    second = await execute(
        path=_ENV_PATH,
        method=_ENV_METHOD,
        confirmation_token=token,
    )
    assert second["status"] == "success"
    client.make_request.assert_awaited_once()


async def test_s2_flag_unset_still_requires_resource_fields(spec_loaded, monkeypatch):
    """Without the flag, a manual operation is still refused when resource fields are absent."""
    monkeypatch.delenv("DCT_CONFIRMATION_HOST_APPROVAL", raising=False)
    execute, _ = make_execute()

    first = await execute(path=_ENV_PATH, method=_ENV_METHOD)
    assert first["status"] == "confirmation_required"
    assert first["confirmation_level"] == "manual"
    # Without host approval, required_fields must advertise all three fields.
    assert "confirmed_resource_name" in first["required_fields"]
    assert "acknowledged_impact" in first["required_fields"]

    token = first["confirmation_token"]

    # Re-call with token but no resource name → still refused
    second = await execute(
        path=_ENV_PATH,
        method=_ENV_METHOD,
        confirmation_token=token,
    )
    assert second["status"] == "confirmation_required"
    assert second["confirmation_level"] == "manual"


async def test_s3_flag_unset_model_sends_display_name_still_refused(
    spec_loaded, monkeypatch
):
    """Without the flag, a model-supplied display name that doesn't match the path ID is refused."""
    monkeypatch.delenv("DCT_CONFIRMATION_HOST_APPROVAL", raising=False)
    execute, _ = make_execute()

    first = await execute(path=_ENV_PATH, method=_ENV_METHOD)
    token = first["confirmation_token"]

    # Model supplies a display name ("My Environment") instead of the resource ID ("env-42")
    second = await execute(
        path=_ENV_PATH,
        method=_ENV_METHOD,
        confirmation_token=token,
        confirmed_resource_name="My Environment",
        acknowledged_impact=True,
    )
    assert second["status"] == "confirmation_required"
    assert second["confirmation_level"] == "manual"
    # The refusal message should indicate the ID mismatch
    assert "env-42" in (second.get("message") or "")


async def test_s4_flag_on_no_token_gate_still_fires(spec_loaded, monkeypatch):
    """With host approval, the per-call token gate still fires when no token is provided."""
    monkeypatch.setenv("DCT_CONFIRMATION_HOST_APPROVAL", "true")
    execute, client = make_execute()

    result = await execute(path=_ENV_PATH, method=_ENV_METHOD)
    assert result["status"] == "confirmation_required"
    # Token must be included in the refusal so the caller can re-submit
    assert result.get("confirmation_token")
    client.make_request.assert_not_called()


async def test_s5_flag_on_forged_token_refused(spec_loaded, monkeypatch):
    """With host approval, a forged/wrong token is rejected — token gate is unchanged."""
    monkeypatch.setenv("DCT_CONFIRMATION_HOST_APPROVAL", "true")
    execute, client = make_execute()

    result = await execute(
        path=_ENV_PATH,
        method=_ENV_METHOD,
        confirmation_token="FORGE:invalid-token-value",
    )
    assert result["status"] == "confirmation_required"
    assert result["confirmation_level"] == "manual"
    client.make_request.assert_not_called()


async def test_s6_consumed_token_not_replayable(spec_loaded, monkeypatch):
    """A token consumed by a successful call cannot be replayed, even with host approval."""
    monkeypatch.setenv("DCT_CONFIRMATION_HOST_APPROVAL", "true")
    execute, _ = make_execute()

    # Get a valid token
    first = await execute(path=_ENV_PATH, method=_ENV_METHOD)
    token = first["confirmation_token"]

    # Use the token — should succeed
    second = await execute(path=_ENV_PATH, method=_ENV_METHOD, confirmation_token=token)
    assert second["status"] == "success"

    # Replay the same token — must be refused
    third = await execute(path=_ENV_PATH, method=_ENV_METHOD, confirmation_token=token)
    assert third["status"] == "confirmation_required"
    assert "invalid" in (third.get("message") or "").lower() or third.get(
        "confirmation_token"
    )


async def test_s7_confirmation_level_remains_manual_with_host_approval(
    spec_loaded, monkeypatch
):
    """confirmation_level is always 'manual' regardless of the host-approval flag.

    The flag skips field checks — it must NOT downgrade the audit level.
    """
    monkeypatch.setenv("DCT_CONFIRMATION_HOST_APPROVAL", "true")
    execute, _ = make_execute()

    result = await execute(path=_ENV_PATH, method=_ENV_METHOD)
    assert result["status"] == "confirmation_required"
    assert result["confirmation_level"] == "manual"
