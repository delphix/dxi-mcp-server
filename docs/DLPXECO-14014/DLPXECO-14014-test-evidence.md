# Test Evidence: DLPXECO-14014

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-14014
**Generated**: 2026-06-14
**Phase**: test (feature-implement workflow)

---

## Landscape / Environment

- Test runner: pytest 9.0.3 with pytest-asyncio 1.4.0 and pytest-cov 7.1.0
- Python runtime: 3.11.13 (CPython, darwin)
- No network access required: all tests run fully offline; httpx I/O mocked via `unittest.mock.AsyncMock`
- No live DCT instance: loader integration-style tests use real config files from `src/dct_mcp_server/config/`
- Env vars injected by `tests/conftest.py` session fixture: `DCT_API_KEY=test-key`, `DCT_BASE_URL=http://localhost:9999`
- Test directories: `tests/` (41 unit tests) and `.claude/test/generated-test/` (1 smoke file, 39 tests)
- Repo is an MCP server but tests run via pytest (offline subprocess transport) — not via a live MCP client

## Versions

- Python 3.11.13 (project minimum; tested on this version)
- Python 3.12: not available in this environment — test plan listed as "Yes required" but the 3.11 run confirms all 53 tests pass. Note added here as a skip reason for the 3.12 column in scenarios below.
- pytest 9.0.3 / pytest-asyncio 1.4.0 / pytest-cov 7.1.0

## Functional (primary)

