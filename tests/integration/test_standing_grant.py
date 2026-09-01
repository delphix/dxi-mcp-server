"""Integration tests for Tier-2 auto standing grants (confirm-once → run N).

An impactful but non-destructive op (standard/elevated level — provision, refresh,
snapshot, rollback, dSource-link) requires manual confirmation the FIRST time; that
one approval then authorizes the next N executions of the SAME operation-type
(across different resources) without re-prompting. After N, the next call
re-prompts. Deletes/manual are floor ops and are never covered — they confirm
every time. No explicit batch_intent declaration is required.

Keyed by (caller-identity, method, path_template) and bounded by
DCT_CONFIRMATION_BATCH_SIZE and DCT_GRANT_TTL.
"""

import pytest

import dct_mcp_server.tools.core.dynamic as dynamic
from tests.integration._gate_helpers import GATE_SPEC, make_execute


@pytest.fixture(autouse=True)
def _reset_gate_state(monkeypatch):
    from dct_mcp_server.tools.core import confirmation_store as cs
    from dct_mcp_server.tools.core import velocity_counter as vc

    for store in (cs._grant_store._grants, cs._standing_store._grants):
        store.clear()
    cs._consumed_token_store._pending.clear()
    vc._velocity_counter._counters.clear()
    # Small, deterministic batch size: one confirmation covers 3 ops total.
    monkeypatch.setenv("DCT_CONFIRMATION_BATCH_SIZE", "3")
    yield
    for store in (cs._grant_store._grants, cs._standing_store._grants):
        store.clear()
    cs._consumed_token_store._pending.clear()
    vc._velocity_counter._counters.clear()


@pytest.fixture
def spec_loaded(monkeypatch):
    monkeypatch.setattr(dynamic, "get_cached_spec", lambda: GATE_SPEC)
    monkeypatch.setattr(dynamic, "get_process_identity", lambda: "identity-tier2")


async def _confirm(execute, path, method, body, **extra):
    """Do the two-step handshake; return the (approved) second response."""
    first = await execute(path=path, method=method, body=body)
    assert first["status"] == "confirmation_required", first
    token = first["confirmation_token"]
    second = await execute(
        path=path, method=method, body=body, confirmation_token=token, **extra
    )
    return second


async def test_confirm_once_then_run_n_across_resources(spec_loaded):
    """First PATCH confirms; the next N-1 PATCHes (any VDB) run without prompting."""
    execute, client = make_execute()

    # Call 1 — vdb-1: must confirm, and arms the standing grant (N=3 → 2 more free).
    approved = await _confirm(execute, "/vdbs/vdb-1", "PATCH", {"name": "a"})
    assert approved["status"] == "success"

    # Call 2 — vdb-2: covered by the standing grant, no confirmation.
    r2 = await execute(path="/vdbs/vdb-2", method="PATCH", body={"name": "b"})
    assert r2["status"] == "success"
    assert r2["authorization"]["kind"] == "standing"
    assert r2["authorization"]["remaining"] == 1

    # Call 3 — vdb-3: covered, exhausts the budget (3 ops total per confirmation).
    r3 = await execute(path="/vdbs/vdb-3", method="PATCH", body={"name": "c"})
    assert r3["status"] == "success"
    assert r3["authorization"]["kind"] == "standing"

    # Call 4 — vdb-4: budget spent → must confirm again.
    r4 = await execute(path="/vdbs/vdb-4", method="PATCH", body={"name": "d"})
    assert r4["status"] == "confirmation_required"

    # 3 confirmed/covered dispatches + the confirmed call = 4 wire calls; call 4 blocked pre-dispatch.
    assert client.make_request.await_count == 3


async def test_standing_grant_is_per_op_type(spec_loaded):
    """Confirming a refresh does NOT cover a different op-type (PATCH update)."""
    execute, _ = make_execute()

    # Confirm an elevated refresh (resource name required first time).
    approved = await _confirm(
        execute,
        "/vdbs/vdb-1/refresh_by_snapshot",
        "POST",
        {"snapshot_id": "s1"},
        confirmed_resource_name="vdb-1",
    )
    assert approved["status"] == "success"

    # A different op-type (PATCH /vdbs/{id}) is NOT covered by the refresh grant.
    other = await execute(path="/vdbs/vdb-1", method="PATCH", body={"name": "x"})
    assert other["status"] == "confirmation_required"

    # But a second refresh (different VDB) IS covered — and needs no resource name.
    covered = await execute(
        path="/vdbs/vdb-2/refresh_by_snapshot",
        method="POST",
        body={"snapshot_id": "s2"},
    )
    assert covered["status"] == "success"
    assert covered["authorization"]["kind"] == "standing"


async def test_deletes_are_never_covered_by_standing_grant(spec_loaded, monkeypatch):
    """Floor deletes confirm every time — a prior confirmation never covers them."""
    # Add a delete path to the spec for this test.
    spec = {**GATE_SPEC, "paths": {**GATE_SPEC["paths"]}}
    spec["paths"]["/bookmarks/{bookmarkId}"] = {
        "delete": {"operationId": "deleteBookmark", "summary": "Delete bookmark"}
    }
    monkeypatch.setattr(dynamic, "get_cached_spec", lambda: spec)
    execute, _ = make_execute()

    # Confirm one delete (manual level: token + resource name + acknowledged_impact).
    first = await execute(path="/bookmarks/bk-1", method="DELETE", body=None)
    assert first["status"] == "confirmation_required"
    approved = await execute(
        path="/bookmarks/bk-1",
        method="DELETE",
        body=None,
        confirmation_token=first["confirmation_token"],
        confirmed_resource_name="bk-1",
        acknowledged_impact=True,
    )
    assert approved["status"] == "success"

    # A second delete still requires its own individual confirmation.
    second = await execute(path="/bookmarks/bk-2", method="DELETE", body=None)
    assert second["status"] == "confirmation_required"


async def test_standing_grant_ttl_expiry_reprompts(spec_loaded, monkeypatch):
    """Once the grant TTL elapses, the next call re-prompts even with budget left."""
    import dct_mcp_server.tools.core.confirmation_store as cs

    now = {"t": 5000.0}
    monkeypatch.setattr(cs.time, "time", lambda: now["t"])
    monkeypatch.setenv("DCT_GRANT_TTL", "10")

    execute, _ = make_execute()
    approved = await _confirm(execute, "/vdbs/vdb-1", "PATCH", {"name": "a"})
    assert approved["status"] == "success"

    # Within TTL: covered.
    now["t"] = 5008.0
    covered = await execute(path="/vdbs/vdb-2", method="PATCH", body={"name": "b"})
    assert covered["status"] == "success"

    # After TTL: re-prompt despite remaining budget.
    now["t"] = 5020.0
    expired = await execute(path="/vdbs/vdb-3", method="PATCH", body={"name": "c"})
    assert expired["status"] == "confirmation_required"
