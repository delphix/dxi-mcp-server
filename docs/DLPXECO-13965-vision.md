# Vision: DLPXECO-13965

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13965
**Title**: Add bulk action support to vdb_tool for parallel start/stop/enable/disable

## Problem Statement

The DCT MCP server (`dxi-mcp-server`) exposes per-VDB lifecycle operations via `vdb_tool` (start, stop, enable, disable, refresh, etc.). When an AI assistant needs to act on many VDBs — e.g. "stop all VDBs in the staging environment" — it must issue N sequential tool calls, each a full round-trip through MCP and DCT. This is slow, noisy in the conversation transcript, and consumes significant tokens for intermediate results. The on-call burden of waiting for sequential operations also makes routine fleet-wide actions feel disproportionately expensive.

## Goals

- G1: Add four bulk action variants (`bulk_start`, `bulk_stop`, `bulk_enable`, `bulk_disable`) to `vdb_tool` that each accept a list of `vdbIds` and fan out concurrently to the existing single-VDB DCT endpoints.
- G2: Cap fan-out concurrency at a default of 5 (configurable via `DCT_BULK_CONCURRENCY`) using `asyncio.Semaphore` so the DCT instance is not overwhelmed by uncontrolled task spawning.
- G3: Return an aggregated response of shape `{status, total, succeeded, failed, jobs}` that lets the caller see per-VDB outcomes in a single tool call rather than N tool turns.
- G4: Require manual confirmation for `bulk_stop` and `bulk_disable` when the list exceeds 5 VDBs, reusing the existing two-step confirmation pipeline (`confirmation_required` then `confirmed=True`).
- G5: Provide automated `pytest`-based test coverage for all 19 scenarios in the ticket (success / partial failure / all-failed / concurrency cap / confirmation gating / toolset registration / regression of single-VDB behaviour), with no live DCT instance required.

## Non-Goals

- NG1: This ticket does NOT add `bulk_delete`, `bulk_refresh`, or `bulk_rollback`. Destructive or stateful bulk operations need their own design and are tracked in a separate ticket.
- NG2: This ticket does NOT add bulk variants to `vdb_group_tool`, `dsource_tool`, or other resource tools. Cross-tool bulk operations are out of scope.
- NG3: This ticket does NOT introduce server-side batching at DCT — the fan-out is purely client-side inside the MCP server.
- NG4: This ticket does NOT introduce a new tool module. Bulk actions are added as new `action=` values on the existing `vdb_tool` grouped tool.

## Success Criteria

- SC1: Calling `vdb_tool(action="bulk_start", vdbIds=["vdb-1", "vdb-2", "vdb-3"])` returns a single aggregated response with `status=success`, `total=3`, `succeeded` matching the input, `failed=[]`, and a `jobs` list of three `{vdbId, jobId}` entries when all three underlying calls succeed.
- SC2: When 1 of N underlying calls returns a 5xx response, the aggregated response has `status=partial_success`, surfaces the failing `vdbId` and error message under `failed`, and still returns the succeeded entries — the batch is never aborted on first failure.
- SC3: With `DCT_BULK_CONCURRENCY=3` and 20 vdbIds in flight, the maximum observed in-flight DCT calls is ≤ 3 at any point, and all 20 calls eventually complete.
- SC4: Calling `vdb_tool(action="bulk_stop", vdbIds=[6 VDBs])` without `confirmed=True` returns `status=confirmation_required` with `confirmation_level=manual` and triggers ZERO DCT calls. Re-calling with `confirmed=True` executes all 6.
- SC5: Calling `vdb_tool(action="bulk_stop", vdbIds=[3 VDBs])` (under the 5-VDB threshold) executes immediately without a confirmation gate.
- SC6: `bulk_enable` never requires confirmation regardless of list size (non-destructive operation).
- SC7: All 19 pytest scenarios listed in the ticket's "Required Test Scenarios" table pass locally and in CI, and coverage of `dataset_endpoints_tool.py` (where `vdb_tool` lives in this codebase) does not drop below the pre-change baseline.
- SC8: Existing single-VDB `vdb_tool(action="start", vdbId="...")` behaviour is unchanged — verified by a regression test in the same suite.

## Stakeholders

