# DLPXECO-14611 Test Evidence

## Feature
Add `DCT_CONFIRMATION_HOST_APPROVAL` flag so a host's own trusted human-approval UI (embedded/DCT AI Assistant path) can satisfy the elevated/manual confirmation field checks, while keeping the per-call `confirmation_token` gate, audit level, and `required_fields` honest.

## Test Execution Summary

All tests run during the implement phase (2026-09-03). Test environment: local Python 3.11, no live DCT instance required (all DCT API I/O mocked).

---

## Unit Tests — TestHostApprovalFlag (7 tests) — PASS

File: `tests/test_sensitive_input_gate.py` (extended)

| Test | Description | Result |
|------|-------------|--------|
| test_host_approval_false_returns_full_elevated_fields | When `DCT_CONFIRMATION_HOST_APPROVAL=false`, `build_required_fields("elevated")` returns `["confirmation_token", "confirmed_resource_name"]` | PASS |
| test_host_approval_false_returns_full_manual_fields | When `DCT_CONFIRMATION_HOST_APPROVAL=false`, `build_required_fields("manual")` returns full 3-field list | PASS |
| test_host_approval_true_returns_token_only_for_elevated | When `DCT_CONFIRMATION_HOST_APPROVAL=true`, `build_required_fields("elevated")` returns `["confirmation_token"]` only | PASS |
| test_host_approval_true_returns_token_only_for_manual | When `DCT_CONFIRMATION_HOST_APPROVAL=true`, `build_required_fields("manual")` returns `["confirmation_token"]` only | PASS |
| test_host_approval_true_standard_unchanged | Standard level is unaffected by the flag | PASS |
| test_host_approval_env_not_set_defaults_false | Unset env var defaults to false (full fields required) | PASS |
| test_host_approval_invalid_value_defaults_false | Non-boolean env var value fails closed (full fields required) | PASS |

---

## Integration Tests — test_host_approval_levels (7 tests) — PASS

File: `tests/integration/test_host_approval_levels.py` (new)

| Scenario | Description | Result |
|----------|-------------|--------|
| S1 | Flag off → elevated requires `confirmed_resource_name` | PASS |
| S2 | Flag off → manual requires `confirmed_resource_name` + `acknowledged_impact` | PASS |
| S3 | Flag on → elevated only requires `confirmation_token` | PASS |
| S4 | Flag on → manual only requires `confirmation_token` | PASS |
| S5 | Flag on → standard still requires `confirmation_token` (unchanged) | PASS |
| S6 | Flag on → per-call confirmation_token gate remains enforced | PASS |
| S7 | Flag on + confirmed=True → operation proceeds (no extra fields needed) | PASS |

---

## Full Test Suite — 789 tests (excl. e2e + functional) — PASS

Command: `python3 -m pytest tests/ --ignore=tests/e2e --ignore=tests/functional -q`

Result: 789 passed, 0 failed, 0 errors

Pre-existing failures in `tests/functional/test_confirmation_handshake.py` (7 tests): confirmed identical on `main` before any DLPXECO-14611 changes — not regressions.

---

## Lint and Format — PASS

- `ruff check src/ tests/` — 0 errors
- `ruff format --check src/ tests/` — 0 format issues

---

## Smoke Tests (.claude/test/generated-test/) — PRE-EXISTING FAILURES ONLY

Tests in `.claude/test/generated-test/` from prior features (DLPXECO-13984, DLPXECO-14324) run as part of smoke check. 5 failures in `test_DLPXECO-14324.py` are confirmed pre-existing on `main` (missing `DCT_API_KEY` mock in some tests — not related to this bugfix). All 57 other tests pass. No new failures introduced by DLPXECO-14611.

---

## Manual Verification

Verified that:
1. With `DCT_CONFIRMATION_HOST_APPROVAL=false` (default): elevated confirmation still requires `confirmed_resource_name`; manual still requires `confirmed_resource_name` + `acknowledged_impact`.
2. With `DCT_CONFIRMATION_HOST_APPROVAL=true`: elevated and manual both only require `confirmation_token` — the host-UI waiver is active.
3. The `confirmation_token` per-call gate is enforced in both modes.
4. `_host_approval_configured()` fails closed on any exception (returns `False`).
5. `manual_confirmation.txt` — removed all 44 `{name}` placeholder-style patterns that were causing incorrect `confirmed_resource_name` population.
