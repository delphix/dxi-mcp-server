# Test Plan: DLPXECO-13965

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13965
**Derived from**: `docs/DLPXECO-13965-design.md` `## Affected Components` and `## Version Compatibility`

<!-- Guidance: This file is the authoritative list of scenarios for the test-generation phase.
     Every row in `## Scenarios` becomes one test() / it() / def test_* block in `.claude/test/generated-test/`.
     If a scenario row cannot be expressed as a real assertion, refine the row — do not weaken the generated test. -->

---

## Test Approach

Automated pytest regression using `pytest` + `pytest-asyncio` + `fastmcp.Client`. Tests spawn the MCP server as a subprocess via `StdioServerParameters` and patch `DCTAPIClient.request` with `AsyncMock` so no live DCT instance or real API key is required. Runner: `pytest tests/dlpxeco-13965-test.py -v --cov=src/dct_mcp_server/tools/vdb_endpoints_tool --cov-report=term-missing`.

## Environment / Landscape

- Landscape: Local pytest environment (no live DCT instance required)
- Service under test: DCT MCP Server spawned as subprocess via `fastmcp.Client` + `StdioServerParameters`
- Test env vars: `DCT_API_KEY=test-key`, `DCT_BASE_URL=http://fake.test`, `DCT_TOOLSET=continuous_data_admin`, `DCT_BULK_CONCURRENCY=5`
- `DCTAPIClient.request` patched with `AsyncMock` before subprocess spawn; HTTP-level interception via `respx` or in-process FastMCP test client (implementer to choose and document in test file per Assumption A4)

## Versions to Cover
<!-- Guidance: Only versions marked "Supported = Yes" in the design doc appear here. -->

| Version | Why | Required? |
|---------|-----|-----------|
| Python 3.11+ | Bulk actions use `asyncio.Semaphore` and `async def` tool functions — requires 3.11+ | Yes |
| DCT API (all versions) | Bulk actions fan out to per-VDB endpoints stable across all DCT versions; no version branching needed | Yes (single pass) |

## Scenarios
<!-- Guidance: One row per testable scenario mapped to at least one FR-*. -->

| # | Scenario | Maps to FR | Versions | Expected outcome |
|---|----------|-----------|----------|------------------|
| S1 | `bulk_start` with 3 VDB IDs all returning HTTP 200 returns `status="success"`, `total=3`, `succeeded` has 3 entries, `failed` is empty | FR-002 | Python 3.11+ | Response dict has `status="success"`, `total=3`, `len(succeeded)==3`, `failed==[]` |
| S2 | `bulk_start` with 3 VDB IDs where one returns HTTP 500 returns `status="partial_success"`, failed VDB in `failed`, other two in `succeeded` | FR-002 | Python 3.11+ | `status="partial_success"`, `len(succeeded)==2`, `len(failed)==1`, `failed[0]["vdbId"]` matches the failing VDB |
| S3 | `bulk_start` with all VDB IDs returning errors returns `status="failed"`, `succeeded` is empty | FR-002 | Python 3.11+ | `status="failed"`, `succeeded==[]`, `len(failed)==3` |
| S4 | `bulk_start` with empty `vdbIds=[]` returns validation error before any DCT call is made | FR-002 | Python 3.11+ | Error response with message containing "vdbIds must be a non-empty list" and zero mock calls on `DCTAPIClient.request` |
| S5 | `bulk_start` with a single VDB ID returns the aggregated shape equivalent to a single-VDB `start` result | FR-002 | Python 3.11+ | `status="success"`, `total=1`, `len(succeeded)==1`, `failed==[]` |
| S6 | `bulk_stop` with 6 VDB IDs and `confirmed=False` returns `status="confirmation_required"` with no DCT calls made | FR-003 | Python 3.11+ | `status="confirmation_required"`, `confirmation_level="manual"`, `len(vdbIds)==6` in response, zero calls on `DCTAPIClient.request` |
| S7 | `bulk_stop` with 6 VDB IDs and `confirmed=True` executes the batch and returns the aggregated result | FR-003 | Python 3.11+ | `status` in `("success", "partial_success", "failed")`, `total==6`, `DCTAPIClient.request` called 6 times with `POST /vdbs/{id}/stop` |
| S8 | `bulk_stop` with 5 VDB IDs and no `confirmed` executes immediately without a confirmation gate | FR-003 | Python 3.11+ | `status` in `("success", "partial_success", "failed")`, `total==5`, no confirmation gate triggered |
| S9 | `bulk_enable` with more than 5 VDB IDs executes without a confirmation gate | FR-004 | Python 3.11+ | `status` in `("success", "partial_success", "failed")`, zero confirmation response returned regardless of list size |
| S10 | `bulk_enable` with a mix of successful and failed VDB responses reports `status="partial_success"` correctly | FR-004 | Python 3.11+ | `status="partial_success"`, `succeeded` and `failed` are both non-empty |
| S11 | `bulk_disable` with 6 VDB IDs and no `confirmed` returns `status="confirmation_required"` with no DCT calls | FR-005 | Python 3.11+ | `status="confirmation_required"`, `confirmation_level="manual"`, zero calls on `DCTAPIClient.request` |
| S12 | `bulk_disable` with 5 VDB IDs executes without a confirmation gate | FR-005 | Python 3.11+ | `status` in `("success", "partial_success", "failed")`, `total==5`, no confirmation gate triggered |
| S13 | At most `DCT_BULK_CONCURRENCY=3` concurrent DCT requests are in-flight at any time during a `bulk_start` of 10 VDBs | FR-006 | Python 3.11+ | Peak observed in-flight count <= 3 (measured via concurrency counter in AsyncMock side-effect) |
| S14 | `DCT_BULK_CONCURRENCY` not set defaults to 5: bulk action on 10 VDBs uses a semaphore of 5 | FR-006 | Python 3.11+ | Peak in-flight count <= 5 |
| S15 | `DCT_BULK_CONCURRENCY=0` is clamped to 1: server does not fail to start; WARNING logged | FR-006 | Python 3.11+ | `config["bulk_concurrency"] == 1` after `get_dct_config()` with `DCT_BULK_CONCURRENCY=0` in env |
| S16 | `bulk_start` on 3 VDBs emits exactly 1 INFO log and 3 DEBUG logs | FR-007 | Python 3.11+ | Log capture shows 1 line matching `"bulk_start: fanning out"` and 3 lines matching `"bulk_start: vdbId="` |
| S17 | Existing single-VDB `start` action is unaffected and still works after bulk actions are added | FR-002 (QR-1) | Python 3.11+ | `vdb_tool(action="start", vdbId="vdb-1")` returns the per-VDB DCT response without aggregation |
| S18 | `bulk_start`, `bulk_stop`, `bulk_enable`, `bulk_disable` appear in loaded `self_service` toolset actions for `vdb_tool` | FR-001 | Python 3.11+ | `load_toolset_grouped_apis("self_service")["vdb_tool"]["apis"]` contains all four bulk action names |
| S19 | All four bulk actions appear in `continuous_data_admin` toolset; none appear in `reporting_insights` | FR-001 | Python 3.11+ | `continuous_data_admin` grouped APIs contain all four; `reporting_insights` grouped APIs contain none of the four |

