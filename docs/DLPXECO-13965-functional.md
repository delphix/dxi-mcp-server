# Functional Specification: DLPXECO-13965

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13965
**Generated from**: Acceptance criteria in Jira ticket DLPXECO-13965

---

## FR-001: Expose four bulk lifecycle actions on the VDB tool

### Description

Add four new actions — `bulk_start`, `bulk_stop`, `bulk_enable`, `bulk_disable` — to the
existing VDB tool (the `data_tool` function in `dataset_endpoints_tool.py`, which also
backs the `vdb_tool` exposed by the `self_service` toolset). Each action accepts a list of
VDB IDs and fans out to the corresponding per-VDB DCT endpoint.

### Input

- `action` (string, required): one of `bulk_start`, `bulk_stop`, `bulk_enable`, `bulk_disable`.
- `vdbIds` (list[str], required, non-empty): one DCT VDB identifier per element.
- `confirmed` (bool, optional, default false): re-confirm token for destructive bulks.
- All existing per-action body parameters (e.g. `instances`, `abort`, `attempt_start`,
  `container_mode`) remain available; if provided, they are passed identically to **every**
  per-VDB call in the batch.

### Processing

1. Validate `vdbIds` is a non-empty list of strings. If it is `None`, empty, or any element
   is not a string, return `{"error": "vdbIds must be a non-empty list of VDB IDs"}`
   without dispatching any DCT calls.
2. If the action is `bulk_stop` or `bulk_disable` and `len(vdbIds) > 5` and `confirmed` is
   falsy, return a `confirmation_required` response (see FR-005) without dispatching any
   DCT calls.
3. Resolve the per-VDB DCT endpoint from the action:
   `bulk_start → POST /vdbs/{id}/start`, `bulk_stop → POST /vdbs/{id}/stop`,
   `bulk_enable → POST /vdbs/{id}/enable`, `bulk_disable → POST /vdbs/{id}/disable`.
4. Read concurrency limit from env var `DCT_BULK_CONCURRENCY` (int, default 5, clamped to
   `[1, 50]`).
5. Run all per-VDB calls concurrently under `asyncio.Semaphore(concurrency)` and aggregate
   results (see FR-002 and FR-003).
6. Return a single aggregated response (see FR-004).

### Output

- Success path: aggregated response object — see FR-004 for exact schema.
- Validation failure: `{"error": "<message>"}` with no DCT calls dispatched.
- Confirmation gate: see FR-005.

### Acceptance Criteria

- [ ] AC-1: Each of the four actions is callable via `data_tool` and `vdb_tool` and returns
      a 5-key response object (see FR-004) on success.
- [ ] AC-2: Given `vdbIds=[]`, when any bulk action is invoked, then a clear validation
      error is returned and the underlying DCT client receives zero calls.
- [ ] AC-3: Given `vdbIds="vdb-1"` (string instead of list), when invoked, then a clear
      validation error is returned and the DCT client receives zero calls.

---

## FR-002: Bounded-concurrency fan-out via asyncio.Semaphore

### Description

The bulk wrapper must run per-VDB DCT calls concurrently, but the number of in-flight calls
at any moment must never exceed the configured concurrency limit. Concurrency is bounded
with a single `asyncio.Semaphore(concurrency)` inside a single async batch coroutine, which
is then wrapped with the existing `async_to_sync` helper. Workers must never spawn
unbounded tasks.

### Input

- `vdbIds` (list[str]) from FR-001.
- `concurrency` (int): resolved from `DCT_BULK_CONCURRENCY` env var, default 5, clamped to
  `[1, 50]`. Invalid values (non-int, ≤ 0) fall back to the default with a WARNING log.

### Processing

1. Create one `asyncio.Semaphore(concurrency)` per batch.
2. Build a worker coroutine `_one(vdb_id)`. The worker acquires the semaphore, calls the
   per-VDB DCT endpoint via `client.make_request(...)`, captures success/failure, releases
   the semaphore, and returns a `(vdb_id, result_or_error)` tuple.
