# Design: DLPXECO-13965 — Bulk action support for vdb_tool

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13965
**Inputs**: `docs/DLPXECO-13965-vision.md`, `docs/DLPXECO-13965-functional.md`
**Domain**: feature
**Project**: Delphix DCT MCP Server (Python 3.11+, FastMCP, async-first)

---

## Summary

Add `bulk_start`, `bulk_stop`, `bulk_enable`, `bulk_disable` actions to the existing
`data_tool` function in `dataset_endpoints_tool.py`. Each action accepts a
`vdbIds: list[str]`, fans out to the per-VDB DCT endpoint
(`POST /vdbs/{id}/{start|stop|enable|disable}`) under one `asyncio.Semaphore(C)` inside
one `asyncio.gather`, isolates per-VDB failures with try/except inside each worker, and
returns a single 5-key aggregated response (`status`, `total`, `succeeded`, `failed`,
`jobs`). Threshold confirmation (>5 VDBs, `bulk_stop` / `bulk_disable` only) is enforced
inline before any DCT call dispatches. The same four actions are registered in both
`self_service.txt` and `continuous_data_admin.txt`. No DCT API changes, no new third-party
dependencies, no new tool module. Detailed walkthrough in §1 Overview below.

## Affected Components

- **`src/dct_mcp_server/tools/dataset_endpoints_tool.py`** — add 4 new action branches in
  the existing `data_tool` function and 4 new private module-level helpers
  (`_resolve_bulk_concurrency`, `_bulk_endpoint_for`, `_bulk_confirmation_envelope`,
  `_run_bulk_batch`). Update `data_tool` signature to accept `vdbIds`.
- **`src/dct_mcp_server/config/toolsets/self_service.txt`** — append 4 synthetic
  `POST|/vdbs/bulk_*|bulk_*` lines under the `vdb_tool` block.
- **`src/dct_mcp_server/config/toolsets/continuous_data_admin.txt`** — append the same 4
  lines under the `data_tool` VDB Operations block.
- **`tests/dlpxeco-13965-test.py`** — new pytest-asyncio file with 19 functional scenarios
  + 3 static checks driving the local MCP server over stdio.
- **NOT changed**: `dct_client/client.py`, `config/loader.py`,
  `config/mappings/manual_confirmation.txt`, `toolsets/reporting_insights.txt`,
  `toolsets/platform_admin.txt`, `toolsets/self_service_provision.txt`. See §2 for the
  full rationale per file.

## Architecture Changes

The change is purely client-side fan-out wrapping existing per-VDB DCT endpoints — no
server-side batch endpoint, no new transport code. The four action branches share a
single `_run_bulk_batch` async coroutine that:

1. Creates one `asyncio.Semaphore(concurrency)` per call (concurrency from
   `DCT_BULK_CONCURRENCY`, default 5, clamped to `[1, 50]`).
2. Builds one worker coroutine per VDB. Each worker acquires the semaphore, calls
   `client.make_request("POST", endpoint, json=extra_body)`, and catches every `Exception`
   inside its body — workers never raise.
3. Awaits the workers via a single `asyncio.gather` whose default `return_exceptions=False`
   is safe because workers never re-raise.
4. Aggregates results in caller-provided `vdbIds` order into `succeeded`, `failed`, `jobs`
   lists and computes `status` from counts.

The whole batch coroutine is wrapped with the existing `async_to_sync` helper at the call
site — one event loop per batch, not per VDB. This addresses vision risk #3.

For `bulk_stop` / `bulk_disable` only, an **inline** threshold check fires when
`len(vdbIds) > 5 and not confirmed` and returns the standard `confirmation_required`
envelope without dispatching any DCT calls. The check is intentionally inline (not in
`manual_confirmation.txt`) because the path-pattern matcher would not handle a synthetic
batch path cleanly — see §8 and ADR-2 for the full rationale.

Full layout map, data-flow diagram, helper signatures, and per-branch code shape are in
§2–§7 below.

## Version Compatibility

| Dimension | Status | Notes |
|-----------|--------|-------|
| Python runtime | 3.11+ | Uses stdlib `asyncio.Semaphore`, `asyncio.gather`, `asyncio.TimeoutError`. All native to Python 3.11. |
| Project floor | Unchanged | `pyproject.toml` already pins `>=3.11`. No floor bump. |
| DCT API | Any version that exposes `POST /vdbs/{id}/{start\|stop\|enable\|disable}` | These endpoints have been part of DCT since v1; this ticket relies on no new DCT version-specific feature. |
| FastMCP | Unchanged | Tool functions remain sync per FastMCP contract (vision C2); we use the existing `async_to_sync` adapter. |
| Third-party deps | None added | Only stdlib `asyncio` plus existing `pytest`, `pytest-asyncio`, `fastmcp`, `unittest.mock`. (Vision C8, QR-2.) |
| MCP client compatibility | Unchanged | Bulk actions are exposed in the same way as existing actions on `vdb_tool` / `data_tool`. Claude Desktop, Cursor, VS Code Copilot all see the new actions without any client-side change. |
| Backward compatibility | Preserved | Existing single-VDB action branches (`start_vdb`, `stop_vdb`, `enable_vdb`, `disable_vdb` at lines 2810–2849 and the `self_service` `start/stop/enable/disable` branches) are untouched. (§12; FR-008; QR-1.) |

## Platform Behavior Notes

