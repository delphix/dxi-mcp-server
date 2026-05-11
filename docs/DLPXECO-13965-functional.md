# Functional Specification: DLPXECO-13965

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13965
**Generated from**: Acceptance criteria in Jira ticket DLPXECO-13965 + Vision G1-G5 / SC1-SC8

---

## FR-001: Bulk start action with bounded concurrency

### Description
Allows the caller to start multiple VDBs in a single tool invocation by issuing concurrent `POST /vdbs/{vdbId}/start` calls under a configurable concurrency cap, returning an aggregated per-VDB outcome.

### Input
- `action` (string, required): must be `"bulk_start"` to route to this requirement
- `vdbIds` (list[str], required, non-empty): identifiers of VDBs to start
- `confirmed` (bool, optional, default `False`): ignored for `bulk_start` (non-destructive); accepted for API symmetry with other bulk actions
- Environment: `DCT_BULK_CONCURRENCY` (int, optional, default `5`): max number of in-flight underlying DCT calls

### Processing
1. Validate `action == "bulk_start"`; if not, return validation error (handled at dispatch).
2. Validate `vdbIds` is a non-empty `list[str]`; if empty or wrong type, raise `MCPError("vdbIds must be a non-empty list of strings")` BEFORE any DCT call.
3. Read `DCT_BULK_CONCURRENCY` from environment (default 5); construct `asyncio.Semaphore(concurrency)`.
4. For each `vdbId` in `vdbIds`, schedule an async task that:
   a. Acquires the semaphore.
   b. Calls `dct_client.request("POST", f"/vdbs/{vdbId}/start")`.
   c. Records `(vdbId, http_status, response_body_or_error)`.
   d. Releases the semaphore.
5. Await all tasks with `asyncio.gather(*tasks, return_exceptions=True)` — DO NOT abort on first failure.
6. Aggregate outcomes:
   - `succeeded`: list of `vdbId` whose call returned 2xx
   - `failed`: list of `{vdbId, error}` for non-2xx or exception cases
   - `jobs`: list of `{vdbId, jobId}` extracted from the 2xx response body for successes
7. Compute `status`:
   - `"success"` if `len(failed) == 0`
   - `"failed"` if `len(succeeded) == 0`
   - `"partial_success"` otherwise
8. Log one INFO line: `bulk_start completed: total=N succeeded=X failed=Y`.
9. Log one DEBUG line per VDB outcome.
10. Return `{status, total, succeeded, failed, jobs}`.

### Output
- Success (`status=="success"`): `{"status": "success", "total": N, "succeeded": ["vdb-1", ...], "failed": [], "jobs": [{"vdbId": "vdb-1", "jobId": "..."}, ...]}`
- Partial (`status=="partial_success"`): same keys; `succeeded` and `failed` both non-empty; `jobs` contains only entries for succeeded VDBs.
- Failed (`status=="failed"`): `succeeded=[]`, `failed.length == total`, `jobs=[]`.
- Validation error (empty list / wrong type): raises `MCPError` with descriptive message; no DCT call attempted.

### Acceptance Criteria
- [ ] AC-1: Given 3 valid vdbIds and all DCT calls return 200 with `{jobId: ...}`, when `bulk_start` is invoked, then response is `{status: "success", total: 3, succeeded: [3 ids], failed: [], jobs: [3 entries]}`. (ticket scenario 1)
- [ ] AC-2: Given 3 vdbIds with 2 succeeding and 1 returning 500, when invoked, then `status == "partial_success"`, `succeeded.length == 2`, `failed.length == 1`, `failed[0].error` is a non-empty string. (ticket scenario 2)
- [ ] AC-3: Given 3 vdbIds all returning 500, when invoked, then `status == "failed"`, `succeeded == []`, `failed.length == 3`. (ticket scenario 3)
- [ ] AC-4: Given `vdbIds=[]`, when invoked, then validation error is raised and `mock_dct.call_count == 0`. (ticket scenario 4)
- [ ] AC-5: Given `vdbIds=["vdb-1"]`, when invoked, then response shape matches AC-1 with `total == 1`. (ticket scenario 5)

---

## FR-002: Bulk stop action with confirmation gate at >5 VDBs