| Stakeholder            | Interest                                                                |
|------------------------|-------------------------------------------------------------------------|
| AI assistant users     | Fleet-wide VDB operations complete in a single tool turn, not N turns   |
| Platform/MCP team      | Bounded concurrency prevents accidental DCT DoS from runaway fan-out    |
| On-call engineers      | Existing single-VDB behaviour is not regressed; opt-in destructive gate |
| Test infrastructure    | No live DCT credentials required in CI — fully mocked at the HTTP layer |
| DCT operators          | DCT-side load is bounded by `DCT_BULK_CONCURRENCY`, not by caller whim  |

## Constraints

- Must be implemented in Python 3.11+ (project minimum), using `asyncio.Semaphore` for concurrency bounding — no third-party concurrency libraries.
- Must reuse the existing `DCTAPIClient` retry/backoff layer; the bulk wrapper must NOT add a second retry layer on top.
- Must follow the project's grouped-tool pattern: new actions are added to the existing `vdb_tool` function in `dataset_endpoints_tool.py` (the actual module where `vdb_tool` is implemented in this codebase — the ticket's reference to `vdb_endpoints_tool.py` is corrected to `dataset_endpoints_tool.py` during design).
- Must register the four new actions in both `self_service.txt` and `continuous_data_admin.txt`. (Note: in `continuous_data_admin`, `vdb_tool` is merged into `data_tool` — design phase must decide whether to add the actions to `data_tool` or restore a separate `vdb_tool` entry; the ticket says four actions in both toolsets.)
- Must NOT log raw API keys, vdbIds, or DCT response bodies at INFO level — INFO is one summary line per bulk call; per-VDB outcomes at DEBUG only.
- Test file must be named `tests/dlpxeco-13965-test.py` per the project convention `tests/<ticket>-test.py`.
- No live DCT instance, no `.claude/settings.local.json`, no real `DCT_API_KEY` may be required by the test suite. The fixture must inject fake env vars and mock the HTTP layer.

## Risks

| Risk                                                                        | Likelihood | Impact | Mitigation                                                                                                                                                                |
|-----------------------------------------------------------------------------|------------|--------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Uncapped task spawn overwhelms the DCT instance                              | Medium     | High   | Enforce `asyncio.Semaphore(DCT_BULK_CONCURRENCY)`; unit test (scenario 6) asserts max in-flight ≤ configured cap                                                          |
| First-failure abort hides partial-success state from the caller             | Medium     | High   | Use `asyncio.gather(..., return_exceptions=True)`; aggregate all outcomes; assert `status=partial_success` in scenario 2                                                  |
| Confirmation gate bypass on destructive bulk ops                            | Low        | High   | Confirmation logic checked BEFORE any DCT call; scenario 7/10 asserts `mock_dct.call_count == 0` when gate triggers                                                       |
| Regression of existing single-VDB `vdb_tool(action="start", vdbId="...")`   | Medium     | Medium | Scenario 16 (regression test) in the same test file; CI fails on regression                                                                                               |
| Toolset registration drift (action listed in `.txt` but not handled in code) | Medium     | Medium | Scenarios 17/18 spawn the server with each toolset and assert `bulk_*` actions are visible to the MCP client; design phase produces a single mapping table to keep aligned |
| Test fixture flakiness from real subprocess + stdio transport               | Low        | Medium | Use module-scoped fixture; mock at `DCTAPIClient.request` boundary so no network or real DCT round-trip is reachable                                                       |
| Coverage drop on `dataset_endpoints_tool.py` from added but untested code    | Medium     | Medium | Run `pytest --cov` and gate CI on baseline; design phase sets the exact pytest command in `docs/DLPXECO-13965-design.md`                                                  |
| Ticket references `vdb_endpoints_tool.py` but code lives in `dataset_endpoints_tool.py` | High | Low | Vision (this doc) calls out the mismatch; design phase pins the exact file path; functional spec FRs reference the real module                                            |
| `continuous_data_admin` exposes `data_tool` (merged), not `vdb_tool` — bulk action registration in that toolset is ambiguous | High | Medium | Design phase resolves: add `bulk_*` actions under the merged `data_tool` entry in `continuous_data_admin.txt`, keep them under `vdb_tool` in `self_service.txt`; scenario 18 asserts visibility from `data_tool` in `continuous_data_admin` |

---
<!-- Cross-reference: Goals (G1-G5) map to FR-001 through FR-005 in the functional spec.
     Success Criteria (SC1-SC8) map to acceptance criteria on individual FRs.
     The ticket-vs-code module mismatch (vdb_endpoints_tool.py → dataset_endpoints_tool.py)
     is a Risk here and will be pinned to a concrete file in the Design phase. -->