- **Event-loop topology**: each bulk invocation creates exactly one event loop via
  `async_to_sync(_run_bulk_batch)(...)`. This is critical: wrapping each per-VDB call in
  its own `async_to_sync` would create N loops and serialize all calls behind the
  thread-per-call fallback (`dataset_endpoints_tool.py:79–87`). The bulk wrapper bypasses
  this trap by wrapping the batch, not the worker. (§7, ADR-1, vision risk #3.)
- **Thread vs. async**: FastMCP runs tool functions on its own thread. `async_to_sync`
  detects the running-loop condition and falls back to `threading.Thread(target=run_in_thread)`
  + `asyncio.run` (lines 75–90). The bulk wrapper's single event loop runs inside that
  worker thread for the duration of the batch; semaphore acquisition and gather are all
  scoped within that single loop.
- **No retry stacking**: `DCTAPIClient.make_request()` already retries up to
  `DCT_MAX_RETRIES` with exponential backoff (`client.py:92–140`). The bulk wrapper does
  **not** add its own retry layer; after `DCTAPIClient` exhausts retries and raises
  `DCTClientError`, the worker catches it and records the failure. (Vision NG4.)
- **Concurrency cap**: clamped to `[1, 50]` to prevent accidental DCT overload. Values
  outside this range or non-int → WARNING log and fallback to 5. (Vision risk: DCT
  protection; FR-002 AC-3, AC-4.)
- **Order preservation**: `asyncio.gather` preserves input order, so the
  `succeeded`/`failed`/`jobs` lists reflect the caller's `vdbIds` order (FR-002 output
  note).
- **Logging volume**: at default INFO level, every bulk call emits exactly 2 INFO lines
  (one before, one after). DEBUG-level adds N lines per batch. Production loggers default
  to INFO. (§9; FR-007.)
- **Toolset visibility**: bulk actions surface in `self_service` and
  `continuous_data_admin`, inherit into `self_service_provision` via `@inherit:self_service`,
  and are absent from `reporting_insights` and `platform_admin`. (§10; FR-006; QR-9.)

## Acceptance Criteria

All criteria below are verified by `tests/dlpxeco-13965-test.py` (see
`docs/DLPXECO-13965-test-plan.md` for the scenario→FR mapping). FR IDs reference the
functional spec.

- [ ] **FR-001 AC-1** — A 3-VDB success call returns the 5-key response shape
      (`status`, `total`, `succeeded`, `failed`, `jobs`). _Scenario 1._
- [ ] **FR-001 AC-2** — `vdbIds=[]` returns a validation error and dispatches zero DCT
      calls. _Scenario 4._
- [ ] **FR-001 AC-3** — `vdbIds="vdb-1"` (string, not list) returns a validation error
      and dispatches zero DCT calls. _Scenario 13._
- [ ] **FR-002 AC-1** — With `DCT_BULK_CONCURRENCY=3` and 20 vdbIds, max observed
      in-flight calls is ≤ 3 throughout. _Scenario 6._
- [ ] **FR-002 AC-2** — All 20 calls complete (no dropped tasks). _Scenario 6._
- [ ] **FR-002 AC-3** — Unset `DCT_BULK_CONCURRENCY` yields effective concurrency 5.
      _Concurrency env-var test._
- [ ] **FR-002 AC-4** — `DCT_BULK_CONCURRENCY=0|-1|foo` logs WARNING and falls back to 5.
      _Concurrency env-var test._
- [ ] **FR-003 AC-1** — 2-of-3 success and 1-of-3 failure → `status="partial_success"`,
      `failed[0].error` non-empty, batch does not abort. _Scenario 2._
- [ ] **FR-003 AC-2** — All 3 fail → `status="failed"`, no exception bubbles to FastMCP.
      _Scenario 3._
- [ ] **FR-004 AC-1** — All-success batch has correct counts and `jobs` length.
      _Scenario 1._
- [ ] **FR-004 AC-2** — All-failure batch has empty `succeeded`/`jobs`. _Scenario 3._
- [ ] **FR-004 AC-3** — Response keys are exactly the 5 specified, no extras.
      _Scenario 1._
- [ ] **FR-004 AC-4** — Single-VDB batch has `total=1` and same 5-key shape.
      _Scenario 5._
- [ ] **FR-005 AC-1** — `bulk_stop`, 6 vdbIds, no `confirmed` → `confirmation_required`,
      zero DCT calls. _Scenario 7._
- [ ] **FR-005 AC-2** — Same call with `confirmed=True` → exactly 6 DCT calls dispatched.
      _Scenario 8._
- [ ] **FR-005 AC-3** — `bulk_stop`, 3 vdbIds, no `confirmed` → proceeds, 3 DCT calls.
      _Scenario 9._
- [ ] **FR-005 AC-4** — `bulk_disable`, 6 vdbIds, no `confirmed` → `confirmation_required`,
      zero DCT calls. _Scenario 10._
- [ ] **FR-005 AC-5** — `bulk_enable`, 6 vdbIds, no `confirmed` → proceeds, 6 DCT calls.
      _Scenario 11._
- [ ] **FR-006 AC-1** — `DCT_TOOLSET=self_service`: bulk actions visible on `vdb_tool`.
      _Scenario 17._
- [ ] **FR-006 AC-2** — `DCT_TOOLSET=continuous_data_admin`: bulk actions visible on
      `data_tool`. _Scenario 17._
- [ ] **FR-006 AC-3** — `DCT_TOOLSET=reporting_insights`: no `bulk_*` action exposed.
      _Scenario 19._
