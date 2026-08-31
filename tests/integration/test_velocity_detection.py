"""Integration tests for FR-006 per-identity velocity detection (DLPXECO-14458).

Covers scenarios deferred from the unit suite:
  S34 — two identities below threshold do not trigger; one identity above does
  S35 — counter state is isolated per identity

Plus the (b) targeted hard-block: once the velocity threshold is exceeded, a
client without elicitation capability is refused outright (BULK_OPERATION_BLOCKED)
rather than handed an advisory token. Below the threshold the operation proceeds
transparently (no per-call friction).

These drive the real ``execute`` gate against the real velocity counter and the
``batch_check:10:60`` rule shipped in ``manual_confirmation.txt`` for
``POST /vdbs/{vdbId}/start``.
"""

import pytest

import dct_mcp_server.tools.core.dynamic as dynamic
from tests.integration._gate_helpers import GATE_SPEC, make_execute

START_PATH = "/vdbs/vdb-1/start"
# batch_check:10:60 → threshold N=10 within a 60s window.
THRESHOLD_N = 10


@pytest.fixture(autouse=True)
def _reset_gate_state():
    """Clear the module-singleton velocity counter and stores between tests."""
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


def _set_identity(monkeypatch, value):
    monkeypatch.setattr(dynamic, "get_process_identity", lambda: value)


async def test_below_threshold_proceeds_transparently(spec_loaded, monkeypatch):
    """Calls under the threshold execute without any confirmation prompt."""
    _set_identity(monkeypatch, "identity-A")
    execute, client = make_execute()

    for i in range(1, THRESHOLD_N):  # calls 1..9
        result = await execute(path=START_PATH, method="POST", body={"n": i})
        assert result["status"] == "success", f"call {i} should pass transparently"

    assert client.make_request.await_count == THRESHOLD_N - 1


async def test_threshold_hard_blocks_non_elicitation_client(spec_loaded, monkeypatch):
    """The Nth call in the window is refused outright (no advisory token)."""
    _set_identity(monkeypatch, "identity-A")
    execute, client = make_execute()

    result = None
    for i in range(1, THRESHOLD_N + 1):  # calls 1..10
        result = await execute(path=START_PATH, method="POST", body={"n": i})

    # 10th call trips the gate.
    assert result["status"] == "error"
    assert result["code"] == "BULK_OPERATION_BLOCKED"
    assert result["count"] == THRESHOLD_N
    assert result["threshold_N"] == THRESHOLD_N
    assert result["window_T"] == 60
    # A blocked call is never dispatched to the DCT API.
    assert client.make_request.await_count == THRESHOLD_N - 1
    # Crucially there is no self-serviceable token in the block response.
    assert "confirmation_token" not in result


async def test_bulk_across_different_resources_trips(spec_loaded, monkeypatch):
    """A burst across DIFFERENT VDBs of the same op trips — keyed by op-template.

    Regression guard: the velocity counter keys on the path TEMPLATE
    (/vdbs/{vdbId}/start), not the resolved resource, so 'start every VDB' is
    correctly correlated as one bulk operation.
    """
    _set_identity(monkeypatch, "identity-A")
    execute, _ = make_execute()

    result = None
    for i in range(1, THRESHOLD_N + 1):  # 10 DISTINCT vdbs
        result = await execute(path=f"/vdbs/vdb-{i}/start", method="POST", body={})

    assert result["status"] == "error"
    assert result["code"] == "BULK_OPERATION_BLOCKED"
    assert result["count"] == THRESHOLD_N


async def test_counter_is_isolated_per_identity(spec_loaded, monkeypatch):
    """S34/S35: identity B's calls do not count toward identity A's threshold."""
    execute, client = make_execute()

    # Identity A makes THRESHOLD_N - 1 calls (stays just under).
    _set_identity(monkeypatch, "identity-A")
    for i in range(1, THRESHOLD_N):  # 9 calls
        res_a = await execute(path=START_PATH, method="POST", body={"a": i})
        assert res_a["status"] == "success"

    # Identity B makes a burst of the same operation — its own fresh counter.
    _set_identity(monkeypatch, "identity-B")
    res_b = None
    for i in range(1, THRESHOLD_N + 1):  # 10 calls
        res_b = await execute(path=START_PATH, method="POST", body={"b": i})

    # Identity B trips; identity A never did.
    assert res_b["status"] == "error"
    assert res_b["code"] == "BULK_OPERATION_BLOCKED"

    # One more call as identity A still succeeds (its count is 9 → 10 would trip,
    # but B's burst must not have advanced A). This is call 10 for A, so it trips
    # for A too — assert it trips at A's *own* count, proving isolation.
    _set_identity(monkeypatch, "identity-A")
    res_a_final = await execute(path=START_PATH, method="POST", body={"a": "final"})
    assert res_a_final["status"] == "error"
    assert res_a_final["count"] == THRESHOLD_N  # A's own 10th, not polluted by B