3. Use `asyncio.gather(*[_one(v) for v in vdbIds])` to await all workers. `gather` is
   called with default `return_exceptions=False` because workers never raise (see FR-003).
4. After gather completes, partition results into `succeeded`, `failed`, `jobs`.

### Output

The fan-out itself produces an unordered list of per-VDB results. Order is restored in the
aggregated response (FR-004) by preserving the request order of `vdbIds`.

### Acceptance Criteria

- [ ] AC-1: Given `vdbIds` of length 20 and `DCT_BULK_CONCURRENCY=3`, when each per-VDB mock
      awaits an `asyncio.Event` and the test tracks an `in_flight` counter, then the
      maximum observed `in_flight` value is ≤ 3 throughout the batch.
- [ ] AC-2: All 20 calls eventually complete (success or failure) — no task is dropped.
- [ ] AC-3: Given `DCT_BULK_CONCURRENCY` is unset, the effective concurrency is 5.
- [ ] AC-4: Given `DCT_BULK_CONCURRENCY=0` or `=-1` or `=foo`, the wrapper logs a WARNING
      and falls back to 5.

---

## FR-003: Per-VDB error isolation — partial failures never abort the batch

### Description

A failure on any individual VDB must not stop the rest of the batch. Each per-VDB call is
wrapped in its own try/except inside the worker; exceptions are recorded as failed entries
in the aggregated response. The bulk action returns a normal response object even when
every per-VDB call fails.

### Input

- A per-VDB result, which is either a successful `dict` from `DCTAPIClient.make_request()`
  or an exception (`DCTClientError`, `MCPError`, `asyncio.TimeoutError`, or any other
  `Exception` raised by the HTTP layer).

### Processing

1. The worker coroutine catches `Exception` (broad on purpose — log layer responsibility),
   converts it to `{"vdbId": <id>, "error": "<str(exc)>"}`, and returns it. The worker
   never re-raises.
2. After `gather`, the aggregator separates entries with an `error` key into the `failed`
   list and entries with a non-error response into `succeeded`.
3. Top-level `status` is computed from counts (see FR-004 AC-1).

### Output

- `failed` list: each entry is `{"vdbId": str, "error": str}` where the error string is
  the string representation of the captured exception. Error strings must be non-empty;
  use `"unknown error"` if `str(exc)` is empty.

### Acceptance Criteria

- [ ] AC-1: Given 3 vdbIds where one mock returns HTTP 500, when the bulk action runs, then
      `status=="partial_success"`, `succeeded` length is 2, `failed` length is 1, and the
      failed entry has a non-empty `error` string.
- [ ] AC-2: Given 3 vdbIds where all 3 mocks raise `DCTClientError`, the response has
      `status=="failed"`, `succeeded=[]`, `failed` length is 3, and no exception is raised
      back to the FastMCP layer.

---

## FR-004: Aggregated response shape

### Description

Every bulk action returns the exact same response shape regardless of action or partial
failure. Consumers must be able to parse the response without conditionally checking which
action was called.

### Input

- The list of per-VDB results from FR-002, in original `vdbIds` order.

### Processing

1. Build `succeeded` = list of `vdbId` strings whose per-VDB call did **not** error.
2. Build `failed` = list of `{"vdbId": str, "error": str}` for each per-VDB call that
   errored.
3. Build `jobs` = list of `{"vdbId": str, "jobId": str}` for each successful call where
   the DCT response contained a `job` object with an `id` field. If a successful response
   has no job id, omit the entry from `jobs` (but it still appears in `succeeded`).
4. Compute `status`: `"success"` if `len(failed) == 0`, `"failed"` if `len(succeeded) == 0`,
   else `"partial_success"`.
5. Compute `total = len(vdbIds)`.
6. Return `{"status", "total", "succeeded", "failed", "jobs"}` — exactly these five keys,
   no extras.

### Output

