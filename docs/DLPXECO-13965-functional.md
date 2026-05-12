# Functional Specification: DLPXECO-13965

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13965
**Generated from**: Acceptance criteria in Jira ticket

---

## FR-001: Register bulk lifecycle actions in toolset configuration files

### Description
Registers the four new bulk actions (`bulk_start`, `bulk_stop`, `bulk_enable`, `bulk_disable`) in the `self_service` and `continuous_data_admin` toolset `.txt` configuration files so they are discoverable by the server at startup.

### Input
- Toolset config files: `src/dct_mcp_server/config/toolsets/self_service.txt` and `src/dct_mcp_server/config/toolsets/continuous_data_admin.txt`

### Processing
1. Append four new action lines under `# TOOL 1: vdb_tool` in `self_service.txt`, using the real HTTP verb and underlying DCT endpoint pattern: `POST|/vdbs/bulk_start|bulk_start`, `POST|/vdbs/bulk_stop|bulk_stop`, `POST|/vdbs/bulk_enable|bulk_enable`, `POST|/vdbs/bulk_disable|bulk_disable`. These paths do not correspond to real DCT API endpoints — `loader.py` uses them only to extract the action name token (the third field); the implementation performs the actual fan-out to per-VDB endpoints internally.
2. Append the same four action lines under the VDB section of `continuous_data_admin.txt`.
3. Do not add these actions to `reporting_insights.txt`, `platform_admin.txt`, or `self_service_provision.txt`.
4. Verify action names in the `.txt` files exactly match the handler branch names in `vdb_endpoints_tool.py` (enforced by tests FR-002 and FR-006).
5. No changes to `loader.py` are required — it already extracts action names from the third `|`-delimited field regardless of the endpoint path value.

### Output
- Success: The four action names appear in the loaded toolset config for `self_service` and `continuous_data_admin` when `loader.py` parses the files.
- Failure: A missing or misspelled action name causes the test (test 17/18/19) to fail in CI, surfacing the sync drift.

### Acceptance Criteria
- [ ] AC-1: Given `DCT_TOOLSET=self_service`, when the server starts, then `bulk_start` and `bulk_stop` appear in the registered actions list for `vdb_tool`.
- [ ] AC-2: Given `DCT_TOOLSET=continuous_data_admin`, when the server starts, then all four bulk actions appear in the registered actions list.
- [ ] AC-3: Given `DCT_TOOLSET=reporting_insights`, when the server starts, then none of the four bulk actions are registered.

---

## FR-002: Implement bulk_start action in vdb_tool

### Description
Adds a `bulk_start` action to `vdb_endpoints_tool.py` that fans out the single-VDB `POST /vdbs/{vdbId}/start` endpoint concurrently across a list of VDB IDs and returns an aggregated response.

### Input
- `action` (string, required): must be `"bulk_start"`
- `vdbIds` (list[str], required): non-empty list of VDB identifiers
- `confirmed` (bool, optional, default `False`): confirmation flag (not required for `bulk_start` — no confirmation gate applies)

### Processing
1. Validate that `vdbIds` is a non-empty list of strings; return `MCPError` with HTTP 400 if empty or wrong type.
2. Resolve concurrency limit from `get_dct_config()["bulk_concurrency"]` (pre-validated and clamped by FR-006; do NOT read `os.getenv` directly in the handler to avoid bypassing the clamping logic).
3. Create an `asyncio.Semaphore(concurrency_limit)`.
4. Log one INFO line: `"bulk_start: fanning out to {len(vdbIds)} VDBs with concurrency={concurrency_limit}"`.
5. Launch one async coroutine per VDB ID, each:
   a. Acquires the semaphore.
   b. Calls `DCTAPIClient.request("POST", f"/vdbs/{vdbId}/start", ...)`.
   c. On success: appends `vdbId` to `succeeded` list and job ID (if returned) to `jobs` list.
   d. On `DCTClientError`: logs one DEBUG line with vdbId and error; appends `{"vdbId": vdbId, "error": str(e)}` to `failed` list.
   e. Releases the semaphore.
6. Await all coroutines.
7. Compute `status`: `"success"` if `failed` is empty, `"partial_success"` if both lists are non-empty, `"failed"` if `succeeded` is empty.
8. Return aggregated response dict.

