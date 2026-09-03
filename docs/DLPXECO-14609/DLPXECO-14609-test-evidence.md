# Test Evidence — DLPXECO-14609

**Ticket**: Sensitive-input gate never clears after the host injects the captured secret
**Branch**: dlpx/pr/admin/dlpxeco-14609
**Date**: 2026-09-04

---

## Summary

The fix introduces `_verify_host_marker()` in `tools/core/dynamic.py` and wires it into the sensitive-input gate so that on the retry leg (after host credential injection), the gate clears the host-injected fields instead of re-firing. Tests cover both the new helper and the gate's second-leg clearance behaviour.

---

## Unit Tests — `tests/test_sensitive_input_gate.py`

**Runner**: `pytest tests/test_sensitive_input_gate.py -v`
**Result**: **37 passed, 0 failed**

### Pre-existing tests (all still pass)

| Class | Tests | Status |
|-------|-------|--------|
| `TestIdentityPairingRules` | 9 | PASS |
| `TestMissingSensitiveFields` | 5 | PASS |
| `TestAnnotatedCredentialFields` | 7 | PASS |

### New regression tests added by DLPXECO-14609

**`TestVerifyHostMarker`** (10 tests) — covers `_verify_host_marker()`:

| Test | Scenario | Result |
|------|----------|--------|
| `test_valid_marker_returns_cleared_fields` | Valid HMAC, correct body binding — returns field frozenset | PASS |
| `test_no_shared_secret_returns_empty` | `DCT_HOST_SHARED_SECRET` empty — no exemptions (AC-6) | PASS |
| `test_none_marker_returns_empty` | Marker is None — returns empty frozenset | PASS |
| `test_wrong_hmac_rejected` | Tampered HMAC — returns empty frozenset (AC-3) | PASS |
| `test_wrong_secret_rejected` | Wrong shared secret — verification fails | PASS |
| `test_replay_against_different_body_rejected` | Same marker, different body — HMAC mismatch (AC-4) | PASS |
| `test_multi_field_marker` | Marker clears multiple fields simultaneously | PASS |
| `test_missing_fields_key_rejected` | Marker missing `fields` key — returns empty | PASS |
| `test_missing_hmac_key_rejected` | Marker missing `hmac` key — returns empty | PASS |
| `test_non_string_field_entries_rejected` | Non-string entries in `fields` list — returns empty | PASS |

**`TestGateSecondLeg`** (7 tests) — covers full gate integration:

| Test | Scenario | Result |
|------|----------|--------|
| `test_gate_fires_on_first_leg` | First call without marker — gate fires (normal flow) | PASS |
| `test_gate_loops_without_marker` | Retry without marker — gate fires again (the original bug) | PASS |
| `test_gate_clears_on_second_leg_with_valid_marker` | Retry with valid marker — gate clears, op proceeds (AC-1, AC-2) | PASS |
| `test_gate_still_fires_for_uncleared_annotated_field` | Marker clears only listed fields; uncleared annotated field still gates (AC-5) | PASS |
| `test_identity_pairing_still_enforced_for_absent_secret` | Rule 2 (identity pairing) is never bypassed by the marker (AC-6 pairing) | PASS |
| `test_nested_body_clears_after_host_injection` | Nested body structure — marker clears correct nested field | PASS |
| `test_no_regression_empty_cleared_set` | Empty `host_cleared_fields` frozenset — no behavioural change (regression guard) | PASS |

---

## Smoke Check — `.claude/test/generated-test/`

**Runner**: `DCT_API_KEY=test-key DCT_BASE_URL=https://dummy.host pytest .claude/test/generated-test/ -q`
**Result**: **62 passed, 0 failed**

Covers previously-generated tests for DLPXECO-13984 (dynamic 2-tool architecture) and DLPXECO-14324 (embedded stdio transport). All pass against the patched codebase — no regressions introduced.

---

## Full Test Suite

**Runner**: `DCT_API_KEY=test-key DCT_BASE_URL=https://dummy.host pytest tests/ -q`
**Per eval-results**: **744 tests pass, 0 failures** (1 pre-existing warning unrelated to this change)
**16 new tests** added in `TestVerifyHostMarker` and `TestGateSecondLeg`

---

## Acceptance Criteria Verification

| AC | Description | Verified |
|----|-------------|---------|
| AC-1 | Gate clears on second leg when valid marker present | Yes — `test_gate_clears_on_second_leg_with_valid_marker` |
| AC-2 | Operation dispatched after gate clears | Yes — gate returns no `missing_secrets` after clearance |
| AC-3 | Marker is not model-forgeable (HMAC-verified) | Yes — `test_wrong_hmac_rejected`, `test_wrong_secret_rejected` |
| AC-4 | Replay against different body rejected | Yes — `test_replay_against_different_body_rejected` |
| AC-5 | Only host-listed fields cleared; other gated fields still enforced | Yes — `test_gate_still_fires_for_uncleared_annotated_field` |
| AC-6 | Non-embedded deployments (no shared secret) receive no exemption | Yes — `test_no_shared_secret_returns_empty` |
