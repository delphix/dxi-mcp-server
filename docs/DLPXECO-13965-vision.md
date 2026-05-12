# Vision: DLPXECO-13965

## Problem Statement

When an AI assistant needs to act on many VDBs simultaneously — for example "stop all VDBs in the staging environment" — it must issue N sequential `vdb_tool` calls, each incurring a full round-trip through MCP and the DCT API. This is slow, produces a noisy conversation transcript, and consumes significant tokens on intermediate results that the user does not need. There is no mechanism today to fan out a lifecycle action across a set of VDBs in a single logical operation.

## Goals

- G1: Reduce AI token overhead and conversation noise when applying the same lifecycle action (start, stop, enable, disable) to multiple VDBs by providing a single bulk action that fans out internally.
- G2: Return a single aggregated response — per-VDB outcomes, overall status, job IDs — so callers can reason about the batch result without iterating over N individual responses.
- G3: Keep fan-out bounded and safe: default concurrency of 5 (configurable via `DCT_BULK_CONCURRENCY`), with partial failures surfaced rather than aborting the batch.
- G4: Require confirmation when bulk_stop or bulk_disable targets more than 5 VDBs, reusing the existing confirmation pipeline.

## Non-Goals

- NG1: No server-side batch endpoint at DCT — this is purely client-side fan-out via the existing per-VDB endpoints.
- NG2: `bulk_delete`, `bulk_refresh`, and `bulk_rollback` are not in scope; destructive and stateful operations require separate design.
- NG3: Cross-resource bulk actions (`vdb_group_tool`, `dsource_tool`, etc.) are not included in this feature.
- NG4: No retry logic inside the bulk wrapper — the DCT client already handles retry/backoff; a second layer would interact unpredictably with the semaphore.
- NG5: No UI or orchestration changes outside the MCP server.

## Success Criteria

- SC1: A single `vdb_tool(action="bulk_start", vdbIds=[...])` call returns an aggregated response with `status`, `total`, `succeeded`, `failed`, and `jobs` keys within the time it would take to run the slowest individual VDB action (plus overhead proportional to `DCT_BULK_CONCURRENCY`).
- SC2: Partial failures do not abort the batch — the response always contains the complete list of per-VDB outcomes regardless of individual errors.
- SC3: Calling `vdb_tool(action="bulk_stop", vdbIds=[...])` with more than 5 VDBs without `confirmed=True` returns `confirmation_required` status; re-calling with `confirmed=True` executes the batch.
- SC4: At-most `DCT_BULK_CONCURRENCY` (default 5) concurrent DCT API requests are in-flight at any time; verified by a unit test using a mock client.
- SC5: All four bulk actions (`bulk_start`, `bulk_stop`, `bulk_enable`, `bulk_disable`) appear in both the `self_service` and `continuous_data_admin` toolset `.txt` files.
- SC6: All 19 required pytest scenarios pass with exit code 0 and coverage of `vdb_endpoints_tool.py` does not drop below the pre-change baseline.

## Stakeholders

| Stakeholder | Interest |
|-------------|----------|
| Vinay Byrappa (Assignee) | Implementing the feature correctly per spec |
| AI assistant users (developers, QA engineers) | Fewer tool calls and cleaner conversation when acting on many VDBs |
| Platform/DBA admins | Safe confirmation gate prevents accidental mass stop/disable |
| CI/CD automation | All tests green; no manual MCP-client step required for verification |

## Constraints

- Must use `asyncio.Semaphore` for concurrency bounding; no additional threading or process pools.
- Must not add a second retry layer inside the bulk wrapper — DCT client retry/backoff is sufficient.
- New actions must follow the grouped tool pattern: action names in `config/toolsets/*.txt` must exactly match handler branches in `tools/vdb_endpoints_tool.py`.
- `DCT_BULK_CONCURRENCY` must be an integer env var parsed in `config/config.py`; default value 5.
- Python 3.11+ async-first; `vdb_tool` will be declared `async def` to support `await`-ing the bulk fan-out helper. `asyncio.run()` must NOT be used inside FastMCP's event loop — the tool must be async or use `loop.run_until_complete()`. See Assumption A1 in the functional spec.
- No new third-party dependencies — `asyncio` is stdlib; `httpx` (already used by the DCT client) handles HTTP.
- Testing is fully automated via pytest with mocked DCT client — no live DCT instance or real API key required in CI.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| `asyncio` event loop conflict: calling `asyncio.run()` inside FastMCP's already-running event loop raises `RuntimeError` | Medium | High | Declare `vdb_tool` as `async def` so the bulk helper can be `await`ed directly; `asyncio.run()` is explicitly prohibited in the tool body (see Assumption A1 in functional spec); unit-test the concurrency cap explicitly (test 6) |
| Confirmation threshold (>5 VDBs) not applied consistently — e.g. check happens after fan-out starts | Low | High | Apply confirmation check as the first step before any DCT API call; existing confirmation pipeline runs at the MCP layer before the tool body executes for single-VDB actions, so bulk must replicate this check explicitly |
| Partial failure aggregation swallows errors silently | Medium | Medium | Each per-VDB coroutine wraps `DCTAPIClient.request` in try/except and appends to the `failed` list; integration test (test 2) asserts the `failed` list is non-empty on a simulated DCT 500 |
| Action names in toolset `.txt` files fall out of sync with code handler | Low | Medium | A dedicated test (test 17, 18, 19) loads toolset config files and asserts the action names are or are not present, catching sync drift in CI |
| `DCT_BULK_CONCURRENCY` set to a very large value starves the DCT server | Low | Medium | Document the default (5) and recommended range (1–20) in config help; add a validation cap (e.g. max 50) in `config.py` with a warning log |
| Test fixture spawning the MCP server via `StdioServerParameters` is flaky in CI (port conflicts, subprocess teardown) | Medium | Medium | Use module-scoped fixture with proper async teardown; isolate tests with function-scoped `mock_dct` fixture; ensure subprocess is terminated in fixture finalizer |
