# Test Plan: DLPXECO-13965 — Bulk action support for vdb_tool

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13965
**Source specs**: `docs/DLPXECO-13965-vision.md`, `docs/DLPXECO-13965-functional.md`,
                  `docs/DLPXECO-13965-design.md`
**Test framework**: `pytest` + `pytest-asyncio` + `fastmcp.Client` over stdio
**Test file**: `tests/dlpxeco-13965-test.py` (~600 lines, all scenarios in one file)

---

## 1. Test Strategy

All 19 scenarios are automated `pytest-asyncio` tests that:

1. Patch `dct_mcp_server.dct_client.client.DCTAPIClient.make_request` **at the import path**,
   inside a module-scoped fixture, **before** the FastMCP server subprocess starts.
2. Spawn the local MCP server as a subprocess using `fastmcp.Client` with
   `StdioServerParameters(command="bash", args=["start_mcp_server_uv.sh"], env={...})`.
3. Drive the server through MCP tool calls (`client.call_tool("data_tool",
   {"action": "bulk_start", "vdbIds": [...]})`).
4. Assert on response shape, mock call count, mock call ordering, and (for logging tests)
   `caplog` records.

The mock-at-import-path approach addresses vision risk #7 (mocking inside an MCP subprocess
is tricky): because `fastmcp.Client` runs the server in the same Python process when
constructed with `StdioServerParameters(transport="memory")` (or, equivalently, the test
fixture imports the server module directly and uses an in-process MCP transport for
deterministic mocking), the patch applies cleanly.

If in-process mocking proves infeasible after the first iteration, fall back to:

- Spawning the real server with `monkeypatch`-set `DCT_BASE_URL=http://localhost:<port>`
  and running a thin httpx-mock proxy on `<port>`. This is heavier but bullet-proof.

Decision point: run scenario 1 first and confirm patch works; if not, switch to the proxy
fallback before writing scenarios 2-19.

## 2. Test Inventory

Each scenario maps to a single `async def test_*` in `tests/dlpxeco-13965-test.py`.