### Description
Allows the caller to stop multiple VDBs in a single tool invocation. Requires manual confirmation when the list exceeds 5 VDBs because stop is a service-affecting operation; otherwise fans out the same way as FR-001.

### Input
- `action` (string, required): `"bulk_stop"`
- `vdbIds` (list[str], required, non-empty)
- `confirmed` (bool, optional, default `False`): when `True`, bypasses the confirmation gate
- Environment: `DCT_BULK_CONCURRENCY` (default 5)

### Processing
1. Validate `vdbIds` as in FR-001 step 2.
2. If `len(vdbIds) > 5` AND `confirmed != True`:
   a. Look up the matching confirmation rule from `config/mappings/manual_confirmation.txt` (added by this ticket): `POST|/vdbs/bulk_stop|manual|Stopping N VDBs will interrupt service — confirm to proceed.`
   b. Return `{"status": "confirmation_required", "confirmation_level": "manual", "message": "<formatted message with N>", "action": "bulk_stop", "vdbIds": vdbIds}` WITHOUT issuing any DCT call.
3. Otherwise (≤ 5 VDBs OR `confirmed=True`): execute fan-out exactly as FR-001 steps 3–10, using `POST /vdbs/{vdbId}/stop`.

### Output
- `confirmation_required` (over threshold, not confirmed): `{status, confirmation_level, message, action, vdbIds}` — no DCT calls.
- Otherwise: same `{status, total, succeeded, failed, jobs}` shape as FR-001.

### Acceptance Criteria
- [ ] AC-1: Given 6 vdbIds and no `confirmed` argument, when `bulk_stop` is invoked, then `status == "confirmation_required"`, `confirmation_level == "manual"`, AND `mock_dct.call_count == 0`. (ticket scenario 7)
- [ ] AC-2: Given the same 6 vdbIds with `confirmed=True`, when `bulk_stop` is invoked, then response is `success`/`partial_success` and `mock_dct.call_count == 6`. (ticket scenario 8)
- [ ] AC-3: Given 3 vdbIds (under threshold) with no `confirmed` argument, when `bulk_stop` is invoked, then response is `success` and `mock_dct.call_count == 3`; no `confirmation_required` returned. (ticket scenario 9)
- [ ] AC-4: Partial-failure and all-failure behaviour matches FR-001 AC-2/AC-3 when the gate is bypassed.

---

## FR-003: Bulk enable action (no confirmation gate)

### Description
Allows the caller to enable multiple VDBs in a single tool invocation. Enable is non-destructive (returns a disabled VDB to operational state), so it never requires confirmation.

### Input
- `action` (string, required): `"bulk_enable"`
- `vdbIds` (list[str], required, non-empty)
- `confirmed` (bool, optional): ignored
- Environment: `DCT_BULK_CONCURRENCY` (default 5)

### Processing
Same as FR-001 with endpoint `POST /vdbs/{vdbId}/enable`. No confirmation gate is consulted regardless of `len(vdbIds)`.

### Output
Same `{status, total, succeeded, failed, jobs}` shape as FR-001.

### Acceptance Criteria
- [ ] AC-1: Given 6 vdbIds and no `confirmed` argument, when `bulk_enable` is invoked, then it executes directly (no confirmation gate), and response shape matches FR-001 AC-1. (ticket scenario 11)
- [ ] AC-2: Partial-failure behaviour matches FR-001 AC-2.

---

## FR-004: Bulk disable action with confirmation gate at >5 VDBs

### Description
Allows the caller to disable multiple VDBs in a single tool invocation. Disable is service-affecting (takes the VDB offline) and is gated identically to `bulk_stop`.

### Input
- `action` (string, required): `"bulk_disable"`
- `vdbIds` (list[str], required, non-empty)
- `confirmed` (bool, optional, default `False`)
- Environment: `DCT_BULK_CONCURRENCY` (default 5)

### Processing
Same as FR-002 with:
- Endpoint: `POST /vdbs/{vdbId}/disable`
- Confirmation rule: `POST|/vdbs/bulk_disable|manual|Disabling N VDBs will take them offline — confirm to proceed.`

### Output
Same as FR-002 (confirmation_required envelope above threshold, aggregate shape otherwise).