```json
{
  "status": "success | partial_success | failed",
  "total": 3,
  "succeeded": ["vdb-1", "vdb-2"],
  "failed": [{"vdbId": "vdb-3", "error": "HTTP 500: boom"}],
  "jobs": [
    {"vdbId": "vdb-1", "jobId": "job-abc"},
    {"vdbId": "vdb-2", "jobId": "job-def"}
  ]
}
```

### Acceptance Criteria

- [ ] AC-1: For an all-success 3-VDB batch, response has `status="success"`, `total=3`,
      `succeeded` length 3, `failed=[]`, `jobs` length 3.
- [ ] AC-2: For an all-failure 3-VDB batch, response has `status="failed"`, `total=3`,
      `succeeded=[]`, `failed` length 3, `jobs=[]`.
- [ ] AC-3: For a 2-VDB all-success batch, the response keys are exactly
      `{"status", "total", "succeeded", "failed", "jobs"}` — no extra fields, no missing
      fields.
- [ ] AC-4: For a 1-VDB batch, response has `total=1` and the same 5-key shape.

---

## FR-005: Threshold-based confirmation for destructive bulks

### Description

`bulk_stop` and `bulk_disable` are destructive — they take VDBs offline. When the request
targets **more than 5** VDBs and `confirmed` is not `True`, the bulk wrapper must return a
`confirmation_required` response **without** dispatching any DCT calls. The user must then
re-call with `confirmed=True` for the operation to proceed. `bulk_start` and `bulk_enable`
are non-destructive and never gate on count.

### Input

- `action` from FR-001.
- `vdbIds` from FR-001.
- `confirmed` (bool, optional). Treated as `False` if absent or falsy.

### Processing

1. After input validation (FR-001 step 1), check if `action in ("bulk_stop", "bulk_disable")`.
2. If yes and `len(vdbIds) > 5` and not `confirmed`, return the confirmation envelope:
   ```python
   {
     "status": "confirmation_required",
     "confirmation_level": "manual",
     "confirmation_message": f"You are about to {verb} {len(vdbIds)} VDBs. This is destructive. Re-call with confirmed=True to proceed.",
     "action": action,
     "tool": "data_tool",  # or "vdb_tool" depending on entry point
     "vdb_count": len(vdbIds),
     "instructions": "STOP: Display confirmation_message to the user, get EXPLICIT approval, then re-call with confirmed=True and the same vdbIds."
   }
   ```
3. Do not dispatch DCT calls. Do not consult `manual_confirmation.txt` for the bulk path
   (it has no real path). The threshold check is intentionally inline in the action handler.

### Output

- Confirmation envelope as above; `status` key is `"confirmation_required"`.

### Acceptance Criteria

- [ ] AC-1: Given `action="bulk_stop"`, `vdbIds=[6 ids]`, `confirmed` absent, response has
      `status="confirmation_required"` and `confirmation_level="manual"`. DCT mock receives
      zero calls.
- [ ] AC-2: Given the same call with `confirmed=True`, the response is `success` or
      `partial_success` and the DCT mock receives exactly 6 calls.
- [ ] AC-3: Given `action="bulk_stop"`, `vdbIds=[3 ids]`, no `confirmed`, response is
      `success` (no confirmation gate) and DCT mock receives exactly 3 calls.
- [ ] AC-4: Given `action="bulk_disable"`, `vdbIds=[6 ids]`, no `confirmed`, response is
      `confirmation_required` and DCT mock receives zero calls (parallel to AC-1).
- [ ] AC-5: Given `action="bulk_enable"`, `vdbIds=[6 ids]`, no `confirmed`, response is
      `success` directly (non-destructive — no threshold check).

---

## FR-006: Toolset registration

### Description

The four new actions must be registered in the `self_service` and `continuous_data_admin`
toolset `.txt` files so they appear in the MCP tool list when those toolsets are active.
They must NOT appear in `reporting_insights` (read-only toolset).

### Input

