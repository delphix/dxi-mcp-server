"""Integration tests for GrantStore expiry semantics (DLPXECO-14458, FR-004).

Covers scenarios deferred from the unit suite:
  S43 — a standing grant expires by *count* (all enumerated targets consumed)
  S44 — a standing grant expires by *TTL* (wall-clock elapsed)
  S45 — count and TTL expiry are independent; whichever comes first wins

Exercises the real ``GrantStore`` with a controllable clock so TTL behaviour is
deterministic (no sleeps).
"""

import pytest

import dct_mcp_server.tools.core.confirmation_store as cs
from dct_mcp_server.tools.core.confirmation_store import GrantStore


@pytest.fixture
def clock(monkeypatch):
    """A controllable wall clock for the confirmation store."""
    now = {"t": 1000.0}
    monkeypatch.setattr(cs.time, "time", lambda: now["t"])
    return now


def _canon(*bodies):
    # Grants store canonical string targets; the exact form is opaque here.
    return [str(b) for b in bodies]


def test_s43_grant_expires_by_count(clock):
    store = GrantStore()
    targets = _canon("a", "b")
    store.create_grant("g1", "PATCH /vdbs/{vdbId}", targets, ttl_seconds=900)

    assert store.consume_target("g1", "a") == "ok"
    assert store.get_remaining("g1") == 1
    assert store.consume_target("g1", "b") == "ok"
    assert store.get_remaining("g1") == 0

    # All targets consumed → further consumption is exhausted, even well within TTL.
    assert store.consume_target("g1", "a") == "exhausted"


def test_s44_grant_expires_by_ttl(clock):
    store = GrantStore()
    store.create_grant("g2", "PATCH /vdbs/{vdbId}", _canon("a"), ttl_seconds=5)

    # Before expiry the target is consumable.
    clock["t"] = 1004.0
    assert store.get_remaining("g2") == 1

    # After expiry (1000 + 5) the grant is gone regardless of remaining count.
    clock["t"] = 1006.0
    assert store.consume_target("g2", "a") == "expired"
    assert store.get_grant("g2") is None


def test_s45_ttl_wins_when_it_elapses_before_count(clock):
    """A grant with unused targets still expires once its TTL passes."""
    store = GrantStore()
    store.create_grant(
        "g3", "PATCH /vdbs/{vdbId}", _canon("a", "b", "c"), ttl_seconds=10
    )

    # Consume one; two remain.
    assert store.consume_target("g3", "a") == "ok"
    assert store.get_remaining("g3") == 2

    # TTL elapses before the remaining targets are used → expired wins over count.
    clock["t"] = 1011.0
    assert store.consume_target("g3", "b") == "expired"
    assert store.get_remaining("g3") is None


def test_missing_grant_reports_grant_missing(clock):
    store = GrantStore()
    assert store.consume_target("nope", "a") == "grant_missing"