- [ ] **FR-007 AC-1** — Successful 3-VDB batch logs ≥1 INFO with `bulk action=` plus
      exactly 3 DEBUG `outcome=success`. _Scenarios 14, 15._
- [ ] **FR-007 AC-2** — All-failure 3-VDB batch logs exactly 3 DEBUG `outcome=failure`
      with non-empty `error=`. _Scenario 16._
- [ ] **FR-008 AC-1** — Existing `start_vdb` single-VDB response is byte-identical
      pre/post change. _Scenario 18._

## Open Questions / Risks

No open questions remain — all ticket ambiguities were resolved in vision and functional
specs and re-checked in §15 below. The active design-time risks are:

| Risk | Likelihood | Impact | Mitigation |
|------|-----------:|-------:|-----------|
| A future maintainer adds a fifth destructive bulk action and forgets to wire the inline confirmation gate. | Medium | Medium | A `#`-comment header at the top of the first bulk branch documents the four-step contract (validate → optional FR-005 gate → fan-out → log → return). Code review of any future bulk addition catches the omission. |
| A future contributor mistakes the synthetic `/vdbs/bulk_*` paths in the toolset `.txt` files for real DCT endpoints. | Low | Low | Add a 1-line `#` comment immediately above the 4 lines in each toolset file: `# Synthetic paths — action handler fans out to per-VDB endpoints.` |
| `data_tool` is already 4959 lines and grows further with this change. | Low | Low | Vision risk #6 already accepted this as Low/Low. File split is deferred to a separate refactor ticket and is explicitly out of scope (vision NG5 spirit). |
| The pre-existing `logging.getLogger(__name__)` at line 11 violates `.claude/rules/code-style.md`. | Low | Low | Out of scope for this ticket — we do not amplify the violation and do not introduce any new `logging.getLogger` call. Fix is a separate refactor. |
| `pytest-asyncio` is missing from `requirements.txt`. | Low (test-infra.md implies it is present) | Medium (tests cannot run) | Verify during the implement phase. If missing, add it to `requirements.txt` alongside the test file. This counts as a test-only dependency, not a runtime dependency — vision C8 still holds. |
| Test mocking inside an MCP subprocess turns out to be infeasible. | Medium | Medium | Fallback documented in test-plan §1: run a thin httpx-mock proxy on `localhost:<port>` with `DCT_BASE_URL` overridden. Decision point is after scenario 1 runs. |

All risks listed above are either accepted (Low/Low items) or have a concrete mitigation
with an owner in the implement phase. No risk blocks the design.

## 1. Overview

Add four new action branches — `bulk_start`, `bulk_stop`, `bulk_enable`, `bulk_disable` — to
the existing grouped `data_tool` function in `src/dct_mcp_server/tools/dataset_endpoints_tool.py`.
Each action accepts `vdbIds: list[str]`, fans the per-VDB DCT calls out under one
`asyncio.Semaphore`-bounded `asyncio.gather`, isolates per-VDB failures inside each worker's
try/except, and returns a single 5-key aggregated response (`status`, `total`, `succeeded`,
`failed`, `jobs`).

The implementation is purely client-side. It re-uses the existing `DCTAPIClient.make_request()`
(no bypass to raw `httpx`), the existing `async_to_sync` wrapper for the FastMCP sync-function
contract, the existing single-VDB endpoints (`POST /vdbs/{id}/start|stop|enable|disable`), and
the existing two-step `confirmation_required` envelope used elsewhere in the codebase. No DCT
API changes, no new dependencies, no new tool module.

Threshold-based confirmation is checked **inline** in the action handler (not via
`manual_confirmation.txt`) because the bulk operation has no real HTTP path that the
path-pattern matcher could key off. This is the deliberate deviation documented in vision risk
#2 / functional FR-005.

## 2. Architecture Changes

### Source Files to Modify

| Path | Purpose | Approx lines |
|------|---------|--------------|
| `src/dct_mcp_server/tools/dataset_endpoints_tool.py` | Add 4 action branches (`bulk_start`, `bulk_stop`, `bulk_enable`, `bulk_disable`) inside the existing `data_tool` function. Add 1 module-level helper coroutine `_run_bulk_batch(...)`. Add `vdbIds: Optional[list] = None` and `confirmed` is already in the signature for the existing destructive actions. | ~180 new lines (4 branches × ~25 lines + ~60-line helper + ~20 lines of docstring updates) |
| `src/dct_mcp_server/config/toolsets/self_service.txt` | Append 4 lines under the `# TOOL 1: vdb_tool - VDB` section so the bulk actions surface in the `self_service` MCP tool list. Bump the header `# Self Service Toolset - 6 Tools` description note if applicable. | +4 lines |
| `src/dct_mcp_server/config/toolsets/continuous_data_admin.txt` | Append 4 lines under the `# TOOL 1: data_tool - VDB / VDB Group / dSources (merged)` section in the VDB Operations block. | +4 lines |
| `tests/dlpxeco-13965-test.py` | New test file with all 19 pytest-asyncio scenarios driving the local MCP server over stdio (see test plan). | ~600 lines |

### Source Files NOT to Modify