| # | Scenario name | Validates | Vision SC / FR AC |
|---|---------------|-----------|-------------------|
| 1 | `test_bulk_start_happy_path_three_vdbs` | 3-VDB success, response shape, DCT mock called exactly 3 times with correct endpoints. | SC1; FR-001 AC-1; FR-002 AC-2; FR-004 AC-1, AC-3 |
| 2 | `test_bulk_start_partial_failure_one_of_three_fails` | 2 of 3 mocks return 200, 1 returns 500 → `status="partial_success"`, `succeeded` length 2, `failed` length 1, `failed[0]["error"]` non-empty. | SC3; FR-003 AC-1; FR-004 AC-1 |
| 3 | `test_bulk_start_all_three_fail` | All 3 mocks raise `DCTClientError` → `status="failed"`, `succeeded=[]`, `failed` length 3, response is a dict (no exception). | FR-003 AC-2; FR-004 AC-2; EC-8 |
| 4 | `test_bulk_start_empty_list_returns_error` | `vdbIds=[]` → `{"error": "vdbIds must be a non-empty list of VDB IDs"}`, DCT mock called 0 times. | FR-001 AC-2; EC-1 |
| 5 | `test_bulk_start_single_vdb_uses_same_response_shape` | `vdbIds=["v1"]` → response has 5-key shape, `total=1`, fan-out works through semaphore. | FR-004 AC-4; EC-2 |
| 6 | `test_bulk_concurrency_cap_three_with_twenty_ids` | `DCT_BULK_CONCURRENCY=3`, 20 vdbIds, each mock awaits an `asyncio.Event` while incrementing/decrementing an `in_flight` counter. Assert `max(in_flight) <= 3` throughout. | SC2; FR-002 AC-1, AC-2 |
| 7 | `test_bulk_stop_threshold_six_returns_confirmation` | `action="bulk_stop"`, 6 vdbIds, no `confirmed` → `status="confirmation_required"`, `confirmation_level="manual"`. DCT mock called 0 times. | SC4; FR-005 AC-1 |
| 8 | `test_bulk_stop_threshold_six_with_confirmed_proceeds` | Same call with `confirmed=True` → DCT mock called exactly 6 times, response `status` in `{"success","partial_success"}`. | SC5; FR-005 AC-2 |
| 9 | `test_bulk_stop_below_threshold_no_confirmation` | `bulk_stop` with 3 vdbIds and no `confirmed` → `status="success"`, DCT mock called 3 times. | SC6; FR-005 AC-3 |
| 10 | `test_bulk_disable_threshold_matches_bulk_stop` | `bulk_disable` with 6 vdbIds and no `confirmed` → `status="confirmation_required"`. | FR-005 AC-4 |
| 11 | `test_bulk_enable_no_threshold_six_runs_directly` | `bulk_enable` with 6 vdbIds, no `confirmed` → `status="success"`, DCT mock called 6 times. (Non-destructive, no gate.) | SC7; FR-005 AC-5 |
| 12 | `test_bulk_unknown_action_returns_unknown_action_error` | `action="bulk_garbage"` → existing `else` branch returns `{"error": "Unknown action: bulk_garbage..."}`. | EC-10 |
| 13 | `test_bulk_start_vdbIds_string_returns_validation_error` | `vdbIds="vdb-1"` (str, not list) → `{"error": "vdbIds must be a non-empty list of VDB IDs"}`. DCT mock called 0 times. | EC-5 |
| 14 | `test_bulk_start_logs_info_on_dispatch_and_completion` | `caplog.at_level(logging.INFO)`. Assert at least two INFO records contain `"bulk action="`. | FR-007 AC-1 (INFO half) |
| 15 | `test_bulk_start_logs_debug_per_vdb_outcome` | `caplog.at_level(logging.DEBUG)`. 3 vdbIds all success → exactly 3 DEBUG records contain `outcome=success`. | FR-007 AC-1 (DEBUG half) |
| 16 | `test_bulk_start_logs_debug_failure_with_error_string` | `caplog.at_level(logging.DEBUG)`. All 3 mocks raise `DCTClientError("HTTP 500: boom")` → exactly 3 DEBUG records contain `outcome=failure` and a non-empty `error=` substring. | FR-007 AC-2 |
| 17 | `test_bulk_visibility_in_self_service_and_cda_only` | Start the server with `DCT_TOOLSET=self_service` and assert the `vdb_tool` action list contains `bulk_start`, `bulk_stop`, `bulk_enable`, `bulk_disable`. Repeat for `continuous_data_admin` / `data_tool`. | FR-006 AC-1, AC-2; SC8 |
| 18 | `test_single_vdb_start_unchanged_after_bulk_addition` | Call `data_tool(action="start_vdb", vdb_id="v1")` against a mock returning a known payload → response matches the pre-change snapshot byte-for-byte (modulo log-line differences). | FR-008 AC-1; QR-1 |
| 19 | `test_reporting_insights_excludes_bulk_actions` | Start the server with `DCT_TOOLSET=reporting_insights` and assert no tool exposes any `bulk_*` action. | FR-006 AC-3; SC8; QR-9 |

## 3. Static / Grep-Based Quality Checks

These run as part of `pytest` (via simple `subprocess.run` calls in dedicated tests) or as
CI grep steps. They enforce QR-3, QR-4, QR-5 cheaply.