### Acceptance Criteria
- [ ] AC-1: Given 6 vdbIds and no `confirmed` argument, when `bulk_disable` is invoked, then `status == "confirmation_required"`, `confirmation_level == "manual"`, AND `mock_dct.call_count == 0`. (ticket scenario 10)
- [ ] AC-2: Given the same 6 vdbIds with `confirmed=True`, response is `success`/`partial_success` and `mock_dct.call_count == 6`.
- [ ] AC-3: Given 3 vdbIds (under threshold) with no `confirmed` argument, response is `success` and `mock_dct.call_count == 3`.

---

## FR-005: Concurrency bounding via DCT_BULK_CONCURRENCY

### Description
Caps the number of simultaneously-in-flight DCT calls during a bulk action at `DCT_BULK_CONCURRENCY` (default 5) to prevent overwhelming the DCT instance with unbounded task spawn.

### Input
- `DCT_BULK_CONCURRENCY` (int, optional, default 5): read from environment at server startup or per-call (design phase to pin).
- Internally: `vdbIds` count from FR-001/2/3/4 input.

### Processing
1. On server startup, read `DCT_BULK_CONCURRENCY` from env. Validate ≥ 1; if invalid or unset, default to 5.
2. Construct a single `asyncio.Semaphore(concurrency)` per bulk-call invocation (one per top-level bulk_* call — semaphore is local to that invocation).
3. Each per-vdbId task acquires before its DCT call and releases after.
4. Never spawn unbounded tasks (e.g. `asyncio.create_task(...)` for all N at once without the semaphore guard is prohibited).

### Output
- Side effect only: the max simultaneous in-flight DCT calls during a single bulk_* invocation is ≤ `DCT_BULK_CONCURRENCY`.

### Acceptance Criteria
- [ ] AC-1: Given 20 vdbIds with `DCT_BULK_CONCURRENCY=3`, where the mocked DCT call awaits an `asyncio.Event` and instruments an in-flight counter, when `bulk_start` is invoked, then the maximum observed in-flight counter value is ≤ 3, and all 20 calls eventually complete. (ticket scenario 6)
- [ ] AC-2: With default config (concurrency=5) and 3 vdbIds, all 3 calls may execute in parallel (counter ≤ 3, not necessarily reaching 5).

---

## FR-006: Toolset registration and visibility

### Description
The four new bulk actions must be registered in the `self_service` and `continuous_data_admin` toolset `.txt` files so they appear in the MCP client's tool list when those toolsets are active, and must NOT appear under `reporting_insights` (which is read-only).

### Input
- `config/toolsets/self_service.txt` — currently has `vdb_tool` entry
- `config/toolsets/continuous_data_admin.txt` — currently has merged `data_tool` entry (covers VDB / dSource / VDB Group)
- `config/toolsets/reporting_insights.txt` — read-only, must NOT receive bulk actions
- `DCT_TOOLSET` env var at server startup

### Processing
1. Append four entries to `config/toolsets/self_service.txt` under the `# TOOL 1: vdb_tool` section:
   ```
   POST|/vdbs/bulk_start|bulk_start
   POST|/vdbs/bulk_stop|bulk_stop
   POST|/vdbs/bulk_enable|bulk_enable
   POST|/vdbs/bulk_disable|bulk_disable
   ```
2. Append the same four entries to `config/toolsets/continuous_data_admin.txt` under the merged `# TOOL 1: data_tool` section so the merged tool exposes them.
3. Do NOT add these entries to `config/toolsets/reporting_insights.txt`.
4. Wire the four `action` values in `tools/dataset_endpoints_tool.py` inside the existing `vdb_tool` function (decorator chain `@app.tool()` + `@log_tool_execution` already in place on that function — extend its dispatch).
5. Ensure `dataset_endpoints_tool` is already in `TOOL_TO_MODULE` for `vdb_tool` (it is) — no change needed to `loader.py`.

### Output
- File-level changes to three text files and one Python file (design phase pins exact line numbers).
- Behavioural: server started with `DCT_TOOLSET=self_service` shows `bulk_start` and `bulk_stop` actions on `vdb_tool`; with `DCT_TOOLSET=continuous_data_admin` shows all four on `data_tool` (the merged form); with `DCT_TOOLSET=reporting_insights` shows none of the four.

