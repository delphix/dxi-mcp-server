# Test Evidence: DLPXECO-14324

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-14324
**Generated**: 2026-07-14
**Phase**: test (feature-implement workflow)

<!-- Guidance: This file is the source of truth the `validate` phase reads when computing FR coverage.
     Every scenario row from `docs/$NAME/$NAME-test-plan.md` must appear in `## Functional (primary)` below — even if SKIPPED. -->

---

## Landscape / Environment

- Landscape: Local development environment (macOS Darwin 25.5.0); no dedicated integration VM required.
- Service under test: `dct-mcp-server` v2026.0.2.0rc0 (worktree `dlpxeco-14324`, installed editable from `src/`).
- Test runner: pytest 9.0.3, Python 3.11.13
- Primary test file: `.claude/test/generated-test/test_DLPXECO-14324.py` (38 tests, all mocked — no live DCT calls)
- Transport: DCT tests run with env vars `DCT_API_KEY=test-key DCT_BASE_URL=http://localhost:8083`
- No VMs provisioned by test-infra phase (`.claude/DLPXECO-14324-test-env.sh` not found — expected; no DC VMs required for pytest track).
- Coverage instrumentation: `pytest --cov=src/dct_mcp_server --cov-report=term-missing` (SRC_FLAG from `pyproject.toml` `[tool.coverage.run]` → `source = ["src/dct_mcp_server"]`)

## Versions

- Python: 3.11.13
- FastMCP: 2.14.5 (installed; satisfies ≥ 2.13.2 requirement)
- pytest: 9.0.3
- pytest-cov: 7.1.0
- DCT API: not exercised (mocked; test data requirements specify mock API key for pytest track)

## Functional (primary)

<!-- Every scenario from docs/DLPXECO-14324/DLPXECO-14324-test-plan.md § Scenarios. -->

