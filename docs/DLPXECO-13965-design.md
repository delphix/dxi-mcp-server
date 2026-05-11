# Design: DLPXECO-13965

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13965
**Title**: Add bulk action support to vdb_tool for parallel start/stop/enable/disable
**Vision**: [docs/DLPXECO-13965-vision.md](DLPXECO-13965-vision.md) — G1–G5 / SC1–SC8
**Functional**: [docs/DLPXECO-13965-functional.md](DLPXECO-13965-functional.md) — FR-001 through FR-010

---

## Summary

This change adds four new bulk lifecycle actions — `bulk_start`, `bulk_stop`, `bulk_enable`, `bulk_disable` — to the DCT MCP server. Each action accepts a `vdbIds: list[str]` and fans out to the corresponding per-VDB DCT endpoint (`POST /vdbs/{vdbId}/start`, etc.) under an `asyncio.Semaphore`-bounded concurrency cap (default 5, overridable via `DCT_BULK_CONCURRENCY`). Outcomes are aggregated into a single deterministic response shape (`{status, total, succeeded, failed, jobs}`) so an AI assistant can drive fleet-wide lifecycle operations in one tool turn instead of N sequential turns.

The bulk actions are exposed as a **separate, new MCP tool named `vdb_bulk_tool`** (not as additional actions on `vdb_tool` / `data_tool`). The same tool name appears in both the `self_service` and `continuous_data_admin` toolsets — preserving the goal of cross-toolset symmetry from the prior design while sidestepping the OpenAPI generator's shadowing behaviour for `dataset_endpoints_tool.py`. `bulk_stop` and `bulk_disable` reuse the existing two-step confirmation pipeline whenever the list exceeds 5 VDBs; `bulk_start` and `bulk_enable` execute immediately. The existing single-VDB actions on `vdb_tool` and `data_tool` are completely untouched.

**Why a new tool and not added actions on `vdb_tool` / `data_tool`** (this is the key correction over the prior design — see "Generator-vs-pre-built decision" below): the OpenAPI generator emits `dataset_endpoints_tool.py` into `$TEMP/dct_mcp_tools/` on every server startup when running from a `pip` / `uvx` install. The loader's `tools/__init__.py:165–167` then skips the pre-built `dataset_endpoints_tool.py` entirely. There is no FastMCP-supported way to "extend" a tool function that another module has already registered with `@app.tool()`. The only mechanism that works identically in local-clone dev and `pip`-installed modes is to register a **new MCP tool with a non-colliding name** in a **new module the generator never produces**.

---

## Affected Components

Components touched (from `.claude/architecture.md` and the live source tree under `src/dct_mcp_server/`):

- [x] `src/dct_mcp_server/tools/vdb_bulk_endpoints_tool.py` — **NEW** pre-built grouped tool module containing the `vdb_bulk_tool` MCP tool. Houses all four bulk action handlers and the `_bulk_fanout` helper.
- [x] `src/dct_mcp_server/config/toolsets/self_service.txt` — append a new `# TOOL N: vdb_bulk_tool` section with four entries.
- [x] `src/dct_mcp_server/config/toolsets/continuous_data_admin.txt` — append a new `# TOOL N: vdb_bulk_tool` section with the same four entries.
- [x] `src/dct_mcp_server/config/mappings/manual_confirmation.txt` — append two rules for `bulk_stop` / `bulk_disable`.
- [x] `src/dct_mcp_server/config/loader.py` — add one entry `"vdb_bulk_tool": "vdb_bulk_endpoints_tool"` to the `TOOL_TO_MODULE` dict so the loader knows which module to load for the new tool name.
- [x] `tests/dlpxeco-13965-test.py` — new pytest file driving all 19 ticket scenarios via the `fastmcp` stdio client.

Components explicitly NOT touched (this is now strictly enforced — see decision section):