### Output
- Success: `{"status": "success", "total": N, "succeeded": [...], "failed": [], "jobs": [{"vdbId": "...", "jobId": "..."}]}`
- Partial: `{"status": "partial_success", "total": N, "succeeded": [...], "failed": [{"vdbId": "...", "error": "..."}], "jobs": [...]}`
- All failed: `{"status": "failed", "total": N, "succeeded": [], "failed": [...], "jobs": []}`
- Validation error: `MCPError` with message `"vdbIds must be a non-empty list of strings"`

### Acceptance Criteria
- [ ] AC-1: Given 3 VDB IDs all returning 200, when `bulk_start` is called, then `status="success"`, `total=3`, `succeeded` has 3 entries, `failed` is empty.
- [ ] AC-2: Given 3 VDB IDs where one returns a 500 from DCT, when `bulk_start` is called, then `status="partial_success"`, the failed VDB appears in `failed`, and the other two appear in `succeeded`.
- [ ] AC-3: Given all VDB IDs returning errors, when `bulk_start` is called, then `status="failed"` and `succeeded` is empty.
- [ ] AC-4: Given an empty `vdbIds` list, when `bulk_start` is called, then the response is an error before any DCT call is made.
- [ ] AC-5: Given a single VDB ID, when `bulk_start` is called, then the response is equivalent to the single-VDB `start` action result wrapped in the aggregated shape.

---

## FR-003: Implement bulk_stop action with confirmation gate in vdb_tool

### Description
Adds a `bulk_stop` action to `vdb_endpoints_tool.py` that fans out `POST /vdbs/{vdbId}/stop` concurrently. When the list contains more than 5 VDB IDs, requires explicit confirmation before executing.

### Input
- `action` (string, required): must be `"bulk_stop"`
- `vdbIds` (list[str], required): non-empty list of VDB identifiers
- `confirmed` (bool, optional, default `False`): must be `True` if `len(vdbIds) > 5`

### Processing
1. Validate `vdbIds` as non-empty list of strings.
2. If `len(vdbIds) > 5` and `confirmed` is not `True`: return immediately with `{"status": "confirmation_required", "confirmation_level": "manual", "message": f"You are about to stop {len(vdbIds)} VDBs. Re-call with confirmed=True to proceed.", "vdbIds": vdbIds}`.
3. Proceed with the same fan-out logic as FR-002, calling `POST /vdbs/{vdbId}/stop` per VDB.
4. Return aggregated response.

### Output
- Confirmation gate triggered: `{"status": "confirmation_required", "confirmation_level": "manual", "message": "...", "vdbIds": [...]}`
- Confirmed (or <= 5 VDBs): same aggregated shape as FR-002
- Validation error: `MCPError` with message `"vdbIds must be a non-empty list of strings"`

### Acceptance Criteria
- [ ] AC-1: Given 6 VDB IDs and `confirmed=False`, when `bulk_stop` is called, then `status="confirmation_required"` is returned without any DCT call.
- [ ] AC-2: Given 6 VDB IDs and `confirmed=True`, when `bulk_stop` is called, then the batch executes and returns the aggregated result.
- [ ] AC-3: Given 5 or fewer VDB IDs, when `bulk_stop` is called without `confirmed`, then the batch executes immediately (no confirmation gate).

---

## FR-004: Implement bulk_enable action in vdb_tool

### Description
Adds a `bulk_enable` action to `vdb_endpoints_tool.py` that fans out `POST /vdbs/{vdbId}/enable` concurrently with no confirmation gate (enable is a non-destructive operation).

### Input
- `action` (string, required): must be `"bulk_enable"`
- `vdbIds` (list[str], required): non-empty list of VDB identifiers

### Processing
1. Validate `vdbIds` as non-empty list of strings.
2. No confirmation gate — proceed directly to fan-out.
3. Fan-out logic identical to FR-002, calling `POST /vdbs/{vdbId}/enable` per VDB.
4. Return aggregated response.

### Output
- Same aggregated shape as FR-002.

### Acceptance Criteria
- [ ] AC-1: Given any number of VDB IDs (including > 5), when `bulk_enable` is called, then the batch executes without a confirmation gate.
- [ ] AC-2: Given a mix of successful and failed VDB responses, when `bulk_enable` is called, then partial success is correctly reported.

---

## FR-005: Implement bulk_disable action with confirmation gate in vdb_tool

### Description
Adds a `bulk_disable` action to `vdb_endpoints_tool.py` that fans out `POST /vdbs/{vdbId}/disable` concurrently. Like `bulk_stop`, requires explicit confirmation when the list contains more than 5 VDB IDs.