- Two toolset configuration files:
  - `src/dct_mcp_server/config/toolsets/self_service.txt` (defines `vdb_tool`)
  - `src/dct_mcp_server/config/toolsets/continuous_data_admin.txt` (defines `data_tool`)

### Processing

1. In `self_service.txt`, under the `# TOOL 1: vdb_tool - VDB` section, append four lines:
   ```
   POST|/vdbs/bulk_start|bulk_start
   POST|/vdbs/bulk_stop|bulk_stop
   POST|/vdbs/bulk_enable|bulk_enable
   POST|/vdbs/bulk_disable|bulk_disable
   ```
   The `/vdbs/bulk_*` paths are synthetic — they exist only as logical action identifiers in
   the toolset config. They never become real HTTP paths because the action handler
   intercepts the call and fans out to the per-VDB endpoints (`/vdbs/{id}/start` etc.)
   instead of resolving the synthetic path.
2. In `continuous_data_admin.txt`, append the same four lines under the `data_tool` section.
3. Do **not** add entries to `reporting_insights.txt`, `self_service_provision.txt`, or
   `platform_admin.txt`. `self_service_provision` inherits from `self_service` (via
   `@inherit:self_service`), so it picks up the bulk actions automatically — that is
   acceptable per ticket scope and does not require an explicit guard.
4. Update the `# TOOL N: vdb_tool - N Tools` header counts in `self_service.txt` and
   `continuous_data_admin.txt` to reflect the four new entries.

### Output

- `self_service.txt` and `continuous_data_admin.txt` modified.
- No code change to `loader.py` required (existing TOOL_TO_MODULE entries already route
  `vdb_tool` and `data_tool` to `dataset_endpoints_tool`).

### Acceptance Criteria

- [ ] AC-1: With `DCT_TOOLSET=self_service`, the server starts and the tools listed include
      `bulk_start` and `bulk_stop` as actions on `vdb_tool` (per ticket AC).
- [ ] AC-2: With `DCT_TOOLSET=continuous_data_admin`, the server starts and all four bulk
      actions are exposed on `data_tool`.
- [ ] AC-3: With `DCT_TOOLSET=reporting_insights`, the server starts and **no** `bulk_*`
      action is exposed on any tool.

---

## FR-007: Logging at INFO (per batch) and DEBUG (per VDB)

### Description

Every bulk invocation must emit exactly one INFO log line summarizing the batch (action,
count, concurrency, final status) and one DEBUG log line per VDB outcome
(success or failure with error string). This matches the project's existing logging
convention (`get_logger(__name__)`) and lets operators run at INFO level without log spam.

### Input

- The bulk action name, `vdbIds`, the effective concurrency, the final aggregated response.

### Processing

1. Before dispatching, log INFO: `bulk action=<name> total=<N> concurrency=<C>`.
2. For each per-VDB completion, log DEBUG: `bulk action=<name> vdbId=<id> outcome=success`
   or `bulk action=<name> vdbId=<id> outcome=failure error=<message>`.
3. After the batch, log INFO:
   `bulk action=<name> total=<N> succeeded=<S> failed=<F> status=<final>`.
4. Use `logger = get_logger(__name__)` (already declared at module top).

### Output

- Log lines flow through the existing rotating file handler; no new sinks.

### Acceptance Criteria

- [ ] AC-1: For an all-success 3-VDB batch run with `caplog` capturing at DEBUG level, the
      INFO log records >= 1 entries containing `bulk action=` and the DEBUG records contain
      exactly 3 entries with `outcome=success`.
- [ ] AC-2: For an all-failure 3-VDB batch, there are exactly 3 DEBUG entries with
      `outcome=failure` and a non-empty `error=` substring.

---

## FR-008: Backward compatibility — single-VDB actions unchanged

### Description

The existing single-VDB actions (`start_vdb`, `stop_vdb`, `enable_vdb`, `disable_vdb` in
`data_tool` and `start`, `stop`, `enable`, `disable` in `vdb_tool`) must behave identically
before and after this change. No signature changes, no response-shape changes, no
performance regressions.