| Path | Why not |
|------|---------|
| `src/dct_mcp_server/dct_client/client.py` | The bulk wrapper goes through `client.make_request()` unchanged. No retry-stacking, no new transport code. |
| `src/dct_mcp_server/config/loader.py` | `vdb_tool` and `data_tool` are already routed to `dataset_endpoints_tool` via the existing `TOOL_TO_MODULE` map (loader.py:445 and :452). No mapping change. |
| `src/dct_mcp_server/config/mappings/manual_confirmation.txt` | Threshold gate is inline (FR-005); the path-pattern matcher would not be a clean fit for the synthetic `/vdbs/bulk_*` paths. |
| `src/dct_mcp_server/config/toolsets/reporting_insights.txt` / `self_service_provision.txt` / `platform_admin.txt` | Read-only / not-in-scope toolsets. `self_service_provision` inherits from `self_service` via `@inherit:self_service` and picks up the bulks automatically (FR-006 step 3). |
| Existing single-VDB action branches (`start_vdb`, `stop_vdb`, `enable_vdb`, `disable_vdb` at lines 2810–2849 and the corresponding self-service `start`, `stop`, `enable`, `disable` branches) | Backward compatibility — FR-008. |

### Module Layout

```
src/dct_mcp_server/tools/dataset_endpoints_tool.py  (existing — 4959 lines today)
├── (existing imports)                                line 1-12
├── check_confirmation(...)                           line 32-67   (untouched)
├── async_to_sync(...)                                line 69-95   (untouched)
├── make_api_request(...)                             line 97-102  (untouched)
├── build_params(...)                                 line 104-106 (untouched)
├── _resolve_bulk_concurrency() -> int                NEW          (clamps DCT_BULK_CONCURRENCY)
├── _bulk_endpoint_for(action) -> str                 NEW          (maps bulk_start → "/vdbs/{id}/start")
├── _bulk_confirmation_envelope(action, vdb_ids,     NEW          (builds FR-005 envelope)
│       tool_name) -> dict
├── _run_bulk_batch(action, vdb_ids, concurrency,    NEW          (async batch coroutine — gather under Semaphore)
│       extra_body, tool_name) -> dict
├── @log_tool_execution                                line 108
│   def data_tool(...)                                 line 109
│       ├── (existing 130 branches)                    line 2690-4940-ish
│       ├── elif action == 'bulk_start': ...           NEW   (~25 lines)
│       ├── elif action == 'bulk_stop': ...            NEW   (~25 lines)
│       ├── elif action == 'bulk_enable': ...          NEW   (~25 lines)
│       ├── elif action == 'bulk_disable': ...         NEW   (~25 lines)
│       └── else: 'Unknown action' branch              (existing; add the 4 new names to the message)
└── register_tools(app, dct_client)                    line 4944-4959 (untouched)
```

The four bulk-action `elif` blocks are inserted **after** the existing `disable_vdb` branch
(line 2849) so they live next to their non-bulk counterparts, keeping the file's existing
"VDB ops first, then VDB group ops, then dSource ops" ordering intact.

## 3. New Helper Functions (module-level, private)

All four helpers live at the top of `dataset_endpoints_tool.py` just below `build_params()`
(after line 106). They are private (`_`-prefixed), sync where they can be, and have no
side-effects other than logging.

### 3.1 `_resolve_bulk_concurrency() -> int`

```
Reads os.environ.get("DCT_BULK_CONCURRENCY"), parses to int, clamps to [1, 50].
On parse failure, value <= 0, or value > 50 → logs WARNING and returns 5.
On missing env var → returns 5 silently (the documented default).
```

- Logger: `logger.warning("DCT_BULK_CONCURRENCY=<raw> is invalid; falling back to 5")`.
- Returns: `int` in `[1, 50]`.
- No exceptions raised.
- Pure function. Called once per bulk invocation (cheap, env vars rarely change at runtime).

### 3.2 `_bulk_endpoint_for(action: str) -> str | None`

```
Map bulk_start → "/vdbs/{vdb_id}/start"
    bulk_stop  → "/vdbs/{vdb_id}/stop"
    bulk_enable → "/vdbs/{vdb_id}/enable"
    bulk_disable → "/vdbs/{vdb_id}/disable"
    other → None
```

The `{vdb_id}` token is a format placeholder; the caller calls
`endpoint_template.format(vdb_id=vid)` for each VDB.

### 3.3 `_bulk_confirmation_envelope(action, vdb_ids, tool_name) -> dict`

Returns the FR-005 envelope. Verb mapping: `bulk_stop → "stop"`, `bulk_disable → "disable"`.

```python
return {
    "status": "confirmation_required",
    "confirmation_level": "manual",
    "confirmation_message": (
        f"You are about to {verb} {len(vdb_ids)} VDBs. This is destructive. "
        "Re-call with confirmed=True to proceed."
    ),
    "action": action,
    "tool": tool_name,
    "vdb_count": len(vdb_ids),
    "instructions": (
        "STOP: Display confirmation_message to the user, get EXPLICIT approval, "
        "then re-call with confirmed=True and the same vdbIds."
    ),
}
```

### 3.4 `_run_bulk_batch(action, vdb_ids, concurrency, extra_body, tool_name) -> dict`

Single `async def` coroutine. Wraps the whole batch — **not** each per-VDB call —
with `async_to_sync` at the call site (see §4 below). One `asyncio.Semaphore(concurrency)`
created here per batch. One `asyncio.gather(...)` per batch.

Signature:

```python
async def _run_bulk_batch(
    action: str,
    vdb_ids: list[str],
    concurrency: int,
    extra_body: dict | None,
    tool_name: str,
) -> dict
```

Inner worker coroutine:

```python
sem = asyncio.Semaphore(concurrency)
endpoint_template = _bulk_endpoint_for(action)

async def _one(vid: str) -> tuple[str, dict]:
    async with sem:
        try:
            endpoint = endpoint_template.format(vdb_id=vid)
            resp = await client.make_request(
                "POST", endpoint,
                params={}, json=extra_body or None,
            )
            logger.debug(
                f"bulk action={action} vdbId={vid} outcome=success"
            )
            return (vid, resp)
        except Exception as exc:               # broad on purpose — FR-003
            err = str(exc) or "unknown error"
            logger.debug(
                f"bulk action={action} vdbId={vid} outcome=failure error={err}"
            )
            return (vid, {"_bulk_error": err})

results = await asyncio.gather(*[_one(v) for v in vdb_ids])
# results is ordered by request order (asyncio.gather preserves input order).
```

Aggregation:

```python
succeeded: list[str] = []
failed:    list[dict] = []
jobs:      list[dict] = []
for vid, resp in results:
    if isinstance(resp, dict) and "_bulk_error" in resp:
        failed.append({"vdbId": vid, "error": resp["_bulk_error"]})
        continue
    succeeded.append(vid)
    job = (resp or {}).get("job") if isinstance(resp, dict) else None
    if job and isinstance(job, dict) and job.get("id"):
        jobs.append({"vdbId": vid, "jobId": job["id"]})

if not failed:
    status = "success"
elif not succeeded:
    status = "failed"
else:
    status = "partial_success"

return {
    "status": status,
    "total": len(vdb_ids),
    "succeeded": succeeded,
    "failed": failed,
    "jobs": jobs,
}
```

## 4. Action-Branch Wiring

Each of the four new branches lives in the existing `data_tool(...)` function (also reachable
via the `vdb_tool` MCP name from `self_service` because both names route to
`dataset_endpoints_tool` via `loader.py:TOOL_TO_MODULE`). The branch body is:

```python
elif action == 'bulk_start':                                              # also: bulk_enable
    # FR-001 validation
    if not isinstance(vdbIds, list) or len(vdbIds) == 0 or \
       not all(isinstance(v, str) and v for v in vdbIds):
        return {"error": "vdbIds must be a non-empty list of VDB IDs"}
    concurrency = _resolve_bulk_concurrency()
    logger.info(
        f"bulk action={action} total={len(vdbIds)} concurrency={concurrency}"
    )
    extra_body = {k: v for k, v in {'instances': instances}.items() if v is not None}
    result = async_to_sync(_run_bulk_batch)(
        action, vdbIds, concurrency, extra_body or None, 'data_tool',
    )
    logger.info(
        f"bulk action={action} total={result['total']} "
        f"succeeded={len(result['succeeded'])} failed={len(result['failed'])} "
        f"status={result['status']}"
    )
    return result
```

For `bulk_stop` / `bulk_disable` the body is the same with two additions: the inline
threshold gate (FR-005) and the per-action `extra_body` shape:

```python
elif action == 'bulk_stop':                                               # also: bulk_disable
    if not isinstance(vdbIds, list) or len(vdbIds) == 0 or \
       not all(isinstance(v, str) and v for v in vdbIds):
        return {"error": "vdbIds must be a non-empty list of VDB IDs"}
    if len(vdbIds) > 5 and not confirmed:
        return _bulk_confirmation_envelope(action, vdbIds, 'data_tool')
    concurrency = _resolve_bulk_concurrency()
    logger.info(
        f"bulk action={action} total={len(vdbIds)} concurrency={concurrency}"
    )
    # bulk_stop body shape: {'instances': ..., 'abort': ...}
    # bulk_disable body shape: {'attempt_cleanup': ..., 'container_mode': ...}
    extra_body = {k: v for k, v in {
        'instances': instances, 'abort': abort,
    }.items() if v is not None}
    result = async_to_sync(_run_bulk_batch)(
        action, vdbIds, concurrency, extra_body or None, 'data_tool',
    )
    logger.info(
        f"bulk action={action} total={result['total']} "
        f"succeeded={len(result['succeeded'])} failed={len(result['failed'])} "
        f"status={result['status']}"
    )
    return result
```

Why `async_to_sync(_run_bulk_batch)(...)` and not per-VDB `make_api_request(...)`:
`make_api_request` already wraps each call in its own `asyncio.run`, which would
spawn/tear-down a fresh event loop per VDB and serialize all calls behind the GIL-held
thread join. By wrapping a single batch coroutine that calls `client.make_request` directly,
we create exactly one event loop per bulk invocation and let `asyncio.gather` do the
concurrency. This addresses vision risk #3 and is verified by `test_bulk_concurrency_cap`.

## 5. Signature Change to `data_tool`

`data_tool` already has a long keyword-argument tail. Two new parameters need to surface in
the public signature:

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `vdbIds` | `Optional[List[str]]` | `None` | Required only when `action` starts with `bulk_`. Camel-case to match the input contract documented in the functional spec FR-001 and the synthetic toolset path. |
| `confirmed` | `Optional[bool]` | `None` (already present) | Existing parameter; reused for the threshold gate. **No change.** |

The reused existing per-action body parameters (`instances`, `abort`, `attempt_start`,
`container_mode`, `attempt_cleanup`, `ownership_spec`) are already in the `data_tool`
signature — they fan out to every VDB in the batch (FR-001 input description) and so need
no signature change.

Update the docstring of `data_tool` near line 109 and line 2047 to list the four new actions
in the docstring `action` enumeration. Update the human-readable docstring section to
include the `vdbIds` parameter and a short example for each new action.

The same vdbIds + confirmed contract applies to the self-service `vdb_tool` MCP name — the
file is single-function (one `data_tool` definition); the dual MCP names are produced by
toolset wiring, not duplicate function definitions, so no second branch set is needed.