- `src/dct_mcp_server/tools/dataset_endpoints_tool.py` — **NOT modified.** The bulk handlers do NOT live here. The pre-existing `data_tool` / `vdb_tool` functions in this file are unchanged. Any change here would be shadowed by the generator in installed mode.
- `src/dct_mcp_server/tools/__init__.py` — **NOT modified.** The standard loader path correctly loads `vdb_bulk_endpoints_tool.py` because the generator never emits a module of that name; the `if module_name in registered_modules: continue` skip on line 165 only ever fires for modules the generator actually wrote.
- `src/dct_mcp_server/toolsgenerator/driver.py` — **MODIFIED (out-of-scope-but-bundled fix).** See "Out-of-scope-but-bundled fix" subsection under Architecture Changes for full justification. The original design intended no change to this file; the destructive-startup-sweep defect was discovered during the validate phase and bundled into this PR because the feature cannot ship without it.
- `src/dct_mcp_server/tools/core/tool_factory.py` — no changes (auto mode bulk support is descoped — see Open Questions #1).
- `src/dct_mcp_server/dct_client/client.py` — bulk wrapper reuses the existing `DCTAPIClient.make_request` retry/backoff layer; no second retry layer is added.
- `src/dct_mcp_server/config/toolsets/self_service_provision.txt`, `platform_admin.txt`, `reporting_insights.txt` — out of scope (per FR-006 and vision Non-Goals). Note: `self_service_provision.txt` inherits from `self_service.txt`, so `vdb_bulk_tool` becomes available there automatically; FR-006 does not require it but it is a free side effect of inheritance.

---

## Architecture Changes

### Pinned file paths (resolving Vision Risks #8 and #9)

The two open items called out in the vision Risks table are resolved here with verified file paths and verified action naming:

| Vision Risk | Resolution |
|---|---|
| Ticket references `tools/vdb_endpoints_tool.py` but the real module is `dataset_endpoints_tool.py` | **Pinned**: the existing single-VDB handlers live in `src/dct_mcp_server/tools/dataset_endpoints_tool.py` (when generation fails) and in the generator-produced `$TEMP/dct_mcp_tools/dataset_endpoints_tool.py` (when generation succeeds). The bulk handlers in this design do NOT touch either of those — they live in a NEW file `src/dct_mcp_server/tools/vdb_bulk_endpoints_tool.py`. The ticket's reference is superseded with a clearer path for the new code. |
| `continuous_data_admin` uses a merged `data_tool` (not `vdb_tool`); ambiguous bulk action registration | **Pinned**: cross-toolset symmetry is now achieved at the **tool-name level**: both toolsets expose the same tool, `vdb_bulk_tool`, with the same four actions. The LLM invokes `vdb_bulk_tool(action="bulk_start", vdbIds=[...])` regardless of which toolset is active. The existing `data_tool` vs `vdb_tool` naming asymmetry on the single-VDB side is irrelevant to this ticket. |

### Cross-toolset action-naming convention (FR-006)

The LLM-facing call shape is uniform across toolsets:

| Toolset | Tool name visible | Bulk action |
|---|---|---|
| `self_service` | `vdb_bulk_tool` | `bulk_start`, `bulk_stop`, `bulk_enable`, `bulk_disable` |
| `self_service_provision` | `vdb_bulk_tool` (inherited from `self_service`) | same four |
| `continuous_data_admin` | `vdb_bulk_tool` | same four |
| `platform_admin` | absent | none (no VDB lifecycle ops in this toolset today) |
| `reporting_insights` | absent | none (read-only toolset; FR-006 AC-3 explicitly excludes) |
| `auto` | absent until `enable_toolset(<name>)` | none — auto mode is out of scope (Open Questions #1) |

This is a deliberate departure from the existing per-endpoint asymmetry between `self_service.txt` (uses `start`) and `continuous_data_admin.txt` (uses `start_vdb`): bulk actions get a single, cross-toolset action-name set, and they live on their own tool. The LLM never has to know which toolset is active to formulate the bulk call.

### Generator-vs-pre-built decision (corrected — Option B)

This is the decision the prior design got wrong. The corrected reasoning, grounded in the live code:

**Evidence (verified against `src/dct_mcp_server/tools/__init__.py:103–184`):**

1. **Shadowing in installed mode is real.** Line 109 sets `temp_tools_dir` only when `'site-packages' in __file__`. For `uvx` / `pip install` (the recommended install per `CLAUDE.md`), this is true. `main.py` then calls `generate_tools_from_openapi()`, which writes `$TEMP/dct_mcp_tools/dataset_endpoints_tool.py`. Lines 113–146 register that generated module. Lines 165–167 hard-skip the pre-built `dataset_endpoints_tool.py`: `if module_name in registered_modules: continue`. The pre-built bulk handlers (if we placed them there) would never load.

2. **FastMCP does not support "extending" an already-registered tool.** Both modules would have to export `@app.tool() def vdb_tool(...)` (or `data_tool`) to extend the dispatch. A second `@app.tool()` registration with the same tool name fails. There is no documented FastMCP API to add actions to an existing tool function from another module. The prior design's "extends it" handwaved a mechanism that does not exist.

3. **Local-clone dev hides the bug.** When running from `./start_mcp_server_uv.sh`, `__file__` is not in site-packages, so the temp-dir branch at line 109 is skipped. The pre-built module loads as a fallback (line 148-178). This is why the prior design's mechanical evals passed but the production install would silently lose bulk actions.

**Decision — Option B (chosen):**

Implement the bulk handlers in a **NEW pre-built module** at `src/dct_mcp_server/tools/vdb_bulk_endpoints_tool.py` that registers a **SEPARATE MCP tool with a non-colliding name** (`vdb_bulk_tool`):

| Concern | Resolution |
|---|---|
| Generator shadowing | The generator's path-to-module mapper (`driver.py:_get_module_for_path`) routes `/vdbs/...` paths into `dataset_endpoints_tool.py`. It never emits a file called `vdb_bulk_endpoints_tool.py` because no upstream OpenAPI path produces that module name. Therefore the loader's "generated wins" rule cannot apply to this module — it is never in the temp dir. |
| FastMCP tool-name collision | `vdb_bulk_tool` is a distinct tool name from `vdb_tool` and `data_tool`. No re-registration conflict. |
| `pip` / `uvx` install behaviour | Identical to local-clone dev. The loader's pre-built scan (line 148-178) loads `vdb_bulk_endpoints_tool.py` from the package directory. The generator's temp dir does not contain this file. No skip ever fires. |
| Toolset visibility | The toolset `.txt` files declare the new tool with a `# TOOL N: vdb_bulk_tool` section and four entries. The loader's `TOOL_TO_MODULE` dict maps `vdb_bulk_tool → vdb_bulk_endpoints_tool` so only this module is loaded when a toolset needs it. |

**Sentinel-path entries in toolset `.txt` files:** the four lines added under `# TOOL N: vdb_bulk_tool` use paths like `POST|/vdbs/bulk_start|bulk_start`. These paths are intentionally NOT in the DCT OpenAPI spec — the spec only knows per-VDB paths like `/vdbs/{vdbId}/start`. The generator hits its "path not found in spec" branch at `driver.py:674–697` and appends to `SKIPPED_ENTRIES`. **This is informational, not load-bearing**: even if the generator did NOT skip these entries, it would emit them into `dataset_endpoints_tool.py`, which is a different module from `vdb_bulk_endpoints_tool.py` — so there is no shadowing risk on the new module regardless. The `SKIPPED_ENTRIES` log will still be emitted (we cannot suppress it without modifying `driver.py`, which we are not doing); it is documented as informational in the "Platform Behavior Notes" section. The `MODULES_WITH_PREBUILT_EXTENSIONS` constant from the prior design is **dropped**.

**Decisions table (final):**

| Concern | Decision |
|---|---|
| Where do bulk action handlers live? | NEW file `src/dct_mcp_server/tools/vdb_bulk_endpoints_tool.py`, registering MCP tool `vdb_bulk_tool`. |
| How do they coexist with generated tools? | They don't have to. The new module's name is not produced by the generator, so `tools/__init__.py` line 165 never skips it. No changes to the loader are required. |
| What about `self_service`'s `vdb_tool`? | Unchanged. `vdb_tool` continues to expose its 17 single-VDB actions, served by the generator's `dataset_endpoints_tool.py` (or the pre-built fallback). The bulk actions are a separate tool. |
| Auto mode (`tool_factory.py`)? | Out of scope for this ticket. Bulk actions are not exposed via auto mode. Tracked as a follow-up (see Open Questions #1). |
| `tool_factory.py` shadowing of pre-built? | Auto mode does not load pre-built modules at all — it generates tools at runtime per `enable_toolset` call. Out of scope per above. |

### Source Files to Modify

| File | Change | Lines (approx.) |
|---|---|---|
| `src/dct_mcp_server/tools/vdb_bulk_endpoints_tool.py` | **NEW FILE.** Contains: (a) module-level `client` and `logger` initialised as in other `*_endpoints_tool.py` files; (b) `_bulk_fanout(method, path_template, vdbIds, dct_client)` async helper using `asyncio.Semaphore(int(os.environ.get("DCT_BULK_CONCURRENCY", 5)))` + per-task acquire + `asyncio.gather(*tasks, return_exceptions=True)`; (c) `_resolve_confirmation(action, vdbIds, confirmed)` helper that calls `get_confirmation_for_operation("POST", f"/vdbs/{action}")` and returns the confirmation envelope when `len(vdbIds) > 5` and `not confirmed`; (d) `vdb_bulk_tool(action, vdbIds, confirmed=False)` function decorated with `@app.tool()` and `@log_tool_execution`, dispatching on the four action names and returning the aggregate; (e) `register_tools(app, dct_client)` entry point following the existing pre-built-module contract. | +180–220 lines |
| `src/dct_mcp_server/config/toolsets/self_service.txt` | Append a new section header `# TOOL N: vdb_bulk_tool - VDB Bulk Lifecycle` and four entries: `POST\|/vdbs/bulk_start\|bulk_start`, `POST\|/vdbs/bulk_stop\|bulk_stop`, `POST\|/vdbs/bulk_enable\|bulk_enable`, `POST\|/vdbs/bulk_disable\|bulk_disable`. Update the file header comment from `6 Tools` to `7 Tools`. Add a one-line comment near the section noting the paths are sentinel and the generator's `SKIPPED_ENTRIES` warning for them is informational. | +6 lines |
| `src/dct_mcp_server/config/toolsets/continuous_data_admin.txt` | Append the same `# TOOL N: vdb_bulk_tool` section and four entries. Update the file header from `22 Tools` to `23 Tools`. | +6 lines |
| `src/dct_mcp_server/config/loader.py` | Add one entry to `TOOL_TO_MODULE` (between the existing `"data_tool"` and `"snapshot_bookmark_tool"` lines): `"vdb_bulk_tool": "vdb_bulk_endpoints_tool",`. No other changes. | +1 line |
| `src/dct_mcp_server/config/mappings/manual_confirmation.txt` | Append two rules: `POST\|/vdbs/bulk_stop\|manual\|Stopping {count} VDBs will interrupt service — confirm to proceed.` and `POST\|/vdbs/bulk_disable\|manual\|Disabling {count} VDBs will take them offline — confirm to proceed.` The rule itself is unconditional in the file; the handler decides whether to consult it based on `len(vdbIds) > 5`. | +2 lines |
| `tests/dlpxeco-13965-test.py` | New pytest module covering all 19 ticket scenarios (success / partial / all-failed / concurrency / confirmation gating / toolset registration / single-VDB regression). Uses `pytest-asyncio` + `fastmcp` stdio client. Mocks at `DCTAPIClient.make_request` level. All bulk-action calls target the new tool: `vdb_bulk_tool(action="bulk_start", vdbIds=[...])`. | +600–800 lines |
| `src/dct_mcp_server/toolsgenerator/driver.py` | **MODIFIED (out-of-scope-but-bundled fix; see subsection below).** Pre-existing destructive cleanup sweep in `generate_tools_from_openapi()` deleted every `*_tool.py` file under `src/dct_mcp_server/tools/` at server startup in local-clone runs, including pre-built modules whose action paths are absent from the OpenAPI spec (such as the new `vdb_bulk_endpoints_tool.py`). Fix (Option D — smart deletion): compute `module_tools` BEFORE the cleanup loop; derive `target_filenames = {f"{m}_tool.py" for m in module_tools}`; filter the deletion glob to skip basenames not in `target_filenames`; log one DEBUG line per preserved file and an INFO summary (`deleted_count` vs `preserved_count`). Pure subtraction from prior behaviour — files the generator regenerates are still deleted-then-rewritten as before. | +19 / -7 |

### New Files (if any)

- `src/dct_mcp_server/tools/vdb_bulk_endpoints_tool.py` — see row 1 of the table above.
- `tests/dlpxeco-13965-test.py` — see row 6 of the table above.

<!-- check-structure.sh cross-references only ### Source Files to Modify (table rows). The new files are also listed there for that reason; this ### New Files section is informational. -->

### Out-of-scope-but-bundled fix: toolsgenerator/driver.py startup cleanup sweep

**Defect discovered during the validate phase.** The validate-phase smoke test could not register `vdb_bulk_tool` against the live DCT instance because the server's startup tool-generation sweep was destructively deleting every `*_tool.py` file from the in-tree `src/dct_mcp_server/tools/` directory before the pre-built-module registration step ran. The new `vdb_bulk_endpoints_tool.py` was wiped with no replacement because its sentinel paths (`/vdbs/bulk_start`, `/vdbs/bulk_stop`, `/vdbs/bulk_enable`, `/vdbs/bulk_disable`) are deliberately not in the OpenAPI spec — the generator therefore had no module to regenerate in its place.

**Pre-existing scope.** The defect predates DLPXECO-13965. It would have blocked ANY future pre-built module whose action paths fell outside OpenAPI coverage (e.g. follow-up tickets for `vdb_group_bulk_tool`, `dsource_bulk_tool`, etc., per Open Questions #6). It is local-clone-only — `pip` and `uvx` installs are unaffected because the cleanup sweep runs only against the writable tools directory inside a checked-out repo.

**Why this PR.** The feature could not ship without fixing this defect. Splitting it into a separate PR would (a) block this PR indefinitely, and (b) deliver a fix with no driving test case. Bundling it here is the pragmatic choice; the scope expansion is documented explicitly so reviewers understand the diff includes one file outside the original design scope.

**Fix details (Option D — smart deletion, approved by user).** In `src/dct_mcp_server/toolsgenerator/driver.py` inside `generate_tools_from_openapi()`:

1. Move the `module_tools` mapping computation above the cleanup sweep (was at line ~530 originally; now at line ~510).
2. Derive `target_filenames = {f"{m}_tool.py" for m in module_tools}` — the set of files this run is about to (re)write.
3. In the deletion loop over `existing_tools`, skip any file whose basename is not in `target_filenames`. Log `logger.debug("Preserving pre-built tool file outside generator coverage: ...")` per preserved file. Track `deleted_count` and `preserved_count`.
4. Replace the original cleanup INFO log with one summarising both: `Cleaned up N existing tool files (preserved M outside generator coverage)`.

**Behavioural contract.**

- Files the generator regenerates this run: still deleted, then rewritten — no change in observable behaviour.
- Pre-built modules outside generator coverage (the new bulk module and any future equivalent): preserved on disk; `register_all_tools()` finds and loads them normally.
- No new env var, no new code path for callers, no change to the public registration contract.
- Verification: `python -c "import py_compile; py_compile.compile('src/dct_mcp_server/toolsgenerator/driver.py', doraise=True)"` passes; the full mock pytest suite (`tests/dlpxeco-13965-test.py`, 22 cases) is unchanged and still PASSes; the validate-phase smoke harness now exercises the corrected startup behaviour.

**Risk.** Low. The fix is a strict subtraction of unwanted deletions — it does not add any new file writes, network calls, or runtime behaviour for the regenerated modules. The only observable side-effect for operators is one additional INFO summary log line at startup.

### Concurrency model

- Semaphore is **per-invocation**, constructed inside `_bulk_fanout` from `int(os.environ.get("DCT_BULK_CONCURRENCY", 5))`. Invalid values (≤ 0, non-integer) fall back to 5 with a single WARNING log. Reading per-invocation (not at module import) lets the env var be changed between calls during tests.
- Tasks are scheduled with `asyncio.create_task(_one(vdbId))` inside a `for` loop, and each task acquires the semaphore as its first statement. There is no unbounded `asyncio.gather(*tasks)` without the semaphore guard — the cap is enforced inside each task.
- Results are collected with `asyncio.gather(*tasks, return_exceptions=True)` so a single per-VDB exception does not abort the batch.
- The bulk wrapper does NOT add a retry layer; per-VDB calls go through `DCTAPIClient.make_request`, which already implements backoff up to `DCT_MAX_RETRIES`.

### Response shape (FR-007 contract)

```python
{
    "status": "success" | "partial_success" | "failed",
    "total": int,
    "succeeded": list[str],                                    # vdbIds
    "failed":    list[dict],                                   # each: {"vdbId": str, "error": str}
    "jobs":      list[dict],                                   # each: {"vdbId": str, "jobId": str}
}
```

Confirmation-required envelope (FR-002 / FR-004):

```python
{
    "status": "confirmation_required",
    "confirmation_level": "manual",
    "confirmation_message": str,    # rule template with {count} substituted
    "action": "bulk_stop" | "bulk_disable",
    "vdbIds": list[str],
}
```

(Key name `confirmation_message` matches the existing `dataset_endpoints_tool.py:check_confirmation` envelope at line 56-65 — uniformity with existing confirmation responses.)

### Confirmation gate sequencing (handler flow)

1. `vdb_bulk_tool(action, vdbIds, confirmed=False)` is invoked by FastMCP.
2. **Validate first** (FR-009): unknown action → MCPError; non-list-of-str `vdbIds` → MCPError; empty list → MCPError. Zero DCT calls made.
3. **Check confirmation gate**: for `bulk_stop` / `bulk_disable` only, if `len(vdbIds) > 5` and `not confirmed`, look up the rule from `manual_confirmation.txt` via `get_confirmation_for_operation("POST", f"/vdbs/{action}")` (resolves to `/vdbs/bulk_stop` or `/vdbs/bulk_disable`). Format the message with `format_map({"count": len(vdbIds)})`. Return the confirmation envelope. **Critical**: this happens BEFORE any task spawning. (FR-002 AC-1 / FR-004 AC-1 assert `mock_dct.call_count == 0`.)
4. **Fan out**: call `await _bulk_fanout("POST", "/vdbs/{vdbId}/start", vdbIds, dct_client)` (or `/stop`, `/enable`, `/disable`). The path-template's `{vdbId}` placeholder is substituted per task.
5. **Aggregate**: build the `{status, total, succeeded, failed, jobs}` dict. `status = "success"` if all succeeded, `"failed"` if all failed, `"partial_success"` otherwise.
6. **Log** (FR-008): one INFO line summarising the fan-out, one DEBUG line per VDB outcome.
7. **Return** the aggregate.

### Logging contract (FR-008)

```python
from dct_mcp_server.core.logging import get_logger
logger = get_logger(__name__)

# After aggregation:
logger.info("bulk_%s completed: total=%d succeeded=%d failed=%d",
            action_short_name, total, len(succeeded), len(failed))
for vdbId in succeeded:
    logger.debug("bulk_%s vdb=%s status=2xx", action_short_name, vdbId)
for entry in failed:
    logger.debug("bulk_%s vdb=%s status=error error=%s",
                 action_short_name, entry["vdbId"], entry["error"])
```

The `@log_tool_execution` decorator on `vdb_bulk_tool` continues to wrap the call as today; no duplicate invocation log is added inside the handler.

---

## Platform Behavior Notes

### Per-toolset visibility

| Toolset | Tools visible (relevant subset) | `vdb_bulk_tool` actions |
|---|---|---|
| `self_service` | `vdb_tool` (existing, unchanged), `vdb_bulk_tool` (new) | all four bulk actions |
| `self_service_provision` | inherits `self_service` tools, including `vdb_bulk_tool` | all four bulk actions (free via inheritance) |
| `continuous_data_admin` | `data_tool` (existing, unchanged), `vdb_bulk_tool` (new) | all four bulk actions |
| `platform_admin` | no VDB lifecycle tools | none — `vdb_bulk_tool` is not declared in this toolset |
| `reporting_insights` | `data_tool` (read-only operations only) | none — `vdb_bulk_tool` is not declared (explicitly excluded by FR-006 AC-3) |
| `auto` | 5 meta-tools until `enable_toolset(<name>)` | depends on enabled toolset (currently no auto-mode support — see Open Questions #1) |

### Generator startup behaviour (informational)

After this change, every server startup that runs `generate_tools_from_openapi()` against a live DCT instance will log four `SKIPPED_ENTRIES` warnings of the form:

```
ERROR: Tool generation skipped 4 toolset entries due to method/path mismatches with the OpenAPI spec...
  - vdb_bulk_tool.bulk_start:   POST /vdbs/bulk_start   — path not found in OpenAPI spec
  - vdb_bulk_tool.bulk_stop:    POST /vdbs/bulk_stop    — path not found in OpenAPI spec
  - vdb_bulk_tool.bulk_enable:  POST /vdbs/bulk_enable  — path not found in OpenAPI spec
  - vdb_bulk_tool.bulk_disable: POST /vdbs/bulk_disable — path not found in OpenAPI spec
```

**This is informational, not load-bearing.** The bulk actions are served by `vdb_bulk_endpoints_tool.py`, a separate module the generator never emits. The toolset `.txt` entries are present primarily so the loader's `get_tools_for_toolset` and `get_modules_for_toolset` machinery discovers `vdb_bulk_tool` and resolves it to `vdb_bulk_endpoints_tool` via the new `TOOL_TO_MODULE` entry. The generator's attempt to handle them is a no-op for our purposes. The implementation will add a `# NOTE: sentinel paths — handled by pre-built module vdb_bulk_endpoints_tool; generator SKIPPED_ENTRIES warning for these is expected and informational` comment immediately above the four lines in each toolset file so future maintainers do not "fix" them by changing the paths to something the spec recognises.

### Confirmation rule lookup

`get_confirmation_for_operation("POST", "/vdbs/bulk_stop")` will match the rule `POST|/vdbs/bulk_stop|manual|...` and return `{"level": "manual", "message": "..."}`. The handler substitutes `{count}` from the rule template with `format_map({"count": N})`. The substitution mechanism is the same `_SafeDict`-based one used elsewhere in `manual_confirmation.txt` (verified in `driver.py:357`). Path-parameter resolution is trivial here because `/vdbs/bulk_stop` and `/vdbs/bulk_disable` have no `{...}` placeholders — the path matches the rule pattern exactly.

### Backward compatibility

- The existing `start_vdb` / `stop_vdb` / `enable_vdb` / `disable_vdb` actions in `data_tool` (used by `continuous_data_admin`) and `start` / `stop` / `enable` / `disable` actions in `vdb_tool` (used by `self_service`) are untouched. Their dispatch paths in `dataset_endpoints_tool.py` are not modified. No code is reused, copied, or shimmed into the new module from the existing single-VDB handlers — each bulk action makes its own direct calls to the per-VDB DCT endpoints via `dct_client.make_request`.
- FR-010 / SC-8 regression tests (`tests/dlpxeco-13965-test.py::test_single_vdb_start_unchanged`) assert the existing single-VDB response shape is preserved when invoked with `vdbId="vdb-1"` against both `vdb_tool` and `data_tool`.
- The new `vdb_bulk_tool` adds one tool name to each affected toolset. Listing the available tools (`list_tools()` over MCP) will show one additional entry on `self_service`, `self_service_provision`, and `continuous_data_admin`. No existing tool name changes. No existing action name changes. No env var changes (with the exception of the new `DCT_BULK_CONCURRENCY` which is purely additive and has a default).

---

## Version Compatibility

| Concern | Position |
|---|---|
| Python version | 3.11+ (project minimum, per `CLAUDE.md`). `asyncio.Semaphore`, `asyncio.gather(return_exceptions=True)`, and type hints are all available. |
| `fastmcp` | The version pinned in `requirements.txt` already supports `@app.tool()` decoration and stdio transport (verified via existing tool registration in `tools/__init__.py`). No upgrade required. |
| `httpx` | The existing `DCTAPIClient` is async and safely usable concurrently. No change. |
| `pytest-asyncio` | Required for the new test file. Must be in `requirements.txt` (or `requirements-test.txt`); confirm during the implement phase that the dependency is present, add if not. |
| DCT API version | No DCT-side change is required — the four bulk actions are pure client-side fan-out over existing per-VDB endpoints `POST /vdbs/{vdbId}/start` etc. that have been stable across DCT versions. |
| Backward compatibility (config files) | New lines in `self_service.txt`, `continuous_data_admin.txt`, `manual_confirmation.txt`, and one new entry in `loader.py:TOOL_TO_MODULE` are additive; existing actions, rules, and mappings are not modified or reordered. Older builds reading these files would simply not invoke the new tool. |
| Backward compatibility (runtime) | An older client that never sends `bulk_*` actions sees no behaviour change. A newer client that sends `vdb_bulk_tool(action="bulk_start")` to an older server would receive a "tool not found" error — acceptable per the project's grouped-tool action dispatch model. |

---

## Open Questions / Risks

1. **Auto mode (`tool_factory.py`) bulk support is descoped.** Auto mode generates tools at runtime per `enable_toolset` and never reads `vdb_bulk_endpoints_tool.py`. With this design, an auto-mode user who enables `self_service` will see all 17 existing `vdb_tool` actions but NOT `vdb_bulk_tool`. This is a deliberate scope reduction in this ticket. Follow-up: extend `tool_factory.py`'s closure-based generation to additionally call `register_tools(app, dct_client)` on pre-built modules whose tool names are in the enabled toolset's `tools` list but which the closure-based generator does not produce. Tracked separately.

2. **`docs/api-external.yaml` bundled fallback does not exist.** `tool_factory.py:_load_bundled_spec()` references `docs/api-external.yaml`, which is not in the repo. If a CI environment ever runs without `DCT_BASE_URL`, tool generation will fail silently and fall through to the pre-built modules — in which case `vdb_bulk_endpoints_tool.py` still loads correctly (the new module does not depend on generation succeeding for any other module). This is unrelated to the bulk-action change and is noted only to document the discovered state of the project. Not a blocker.

3. **Concurrency stress beyond the configured cap is unverified.** The test for FR-005 AC-1 (scenario 6) uses an instrumented in-flight counter and asserts max ≤ cap. We do not test scaling beyond N=20 because (a) the AC says so, and (b) `DCTAPIClient` already handles backoff for the underlying calls. If a real-world caller passes N=1000, the bulk wrapper will work, but we have no benchmark. Documented in vision Performance Considerations; accepted risk.

4. **`SKIPPED_ENTRIES` startup warning is noisy in logs.** Every startup with a live DCT instance will emit 4 ERROR-level lines from `generate_tools_from_openapi`. Operators may interpret this as a misconfiguration. Mitigation: the inline comment in each toolset `.txt` file documents that these warnings are expected. A separate ticket could either (a) downgrade the log to INFO when the path matches a sentinel pattern, or (b) introduce a `pre_built_only` flag in the toolset format. Out of scope here.

5. **Confirmation message rendering with `{count}`.** `manual_confirmation.txt` uses `{name}`-style placeholders elsewhere. Our new rule uses `{count}`, which is not pre-existing in the file. The substitution is via `_SafeDict.format_map`; missing keys render as the literal `{key}`. Passing `context={"count": N}` produces the expected substitution. Test scenario 8 asserts the substituted message contains the literal string of the count.

6. **The new module duplicates `_bulk_fanout` rather than reusing a utility.** A future ticket could lift `_bulk_fanout` and the validation helpers into a shared module (e.g. `src/dct_mcp_server/tools/_bulk_utils.py`) once a second bulk-tool module is needed (e.g. `vdb_group_bulk_tool`, `dsource_bulk_tool`). For now, keeping it co-located in `vdb_bulk_endpoints_tool.py` is simpler and avoids speculative abstraction. The vision's Non-Goals explicitly defer those tools to a separate ticket.

---

## Acceptance Criteria

These mirror the Jira ticket's "Required Test Scenarios" and the functional spec's FR-* acceptance criteria. Each is verifiable in `tests/dlpxeco-13965-test.py`. **All bulk-action calls in the tests target the new `vdb_bulk_tool` MCP tool, not `vdb_tool` / `data_tool`.**

- [ ] **AC-1 (FR-001 AC-1; ticket scenario 1)** — `vdb_bulk_tool(action="bulk_start", vdbIds=[3 ids])` with all DCT calls returning 200 produces `{status: "success", total: 3, succeeded: [3 ids], failed: [], jobs: [3 entries]}`.
- [ ] **AC-2 (FR-001 AC-2; ticket scenario 2)** — Partial failure (2 success + 1 5xx) produces `status: "partial_success"` with both `succeeded` and `failed` populated.
- [ ] **AC-3 (FR-001 AC-3; ticket scenario 3)** — All 5xx produces `status: "failed"`, `succeeded == []`, `failed.length == total`.
- [ ] **AC-4 (FR-001 AC-4; ticket scenario 4)** — `vdbIds=[]` raises MCPError; `mock_dct.call_count == 0`.
- [ ] **AC-5 (FR-001 AC-5; ticket scenario 5)** — Single-element list executes fan-out with `total == 1`.
- [ ] **AC-6 (FR-005 AC-1; ticket scenario 6)** — `DCT_BULK_CONCURRENCY=3` with 20 vdbIds: instrumented in-flight counter ≤ 3 at all times; all 20 complete.
- [ ] **AC-7 (FR-002 AC-1; ticket scenario 7)** — `vdb_bulk_tool(action="bulk_stop", vdbIds=[6 ids])` without `confirmed` → `confirmation_required` envelope; `mock_dct.call_count == 0`.
- [ ] **AC-8 (FR-002 AC-2; ticket scenario 8)** — Same 6 vdbIds with `confirmed=True` executes; `mock_dct.call_count == 6`; confirmation message previously contained `"6"`.
- [ ] **AC-9 (FR-002 AC-3; ticket scenario 9)** — `vdb_bulk_tool(action="bulk_stop", vdbIds=[3 ids])` (under threshold) executes immediately; no confirmation envelope.
- [ ] **AC-10 (FR-004 AC-1; ticket scenario 10)** — `vdb_bulk_tool(action="bulk_disable", vdbIds=[6 ids])` without `confirmed` → confirmation envelope; `mock_dct.call_count == 0`.
- [ ] **AC-11 (FR-003 AC-1; ticket scenario 11)** — `vdb_bulk_tool(action="bulk_enable", vdbIds=[6 ids])` executes immediately, no confirmation gate, response shape matches FR-001 AC-1.
- [ ] **AC-12 (FR-009 AC-1; ticket scenario 12)** — `vdb_bulk_tool(action="bulk_unknown", ...)` → MCPError; `mock_dct.call_count == 0`.
- [ ] **AC-13 (FR-009 AC-2; ticket scenario 13)** — `vdbIds="vdb-1"` (string, not list) → MCPError; `mock_dct.call_count == 0`.
- [ ] **AC-14 (FR-007 AC-1; ticket scenario 14)** — Response keys are exactly `{status, total, succeeded, failed, jobs}` — set-equality assertion.
- [ ] **AC-15 (FR-008 AC-1; ticket scenario 15)** — Exactly 1 INFO record AND 3 DEBUG records captured for a 3-VDB `bulk_start` via `caplog`.
- [ ] **AC-16 (FR-010 AC-1; ticket scenario 16)** — Single-VDB regression: `data_tool(action="start_vdb", vdbId="vdb-1")` returns the same shape as before this change. Same for `vdb_tool(action="start", vdbId="vdb-1")`. Confirms the existing tools are untouched.
- [ ] **AC-17 (FR-006 AC-1; ticket scenario 17)** — Server spawned with `DCT_TOOLSET=self_service`: `vdb_bulk_tool` is listed and its four actions (`bulk_start`, `bulk_stop`, `bulk_enable`, `bulk_disable`) are discoverable.
- [ ] **AC-18 (FR-006 AC-2; ticket scenario 18)** — Server spawned with `DCT_TOOLSET=continuous_data_admin`: `vdb_bulk_tool` is listed with the same four actions. The cross-toolset symmetry is satisfied at the tool-name level: the LLM invokes `vdb_bulk_tool(action="bulk_start", ...)` identically in both toolsets.
- [ ] **AC-19 (FR-006 AC-3; ticket scenario 19)** — Server spawned with `DCT_TOOLSET=reporting_insights`: `vdb_bulk_tool` is NOT present in the tool list.

---

<!-- Cross-reference:
     - FR-001..FR-010 from docs/DLPXECO-13965-functional.md
     - G1..G5 / SC1..SC8 from docs/DLPXECO-13965-vision.md
     - Vision Risks #8 (file path mismatch) and #9 (data_tool vs vdb_tool naming in continuous_data_admin) are resolved in "Pinned file paths" via the new tool approach.
     - Prior design's "Path D" shadowing fix is rejected; replaced with Option B (new module + new tool name). Evidence drawn from src/dct_mcp_server/tools/__init__.py:103-184, in particular the temp_tools_dir = ... if 'site-packages' in __file__ branch at line 109 and the if module_name in registered_modules: continue skip at lines 165-167.
     - The MODULES_WITH_PREBUILT_EXTENSIONS constant proposed in the prior design is dropped — no change to tools/__init__.py.
     - The SKIPPED_ENTRIES log line for the sentinel paths is downgraded from "expected and load-bearing" to "informational" — its presence/absence does not affect correctness because the bulk handlers live in a separate, generator-untouched module.
     - Test plan in docs/DLPXECO-13965-test-plan.md derives from these 19 ACs and will be updated to reflect the new tool name vdb_bulk_tool.
-->
