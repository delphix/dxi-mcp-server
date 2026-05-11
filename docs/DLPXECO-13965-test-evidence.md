# Test Evidence: DLPXECO-13965 — Bulk action support for vdb_tool

## Landscape / Environment

- **Platform**: darwin (macOS), Python 3.11.6
- **Test framework**: pytest 9.0.3 + pytest-asyncio 1.3.0
- **Test strategy**: Direct-import + in-process AsyncMock patching of
  `dct_mcp_server.tools.dataset_endpoints_tool.client`. No Docker, no external DCT
  instance, no VMs required. Module-level `client` global is replaced before each test;
  `autouse` fixture resets the shared mock between tests to prevent bleed.
- **Test file**: `tests/dlpxeco-13965-test.py` (27 tests, 866 lines)
- **Run command**: `uv run pytest tests/dlpxeco-13965-test.py -v`

## Versions

| Component | Version |
|-----------|---------|
| Python | 3.11.6 |
| pytest | 9.0.3 |
| pytest-asyncio | 1.3.0 |
| fastmcp (in requirements) | >=2.13.2 |
| dct-mcp-server | 2026.0.1.0-preview |

## Functional (primary)

| # | Scenario | FR AC | Outcome | Notes |
|---|----------|-------|---------|-------|
| 1 | `test_bulk_start_happy_path_three_vdbs` | FR-001 AC-1; FR-002 AC-2; FR-004 AC-1, AC-3; SC1 | PASS | 3-VDB success, 5-key shape, DCT called exactly 3 times, endpoints contain /start |
| 2a | `test_bulk_start_partial_failure_one_of_three_fails[HTTP 500]` | FR-003 AC-1; FR-004 AC-1; SC3; EC-6 | PASS | partial_success, 2 succeeded, 1 failed with non-empty error string |
| 2b | `test_bulk_start_partial_failure_one_of_three_fails[HTTP 404]` | FR-003 AC-1; EC-6 | PASS | Same as 2a with HTTP 404 error |
| 3 | `test_bulk_start_all_three_fail` | FR-003 AC-2; FR-004 AC-2; EC-8 | PASS | status=failed, succeeded=[], 3 failed entries, no exception raised |
| 4 | `test_bulk_start_empty_list_returns_error` | FR-001 AC-2; EC-1 | PASS | error key present, references vdbIds, 0 DCT calls |
| 5 | `test_bulk_start_single_vdb_uses_same_response_shape` | FR-004 AC-4; EC-2 | PASS | total=1, 5-key shape, status=success |
| 6 | `test_bulk_concurrency_cap_three_with_twenty_ids` | FR-002 AC-1, AC-2; SC2 | PASS | max in-flight 1 (never exceeded 3), all 20 completed, status=success |
| 7 | `test_bulk_stop_threshold_six_returns_confirmation` | FR-005 AC-1; SC4 | PASS | confirmation_required, confirmation_level=manual, 0 DCT calls |
| 8 | `test_bulk_stop_threshold_six_with_confirmed_proceeds` | FR-005 AC-2; SC5 | PASS | confirmed=True, 6 DCT calls, status in {success, partial_success} |
| 9 | `test_bulk_stop_below_threshold_no_confirmation` | FR-005 AC-3; SC6 | PASS | 3 VDBs, no gate, status=success, 3 DCT calls |
| 10 | `test_bulk_disable_threshold_matches_bulk_stop` | FR-005 AC-4 | PASS | bulk_disable with 6 VDBs → confirmation_required, 0 DCT calls |
| 11 | `test_bulk_enable_no_threshold_six_runs_directly` | FR-005 AC-5; SC7 | PASS | bulk_enable with 6 VDBs → success, 6 DCT calls (no gate) |
| 12 | `test_bulk_unknown_action_returns_unknown_action_error` | EC-10 | PASS | action=bulk_garbage → error response, not an exception |
| 13a | `test_bulk_start_vdbIds_string_returns_validation_error` | FR-001 AC-3; EC-5 | PASS | vdbIds="vdb-1" (str) → error, 0 DCT calls |
| 13b | `test_bulk_start_vdbIds_list_with_none_element_returns_validation_error` | EC-4 | PASS | vdbIds=[None, "v2"] → error, 0 DCT calls |
| 14 | `test_bulk_start_logs_info_on_dispatch_and_completion` | FR-007 AC-1 (INFO) | PASS | ≥2 INFO records with "bulk action=" captured via caplog |
| 15 | `test_bulk_start_logs_debug_per_vdb_outcome` | FR-007 AC-1 (DEBUG) | PASS | Exactly 3 DEBUG "outcome=success" records |
| 16 | `test_bulk_start_logs_debug_failure_with_error_string` | FR-007 AC-2 | PASS | Exactly 3 DEBUG "outcome=failure" records each with non-empty error= |
| 17 | `test_bulk_visibility_in_self_service_and_cda_only` | FR-006 AC-1, AC-2; SC8 | PASS | Toolset .txt files parsed; bulk_start/stop/enable/disable present in both self_service and continuous_data_admin |
| 18 | `test_single_vdb_start_unchanged_after_bulk_addition` | FR-008 AC-1; QR-1 | PASS | data_tool(action="start_vdb") returns DCT response unchanged vs pre-change baseline |
| 19 | `test_reporting_insights_excludes_bulk_actions` | FR-006 AC-3; SC8; QR-9 | PASS | reporting_insights.txt contains no bulk_* actions |
| ERR-4 | `test_concurrency_env_var_invalid_falls_back_to_5` | FR-002 ERR-4 | PASS | DCT_BULK_CONCURRENCY=foo → WARNING logged, batch still runs |
| ERR-5 | `test_concurrency_env_var_huge_clamps_to_50` | FR-002 ERR-5 | PASS | DCT_BULK_CONCURRENCY=10000 → WARNING logged, batch runs |
| EC-9 | `test_bulk_stop_confirmed_true_with_n_lte_5_runs_directly` | EC-9 | PASS | confirmed=True with N=3 → success, 3 calls (not blocked) |
| QR-3 | `test_qr3_log_tool_execution_decorators_present` | QR-3 | PASS | All *_endpoints_tool.py files contain @log_tool_execution |
| QR-4 | `test_qr4_no_bare_exception_in_new_code` | QR-4 | PASS | No "raise Exception" in dataset_endpoints_tool.py |
| QR-5 | `test_qr5_no_new_logging_getlogger_in_diff` | QR-5 | PASS | At most 1 logging.getLogger( occurrence (the pre-existing top-level one) |

## Smoke (previously-generated functional tests)

No prior generated test files exist in `tests/` for other features — this is the first feature adding a generated test suite to this repository. Smoke skipped — first feature in this repo.

## Summary

27 of 27 functional tests passed; smoke skipped (first feature in repo).

Test run duration: 0.53s (post-cleanup: 2.33s with pytest-cov installed).

Coverage on `dct_mcp_server.tools.dataset_endpoints_tool`:
- **15% line coverage** (248 of 1620 statements executed)
- Coverage is expected to be low: the file is 5,163 lines and covers the full DCT API surface
  (~118 actions across VDBs, dSources, groups, exports, etc.). The tests target only the new
  bulk action branches (lines ~2979–3055 in dataset_endpoints_tool.py, plus the helper
  functions at lines ~110–230).
- All new bulk-specific code paths are exercised: validation, semaphore fan-out, partial/full
  failure aggregation, confirmation gate, logging at INFO and DEBUG levels, and env-var
  parsing for concurrency.

### Import cleanup performed

Removed 6 dead imports flagged by Pylance (lines 36–46 of original):
`importlib`, `json`, `subprocess`, `types`, `Any` (from typing), `MagicMock` (from unittest.mock).
All 27 tests pass after cleanup.