## 6. Data Flow

```
MCP client
  │  call_tool("vdb_tool" | "data_tool", action="bulk_start", vdbIds=["v1","v2","v3"])
  ▼
FastMCP dispatch  ─────────────────────────────────────────────────────────────────►  data_tool()
                                                                                     @log_tool_execution
                                                                                       │
                                                                                       ▼
                                                          ┌─ elif action == 'bulk_start' ─┐
                                                          │  validate vdbIds              │
                                                          │  concurrency=_resolve_bulk_…  │
                                                          │  logger.info("bulk action…")  │
                                                          │  extra_body = {...}           │
                                                          │  async_to_sync(               │
                                                          │     _run_bulk_batch          │
                                                          │  )(action, ids, c, body, t)   │
                                                          └────────────────┬──────────────┘
                                                                           ▼
                                              ┌────── _run_bulk_batch (async) ────────┐
                                              │  sem = asyncio.Semaphore(c)            │
                                              │  await asyncio.gather([_one(v) ...])   │
                                              │     ┌─ _one(v) ─────────────────────┐  │
                                              │     │ async with sem:                │  │
                                              │     │  try:                          │  │
                                              │     │   resp = await client          │  │
                                              │     │       .make_request(POST,     │  │
                                              │     │        /vdbs/v/start, body)   │  │
                                              │     │   → debug log success         │  │
                                              │     │   return (v, resp)            │  │
                                              │     │  except Exception as exc:     │  │
                                              │     │   → debug log failure         │  │
                                              │     │   return (v, {_bulk_error:…}) │  │
                                              │     └───────────────────────────────┘  │
                                              │  aggregate succeeded / failed / jobs   │
                                              │  status = success | partial | failed   │
                                              │  return {status, total, succeeded,     │
                                              │           failed, jobs}                │
                                              └─────────────┬──────────────────────────┘
                                                            ▼
                                                logger.info("bulk action=… total=…")
                                                return aggregated dict
                                                            ▼
                                                       FastMCP response
                                                            ▼
                                                       MCP client
```

For `bulk_stop` / `bulk_disable` with `len(vdbIds) > 5` and no `confirmed`, the flow short-
circuits at the validation block — `_run_bulk_batch` is never called and zero DCT requests
are dispatched (FR-005 AC-1).

## 7. Concurrency Semantics

- **One event loop per bulk invocation.** `async_to_sync(_run_bulk_batch)(...)` creates a
  single loop, runs the entire batch, and tears it down. Per-VDB calls do **not** call
  `async_to_sync` themselves.
- **One `asyncio.Semaphore(C)` per batch.** Workers acquire/release via `async with`.
- **`asyncio.gather` with default `return_exceptions=False`.** Safe because workers never
  raise — they catch every `Exception` inside `_one`.
- **Order preservation.** `asyncio.gather` returns results in input order; aggregator
  iterates in input order; therefore `succeeded`, `failed`, and `jobs` lists preserve the
  caller's `vdbIds` order (FR-002 output note).
- **No retry stacking.** The wrapper does not retry. `DCTAPIClient.make_request` already
  retries with exponential backoff up to `DCT_MAX_RETRIES` (client.py:92–140); after that,
  it raises `DCTClientError`, which the worker catches and records as `failed`.
- **Concurrency cap clamp.** `[1, 50]`. Values outside the range or non-int → WARNING log
  + fallback to 5. (FR-002 AC-3, AC-4; vision risk: prevent DCT overload.)

## 8. Confirmation Gate — Threshold Logic

| Action | Threshold check fires? | Trigger |
|--------|------------------------|---------|
| `bulk_start` | No | Non-destructive (matches FR-005 description / SC7) |
| `bulk_enable` | No | Non-destructive (FR-005 AC-5) |
| `bulk_stop` | Yes | `len(vdbIds) > 5 and not confirmed` |
| `bulk_disable` | Yes | `len(vdbIds) > 5 and not confirmed` |

When the gate fires, the function returns immediately with the FR-005 envelope. Zero DCT
calls are dispatched. The user must re-call with `confirmed=True` and the same `vdbIds` for
the operation to proceed. This is the standard two-step pattern used throughout the codebase
(see CLAUDE.md "Confirmation System" section and `check_confirmation` at line 32).