### Acceptance Criteria
- [ ] AC-1: Spawn the server with `DCT_TOOLSET=self_service`, list tools, assert `bulk_start` and `bulk_stop` are present on `vdb_tool` (ticket AC + scenario 17).
- [ ] AC-2: Spawn the server with `DCT_TOOLSET=continuous_data_admin`, list tools, assert all four `bulk_*` actions are present (on `data_tool`, the merged tool that covers VDB operations in this toolset). (ticket scenario 18)
- [ ] AC-3: Spawn the server with `DCT_TOOLSET=reporting_insights`, list tools, assert NO `bulk_*` actions appear. (ticket scenario 19)

---

## FR-007: Schema-stable aggregated response

### Description
The aggregated response shape must be exactly `{status, total, succeeded, failed, jobs}` — no missing keys, no extra keys, no renamed keys — so that AI assistants and downstream test code can rely on a deterministic schema.

### Input
- Outcomes from per-VDB tasks in FR-001 step 6.

### Processing
1. Always emit all five keys: `status`, `total`, `succeeded`, `failed`, `jobs`.
2. Empty collections are emitted as `[]`, not omitted.
3. `failed[i]` entries have exactly `{vdbId, error}` (no extras).
4. `jobs[i]` entries have exactly `{vdbId, jobId}` (no extras).
5. The confirmation-required envelope (`{status, confirmation_level, message, action, vdbIds}`) is a DIFFERENT shape; FR-007 covers only the post-execution aggregate.

### Output
Schema as above.

### Acceptance Criteria
- [ ] AC-1: Given 2 vdbIds, all succeed, then response keys are exactly `{status, total, succeeded, failed, jobs}` — assert set equality. (ticket scenario 14)
- [ ] AC-2: When all fail, `jobs == []` is present (not omitted).

---

## FR-008: Logging hygiene

### Description
Each bulk_* call emits exactly one INFO-level log line summarising the batch, and one DEBUG-level log line per VDB outcome. No raw API keys, no full response bodies at INFO. Uses `get_logger(__name__)` from `dct_mcp_server.core.logging` (per `.claude/rules/code-style.md`).

### Input
- Per-call outcomes from FR-001 step 6.

### Processing
1. At end of bulk_* execution, emit one INFO line: `bulk_<action> completed: total=N succeeded=X failed=Y`.
2. For each vdbId, emit one DEBUG line: `bulk_<action> vdb=<vdbId> status=<2xx|error code>`.
3. Use the existing `@log_tool_execution` decorator on `vdb_tool` for telemetry; do not add a second invocation log.

### Output
- Side effect: log entries via the project logger.

### Acceptance Criteria
- [ ] AC-1: Given 3 vdbIds, all succeed, when invoked, then exactly 1 INFO record AND 3 DEBUG records are captured via `caplog`. (ticket scenario 15)
- [ ] AC-2: No INFO/DEBUG record contains the raw `DCT_API_KEY` value (asserted via substring check).

---

## FR-009: Validation of action and input types

### Description
Unknown bulk actions and incorrect input types must be rejected before any DCT call is made.

### Input
- `action` (string)
- `vdbIds` (any type)

### Processing
1. If `action` starts with `bulk_` but is not one of the four supported actions (`bulk_start`, `bulk_stop`, `bulk_enable`, `bulk_disable`): raise `MCPError(f"Unknown bulk action: {action}")` immediately; do not consult the DCT client.
2. If `vdbIds` is not a `list[str]`: raise `MCPError("vdbIds must be a list of strings")` immediately; do not consult the DCT client.

### Output
- `MCPError` raised; no DCT call.

### Acceptance Criteria
- [ ] AC-1: Given `action="bulk_unknown"`, when invoked, then `MCPError` (or equivalent clear error response) is returned AND `mock_dct.call_count == 0`. (ticket scenario 12)
- [ ] AC-2: Given `vdbIds="vdb-1"` (string, not list), when invoked, then validation error AND `mock_dct.call_count == 0`. (ticket scenario 13)

---

## FR-010: Single-VDB action regression preservation

### Description
The existing single-VDB `vdb_tool(action="start", vdbId="vdb-1")` behaviour must remain unchanged after the bulk actions are added. The new actions are pure additions, not replacements.

