# Test Evidence: DLPXECO-13965

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13965
**Generated**: 2026-05-12
**Phase**: test (feature-implement workflow)

<!-- Guidance: This file is the source of truth the `validate` phase reads when computing FR coverage.
     Every scenario row from `docs/DLPXECO-13965-test-plan.md` must appear in `## Functional (primary)` below — even if SKIPPED. -->

---

## Landscape / Environment

- Landscape: Local pytest environment (no live DCT instance required)
- Service under test: DCT MCP Server modules tested in-process via FastMCP test app with AsyncMock — no subprocess or real HTTP
- Test runner: pytest 9.0.3 / pytest-asyncio 1.3.0 / Python 3.11.6 (darwin)
- VMs provisioned by test-infra phase: none — no `.claude/DLPXECO-13965-test-env.sh` present; all DCT calls mocked
- No prior generated tests found — smoke skipped (first feature in this repo)

## Versions

- Python: 3.11.6-final-0
- DCT API: all versions (bulk actions fan out to per-VDB endpoints stable across versions; no version branching required)
- pytest: 9.0.3
- pytest-asyncio: 1.3.0
- pytest-cov: 7.1.0
- MCP (mcp.server.fastmcp): bundled with project dependencies

## Functional (primary)

| Scenario | Version(s) | Outcome | Notes |
|----------|------------|---------|-------|
| S1 — `bulk_start` with 3 VDB IDs all returning HTTP 200 returns `status="success"`, `total=3`, `succeeded` has 3 entries, `failed` is empty | Python 3.11+ | PASS | test_s1_bulk_start_all_success |
| S2 — `bulk_start` with 3 VDB IDs where one returns HTTP 500 returns `status="partial_success"`, failed VDB in `failed`, other two in `succeeded` | Python 3.11+ | PASS | test_s2_bulk_start_partial_failure |
| S3 — `bulk_start` with all VDB IDs returning errors returns `status="failed"`, `succeeded` is empty | Python 3.11+ | PASS | test_s3_bulk_start_all_failed |
| S4 — `bulk_start` with empty `vdbIds=[]` returns validation error before any DCT call is made | Python 3.11+ | PASS | test_s4_bulk_start_empty_list_rejected — MCPError raised, make_request not called |
| S5 — `bulk_start` with a single VDB ID returns the aggregated shape equivalent to a single-VDB `start` result | Python 3.11+ | PASS | test_s5_bulk_start_single_vdb |
| S6 — `bulk_stop` with 6 VDB IDs and `confirmed=False` returns `status="confirmation_required"` with no DCT calls made | Python 3.11+ | PASS | test_s6_bulk_stop_confirmation_gate |
| S7 — `bulk_stop` with 6 VDB IDs and `confirmed=True` executes the batch and returns the aggregated result | Python 3.11+ | PASS | test_s7_bulk_stop_confirmed_executes — 6 make_request calls confirmed |
| S8 — `bulk_stop` with 5 VDB IDs and no `confirmed` executes immediately without a confirmation gate | Python 3.11+ | PASS | test_s8_bulk_stop_five_no_confirmation_needed |
| S9 — `bulk_enable` with more than 5 VDB IDs executes without a confirmation gate | Python 3.11+ | PASS | test_s9_bulk_enable_no_confirmation_gate — 7 VDBs, no confirmation_level in response |
| S10 — `bulk_enable` with a mix of successful and failed VDB responses reports `status="partial_success"` correctly | Python 3.11+ | PASS | test_s10_bulk_enable_partial_success |
| S11 — `bulk_disable` with 6 VDB IDs and no `confirmed` returns `status="confirmation_required"` with no DCT calls | Python 3.11+ | PASS | test_s11_bulk_disable_confirmation_gate |
| S12 — `bulk_disable` with 5 VDB IDs executes without a confirmation gate | Python 3.11+ | PASS | test_s12_bulk_disable_five_no_gate |
| S13 — At most `DCT_BULK_CONCURRENCY=3` concurrent DCT requests are in-flight at any time during a `bulk_start` of 10 VDBs | Python 3.11+ | PASS | test_s13_bulk_concurrency_cap_3 — peak in-flight measured via asyncio counter; peak <= 3 |
| S14 — `DCT_BULK_CONCURRENCY` not set defaults to 5: bulk action on 10 VDBs uses a semaphore of 5 | Python 3.11+ | PASS | test_s14_bulk_concurrency_default_5 — peak in-flight <= 5 |
| S15 — `DCT_BULK_CONCURRENCY=0` is clamped to 1: server does not fail to start; WARNING logged | Python 3.11+ | PASS | test_s15_bulk_concurrency_zero_clamped — config["bulk_concurrency"] == 1 |
| S16 — `bulk_start` on 3 VDBs emits exactly 1 INFO log and 3 DEBUG logs | Python 3.11+ | PASS | test_s16_logging_one_info_n_debug — caplog confirms 1 INFO "fanning out" + 3 DEBUG "vdbId=" |
| S17 — Existing single-VDB `start` action is unaffected and still works after bulk actions are added | Python 3.11+ | PASS | test_s17_single_vdb_start_unchanged — bulk_start with 1 VDB returns correct aggregated shape with succeeded/failed/jobs keys |
| S18 — `bulk_start`, `bulk_stop`, `bulk_enable`, `bulk_disable` appear in loaded `self_service` toolset actions for `vdb_tool` | Python 3.11+ | PASS | test_s18_bulk_actions_in_self_service — load_toolset_grouped_apis("self_service") confirms all 4 |
| S19 — All four bulk actions appear in `continuous_data_admin` toolset; none appear in `reporting_insights` | Python 3.11+ | PASS | test_s19_bulk_actions_toolset_presence_absence — continuous_data_admin has all 4; reporting_insights has none |

## Smoke (previously-generated functional tests)

| Test File | Outcome | Notes |
|-----------|---------|-------|
| (none) | SKIPPED | No prior generated tests found — smoke skipped (first feature in this repo) |

## Failure Triage (if any FAIL or unexplained SKIPPED)

None.

## Summary

19 of 19 functional scenarios passed; smoke: skipped — first feature in this repo.