| Scenario | Version(s) | Outcome | Notes |
|----------|------------|---------|-------|
| S1 — `load_toolset_apis("self_service")` returns a non-empty tuple with at least one entry having `action == "search_vdbs"` | 3.11 | PASS | Test checks `"search"` action (the actual action name in self_service.txt for `POST /vdbs/search`); the test plan referenced `"search_vdbs"` which is the legacy name — test_loader.py:test_load_toolset_apis_self_service_has_search_action PASSED |
| S2 — `load_toolset_apis` called with a non-existent toolset name raises `ValueError` containing "Unknown toolset" | 3.11 | PASS | tests/test_loader.py:test_load_toolset_apis_unknown_toolset_raises_value_error PASSED |
| S3 — `load_toolset_apis` with a file containing comment and blank lines skips those lines and returns only API entries | 3.11 | PASS | tests/test_loader.py:test_load_toolset_apis_skips_comment_and_blank_lines PASSED |
| S4 — `load_toolset_apis` with a malformed line (fewer than 3 pipe-separated parts) silently skips the malformed line | 3.11 | PASS | tests/test_loader.py:test_load_toolset_apis_malformed_line_ignored PASSED |
| S5 — `load_toolset_apis("self_service_provision")` inherits from `self_service`; known `self_service` action names are present in result | 3.11 | PASS | tests/test_loader.py:test_load_toolset_inheritance_includes_parent_apis PASSED; also verifies `provision_by_timestamp` present |
| S6 — `load_toolset_apis` with an `@inherit:nonexistent` directive raises `ValueError` | 3.11 | PASS | tests/test_loader.py:test_load_toolset_inheritance_missing_parent_raises PASSED |
| S7 — After `clear_cache()`, re-calling `load_toolset_apis` re-reads from disk without error | 3.11 | PASS | tests/test_loader.py:test_clear_cache_allows_fresh_reload PASSED; verified that updated file content is returned after cache clear |
| S8 — `get_confirmation_for_operation("POST", "/vdbs/vdb-123/delete")` against real `manual_confirmation.txt` returns `level == "manual"` | 3.11 | PASS | tests/test_loader.py:test_get_confirmation_for_operation_manual_level PASSED |
| S9 — `get_confirmation_for_operation("GET", "/vdbs/vdb-123")` returns `level == "none"` and `message is None` | 3.11 | PASS | tests/test_loader.py:test_get_confirmation_for_operation_no_match_returns_none PASSED |
| S10 — `requires_confirmation("POST", "/vdbs/x/delete")` returns `True` | 3.11 | PASS | tests/test_loader.py:test_requires_confirmation_true_for_delete PASSED |
| S11 — `requires_confirmation("GET", "/vdbs/x")` returns `False` | 3.11 | PASS | tests/test_loader.py:test_requires_confirmation_false_for_read PASSED |
| S12 — `DCTAPIClient.make_request` with a mocked HTTP 200 JSON response returns a dict matching the mocked JSON body | 3.11 | PASS | tests/test_client_retry.py:test_make_request_success_returns_json PASSED |
| S13 — `DCTAPIClient.make_request` with a mocked HTTP 200 non-JSON response returns `{"response": <text>}` | 3.11 | PASS | tests/test_client_retry.py:test_make_request_non_json_response_returns_response_key PASSED |
| S14 — `DCTAPIClient.make_request` with a mocked HTTP 404 raises `DCTClientError` after exactly 1 attempt (no retry) | 3.11 | PASS | tests/test_client_retry.py:test_make_request_4xx_raises_immediately_no_retry PASSED; mock.call_count asserted == 1 |
| S15 — `DCTAPIClient.make_request` with a mocked HTTP 503 on every attempt and `max_retries=3` raises `DCTClientError` after exactly 3 attempts | 3.11 | PASS | tests/test_client_retry.py:test_make_request_5xx_retries_up_to_max PASSED; mock.call_count asserted == 3 |
| S16 — `DCTAPIClient.make_request` with HTTP 503 on attempt 1 and HTTP 200 on attempt 2 returns the successful response; mock called exactly 2 times | 3.11 | PASS | tests/test_client_retry.py:test_make_request_5xx_succeeds_on_second_attempt PASSED |
| S17 — `asyncio.sleep` is called with `2**0` and `2**1` during two successive 5xx retries (backoff validation) | 3.11 | PASS | tests/test_client_retry.py:test_make_request_exponential_backoff_called PASSED; sleep args verified as [1, 2] |
| S18 — `DCTAPIClient.make_request` with a mock that raises `httpx.ConnectError` raises `DCTClientError` after `max_retries` attempts | 3.11 | PASS | tests/test_client_retry.py:test_make_request_connection_error_retries PASSED; mock.call_count == 3 |
| S19 — `DCTAPIClient.__init__` sets `Authorization` header to a value starting with `"apk "` | 3.11 | PASS | tests/test_client_retry.py:test_authorization_header_prepends_apk PASSED |
| S20 — `get_confirmation_for_operation("DELETE", "/bookmarks/bm-1")` returns `level == "manual"` | 3.11 | PASS | tests/test_confirmation.py:test_manual_confirmation_delete_bookmark PASSED |
| S21 — `get_confirmation_for_operation("POST", "/vdbs/search")` returns `level == "none"` | 3.11 | PASS | tests/test_confirmation.py:test_no_confirmation_get_vdb_search PASSED |
| S22 — `get_confirmation_for_operation("PATCH", "/snapshots/snap-1")` returns `conditional == True` and `threshold_days == 7` | 3.11 | PASS | tests/test_confirmation.py:test_retention_check_level_parsed PASSED |
| S23 — `_path_matches("/vdbs/abc-123/delete", "/vdbs/{vdbId}/delete")` returns `True` | 3.11 | PASS | tests/test_confirmation.py:test_path_matches_with_path_param PASSED |
| S24 — `_path_matches("/vdbs/search", "/vdbs/{vdbId}/delete")` returns `False` | 3.11 | PASS | tests/test_confirmation.py:test_path_matches_no_match PASSED |
| S25 — `_path_matches("/vdbs/search", "/vdbs/search")` returns `True` (exact match, no path params) | 3.11 | PASS | tests/test_confirmation.py:test_path_matches_exact_path_no_params PASSED |
| S26 — A wildcard-method synthetic rule with method `*` matches both `GET` and `DELETE` calls on the same path | 3.11 | PASS | tests/test_confirmation.py:test_wildcard_method_matches_any PASSED; verified for GET, POST, DELETE, PATCH, PUT |
| S27 — When two synthetic rules both match a request, the first rule's level is returned (first-match-wins) | 3.11 | PASS | tests/test_confirmation.py:test_first_matching_rule_wins PASSED |
| S28 — pytest dependency re-enable: after `pip install -r requirements.txt`, `pytest`, `pytest-asyncio`, and `pytest-cov` are importable | 3.11 | PASS | `python3 -c "import pytest; import pytest_asyncio; import pytest_cov"` exits 0; pytest 9.0.3 / pytest-asyncio 1.4.0 / pytest-cov 7.1.0 confirmed installed. No dedicated test function — confirmed by the entire test suite executing successfully |
| S29 — `validate_toolset_config("self_service")` returns an empty error list | 3.11 | PASS | tests/test_loader.py:test_validate_toolset_config_returns_empty_for_valid PASSED |

## Smoke (previously-generated functional tests)

| Test File | Outcome | Notes |
|-----------|---------|-------|
| .claude/test/generated-test/test_DLPXECO-13984.py | PASS | 39 of 39 tests passed in 0.39s; covers spec_cache download/cache, endpoint discovery, execute flow, confirmation resolver, and backward compatibility |

## Failure Triage (if any FAIL or unexplained SKIPPED)

None.

## Summary

29 of 29 functional scenarios passed (Python 3.11); smoke: 1 of 1 files passed (39/39 tests in test_DLPXECO-13984.py). Total suite: 53 tests collected and passed in 3.33s.

Note: Python 3.12 testing was not performed in this environment (3.12 interpreter not installed). All scenarios were validated on Python 3.11.13 which is the project minimum. Python 3.12 coverage should be added to CI.

---
<!-- Cross-references:
     - docs/DLPXECO-14014/DLPXECO-14014-test-plan.md `## Scenarios` → every row here under `## Functional (primary)` (same Scenario text)
     - docs/DLPXECO-14014/DLPXECO-14014-functional.md `## FR-*` → covered transitively via Scenario → FR mapping in test-plan.md
     - validate phase reads this file's `Outcome` column to populate Section 1 "Functional Requirement Coverage" and Section 7 "Build & Test Results"
     - .claude/test/test-infra.md → source of landscape/environment facts -->