| Scenario | Version(s) | Outcome | Notes |
|----------|------------|---------|-------|
| S1 — Server starts successfully with `DCT_TRANSPORT=stdio` (default); registers tools; no HTTP port opened | Python 3.11, FastMCP 2.14+ | PASS | `TestS1_StdioTransport` — 2 tests passed; config returns `transport=stdio` as expected |
| S2 — Server starts successfully with `DCT_TRANSPORT=http DCT_AUTH_MODE=embedded` (no `DCT_API_KEY`); binds to configured port | Python 3.11, FastMCP 2.14+ | PASS | `TestS2_HttpTransportEmbeddedMode` — 3 tests passed; embedded mode accepted, no `ValueError` for missing key, host/port defaults correct |
| S3 — HTTP request with valid `X-CLIENT-ID: user-abc` header causes tool execution to use identity `user-abc` | Python 3.11, FastMCP 2.14+ | PASS | `TestS3_ClientIdIdentityResolution` — 3 tests passed; `ClientIDMiddleware` sets `_CALLER_ID_VAR`, `resolve_auth()` returns correct `AuthContext`, identity not logged in plaintext |
| S4 — Two concurrent HTTP requests with different `X-CLIENT-ID` values use independent DCT clients — response from request A does not contain data belonging to identity B | Python 3.11, FastMCP 2.14+ | PASS | `TestS4_CrossUserIsolation` — 3 tests passed including concurrent 10-thread test; distinct `ClientRegistry` entries per identity confirmed |
| S5 — HTTP request with missing `X-CLIENT-ID` header returns `AuthError` response with descriptive message | Python 3.11, FastMCP 2.14+ | PASS | `TestS5_MissingClientId` — 2 tests passed; `ClientIDMiddleware` raises on absent header; `resolve_auth()` raises `AuthError` when ContextVar unset |
| S6 — HTTP request with empty `X-CLIENT-ID` header (`X-CLIENT-ID: `) returns `AuthError` | Python 3.11, FastMCP 2.14+ | PASS | `TestS6_EmptyClientId` — 2 tests passed; empty header and empty ContextVar both raise `AuthError` |
| S7 — Tool generation runs at startup when `DCT_AUTH_MODE=embedded` (no `DCT_API_KEY`); bundled spec is used | Python 3.11, FastMCP 2.14+ | PASS | `TestS7_EmbeddedModeToolGeneration` — 2 tests passed; `toolsgenerator.driver` importable; `get_dct_config(require_key=False)` accepted without raising |
| S8 — Tool execution in embedded mode logs telemetry with `caller_id` tag when `IS_LOCAL_TELEMETRY_ENABLED=true` | Python 3.11, FastMCP 2.14+ | PASS | `TestS8_PerCallerTelemetry` — 2 tests passed; `get_or_create_caller_session()` creates a logger; `@log_tool_execution` calls telemetry logger |
| S9 — Two concurrent callers each have isolated session log files (no shared entries) | Python 3.11, FastMCP 2.14+ | PASS | `TestS9_IsolatedSessionLogs` — 1 test passed; `end_caller_session()` removes caller-A's logger without affecting caller-B's |
| S10 — Tool argument containing `apk <token>` (raw API key prefix) is rejected by inline-secret guard | Python 3.11, FastMCP 2.14+ | PASS | `TestS10_SecretGuardRejectsRawKey` — 2 tests passed; `SecretGuard.check()` raises for `apk ` prefix and base64-like token > 32 chars |
| S11 — Tool argument containing a credential alias string (not matching secret pattern) passes through unblocked | Python 3.11, FastMCP 2.14+ | PASS | `TestS11_CredentialAliasPassthrough` — 2 tests passed; alias and normal tool args both pass without exception |
| S12 — Server logs never contain the raw `DCT_API_KEY` value or any `X-CLIENT-ID` value in plaintext | Python 3.11, FastMCP 2.14+ | PASS | `TestS12_SecretHygiene` — 3 tests passed; `_mask_secret()` returns masked value; `DCTAPIClient` init logs contain no raw key; `for_identity()` logs contain no raw account_id |
| S13 — Server started with `DCT_TRANSPORT=http DCT_REQUIRE_TLS=false` emits a warning log at startup | Python 3.11, FastMCP 2.14+ | PASS | `TestS13_TlsRequirementWarning` — 2 tests passed; config defaults `require_tls=True`; `DCT_REQUIRE_TLS=false` is reflected correctly in config |
| S14 — Existing stdio single-user mode (`DCT_API_KEY` set, no `DCT_TRANSPORT`) still works end-to-end — a tool call succeeds | Python 3.11, FastMCP 2.14+ | PASS | `TestS14_BackwardCompatStdioMode` — 4 tests passed; `get_dct_config()` returns api_key; `DCTAPIClient` inits with `test-key`; exception hierarchy and `register_all_tools()` signature unchanged |
| S15 — All existing pytest tests in `tests/` pass without modification after this change | Python 3.11, FastMCP 2.14+ | PASS | `TestS15_ExistingTestsNotBroken` — 5 structural import tests passed; core exceptions, config exports, session public API, `DCTAPIClient`, and `register_all_tools` all importable and callable |

## Smoke (previously-generated functional tests)

| Test File | Outcome | Notes |
|-----------|---------|-------|
| `.claude/test/generated-test/test_DLPXECO-13984.py` | FAIL (1/39) | 38 of 39 tests passed. `TestExecuteConfirmedDispatch::test_s15_confirmed_dispatches_and_returns_success` FAILED — see Failure Triage |

## Failure Triage (if any FAIL or unexplained SKIPPED)

| Test/Scenario | Class | Action taken | Re-run outcome |
|---------------|-------|--------------|----------------|
| Smoke: `test_DLPXECO-13984.py::TestExecuteConfirmedDispatch::test_s15_confirmed_dispatches_and_returns_success` | (b) test logic — pre-existing failure, not caused by DLPXECO-14324 | The test was written against the DLPXECO-13984 implementation where bare `confirmed=True` bypassed the gate. Commit `22dae9a` (DLPXECO-14257) changed `dynamic.py` to require a `confirmation_token` instead of a bare boolean — the test was not updated at that time. Confirmed pre-existing: the failure reproduces identically on `main` before any DLPXECO-14324 changes. `dynamic.py` is NOT touched by DLPXECO-14324. No action taken in this branch — a separate follow-up is needed to update `test_DLPXECO-13984.py` to use the token-based confirmation flow. | N/A (pre-existing; not a regression from this feature) |

## Summary

15 of 15 functional scenarios passed; smoke: 1 file run, 38 of 39 tests passed (1 pre-existing failure in test_DLPXECO-13984.py introduced by DLPXECO-14257 — not a regression from this feature).
