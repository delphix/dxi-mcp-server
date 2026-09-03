"""Integration tests for host-attested per-operation approval (DLPXECO-14613).

Drives the real gate wiring in ``tools/core/dynamic.py`` with the real
confirmation stores and ``manual_confirmation.txt`` rules; only the DCT API
dispatch and the cached spec are stubbed.

The embedding host gates every mutating call behind its own trusted approval UI.
When a human approves an individual operation there, replaying the call with an
authenticated ``human_approved`` marker satisfies the server's confirmation
requirement -- otherwise the same person is asked the same question twice more
(the three-click delete).

All functions in this module were AI-generated.
"""

import pytest

import dct_mcp_server.tools.core.dynamic as dynamic
from dct_mcp_server.tools.core.dynamic import _SENSITIVE_NONCE_ENV
from tests.integration._gate_helpers import make_execute

NONCE = "host-nonce-14613"

# DELETE /environments/{environmentId} is `manual`; POST /vdbs/{vdbId}/delete is
# a floor operation; PATCH /vdbs/{vdbId} is `standard`.
ATTEST_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "attest-test", "version": "1.0.0"},
    "paths": {
        "/environments/{environmentId}": {
            "delete": {
                "operationId": "deleteEnvironment",
                "summary": "Delete environment",
                "tags": ["Environments"],
            },
        },
        "/vdbs/{vdbId}": {
            "patch": {
                "operationId": "updateVdb",
                "summary": "Update VDB",
                "tags": ["VDBs"],
            },
        },
    },
}

_ENV_PATH = "/environments/2-UNIX_HOST_ENVIRONMENT-9"
_VDB_PATH = "/vdbs/vdb-1"


@pytest.fixture(autouse=True)
def _reset_gate_state(monkeypatch):
    from dct_mcp_server.tools.core import confirmation_store as cs
    from dct_mcp_server.tools.core import velocity_counter as vc

    for store in (cs._grant_store._grants, cs._standing_store._grants):
        store.clear()
    cs._consumed_token_store._pending.clear()
    vc._velocity_counter._counters.clear()
    monkeypatch.setenv(_SENSITIVE_NONCE_ENV, NONCE)
    yield
    for store in (cs._grant_store._grants, cs._standing_store._grants):
        store.clear()
    cs._consumed_token_store._pending.clear()
    vc._velocity_counter._counters.clear()


@pytest.fixture
def spec_loaded(monkeypatch):
    monkeypatch.setattr(dynamic, "get_cached_spec", lambda: ATTEST_SPEC)
    monkeypatch.setattr(dynamic, "get_process_identity", lambda: "identity-attest")


def _attestation():
    return {"nonce": NONCE}


async def test_DLPXECO14613_attested_delete_runs_without_confirmation(
    spec_loaded,
):  # AI-generated
    """AC-1: the reproduction -- one human approval, no confirmation_required.

    Without the marker this same call returns confirmation_required, which is
    what produced the second and third Allow once cards.
    """
    execute, client = make_execute()

    gated = await execute(path=_ENV_PATH, method="DELETE")
    assert gated["status"] == "confirmation_required"
    client.make_request.assert_not_awaited()

    approved = await execute(
        path=_ENV_PATH, method="DELETE", human_approved=_attestation()
    )
    assert approved["status"] == "success", approved
    client.make_request.assert_awaited_once()


async def test_DLPXECO14613_forged_attestation_is_ignored(
    spec_loaded,
):  # AI-generated
    """AC-3: a caller that guesses the argument gains nothing without the nonce."""
    execute, client = make_execute()

    for marker in (
        {"nonce": "guessed"},
        {},
        None,
        "yes",
        {"nonce": ""},
    ):
        result = await execute(path=_ENV_PATH, method="DELETE", human_approved=marker)
        assert result["status"] == "confirmation_required", marker
    client.make_request.assert_not_awaited()


async def test_DLPXECO14613_no_nonce_configured_ignores_attestation(
    spec_loaded, monkeypatch
):  # AI-generated
    """AC-4: a standalone deployment has no shared secret, so nothing is
    honoured and every level behaves exactly as before."""
    monkeypatch.delenv(_SENSITIVE_NONCE_ENV, raising=False)
    execute, client = make_execute()

    result = await execute(
        path=_ENV_PATH, method="DELETE", human_approved={"nonce": NONCE}
    )
    assert result["status"] == "confirmation_required"
    client.make_request.assert_not_awaited()


async def test_DLPXECO14613_attestation_is_per_call(spec_loaded):  # AI-generated
    """AC-2: the marker authorises the call it accompanies and nothing else --
    a second operation without it is still gated."""
    execute, client = make_execute()

    approved = await execute(
        path=_ENV_PATH, method="DELETE", human_approved=_attestation()
    )
    assert approved["status"] == "success"

    # A different operation on the same server, no marker -> still gated.
    other = await execute(path=_VDB_PATH, method="PATCH", body={"name": "x"})
    assert other["status"] == "confirmation_required"
    client.make_request.assert_awaited_once()


async def test_DLPXECO14613_attestation_does_not_persist(
    spec_loaded,
):  # AI-generated
    """An attestation authorises one call, not a session: repeating the same
    operation without the marker is gated again."""
    execute, client = make_execute()

    first = await execute(
        path=_ENV_PATH, method="DELETE", human_approved=_attestation()
    )
    assert first["status"] == "success"

    second = await execute(path=_ENV_PATH, method="DELETE")
    assert second["status"] == "confirmation_required"
    client.make_request.assert_awaited_once()


async def test_DLPXECO14613_reads_are_unaffected(spec_loaded):  # AI-generated
    """GET traffic never entered the confirmation gate and still does not."""
    execute, client = make_execute()

    # The spec has no GET on this path, so a read is rejected by lookup rather
    # than by the gate -- proving the gate is not what stops it.
    result = await execute(path=_ENV_PATH, method="GET")
    assert result["status"] == "error"
    assert result["code"] == "OPERATION_NOT_FOUND"
    client.make_request.assert_not_awaited()


async def test_DLPXECO14613_audit_records_attested_outcome(
    spec_loaded, monkeypatch
):  # AI-generated
    """AC-6: an attested call is recorded under its own outcome, carrying the
    policy level, so it is never confused with a token-confirmed one."""
    events = []
    monkeypatch.setattr(
        dynamic,
        "emit_gate_event",
        lambda outcome, identity, method, path, level, **kw: events.append(
            (outcome, level)
        ),
    )
    execute, _ = make_execute()

    await execute(path=_ENV_PATH, method="DELETE", human_approved=_attestation())

    assert ("host_attested", "manual") in events


async def test_DLPXECO14613_attestation_satisfies_a_floor_operation(
    spec_loaded,
):  # AI-generated
    """Deliberate, and the distinction a reviewer will look for.

    floor_operations.py holds that any DELETE requires individual single-use
    confirmation and "cannot be authorized by batch grant, standing approval,
    or any configuration value". An attestation is none of those -- it *is* an
    individual human approval of this one call, which is precisely what the
    policy demands. The host's contract is therefore that it never attests for
    a session-wide grant (its Allow always), only for an individual approval.
    """
    from dct_mcp_server.tools.core.floor_operations import is_floor_operation

    assert is_floor_operation("DELETE", _ENV_PATH) is True

    execute, client = make_execute()
    approved = await execute(
        path=_ENV_PATH, method="DELETE", human_approved=_attestation()
    )
    assert approved["status"] == "success"
    client.make_request.assert_awaited_once()
