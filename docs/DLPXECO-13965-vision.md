# Vision: DLPXECO-13965

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13965
**Title**: Add bulk action support to vdb_tool for parallel start/stop/enable/disable
**Domain**: feature

## Problem Statement

When an AI assistant connected to the DCT MCP server needs to perform a lifecycle action
(start, stop, enable, disable) on more than one VDB — e.g. "stop all VDBs in the staging
environment" — it currently has no choice but to issue N sequential `data_tool` / `vdb_tool`
calls, one per VDB. Every call is a full MCP round-trip plus a DCT HTTP request. For 20 VDBs
this is ~20× the wall-clock latency of a single call, generates ~20 turns of intermediate
chatter in the conversation, and consumes a large chunk of the model's context budget on
near-duplicate response payloads. The user experiences slow, noisy bulk operations that they
would intuitively expect to be a single action.

## Goals

- G1: Reduce wall-clock time for bulk lifecycle actions on N VDBs from O(N · latency) to
  O(ceil(N / concurrency) · latency), with concurrency default 5 and configurable via
  `DCT_BULK_CONCURRENCY`.
- G2: Reduce the number of MCP tool calls required for a bulk operation from N to exactly 1
  (or 2 when manual confirmation is triggered).
- G3: Surface per-VDB success and failure outcomes in a single aggregated response so the AI
  assistant can present a complete result without further tool calls.
- G4: Preserve the project's two-step manual-confirmation pattern for destructive bulk actions
  (`bulk_stop`, `bulk_disable`) when the request targets more than 5 VDBs.

## Non-Goals

- NG1: No bulk variants for destructive or stateful actions in this ticket
  (`bulk_delete`, `bulk_refresh`, `bulk_rollback`) — these require separate design because
  they take additional per-VDB parameters and have larger blast radius.
- NG2: No cross-tool bulk operations — `vdb_group_tool`, `dsource_tool`, `bookmark_tool`,
  etc. are out of scope.
- NG3: No server-side batch endpoints — this is a purely client-side fan-out wrapping the
  existing per-VDB DCT endpoints. No DCT API changes.
- NG4: No retry layer in the bulk wrapper. `DCTAPIClient` already has exponential-backoff
  retry; the wrapper must not stack a second retry on top.
- NG5: No changes to the existing single-VDB action behavior. The `start_vdb`, `stop_vdb`,
  `enable_vdb`, `disable_vdb` actions in `data_tool` and the `start`, `stop`, `enable`,
  `disable` actions in `vdb_tool` (self_service) must behave identically before and after.

## Success Criteria

- SC1: Calling `vdb_tool(action="bulk_start", vdbIds=["v1","v2","v3"])` returns a single
  aggregated response with `status`, `total`, `succeeded`, `failed`, `jobs` keys after at
  most one round-trip per concurrency batch.
- SC2: With `DCT_BULK_CONCURRENCY=3` and a 20-VDB request, the maximum number of in-flight
  DCT HTTP requests observed at any instant never exceeds 3, and all 20 complete.
- SC3: When 2 of 3 fan-out calls return 200 and 1 returns 500, the aggregated response has
  `status="partial_success"`, `succeeded` length 2, `failed` length 1, and the
  failed entry carries a non-empty error string. The batch does **not** abort early.
- SC4: Calling `vdb_tool(action="bulk_stop", vdbIds=[6 ids])` with no `confirmed` argument
  returns `{"status":"confirmation_required","confirmation_level":"manual", ...}` and makes
  zero DCT HTTP calls.
- SC5: The same call with `confirmed=True` proceeds and makes exactly 6 DCT HTTP calls.
- SC6: Calling the same action with 5 or fewer VDBs (`bulk_stop`, `bulk_disable`) proceeds
  directly without a confirmation gate.
- SC7: `bulk_enable` does not gate on threshold (non-destructive operation).
- SC8: All four bulk actions are visible in the MCP tool list when `DCT_TOOLSET=self_service`
  and `DCT_TOOLSET=continuous_data_admin`; none are visible when
  `DCT_TOOLSET=reporting_insights`.
- SC9: All 19 pytest scenarios in `tests/dlpxeco-13965-test.py` pass locally and in CI;
  coverage of `dataset_endpoints_tool.py` does not drop below the pre-change baseline.

## Stakeholders

| Stakeholder | Interest |
|-------------|----------|
| AI assistant users (Claude Desktop / Cursor / VS Code Copilot) | Faster bulk VDB operations with one tool call and one consolidated response |
| Self-service operators | Ability to stop / disable a fleet of VDBs at end-of-day without scripting 20 individual calls |
| Continuous data admins | Same as above but at higher fleet scale (50–200 VDBs) |
| Platform engineering (Delphix) | Tool-count discipline: bulk actions added without a new MCP tool — keeps the context surface small |
| Security / audit | Each per-VDB call still runs through `DCTAPIClient` (audit trail preserved), and destructive bulks ≥ 6 still gate on manual confirmation |
| Maintainers of `dataset_endpoints_tool.py` | Implementation must follow existing patterns: `@log_tool_execution`, `check_confirmation`, `make_api_request`; no new global state |

## Constraints

