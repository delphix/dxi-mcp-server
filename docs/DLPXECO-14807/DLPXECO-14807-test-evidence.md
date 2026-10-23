# Test Evidence — DLPXECO-14807

## Landscape / Environment

Lite mode — `test` phase not run; evidence generated from the pr-phase smoke check below.

- Runner: pytest 8.x via `python3 -m pytest`
- Environment: DCT_API_KEY and DCT_BASE_URL set to test values; no live DCT connection required (tests use `unittest.mock`)
- Source: `.claude/test/generated-test/` (2 files discovered)

## Functional (primary)

Not applicable — lite mode has no test-plan.md scenarios (test-generation/test phases are not part of this workflow).

## Smoke (previously-generated functional tests)

| File | Tests | Pass | Fail | Outcome |
|------|-------|------|------|---------|
| `test_DLPXECO-13984.py` | 42 | 42 | 0 | PASS — all dynamic 2-tool architecture tests pass |
| `test_DLPXECO-14324.py` | 20 | 20 | 0 | PASS — all stdio-only embedded auth tests pass (requires `DCT_API_KEY` env var; pre-existing env-setup failures confirmed unrelated to this urllib3 version bump) |

**Note on pre-run failures**: When `DCT_API_KEY` is not set, 5 tests in `test_DLPXECO-14324.py` fail with `ValueError: DCT_API_KEY environment variable is required`. This is a pre-existing test environment setup issue — these tests require the env var to be set as a precondition. Our change (urllib3 `>=2.7.0` → `>=2.8.0`) does not import urllib3 and cannot cause these failures. All 62 tests pass when `DCT_API_KEY=test-key` is set.

## Failure Triage

None. All 62 tests pass with the correct environment. The 5 initially-failing tests were due to a missing `DCT_API_KEY` environment variable, which is a test environment precondition unrelated to the urllib3 version bump in this PR.

## Summary

Lite mode: no functional test-plan (test phase skipped); smoke: `2 of 2` files passed (62 tests total, all green with correct env setup).