### Input
- `action` (string): `"start"` (or any existing single-VDB action: `stop`, `enable`, `disable`, etc.)
- `vdbId` (string)

### Processing
- Unchanged from the current implementation in `dataset_endpoints_tool.py`'s `vdb_tool`.

### Output
- Unchanged from the current implementation: a single `{status, jobId, ...}` from the DCT response.

### Acceptance Criteria
- [ ] AC-1: Calling `vdb_tool(action="start", vdbId="vdb-1")` returns the same response shape as before the change (ticket scenario 16). The test mocks the DCT call and asserts response keys.

---

## Quality Rules

| Rule | Description | Enforcement | Status | Evidence |
|------|-------------|-------------|--------|----------|
| API backward compatibility preserved | Existing single-VDB actions (`start`, `stop`, `enable`, `disable`, etc.) on `vdb_tool` continue to work unchanged | FR-010 regression test (ticket scenario 16) in `tests/dlpxeco-13965-test.py`; CI fails on regression | pending | — |
| Bounded concurrency required | All bulk fan-out must use `asyncio.Semaphore` — NO unbounded `asyncio.create_task` loops | Code review checklist + FR-005 AC-1 (ticket scenario 6) asserts max in-flight ≤ cap | pending | — |
| No second retry layer | Bulk wrapper must NOT add retry/backoff; rely on `DCTAPIClient`'s existing retry | Code review + grep for retry/backoff imports in the new code | pending | — |
| Confirmation gate enforced before DCT call | For `bulk_stop`/`bulk_disable` over threshold, ZERO DCT calls allowed pre-confirmation | FR-002 AC-1 and FR-004 AC-1 assert `mock_dct.call_count == 0` (scenarios 7 and 10) | pending | — |
| No raw API key in logs | INFO/DEBUG log records must not contain the `DCT_API_KEY` value | FR-008 AC-2 (`caplog` substring assertion); grep CI step | pending | — |
| Test coverage baseline preserved | Coverage of `dataset_endpoints_tool.py` must not drop below the pre-change baseline | `pytest --cov=src/dct_mcp_server/tools/dataset_endpoints_tool` in CI gate; design phase pins exact baseline | pending | — |
| Logger sourced from project module | Use `get_logger(__name__)` from `dct_mcp_server.core.logging`, never `logging.getLogger` directly | Code review + grep `logging.getLogger` in changed files (must be empty) | pending | — |
| Decorator chain preserved | `vdb_tool` keeps `@app.tool()` and `@log_tool_execution` — no removal or wrapping that breaks telemetry | Code review; visual diff inspection in PR | pending | — |
| No third-party concurrency libs | Concurrency uses only stdlib `asyncio` primitives | Code review + grep `import` statements in changed files | pending | — |
| Toolset .txt files updated in lockstep | Every new `action_name` in code is also listed in the relevant `config/toolsets/*.txt` | FR-006 AC-1/2/3 spawn-and-list tests (scenarios 17/18/19) | pending | — |

---

## Edge Cases

- EC-1: `vdbIds=[]` → `MCPError("vdbIds must be a non-empty list of strings")` raised before any DCT call; `mock_dct.call_count == 0`. (FR-001 AC-4 / scenario 4)
- EC-2: `vdbIds=["vdb-1"]` (single element) → executes fan-out with one task; aggregate shape with `total=1` returned. (FR-001 AC-5 / scenario 5)
- EC-3: All N underlying calls fail with 5xx → `status=="failed"`, `succeeded==[]`, `failed.length==N`, `jobs==[]`. (FR-001 AC-3 / scenario 3)
- EC-4: Mixed success/failure (N-1 succeed, 1 fail) → `status=="partial_success"`; `failed` contains the one failing vdbId with a non-empty error string; `succeeded` contains the rest. (FR-001 AC-2 / scenario 2)
- EC-5: `DCT_BULK_CONCURRENCY=3` with 20 vdbIds → instrumented in-flight counter never exceeds 3 at any sample point; all 20 eventually finish. (FR-005 AC-1 / scenario 6)
- EC-6: `bulk_stop` with exactly 5 vdbIds (boundary) → executes without confirmation (`> 5` is the gate, not `>= 5`). Verified by exact boundary in scenario 9 (3 VDBs) plus a future regression if the boundary ever changes.
- EC-7: `bulk_stop` with 6 vdbIds, `confirmed=False` → `confirmation_required` envelope; ZERO DCT calls. (FR-002 AC-1 / scenario 7)
- EC-8: `bulk_disable` with 6 vdbIds, `confirmed=False` → confirmation envelope (same as EC-7, distinct action). (FR-004 AC-1 / scenario 10)
- EC-9: `bulk_enable` with 6 vdbIds → executes immediately; no confirmation regardless of size. (FR-003 AC-1 / scenario 11)
- EC-10: `vdbIds` is a string (not list) → validation error; ZERO DCT calls. (FR-009 AC-2 / scenario 13)
- EC-11: `action="bulk_unknown"` → validation error; ZERO DCT calls. (FR-009 AC-1 / scenario 12)
- EC-12: Network/transport-level exception (e.g. `asyncio.TimeoutError`) on one VDB → that vdbId appears in `failed` with the exception message; other VDBs still complete. Surface via `asyncio.gather(..., return_exceptions=True)`.