| # | Check | Command | Assertion |
|---|-------|---------|-----------|
| QR-3 | All tool functions have `@log_tool_execution` | `grep -L "@log_tool_execution" src/dct_mcp_server/tools/*_endpoints_tool.py` | Output is empty. |
| QR-4 | No bare `Exception` raised in new code | `grep -nE "raise Exception" src/dct_mcp_server/tools/dataset_endpoints_tool.py` | No matches inside the bulk branches (line range to be determined post-merge). |
| QR-5 | No new `logging.getLogger(` calls in modified file | `git diff origin/main -- src/dct_mcp_server/tools/dataset_endpoints_tool.py \| grep "+.*logging\.getLogger("` | Output is empty (the existing line 11 declaration is **unchanged**, not a new addition). |

These checks are encoded as `test_qr3_log_tool_execution_decorators_present`,
`test_qr4_no_bare_exception_in_new_code`, `test_qr5_no_new_logging_getlogger_in_diff`
inside the same test file but kept separate from the 19 functional scenarios above to
preserve the one-scenario-one-FR mapping.

## 4. Coverage Strategy (QR-8)

1. Run `pytest --cov=src/dct_mcp_server/tools/dataset_endpoints_tool --cov-report=term`
   against the pre-PR commit on `main`. Record the line-coverage % in the PR description
   as the **baseline**.
2. Run the same command on the PR branch.
3. Coverage gate: post-PR line-coverage must be **>= baseline**. Drop-by-one tolerance is
   not allowed — if a new branch is added it must be covered.
4. CI step: a one-line `pytest --cov-fail-under=<baseline>` invocation enforces this in the
   GitHub Actions workflow.

## 5. Edge Cases Not Listed Above (Defensive)

| Edge case | Coverage | Notes |
|-----------|----------|-------|
| EC-3 — Duplicate `vdbIds` | Manual smoke during scenario 1 variant | Document in PR description; full automation not required (out of risk band). |
| EC-4 — `vdbIds=[None, "v2"]` | Folded into scenario 13 (`vdbIds` type validation) — single assertion that any non-string element triggers the validation error. | — |
| EC-6 — HTTP 404 from one VDB | Folded into scenario 2 — the 500 in scenario 2 can be parametrized to also cover 404. | Add a `pytest.mark.parametrize("status_code", [404, 500])` decoration on scenario 2. |
| EC-7 — Timeout on one VDB | Same as EC-6 — parametrize scenario 2 with `asyncio.TimeoutError` raised inside the mock. | — |
| EC-9 — `confirmed=True` with N<=5 | Folded into scenario 9 — pass `confirmed=True` in a variant assertion. | — |
| ERR-4, ERR-5 — `DCT_BULK_CONCURRENCY` invalid / huge | Add scenario `test_concurrency_env_var_invalid_falls_back_to_5` and `test_concurrency_env_var_huge_clamps_to_50`. These are extra scenarios beyond the 19. | Both verify a WARNING log via `caplog`. |
| ERR-6 — Rate-limited 429 on one VDB | Covered by scenario 2 parametrization; `DCTAPIClient` retries are not stacked by the bulk wrapper. | — |

## 6. Manual Verification (MCP Client) — Per `.claude/rules/testing.md`

After all automated tests pass, run the following manual MCP-client scenarios against a
live DCT instance. These are **not** automated — they verify end-to-end UX in a real client.

### `self_service` toolset

1. Start the server with `DCT_TOOLSET=self_service` and a fresh log file.
2. Connect Claude Desktop. Verify `vdb_tool` is in the tool list with `bulk_start`,
   `bulk_stop`, `bulk_enable`, `bulk_disable` as available actions.
3. `vdb_tool(action="search")` → pick three real VDB IDs.
4. `vdb_tool(action="bulk_stop", vdbIds=[the 3])` → response: `status="success"` (count
   below threshold, no gate). Server logs show 1 INFO before, 3 DEBUG outcomes, 1 INFO
   after.
5. `vdb_tool(action="bulk_stop", vdbIds=[6 IDs])` → response:
   `status="confirmation_required"`, `confirmation_level="manual"`. **The 6 VDBs are not
   touched.** Verify the DCT UI shows them still in their previous state.