### Input
- `action` (string, required): must be `"bulk_disable"`
- `vdbIds` (list[str], required): non-empty list of VDB identifiers
- `confirmed` (bool, optional, default `False`): must be `True` if `len(vdbIds) > 5`

### Processing
1. Validate `vdbIds` as non-empty list of strings.
2. If `len(vdbIds) > 5` and `confirmed` is not `True`: return `{"status": "confirmation_required", "confirmation_level": "manual", "message": f"You are about to disable {len(vdbIds)} VDBs. Re-call with confirmed=True to proceed.", "vdbIds": vdbIds}`.
3. Fan-out logic identical to FR-002, calling `POST /vdbs/{vdbId}/disable` per VDB.
4. Return aggregated response.

### Output
- Confirmation gate triggered: `{"status": "confirmation_required", "confirmation_level": "manual", "message": "...", "vdbIds": [...]}`
- Confirmed: aggregated shape as FR-002.

### Acceptance Criteria
- [ ] AC-1: Given 6 VDB IDs and no `confirmed`, when `bulk_disable` is called, then `status="confirmation_required"` is returned.
- [ ] AC-2: Given 5 or fewer VDB IDs, when `bulk_disable` is called, then it executes without a confirmation gate.

---

## FR-006: Add DCT_BULK_CONCURRENCY configuration variable

### Description
Exposes `DCT_BULK_CONCURRENCY` as a configurable integer environment variable (default 5) so operators can tune the fan-out parallelism per deployment without code changes.

### Input
- Environment variable `DCT_BULK_CONCURRENCY` (integer string, optional, default `"5"`)

### Processing
1. In `config/config.py`, read `DCT_BULK_CONCURRENCY` with `int(os.getenv("DCT_BULK_CONCURRENCY", "5"))`, wrapped in a try/except `ValueError` to catch non-integer strings (fall back to 5 with a WARNING log).
2. Validate the value is between 1 and 50 (inclusive); if out of range, log a WARNING and clamp to the nearest bound.
3. Add the key `"bulk_concurrency"` to the config dict returned by `get_dct_config()`.
4. The bulk action handlers in `vdb_endpoints_tool.py` read this value via `get_dct_config()["bulk_concurrency"]` at call time (not at import time) to support test injection via env var. Direct `os.getenv` reads in the handler are prohibited — they bypass the clamping and type-validation logic.

### Output
- Success: `config["bulk_concurrency"]` is an integer in [1, 50].
- Invalid value: value is clamped and a WARNING is logged; server startup does not fail.

### Acceptance Criteria
- [ ] AC-1: Given `DCT_BULK_CONCURRENCY=3`, when a bulk action is called with 10 VDBs, then at most 3 concurrent DCT requests are in-flight at once.
- [ ] AC-2: Given `DCT_BULK_CONCURRENCY` not set, when a bulk action is called, then the concurrency limit defaults to 5.
- [ ] AC-3: Given `DCT_BULK_CONCURRENCY=0` (invalid), when the server starts, then the value is clamped to 1 and a WARNING is logged.

---

## FR-007: Instrument bulk actions with log_tool_execution decorator and logging

### Description
Ensures each bulk action is decorated with `@log_tool_execution` for telemetry consistency and emits exactly one INFO log per invocation plus one DEBUG log per per-VDB outcome.

### Input
- Any bulk action invocation.

### Processing
1. The `@log_tool_execution` decorator (already in `dct_mcp_server/core/decorators.py`) is applied to `vdb_tool` which handles all actions including the bulk ones — no separate decoration is needed per action branch.
2. The bulk fan-out helper emits one INFO log before dispatching: `"bulk_{action}: fanning out to {N} VDBs with concurrency={C}"`.
3. Each per-VDB coroutine emits one DEBUG log on completion (success or failure): `"bulk_{action}: vdbId={vdbId} status={ok|error} [{error_msg}]"`.
4. No VDB ID list is emitted at INFO level to avoid token-heavy log lines; the full list appears only at DEBUG level.

### Output
- Observability: exactly 1 INFO log + N DEBUG logs per bulk invocation.
- Telemetry: `@log_tool_execution` records the invocation as it does for all other tool actions.

### Acceptance Criteria
- [ ] AC-1: Given a `bulk_start` call on 3 VDBs, when the action completes, then exactly 1 INFO log entry and 3 DEBUG log entries are emitted.
- [ ] AC-2: Given any bulk action, when `@log_tool_execution` records the call, then no secrets or DCT credentials appear in the log output.

---

## FR-008: Provide full pytest coverage for bulk actions