## Error Scenarios

- ERR-1: DCT returns 5xx for vdbId X → caller still gets results for all other vdbIds; X appears under `failed` with `error` populated from the response body or HTTP status. Batch is never aborted on first failure.
- ERR-2: `DCTAPIClient.request` raises `DCTClientError` for vdbId X → caught at the per-task boundary; converted to a `failed` entry with the exception message; other tasks continue. The bulk wrapper never propagates `DCTClientError` out — it always returns the aggregate.
- ERR-3: `asyncio.gather` itself receives an unexpected exception (defensive case) → caught at the bulk wrapper boundary; rethrown as `MCPError` with batch context (which actions had completed). Should never happen in practice; presence of this guard documented in code comments.
- ERR-4: Server-side `confirmation_level` lookup fails (e.g. `manual_confirmation.txt` malformed) → fall back to "always require confirmation" for `bulk_stop`/`bulk_disable` when `len > 5`; log a WARNING; do NOT bypass the gate by accident.
- ERR-5: `DCT_BULK_CONCURRENCY` is set to `0` or a negative number → fall back to default `5` and log a WARNING; do not crash on startup.

## Performance Considerations

- Throughput target: a bulk_* call against N=20 VDBs at `DCT_BULK_CONCURRENCY=5` completes in roughly `ceil(N/concurrency) * single_call_latency`, not `N * single_call_latency`. This is a 4× speedup at N=20 vs sequential; the primary motivation for the feature per the ticket.
- Latency budget: the bulk wrapper adds no synthetic delays — total latency is dominated by the slowest in-flight DCT call. Wrapper overhead must be < 50ms regardless of N (asserted indirectly via the concurrency-cap test; not separately benchmarked).
- Memory: per-VDB outcome is a small dict (≤ ~200 bytes); for N=1000 the in-memory aggregate is < 1 MB. No streaming / pagination needed at this scale.
- Resource bounds: `asyncio.Semaphore(DCT_BULK_CONCURRENCY)` caps DCT-side load. The DCT client's existing retry/backoff handles transient 5xx; the bulk wrapper does NOT add a second retry layer (Quality Rule "No second retry layer").
- Caching: none — every call always hits DCT. Lifecycle operations are not safely cacheable.

---
<!-- Cross-reference:
     FR-001 maps to vision G1 (add bulk_start) and SC1, SC2, SC3 (success/partial/cap).
     FR-002 maps to G1 + G4 (bulk_stop with confirmation gate) and SC4, SC5.
     FR-003 maps to G1 + SC6 (bulk_enable, never gated).
     FR-004 maps to G1 + G4 (bulk_disable mirrors bulk_stop) and SC4, SC5.
     FR-005 maps to G2 (bounded concurrency) and SC3.
     FR-006 maps to G1 + SC7 (toolset registration).
     FR-007 maps to G3 (schema-stable aggregate) and SC1.
     FR-008 maps to logging hygiene from ticket "Notes for Implementer".
     FR-009 maps to validation requirements implicit in SC1 (no surprise calls).
     FR-010 maps to SC8 (no regression of single-VDB behaviour).

     FR-IDs defined here are referenced in tasks-template (Spec References) and validation-template (FR Coverage).
-->