### Input

- A single-VDB call: `vdb_tool(action="start", vdbId="vdb-1")` or
  `data_tool(action="start_vdb", vdb_id="vdb-1")`.

### Processing

- Untouched. The new bulk branches are added below the existing single-VDB branches and
  guarded by `action.startswith("bulk_")`.

### Output

- Same response as today.

### Acceptance Criteria

- [ ] AC-1: Given `vdb_tool(action="start", vdbId="vdb-1")` with a mock returning the same
      payload it returns today, the response shape and contents match the pre-change
      baseline byte-for-byte (modulo log-line differences).

---

## Quality Rules

| Rule | Description | Enforcement | Status | Evidence |
|------|-------------|-------------|--------|----------|
| QR-1 | API backward compatibility preserved — no change to single-VDB action signatures or response shape | `test_single_vdb_start_unchanged` plus manual diff of `dataset_endpoints_tool.py` around lines 2810–2849 | pending | — |
| QR-2 | No new third-party dependencies — only stdlib `asyncio`, plus existing `pytest`, `pytest-asyncio`, `fastmcp`, `unittest.mock` | `pip-audit` / `requirements.txt` diff review during PR | pending | — |
| QR-3 | All tool functions decorated with `@log_tool_execution` per `.claude/rules/code-style.md` | Grep CI step: `grep -L "@log_tool_execution" src/dct_mcp_server/tools/*_endpoints_tool.py` must be empty | pending | — |
| QR-4 | No bare `Exception` raised in new code — use `DCTClientError` or `MCPError` per code-style.md | Grep CI step: `grep -nE "raise Exception" src/dct_mcp_server/tools/dataset_endpoints_tool.py` must show no matches in the new code blocks | pending | — |
| QR-5 | Logger is `get_logger(__name__)` — never `logging.getLogger` directly in the new code | Grep CI step: `grep -nE "logging\.getLogger\(" src/dct_mcp_server/tools/dataset_endpoints_tool.py` matches only the existing top-level declaration | pending | — |
| QR-6 | Concurrency cap is honored — fan-out never exceeds `DCT_BULK_CONCURRENCY` simultaneous in-flight calls | `test_bulk_concurrency_cap` (scenario 6) | pending | — |
| QR-7 | Confirmation gate fires for `bulk_stop` / `bulk_disable` at >5 VDBs and only those two actions | Scenarios 7, 8, 9, 10, 11 | pending | — |
| QR-8 | Coverage of `dataset_endpoints_tool.py` does not drop below the pre-change baseline | `pytest --cov=src/dct_mcp_server/tools/dataset_endpoints_tool --cov-report=term-missing` in CI; PR description records baseline number | pending | — |
| QR-9 | Tool count for `reporting_insights` is unchanged (no bulk actions leak into read-only toolset) | `test_reporting_insights_excludes_bulk_actions` (scenario 19) | pending | — |
| QR-10 | All 19 ticket-mandated test scenarios pass locally and in CI | `pytest tests/dlpxeco-13965-test.py -v` exits 0 | pending | — |

---

## Edge Cases

- EC-1: `vdbIds=[]` (empty list) → return `{"error": "vdbIds must be a non-empty list"}`;
  zero DCT calls dispatched. **Test scenario 4.**
- EC-2: `vdbIds=["vdb-1"]` (single element) → fan-out still runs through the semaphore;
  response has `total=1` and shape identical to multi-element batch. **Test scenario 5.**
- EC-3: `vdbIds=["vdb-1", "vdb-1", "vdb-1"]` (duplicates) → each entry produces its own
  DCT call; if all three succeed the response shows the same `vdbId` three times in
  `succeeded` and `jobs`. No deduplication. (Deliberate — users may have legitimate reasons
  to issue duplicate calls and silent deduplication would be surprising.)
- EC-4: `vdbIds` contains a `None` or non-string element → return validation error before
  fan-out, zero DCT calls dispatched.
