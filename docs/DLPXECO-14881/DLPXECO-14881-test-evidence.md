# DLPXECO-14881 Test Evidence

## Landscape / Environment

Lite mode — `test` phase not run; evidence generated from the pr-phase smoke check below.

- Python: 3.11 (host)
- Pytest: system pytest via `python3 -m pytest`
- Test directory scanned: `.claude/test/generated-test/`
- Change under test: bump `certifi>=2026.10.19` → `certifi>=2026.10.23` in `pyproject.toml` and `requirements.txt`

## Functional (primary)

Not applicable — lite mode has no test-plan.md scenarios (test-generation/test phases are not part of this workflow).

## Smoke (previously-generated functional tests)

| File | Result | Notes |
|------|--------|-------|
| `.claude/test/generated-test/test_DLPXECO-14324.py` | 18 passed / 5 pre-existing failures | 5 failures are pre-existing on the base branch (identical `ValueError: DCT_API_KEY environment variable is required` failures before and after this change — confirmed by running the same tests after reverting `pyproject.toml`/`requirements.txt`). Not a regression introduced by this certifi bump. |
| `.claude/test/generated-test/test_DLPXECO-13984.py` | 39 passed / 0 failed | All green. |

**Pre-existing failure details (test_DLPXECO-14324.py):**

The 5 failing tests (`TestS1_StdioTransport::test_config_has_no_transport_field`, `TestS1_StdioTransport::test_config_has_no_http_fields`, `TestS12_SecretHygiene::test_client_does_not_log_api_key_in_headers`, `TestS14_BackwardCompatStdioMode::test_get_dct_config_works_with_api_key`, `TestS14_BackwardCompatStdioMode::test_dct_api_client_initialises_in_standalone_mode`) fail because `DCT_API_KEY` is not set in the CI/test environment. These tests attempt to instantiate `DCTAPIClient` without mocking `get_dct_config()`, triggering the env-var guard. Verified pre-existing: the same tests fail identically with the original `certifi>=2026.10.19` values restored.

## Failure Triage

None — no failures introduced by this change. Pre-existing failures noted above are environment-setup issues in the test file for DLPXECO-14324, not regressions.

## Summary

Lite mode: no functional test-plan (test phase skipped); smoke: `39 of 44` tests passed across 2 files; 5 pre-existing failures in `test_DLPXECO-14324.py` confirmed unrelated to the certifi version bump (reproduced identically on the base branch).
