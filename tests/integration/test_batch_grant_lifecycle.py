"""Integration tests for FR-004 scoped batch-grant lifecycle (DLPXECO-14458).

Covers scenarios deferred from the unit suite, driven end-to-end through the real
``execute`` gate and the real ``GrantStore``:
  S21 — a batch_intent issues a single grant enumerating N targets
  S22 — calls under the grant execute without further prompting (FR-007 authz meta)
  S23 — a call against an exhausted grant falls back to individual confirmation
  S24 — a call whose body is not in the grant's targets falls back to confirmation
  S25 — a call after the grant TTL has elapsed falls back to individual confirmation
"""

import pytest

import dct_mcp_server.tools.core.dynamic as dynamic
from tests.integration._gate_helpers import GATE_SPEC, make_execute

VDB_PATH = "/vdbs/vdb-1"
OPERATION = "PATCH /vdbs/{vdbId}"


@pytest.fixture(autouse=True)
def _reset_gate_state():
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
    monkeypatch.setattr(dynamic, "get_cached_spec", lambda: GATE_SPEC)
    monkeypatch.setattr(dynamic, "get_process_identity", lambda: "identity-grant")


async def _issue_grant(execute, targets):
    return await execute(
        path=VDB_PATH,
        method="PATCH",
        batch_intent={"operation": OPERATION, "targets": targets},
    )


async def test_s21_batch_intent_issues_single_grant(spec_loaded):
    execute, client = make_execute()
    targets = [{"n": 1}, {"n": 2}, {"n": 3}]

    issued = await _issue_grant(execute, targets)

    assert issued["status"] == "confirmation_required"
    assert issued["batch_confirmation_token"]
    assert issued["count"] == 3
    assert issued["operation"] == OPERATION
    # Issuing a grant never dispatches to the DCT API.
    client.make_request.assert_not_called()


async def test_s22_calls_under_grant_execute_without_prompting(spec_loaded):
    execute, client = make_execute()
    targets = [{"n": 1}, {"n": 2}, {"n": 3}]
    grant = (await _issue_grant(execute, targets))["batch_confirmation_token"]

    remaining_seen = []
    for t in targets:
        res = await execute(path=VDB_PATH, method="PATCH", body=t, grant_token=grant)
        assert res["status"] == "success"
        # FR-007: grant-covered executions carry authorization metadata.
        assert res["authorization"]["grant_token"] == grant
        remaining_seen.append(res["authorization"]["remaining"])

    assert client.make_request.await_count == 3
    # remaining decrements 2 → 1 → 0 across the three covered calls.
    assert remaining_seen == [2, 1, 0]


async def test_s23_exhausted_grant_requires_individual_confirmation(spec_loaded):
    execute, client = make_execute()
    target = {"n": 1}
    grant = (await _issue_grant(execute, [target]))["batch_confirmation_token"]

    # Consume the single target.
    ok = await execute(path=VDB_PATH, method="PATCH", body=target, grant_token=grant)
    assert ok["status"] == "success"

    # A further call against the now-empty grant is refused back to confirmation.
    exhausted = await execute(
        path=VDB_PATH, method="PATCH", body=target, grant_token=grant
    )
    assert exhausted["status"] == "confirmation_required"
    assert "exhausted" in exhausted["message"].lower()
    assert exhausted["confirmation_token"]
    # Only the first (covered) call reached the API.
    assert client.make_request.await_count == 1


async def test_s24_body_not_in_grant_requires_individual_confirmation(spec_loaded):
    execute, client = make_execute()
    grant = (await _issue_grant(execute, [{"n": 1}]))["batch_confirmation_token"]

    # A body that was never enumerated in the grant is not covered.
    res = await execute(
        path=VDB_PATH, method="PATCH", body={"n": 999}, grant_token=grant
    )
    assert res["status"] == "confirmation_required"
    assert "not in the enumerated batch grant" in res["message"].lower()
    assert res["confirmation_token"]
    client.make_request.assert_not_called()


async def test_s25_grant_ttl_expiry_requires_individual_confirmation(
    spec_loaded, monkeypatch
):
    import dct_mcp_server.tools.core.confirmation_store as cs

    # Controllable clock for the grant store; issue at t=1000, TTL=5s.
    now = {"t": 1000.0}
    monkeypatch.setattr(cs.time, "time", lambda: now["t"])
    monkeypatch.setenv("DCT_GRANT_TTL", "5")

    execute, client = make_execute()
    target = {"n": 1}
    grant = (await _issue_grant(execute, [target]))["batch_confirmation_token"]

    # Advance the clock beyond the grant's expiry (1000 + 5).
    now["t"] = 1006.0

    expired = await execute(
        path=VDB_PATH, method="PATCH", body=target, grant_token=grant
    )
    assert expired["status"] == "confirmation_required"
    assert "expired" in expired["message"].lower()
    assert expired["confirmation_token"]
    client.make_request.assert_not_called()