- EC-5: `vdbIds="vdb-1"` (string instead of list) → return validation error.
  **Test scenario 13.**
- EC-6: One VDB returns HTTP 404 (`vdb not found`) — recorded in `failed`, batch continues.
- EC-7: One VDB call times out at `DCT_TIMEOUT` seconds — `DCTClientError` raised by
  `DCTAPIClient`, captured by worker try/except, recorded in `failed`. Batch continues.
- EC-8: All VDBs return network errors — `status="failed"`, `succeeded=[]`,
  `failed` length = `total`. **Test scenario 3.**
- EC-9: `confirmed=True` passed but `len(vdbIds) <= 5` (no gate fires) — the `confirmed` arg
  is silently ignored, batch runs normally. No error.
- EC-10: `action="bulk_unknown"` — caller hits the bulk-dispatch branch but action is not
  one of the four supported names → return validation error. **Test scenario 12.**

## Error Scenarios

- ERR-1: `DCTAPIClient.make_request()` raises `DCTClientError` for one VDB →
  worker captures, records into `failed`, batch continues. Per-VDB error string captured
  via `str(exc)`.
- ERR-2: `DCTAPIClient.make_request()` raises an unexpected `RuntimeError` (e.g. event
  loop closure issue) → worker captures via broad `except Exception`, records the
  exception type and message as `error`, batch continues. The wrapper does not crash the
  MCP tool layer.
- ERR-3: `asyncio.Semaphore` deadlocks (theoretical) → not possible in current design
  because workers always release in `finally`. No recovery path needed.
- ERR-4: `DCT_BULK_CONCURRENCY` set to a non-integer string → log WARNING, fall back to 5.
- ERR-5: `DCT_BULK_CONCURRENCY` set to a very large value (e.g. 10000) → clamp to 50 and
  log WARNING. Prevents accidental DCT overload.
- ERR-6: Server-side rate limiting (HTTP 429) on one or more per-VDB calls → captured as
  failure. The existing `DCTAPIClient` retry/backoff handles transient 429s before the
  failure surfaces. The bulk wrapper does **not** add additional retry logic.

## Performance Considerations

- Latency target: for a 20-VDB batch with `DCT_BULK_CONCURRENCY=5` and a 200ms per-call
  latency, total wall-clock should be approximately `(20/5) * 200ms = 800ms`, plus
  ~50ms overhead for `asyncio.run` setup and result aggregation. Total budget: ≤ 1.0s p99.
- Memory: bounded by `concurrency × max-response-size`. Per-VDB response is small (~1 KB
  for a job-id payload), so worst-case in-flight memory for `concurrency=50` is ~50 KB.
- CPU: dominated by JSON encoding/decoding inside `httpx`, which is what the
  existing single-VDB path uses. No new hot loops.
- DCT load: 50× concurrent calls per client is generous but bounded; multiple AI assistants
  hitting the same server simultaneously could overwhelm DCT. Default of 5 is conservative
  by design; operators who scale up must accept the responsibility of monitoring DCT.
- Scaling beyond 200 VDBs per call: tested with `vdbIds` up to 50 in test scenario 6
  variants; behavior above 1000 is undefined and out of scope.

---
<!-- Cross-reference: FR-001 through FR-008 map back to vision Goals G1-G4.
     AC entries in each FR satisfy vision Success Criteria SC1-SC9 as follows:
       FR-001 AC-1 / FR-004 AC-3       → SC1, SC9
       FR-002 AC-1                     → SC2
       FR-003 AC-1, AC-2               → SC3
       FR-005 AC-1, AC-3, AC-4         → SC4, SC6, SC7
       FR-005 AC-2                     → SC5
       FR-006 AC-1, AC-2, AC-3         → SC8
       QR-10                           → SC9
     Risks #2, #4 from vision drive QR-1, QR-3, QR-6, QR-7, EC-4, ERR-1, ERR-2. -->