- C1: Python 3.11+ (project floor); use `asyncio.Semaphore`, `asyncio.gather`, and `asyncio.run`.
- C2: Tool functions are **sync** by FastMCP convention in this codebase. The bulk wrapper
  must use the existing `async_to_sync` pattern from `dataset_endpoints_tool.py:69-95`. Do
  not change the public function signature to `async def`.
- C3: All HTTP traffic must go through the existing `DCTAPIClient.make_request()` — do not
  bypass to call `httpx` directly. This preserves auth header injection, retry, timeout,
  SSL verification, and telemetry.
- C4: Confirmation must reuse the existing two-step pattern (`status=confirmation_required`
  on first call, `confirmed=True` on second). The threshold check is per-call, not per-VDB.
- C5: The bulk wrapper must be added to the existing `data_tool` and `vdb_tool` function in
  `src/dct_mcp_server/tools/dataset_endpoints_tool.py`. The ticket text mentions
  `tools/vdb_endpoints_tool.py`, but no such file exists — `data_tool` (and the OpenAPI-
  generated `vdb_tool`) both resolve to `dataset_endpoints_tool` per
  `loader.py:TOOL_TO_MODULE`. Creating a new file would diverge from project layout.
- C6: Per `.claude/rules/code-style.md`: every tool function is decorated with
  `@log_tool_execution`; logger is `get_logger(__name__)`; exceptions are `DCTClientError`
  or `MCPError`, never bare `Exception`.
- C7: Per `.claude/rules/toolsets.md`: when adding bulk actions, both the `.txt` toolset
  config **and** the `action == 'bulk_*'` branch in the implementation function must be
  updated; the action names must match exactly.
- C8: No new third-party dependencies. `asyncio`, `pytest`, `pytest-asyncio`, `fastmcp`,
  `unittest.mock` are all already available.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Single-VDB action names differ between `self_service` (e.g. `start`) and `continuous_data_admin` (e.g. `start_vdb`). Adding `bulk_start` to both could inadvertently mean two different things. | Medium | Medium | Use the SAME action names (`bulk_start`, `bulk_stop`, `bulk_enable`, `bulk_disable`) in both toolset `.txt` files, and have a single action-handler branch in `dataset_endpoints_tool.py` that always hits the same DCT endpoint (`/vdbs/{id}/start` etc.). Document this normalization in the design doc. |
| Threshold confirmation is path-keyed in `manual_confirmation.txt` today; the bulk operation has no real path. | High | Medium | Implement the threshold check inline in the action handler (count `len(vdbIds) > 5` before fan-out, return `confirmation_required` directly) rather than trying to bend the path-pattern matcher. Document the deliberate deviation from `manual_confirmation.txt` in the design doc and add `# TOOL N` comments referencing the inline check. |
| `async_to_sync` wraps each call in a fresh `asyncio.run`, which spawns/tears-down an event loop per call. Fan-out inside a single async function and then `async_to_sync` the whole batch — not per VDB — to avoid 20× loop-creation overhead. | Medium | Medium | The bulk handler will create one `async def _run_batch()` that gathers all N tasks under a single `asyncio.Semaphore`, and wrap that single function with `async_to_sync`. Unit test 6 (`test_bulk_concurrency_cap`) verifies the semaphore is respected. |
| Partial failures: an in-flight call raising `DCTClientError` could bubble out of `asyncio.gather` and abort the entire batch. | High | High | Wrap each per-VDB task in a try/except inside the worker coroutine; never let an exception escape. Record the failure into the `failed` list and return success from the worker so `gather` completes for all tasks. Verified by `test_bulk_start_partial_failure` and `test_bulk_start_all_failed`. |
| Memory: 200-VDB fan-out keeps 200 response bodies in memory until the batch completes. | Low | Low | Each response is small (job id, status). Bounded concurrency keeps in-flight memory at concurrency × response-size. No streaming required. If users hit >1000 VDB requests in practice, revisit. |
| Logging volume: per-VDB DEBUG logs at concurrency=200 produce 200 log lines per call. | Low | Low | Ticket explicitly says log at DEBUG per VDB and INFO once per batch — this is the right split. Production loggers are INFO by default. |
| `data_tool` already has 130+ action branches and is 4959 lines. Adding 4 more grows the file but does not warrant a refactor. | Low | Low | Add the 4 branches inline in the existing pattern. Defer file-split to a separate refactor ticket. |
| Tests must spawn the MCP server as a subprocess and mock `DCTAPIClient` from outside. Mocking inside a subprocess is tricky. | Medium | Medium | Per the ticket: use `unittest.mock.patch` on `dct_mcp_server.dct_client.client.DCTAPIClient.make_request` at the module level, applied inside the test fixture before `fastmcp.Client` connects. Verify this works by running scenario 1 first and iterating. |
| Tests/ directory does not exist on `origin/main` yet — no baseline coverage to compare against. | Low | Low | Coverage gate must be "no regression vs. pre-PR baseline" measured by running `pytest --cov` on `main` once before merging. Document the baseline number in the PR description. |

---
<!-- Cross-reference: G1–G4 map to FR-001 through FR-008 in functional spec.
     SC1–SC9 map to AC entries inside the FRs.
     Risks #4 (partial failure) and #2 (threshold) drive the Quality Rules and Edge Cases. -->