6. Repeat with `confirmed=True` → 6 stop jobs visible in DCT job history.
7. `vdb_tool(action="bulk_start", vdbIds=[6 IDs])` → no confirmation gate, 6 start jobs.

### `continuous_data_admin` toolset

Same flow but using `data_tool` and the `bulk_*` action names. Verify `vdb_tool` is
**not** in the tool list (CDA uses `data_tool`).

### `reporting_insights` toolset

Start the server with `DCT_TOOLSET=reporting_insights`. Verify **no** `bulk_*` action is
exposed on any tool. The read-only contract is preserved.

## 7. Test Infrastructure Setup

- Per `.claude/test-infra.md`: read `DCT_API_KEY` and `DCT_BASE_URL` from
  `.claude/settings.local.json` (under `mcpServers.dct.env`) inside the test fixture.
- Module-scoped fixture spawns the MCP server **once** per test module to keep the test
  suite fast.
- Each test function uses its own `unittest.mock.patch` context for the DCT call mock, so
  scenarios do not bleed mock state into each other.
- `pytest-asyncio` is in `requirements.txt` (verify); if not, the implement phase adds it
  alongside the test file (vision C8 — no new third-party deps, but pytest-asyncio is
  already listed in `.claude/rules/testing.md` as expected).

## 8. Run Commands

```bash
# Full suite (CI):
pytest tests/dlpxeco-13965-test.py -v

# With coverage gate (CI):
pytest tests/dlpxeco-13965-test.py \
       --cov=src/dct_mcp_server/tools/dataset_endpoints_tool \
       --cov-fail-under=<baseline> -v

# Just the concurrency cap test (debug):
pytest tests/dlpxeco-13965-test.py::test_bulk_concurrency_cap_three_with_twenty_ids -v -s

# Smoke (single scenario for first iteration):
pytest tests/dlpxeco-13965-test.py::test_bulk_start_happy_path_three_vdbs -v -s
```

## 9. Acceptance Mapping (round-trip check)

| Vision SC | Covered by test scenarios |
|-----------|---------------------------|
| SC1 | 1 |
| SC2 | 6 |
| SC3 | 2 |
| SC4 | 7 |
| SC5 | 8 |
| SC6 | 9 |
| SC7 | 11 |
| SC8 | 17, 19 |
| SC9 | All 19 + QR static checks + coverage gate |

| FR AC | Covered |
|-------|---------|
| FR-001 AC-1, AC-2, AC-3 | 1, 4, 13 |
| FR-002 AC-1, AC-2, AC-3, AC-4 | 6 (cap), 1 (no drop), + concurrency env-var fallback test |
| FR-003 AC-1, AC-2 | 2, 3 |
| FR-004 AC-1, AC-2, AC-3, AC-4 | 1, 3, 1 (shape), 5 |
| FR-005 AC-1, AC-2, AC-3, AC-4, AC-5 | 7, 8, 9, 10, 11 |
| FR-006 AC-1, AC-2, AC-3 | 17, 19 |
| FR-007 AC-1, AC-2 | 14, 15, 16 |
| FR-008 AC-1 | 18 |

| Quality Rule | Coverage |
|--------------|----------|
| QR-1 | Scenario 18 + manual diff |
| QR-2 | PR checklist (`requirements.txt` diff) |
| QR-3 | Static check `test_qr3_*` |
| QR-4 | Static check `test_qr4_*` |
| QR-5 | Static check `test_qr5_*` |
| QR-6 | Scenario 6 |
| QR-7 | Scenarios 7, 8, 9, 10, 11 |
| QR-8 | Coverage gate in CI |
| QR-9 | Scenario 19 |
| QR-10 | All 19 scenarios green in CI |

---
<!-- This test plan is consumed by the executor's internal test-generation phase
     during `--step implement`. Each scenario row above produces one `async def test_*`
     function in tests/dlpxeco-13965-test.py.  -->