**Why inline and not via `manual_confirmation.txt`** (vision risk #2): the path-pattern
matcher in `loader.py` keys off real DCT paths like `/vdbs/{vdbId}/stop`. The bulk operation
has no single real path — it fans out to N different paths. Encoding a threshold on a
synthetic `/vdbs/bulk_stop` path would require teaching the matcher about a special bulk
path and feeding `len(vdbIds)` into the level decision, which couples the loader to a
specific tool's input shape. Inline keeps the special-case logic next to the only place
that knows about it (the bulk action branch).

## 9. Logging

Per FR-007 and the project's logging rule (CLAUDE.md `tools/CLAUDE.md`, code-style.md):

- Module-level logger: the file currently uses `logger = logging.getLogger(__name__)` at
  line 11. **Defer rewriting that to `get_logger(__name__)`** to a separate refactor —
  changing it here is out of scope and would touch unrelated code (vision NG5 spirit).
  The new bulk branches use the existing module logger so behavior is identical.
- One INFO line **before** dispatch: `bulk action=<name> total=<N> concurrency=<C>`.
- One DEBUG line **per VDB**: `bulk action=<name> vdbId=<id> outcome=success` or
  `... outcome=failure error=<msg>`.
- One INFO line **after** aggregation: `bulk action=<name> total=<N> succeeded=<S>
  failed=<F> status=<final>`.
- At default INFO level, a single bulk call produces 2 log lines regardless of N (FR-007
  AC-1 / AC-2 verify content; DEBUG-level capture in tests verifies per-VDB lines).

## 10. Toolset Wiring (FR-006)

### `src/dct_mcp_server/config/toolsets/self_service.txt`

Append the following 4 lines at the end of the `# TOOL 1: vdb_tool - VDB` block (i.e. just
before the blank line that precedes `# TOOL 2: vdb_group_tool`):

```
POST|/vdbs/bulk_start|bulk_start
POST|/vdbs/bulk_stop|bulk_stop
POST|/vdbs/bulk_enable|bulk_enable
POST|/vdbs/bulk_disable|bulk_disable
```

These synthetic paths (`/vdbs/bulk_*`) exist only as logical action identifiers in the toolset
parser. The action handler intercepts the call and never resolves the synthetic path — it
fans out to per-VDB endpoints instead (FR-006 step 1 commentary).

### `src/dct_mcp_server/config/toolsets/continuous_data_admin.txt`

Append the **same 4 lines** at the end of the VDB Operations block inside `# TOOL 1:
data_tool` (i.e. immediately before the comment line `# VDB Group Operations` or whatever
section marker separates VDB ops from VDB group ops).

### Header counts

The existing toolset headers carry an aggregate "N Tools" count
(`# Self Service Toolset - 6 Tools`, `# Continuous Data Administrator Toolset - 22 Tools`).
The count refers to the **number of grouped tools** (e.g. `vdb_tool`, `vdb_group_tool`,
…), not the number of actions. We add 4 actions to existing tools and do not add new tools,
so **the header counts do not change**. Update only the per-tool comment count if one
exists (it does not for `self_service.txt`/`continuous_data_admin.txt` based on the file
inspection).

### Toolsets NOT to modify

- `reporting_insights.txt` — read-only, must remain free of bulk actions (FR-006 AC-3,
  test scenario 19).
- `platform_admin.txt` — out of scope.
- `self_service_provision.txt` — inherits `self_service` via `@inherit:self_service`,
  picks up the bulks automatically. **Do not add explicit entries** — duplicate inheritance
  would either be flagged by `loader.py` or silently merge, both bad outcomes.

## 11. Error Handling

Mapping vision risks and functional FR-003 / ERR-* to concrete code:

| Scenario | Handled by | Outcome |
|----------|-----------|---------|
| `vdbIds=None` or `[]` or non-list | Validation block at top of branch (FR-001 step 1) | `{"error": "vdbIds must be a non-empty list of VDB IDs"}`, zero DCT calls. |
| `vdbIds` contains a `None`/non-string | Same validation block | Same error response. |
| Per-VDB call raises `DCTClientError` (HTTP 4xx, 5xx after retries, timeout) | `_one()` `except Exception` block | Recorded into `failed`, batch continues. |
| Per-VDB call raises unexpected `RuntimeError` | Same `except Exception` block | Same — broad catch is deliberate and required by FR-003 description. |
| One VDB returns 200 but no `job.id` in response | Aggregator: appends to `succeeded`, omits from `jobs` | `succeeded` includes vdbId; `jobs` does not. |
| All VDBs fail | Aggregator: `succeeded=[]` → `status="failed"` | Single response, no exception, no abort. |
| `DCT_BULK_CONCURRENCY` parse error | `_resolve_bulk_concurrency` WARNING log | Fallback to 5. |
| `DCT_BULK_CONCURRENCY` very large | Same helper | Clamped to 50 + WARNING log. |
| Caller passes `confirmed=True` for a non-destructive bulk (`bulk_start` / `bulk_enable`) | Branch ignores `confirmed` | No error, batch runs. (EC-9.) |
| Caller hits a typo like `action="bulk_unknown"` | Falls through to the existing final `else: 'Unknown action: …'` branch (line ~4940 in `data_tool`) | Already returns `{"error": "Unknown action: ..."}`. Update that error message to include the four new action names. |

No `except Exception` outside the worker. The branch validation block uses explicit type
checks, not try/except. No `raise Exception` anywhere — only `DCTClientError` and `MCPError`
are valid raise targets per code-style.md, and the bulk wrapper never raises (always returns
a dict).

## 12. Backward Compatibility (FR-008)

- Existing `data_tool` actions `start_vdb`, `stop_vdb`, `enable_vdb`, `disable_vdb` (lines
  2810–2849) are **not** touched. The bulk branches are appended below.
- Existing `vdb_tool` actions `start`, `stop`, `enable`, `disable` from `self_service.txt`
  resolve to the same `data_tool` function via the OpenAPI generator's translation layer;
  they hit different action-name branches and are unaffected.
- Existing destructive single-VDB actions still consult `manual_confirmation.txt` via
  `check_confirmation` — no shared state with the new inline threshold.
- The `data_tool` signature adds one new optional kwarg (`vdbIds`); existing callers that
  do not pass it see no change in behavior or response shape.
- Test `test_single_vdb_start_unchanged` (scenario 18 in test plan) verifies the existing
  single-VDB path returns identical response bytes pre/post change against a mock.

## 13. Performance

- Wall-clock target: 20-VDB batch, `DCT_BULK_CONCURRENCY=5`, 200ms per-call latency →
  `(20 / 5) * 200ms + ~50ms overhead = ~850ms` (vision SC1 implied by G1).
- Memory: bounded by `concurrency × per-response-size`. Per response is small (~1 KB job
  payload), so worst-case in-flight memory at `concurrency=50` is ~50 KB. No streaming.
- No new allocation hot paths. `asyncio.Semaphore`, `asyncio.gather`, dict literals and a
  for-loop aggregator. JSON work happens inside `httpx`, identical to single-VDB calls.

## 14. Testability

The test file `tests/dlpxeco-13965-test.py` uses `pytest-asyncio` + `fastmcp.Client` over
stdio per the project test-infra. The DCT client is mocked at the import path
`dct_mcp_server.dct_client.client.DCTAPIClient.make_request` using `unittest.mock.patch`
applied in the fixture **before** the MCP server subprocess starts (per vision risk #7 and
test-infra.md). 19 scenarios cover:

1. All FR ACs (`bulk_start` success path, threshold gate, partial failure, all-failure,
   concurrency cap, env var clamping, response shape, logging, backward compat).
2. All edge cases (`vdbIds=[]`, `vdbIds="string"`, duplicate VDB IDs, unknown bulk action).
3. All quality rules with grep-based static checks where possible (QR-3, QR-4, QR-5).

Detailed scenarios are in `docs/DLPXECO-13965-test-plan.md`.

## 15. Open Questions

None. All ticket ambiguities were resolved in vision and functional specs:

- **Q**: Where does the function live? **A**: Existing `data_tool` in
  `dataset_endpoints_tool.py` — see vision C5.
- **Q**: How is threshold confirmation triggered? **A**: Inline in the action handler — see
  vision risk #2 and FR-005.
- **Q**: How is the event loop managed under fan-out? **A**: One loop per batch via
  `async_to_sync(_run_bulk_batch)` — see vision risk #3 and §7 above.
- **Q**: Are bulk actions visible in `reporting_insights`? **A**: No — see FR-006 AC-3 and
  test scenario 19.

## 16. Risks and Mitigations (Design-Time)

| Design risk | Mitigation |
|-------------|-----------|
| Future maintainer copy-pastes the bulk branch and forgets to wire the inline confirmation gate for a new destructive bulk. | All bulk branches share the same shape (FR-001 validation → optional FR-005 gate → fan-out → log → return). Document this contract as a comment at the top of the first bulk branch. |
| Adding a fifth bulk action later silently leaves `manual_confirmation.txt` out of sync. | Out of scope today (NG1). When a future ticket adds e.g. `bulk_delete`, that ticket can decide whether to keep inline-only or migrate the bulk-threshold concept into the path matcher. |
| The synthetic `/vdbs/bulk_*` paths in the toolset `.txt` files could be mistaken for real DCT endpoints by a future contributor reading the file. | Add a 1-line `#` comment above the 4 lines in each toolset file: `# Synthetic paths — action handler fans out to per-VDB endpoints.` |
| `data_tool` is already 4959 lines; adding 4 more branches + helpers grows it further. | Vision risk #6 marked this as Low/Low. Defer file split to a later refactor ticket. |
| `logging.getLogger(__name__)` at line 11 violates the `get_logger` rule. | Vision NG5 spirit — out of scope for this ticket. The new bulk code uses the existing module-level `logger` so we do not amplify the violation, and we do not introduce any new `logging.getLogger` call. |

## 17. Architecture Decision Records (inline)

**ADR-1 — One event loop per batch, not per VDB.**
Status: Accepted. Reason: per-VDB `asyncio.run` would serialize via the thread-per-call
fallback in `async_to_sync`, defeating the concurrency goal. One outer `async_to_sync`
plus inner `asyncio.gather` gives true parallelism with minimal change.

**ADR-2 — Inline threshold for confirmation, not `manual_confirmation.txt`.**
Status: Accepted. Reason: the path matcher is keyed on DCT path patterns, and the bulk
operation has no real path. See §8.

**ADR-3 — Same action names (`bulk_start` etc.) in both `self_service` and
`continuous_data_admin`.**
Status: Accepted. Reason: a single action-handler branch in `data_tool` always hits the
same DCT endpoints. Using identical names keeps the contract obvious and the test surface
unified. The asymmetry between `self_service.start` and `continuous_data_admin.start_vdb`
exists today only because the original generator chose differently; bulk actions standardize
on the more explicit `bulk_*` prefix.

**ADR-4 — Threshold value of `> 5` lives as a literal in code, not as a config knob.**
Status: Accepted. Reason: YAGNI — no ticket or stakeholder has asked for it to be tunable.
If we later want it tunable, lifting to env var `DCT_BULK_CONFIRMATION_THRESHOLD` is a
one-line change.

**ADR-5 — No deduplication of `vdbIds`.**
Status: Accepted. Reason: silent deduplication is surprising and would mask
double-submission bugs in the caller. If a caller passes the same VDB ID three times, they
get three DCT calls and three entries in the response. (EC-3.)

---
<!-- Spec cross-references:
     Sections 2-6  → FR-001, FR-002, FR-006, FR-008
     Section 7     → FR-002, vision risk #3
     Section 8     → FR-005, vision risk #2
     Section 9     → FR-007
     Section 10    → FR-006
     Section 11    → FR-003, FR-001, edge cases EC-1..EC-10, ERR-1..ERR-6
     Section 12    → FR-008
     Section 13    → Performance section in functional spec
     Section 14    → QR-10
     ADRs 1-5      → vision risks #2, #3, #6 and design decisions    -->