### Description
Delivers `tests/dlpxeco-13965-test.py` containing all 19 required test scenarios, a module-scoped MCP client fixture, and a function-scoped mock DCT fixture, ensuring CI can validate the feature without a live DCT instance.

### Input
- `tests/dlpxeco-13965-test.py` (new file)
- Environment: `DCT_API_KEY=test-key`, `DCT_BASE_URL=http://fake.test`, `DCT_TOOLSET=continuous_data_admin`, `DCT_BULK_CONCURRENCY=5`
- `DCTAPIClient.request` patched with `AsyncMock`

### Processing
1. Module-scoped `mcp_client` fixture: sets env vars, patches `DCTAPIClient.request`, spawns server via `StdioServerParameters`, yields open `fastmcp.Client`, tears down subprocess.
2. Function-scoped `mock_dct` fixture: accepts a dict of `{vdbId: (status_code, response_body)}` and configures the `AsyncMock` side-effect accordingly.
3. Each of the 19 test functions is `async def test_*` decorated with `@pytest.mark.asyncio`.
4. Tests call `client.call_tool("vdb_tool", {...})` and assert the response shape and values.
5. Concurrency cap test (test 6) uses a `asyncio.Barrier` or counter to measure peak simultaneous in-flight requests.

### Output
- All 19 tests pass: `pytest` exits 0.
- Coverage of `tools/vdb_endpoints_tool.py` >= pre-change baseline (measured via `--cov`).

### Acceptance Criteria
- [ ] AC-1: Running `pytest tests/dlpxeco-13965-test.py -v --cov=src/dct_mcp_server/tools/vdb_endpoints_tool --cov-report=term-missing` exits 0 with all 19 tests passing.
- [ ] AC-2: No test requires a live DCT instance, real API key, or manual MCP-client step.
- [ ] AC-3: The test file is added to the existing GitHub Actions workflow so CI fails the PR on any test failure or coverage drop.

---

## Quality Rules

| Rule | Description | Enforcement | Status | Evidence |
|------|-------------|-------------|--------|----------|
| QR-1 | API backward compatibility: existing single-VDB `start`, `stop`, `enable`, `disable` actions must continue to work unchanged | Regression test `test_single_vdb_start_unchanged` (test 16); no modifications to existing action branches | Pending | — |
| QR-2 | Concurrency is always bounded: `asyncio.Semaphore(DCT_BULK_CONCURRENCY)` is always used; no unbounded `asyncio.gather` without a semaphore | `test_bulk_concurrency_cap` (test 6) measures peak in-flight requests; code review confirms semaphore usage | Pending | — |
| QR-3 | Partial failures do not abort the batch: exceptions from individual VDB coroutines are caught and aggregated, never re-raised | Tests 2, 3, and 8 assert that partial/full failure states return the correct aggregated shape | Pending | — |
| QR-4 | No secrets in log output: VDB IDs may appear at DEBUG but API key and DCT credentials must not appear in any log line emitted by the bulk handler | `test_log_tool_execution_records_invocation` (test 15) inspects log output; CI grep step for credential patterns | Pending | — |
| QR-5 | Action names in `.txt` files match handler code exactly: toolset config and implementation are always in sync | Tests 17, 18, 19 load toolset config files at test time and assert action name presence/absence | Pending | — |
| QR-6 | Validation before execution: `vdbIds` is validated as non-empty list of strings before any async fan-out begins | `test_bulk_start_empty_list_rejected` (test 4) and `test_bulk_invalid_vdbid_type` (test 13) | Pending | — |
| QR-7 | Invalid `DCT_BULK_CONCURRENCY` values are clamped to [1, 50] at startup — server never fails to start due to a bad concurrency setting | `test_bulk_concurrency_cap` (test 6) uses `DCT_BULK_CONCURRENCY=5`; manual: set to `"0"` or `"abc"` and verify WARNING log + fallback behavior | Pending | — |
| QR-8 | `CancelledError` is not swallowed: per-VDB exception handling catches only `DCTClientError`, allowing `asyncio.CancelledError` to propagate for graceful cancellation | Code review: inspect the `except` clause in `_bulk_vdb_action` to confirm it is `except DCTClientError` not bare `except Exception` | Pending | — |

---

## Edge Cases

