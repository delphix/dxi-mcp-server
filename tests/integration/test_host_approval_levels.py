"""Integration tests for host-supplied approval on elevated/manual levels
(DLPXECO-14611).

Drives the real gate wiring in ``tools/core/dynamic.py`` with the real
confirmation stores and ``manual_confirmation.txt`` rules; only the DCT API
dispatch and the cached spec are stubbed.

An embedding host with its own trusted approval UI (the DCT AI Assistant's
Allow once / Allow always buttons) already holds out-of-band evidence of human
intent, so the typed-resource-name checks add nothing there: on that path the
*model* supplies ``confirmed_resource_name``, not a person. With the flag off,
a generic MCP client must keep the full friction.

All functions in this module were AI-generated.
"""

import pytest

import dct_mcp_server.tools.core.dynamic as dynamic
from tests.integration._gate_helpers import make_execute

# DELETE /environments/{environmentId} is mapped `manual` in
# manual_confirmation.txt -- the operation from the bug report.
HOST_APPROVAL_SPEC = {
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

_ENV_PATH = "/environments/2-UNIX_HOST_ENVIRONMENT-9"


@pytest.fixture(autouse=True)
def _reset_gate_state():
    from dct_mcp_server.tools.core import confirmation_store as cs
    from dct_mcp_server.tools.core import velocity_counter as vc

    for store in (cs._grant_store._grants, cs._standing_store._grants):
        store.clear()
    cs._consumed_token_store._pending.clear()
    vc._velocity_counter._counters.clear()
    yield
    for store in (cs._grant_store._grants, cs._standing_store._grants):
        store.clear()
    cs._consumed_token_store._pending.clear()
    vc._velocity_counter._counters.clear()


@pytest.fixture
def spec_loaded(monkeypatch):
    monkeypatch.setattr(dynamic, "get_cached_spec", lambda: HOST_APPROVAL_SPEC)
    monkeypatch.setattr(
        dynamic, "get_process_identity", lambda: "identity-host-approval"
    )


async def _first_leg(execute):
    """Ask for the delete and return the confirmation_required response."""
    result = await execute(path=_ENV_PATH, method="DELETE")
    assert result["status"] == "confirmation_required"
    return result


async def test_DLPXECO14611_manual_delete_completes_on_token_alone(
    spec_loaded, monkeypatch
):  # AI-generated
    """AC-1: the reproduction from the ticket -- a manual-level delete run by a
    host that supplied its own approval completes with the token alone."""
    monkeypatch.setenv("DCT_CONFIRMATION_HOST_APPROVAL", "true")
    execute, client = make_execute()

    first = await _first_leg(execute)
    # AC-2: only the token is advertised, since only the token is enforced.
    assert first["required_fields"] == ["confirmation_token"]

    second = await execute(
        path=_ENV_PATH,
        method="DELETE",
        confirmation_token=first["confirmation_token"],
    )

    assert second["status"] == "success", second
    client.make_request.assert_awaited_once()


async def test_DLPXECO14611_typed_id_still_required_by_default(
    spec_loaded, monkeypatch
):  # AI-generated
    """AC-3: with the flag unset, a generic MCP client keeps the friction --
    the same token-only retry is refused and asked for the resource id."""
    monkeypatch.delenv("DCT_CONFIRMATION_HOST_APPROVAL", raising=False)
    execute, client = make_execute()

    first = await _first_leg(execute)
    assert "confirmed_resource_name" in first["required_fields"]

    second = await execute(
        path=_ENV_PATH,
        method="DELETE",
        confirmation_token=first["confirmation_token"],
    )

    assert second["status"] == "confirmation_required"
    assert "confirmed_resource_name" in second["required_fields"]
    client.make_request.assert_not_awaited()


async def test_DLPXECO14611_wrong_resource_name_refused_by_default(
    spec_loaded, monkeypatch
):  # AI-generated
    """The reported failure: the model sends the environment *name* where the
    id is required. Still refused when the host has not approved."""
    monkeypatch.delenv("DCT_CONFIRMATION_HOST_APPROVAL", raising=False)
    execute, client = make_execute()

    first = await _first_leg(execute)
    second = await execute(
        path=_ENV_PATH,
        method="DELETE",
        confirmation_token=first["confirmation_token"],
        confirmed_resource_name="r92-tgt",
        acknowledged_impact=True,
    )

    assert second["status"] == "confirmation_required"
    assert "does not match" in second["message"]
    client.make_request.assert_not_awaited()


async def test_DLPXECO14611_token_gate_still_enforced(
    spec_loaded, monkeypatch
):  # AI-generated
    """AC-4: the flag waives the typed-id checks only -- a call carrying no
    token, and one carrying a bad token, are both still refused."""
    monkeypatch.setenv("DCT_CONFIRMATION_HOST_APPROVAL", "true")
    execute, client = make_execute()

    no_token = await execute(path=_ENV_PATH, method="DELETE")
    assert no_token["status"] == "confirmation_required"

    bad_token = await execute(
        path=_ENV_PATH, method="DELETE", confirmation_token="forged-token"
    )
    assert bad_token["status"] == "confirmation_required"
    client.make_request.assert_not_awaited()


async def test_DLPXECO14611_token_is_not_replayable(
    spec_loaded, monkeypatch
):  # AI-generated
    """AC-4: a token consumed by an approved call cannot be reused."""
    monkeypatch.setenv("DCT_CONFIRMATION_HOST_APPROVAL", "true")
    execute, client = make_execute()

    first = await _first_leg(execute)
    token = first["confirmation_token"]

    approved = await execute(path=_ENV_PATH, method="DELETE", confirmation_token=token)
    assert approved["status"] == "success"

    replayed = await execute(path=_ENV_PATH, method="DELETE", confirmation_token=token)
    assert replayed["status"] == "confirmation_required"
    client.make_request.assert_awaited_once()


async def test_DLPXECO14611_level_preserved_for_audit(
    spec_loaded, monkeypatch
):  # AI-generated
    """AC-5: the level is not downgraded to standard, so gate events and the
    response still identify this as a manual-level operation."""
    monkeypatch.setenv("DCT_CONFIRMATION_HOST_APPROVAL", "true")
    execute, _ = make_execute()

    first = await _first_leg(execute)
    assert first["confirmation_level"] == "manual"


async def test_DLPXECO14611_policy_message_passed_through(
    spec_loaded, monkeypatch
):  # AI-generated
    """The rule's own message still reaches the caller unchanged, placeholder
    included -- the flag waives the typed-id checks, not the policy text."""
    monkeypatch.setenv("DCT_CONFIRMATION_HOST_APPROVAL", "true")
    execute, _ = make_execute()

    first = await _first_leg(execute)
    assert "permanently delete environment" in first["message"]
    assert "Provide confirmed_resource_name" not in first["message"]