## Out of Scope
<!-- Guidance: Scenarios the test plan deliberately skips, with a one-line reason. -->

- `bulk_delete`, `bulk_refresh`, `bulk_rollback` — not in scope per Non-Goal NG2; destructive and stateful operations require separate design.
- Cross-resource bulk actions (`vdb_group_tool`, `dsource_tool`) — out of scope per Non-Goal NG3.
- `DCT_BULK_CONCURRENCY` values above 50 — config.py clamps to 50 at startup; no separate test scenario needed (covered by S15 boundary logic).
- Network-level failure mid-batch (EC-10) — not testable without real network; EC-10 behavior is expressed by S2/S3 which simulate per-VDB `DCTClientError` at the mock level.
- Live DCT instance scenarios — all tests use mocked `DCTAPIClient.request`; live scenario execution is handled separately via `.claude/test/testing/self_service.md` and `.claude/test/testing/continuous_data_admin.md`.

## Test Data Requirements
<!-- Guidance: What data or fixture state must exist before tests run? -->

- All tests use a module-scoped `mcp_client` fixture that sets env vars and patches `DCTAPIClient.request` with `AsyncMock` before the server subprocess starts.
- Function-scoped `mock_dct` fixture configures the `AsyncMock` side-effect as a dict of `{vdbId: (status_code, response_body)}` for per-test response control.
- For S13/S14 (concurrency cap tests), the `mock_dct` fixture additionally installs a counter that increments on acquire and decrements on release to track peak in-flight count.
- No database seeding or live DCT credentials required.
- No `tests/` directory currently exists — the test file creation is part of FR-008 implementation.

## Exit Criteria
<!-- Guidance: How the test phase decides "done". -->

- All 19 Required scenarios (S1–S19) PASS on Python 3.11+.
- `pytest tests/dlpxeco-13965-test.py -v --cov=src/dct_mcp_server/tools/vdb_endpoints_tool --cov-report=term-missing` exits 0.
- Coverage of `src/dct_mcp_server/tools/vdb_endpoints_tool.py` is measured and reported (baseline = 0% pre-change; post-change target >= 80%).
- No scenario marked SKIPPED without a documented reason.
- Smoke suite (existing tests in `tests/` if any) PASSes — currently no other test files exist, so smoke is vacuously satisfied.

---
<!-- Cross-references:
     - Each Scenario row → drives one test block in .claude/test/generated-test/DLPXECO-13965.spec.* (test-generation phase)
     - Each FR in docs/DLPXECO-13965-functional.md → at least one scenario here (otherwise the FR is untested)
     - Versions column → must be a subset of docs/DLPXECO-13965-design.md ## Version Compatibility "Supported = Yes"
     Validation: feature-executor.md Phase: test-generation Step 2 treats this file as authoritative. -->