- EC-1: `vdbIds` is an empty list `[]` → return `MCPError` immediately; no coroutines are launched and no DCT call is made.
- EC-2: `vdbIds` contains a duplicate VDB ID (e.g. `["vdb-1", "vdb-1"]`) → both coroutines execute independently; the response may show the same VDB ID in `succeeded` twice or in both lists; no deduplication is applied (semantics match the caller's intent).
- EC-3: `DCT_BULK_CONCURRENCY=1` → actions execute serially; the semaphore is valid at concurrency=1; this should not deadlock.
- EC-4: A VDB returns HTTP 409 (conflict, already started) from DCT → treated as a `DCTClientError` and added to `failed`; the batch continues.
- EC-5: The DCT API takes longer than `DCT_TIMEOUT` for one VDB → `DCTAPIClient` raises `DCTClientError` with timeout context; the coroutine catches it and appends to `failed`; other in-flight VDBs are unaffected.
- EC-6: `vdbIds` contains 1000 entries with `DCT_BULK_CONCURRENCY=5` → only 5 coroutines run at a time; the semaphore prevents request storms; memory usage stays bounded since coroutines are small.
- EC-7: `DCT_BULK_CONCURRENCY` env var is set to a non-integer string (e.g. `"abc"`) → `int()` raises `ValueError`; `config.py` should catch and fall back to default 5 with a WARNING log.
- EC-8: `bulk_stop` called with exactly 5 VDBs (boundary) → no confirmation gate triggers; executes immediately.
- EC-9: `bulk_stop` called with exactly 6 VDBs (boundary + 1) → confirmation gate triggers; `status="confirmation_required"` returned.
- EC-10: Network connectivity to DCT drops mid-batch (some VDBs started, some not) → completed coroutines are already in `succeeded`; in-flight ones raise `DCTClientError` and land in `failed`; the aggregated response accurately reflects the split state.
- EC-11: Two concurrent `bulk_stop` calls arrive simultaneously for overlapping VDB ID sets → each call gets its own semaphore and coroutine group; the semaphore is per-call, not global; both batches proceed independently. DCT may return 409 for VDBs already being stopped by the first call — these land in `failed` for the second call. No server-side locking is added.
- EC-12: `vdbIds` contains a VDB ID that does not exist in DCT (e.g. `"vdb-nonexistent"`) → DCT returns 404; `DCTAPIClient` raises `DCTClientError`; the ID is added to `failed` with the 404 error message; the batch continues for valid IDs.
- EC-13: `confirmed` is passed as the string `"true"` instead of boolean `True` (MCP JSON serialization edge case) → the handler must coerce `confirmed` to bool; a string `"true"` must NOT bypass the confirmation gate (truthy strings in Python evaluate to `True` in `if confirmed:` — this is fine, but JSON `"true"` is a string, not a bool; FastMCP deserializes it correctly if the parameter type annotation is `bool`). The parameter annotation `confirmed: bool = False` must be present to ensure correct deserialization.
- EC-14: `DCT_BULK_CONCURRENCY` is set to a float string (e.g. `"2.5"`) → `int("2.5")` raises `ValueError`; `config.py` falls back to default 5 with a WARNING log (same path as non-integer string in EC-7).

## Error Scenarios

- ERR-1: `DCTAPIClient.request` raises `DCTClientError` for a subset of VDBs → partial failure path: `failed` list populated, `succeeded` non-empty, `status="partial_success"` returned; no exception propagated to the caller.
- ERR-2: All VDB requests fail → `succeeded=[]`, `status="failed"`, `failed` contains all VDB IDs with their error messages; the response is valid JSON, not an exception.
- ERR-3: `asyncio.Semaphore` creation fails due to invalid concurrency value (<=0) → `config.py` clamps to 1 before the handler sees the value; `ValueError` never reaches the tool body.
- ERR-4: `vdb_tool` is called with an unrecognized bulk action (e.g. `action="bulk_restart"`) → falls through to the existing unknown-action error handler in `vdb_endpoints_tool.py`; returns `MCPError` with `"Unknown action: bulk_restart"`.
- ERR-5: `vdbIds` is passed as a string instead of a list (e.g. `"vdb-1"`) → validation check rejects it with `MCPError` before fan-out; no DCT calls are made.
- ERR-6: The MCP client disconnects mid-batch → the server's async task group continues to completion; results are computed but not delivered; no partial state is written; the next call is independent.
- ERR-7: `get_dct_config()` raises `ValueError` (e.g. `DCT_API_KEY` not set) when called from within a bulk handler → this is not a bulk-specific error; FastMCP catches it and returns an MCP error response; the bulk handler does not need to handle it separately.
- ERR-8: A coroutine is cancelled by the Python runtime (e.g. `asyncio.CancelledError`) mid-fan-out → `CancelledError` must NOT be caught in the per-VDB try/except (it should propagate to allow graceful cancellation); the `except DCTClientError` clause must not use a bare `except Exception` that would swallow `CancelledError`.

## Performance Considerations

- The bulk handler is designed for batches of 1–1000 VDBs. At the default `DCT_BULK_CONCURRENCY=5`, a batch of 100 VDBs requires ceil(100/5) = 20 sequential "waves" of 5 concurrent requests. Assuming each DCT call takes ~200ms, total wall-clock time is approximately 20 × 200ms = 4 seconds — acceptable for a single MCP tool call.
- Memory footprint per coroutine is small (one HTTP request context + response dict). At `DCT_BULK_CONCURRENCY=5` and a 1000-VDB batch, peak memory addition is proportional to 5 × (average DCT response size), typically < 5 KB.
- The `asyncio.Semaphore` adds negligible overhead (nanosecond-scale acquire/release).
- Do not cache bulk results — results must reflect the actual state at call time.
- If `DCT_BULK_CONCURRENCY` is set > 50, the operator is warned and the value is clamped; values > 50 risk overwhelming the DCT API's rate limiter on small deployments.

---

## Assumptions

- **A1 — Async execution model**: `vdb_tool` in `vdb_endpoints_tool.py` will be declared as `async def` to allow `await`-ing the bulk fan-out helper `_bulk_vdb_action`. This overrides the "tool functions are sync" convention in `code-style.md` for this file only. `asyncio.run()` must NOT be used inside FastMCP's already-running event loop — it would raise `RuntimeError`. If any existing single-VDB actions in the same function are sync, they will remain sync; the async declaration is transparent to FastMCP callers.
- **A2 — `manual_confirmation.txt` not used for bulk confirmation**: The bulk action confirmation gate (>5 VDBs triggers `confirmation_required`) is implemented inline in the tool handler, not via entries in `config/mappings/manual_confirmation.txt`. This is necessary because the threshold is data-dependent (list length), which `manual_confirmation.txt` path patterns cannot express. The existing single-VDB stop/disable rules in `manual_confirmation.txt` (RULE 4) do NOT apply to bulk actions because the bulk handler fans out to per-VDB endpoints internally after the confirmation check passes — the MCP layer never sees individual `/vdbs/{vdbId}/stop` calls from the caller.
- **A3 — `vdb_endpoints_tool.py` is a new file**: No file by this name currently exists in `src/dct_mcp_server/tools/`. VDB single-VDB actions (start, stop, enable, disable, etc.) currently live in another tool file (e.g., generated tools or `dataset_endpoints_tool.py`). The bulk actions are net-new additions in the new file; no refactoring of existing single-VDB action code is required.
- **A4 — Test subprocess mock approach**: Because the MCP server spawns as a subprocess via `StdioServerParameters`, `unittest.mock.patch` cannot cross the process boundary to mock `DCTAPIClient.request`. Tests must either: (a) use `respx` (or `pytest-httpx`) to intercept outbound HTTP calls at the network level from the subprocess, or (b) spawn the server in-process using FastMCP's test utilities. The implementer must choose and document one approach in the test file; if `respx` is chosen, it must be added to `requirements.txt` or `pyproject.toml` test dependencies.
- **A5 — GitHub Actions workflow file**: The existing CI workflow is in `.github/workflows/` (implementer should confirm the exact filename before adding the test step). The new test file `tests/dlpxeco-13965-test.py` is added to the same `pytest` invocation used for existing tests.
- **A6 — Duplicate VDB IDs are deduplicated**: If `vdbIds` contains duplicate entries, the implementation deduplicates the list before fan-out (using `list(dict.fromkeys(vdbIds))` to preserve insertion order). A DEBUG-level warning is logged listing the duplicates removed. This prevents double-operations on the same VDB within a single bulk call.
- **A7 — `jobs` list only includes VDBs with a returned jobId**: If a DCT response for a successful VDB action does not include a `jobId` (synchronous operation or DCT version difference), that VDB is added to `succeeded` but NOT to `jobs`. No null-jobId entries appear in `jobs`.

---
<!-- Cross-reference: FR descriptions map to Goals (G1–G4) in vision.md.
     FR Acceptance Criteria satisfy the corresponding Success Criteria (SC1–SC6).
     Quality Rules and Edge Cases address Constraints and Risks from vision.md. -->
