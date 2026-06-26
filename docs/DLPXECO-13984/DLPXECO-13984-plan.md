# Implementation Tasks: DLPXECO-13984

**Spec**: docs/DLPXECO-13984/DLPXECO-13984-functional.md
**Design**: docs/DLPXECO-13984/DLPXECO-13984-design.md

---

## Task 1: Confirmation Resolver  [parallel][model:haiku]

### Description
Creates `src/dct_mcp_server/tools/core/confirmation_resolver.py` — a standalone, stateless
module that wraps the existing `get_confirmation_for_operation()` from `loader.py` and adds
support for `retention_check:N` and `policy_impact_check:N` conditional rule evaluation
against caller-supplied `context`. This must be created first because the `dynamic.py`
module (Task 3) imports from it.

### Spec References
- FR-004 (AC-1 through AC-5): Confirmation gate resolver for 2-tool architecture

### Sub-tasks (TDD)
- [ ] **RED**: Define expected interface: `check_confirmation(method, path, context) -> dict`
  with keys `requires_confirmation`, `confirmation_level`, `message_template`
- [ ] **GREEN**: Implement `confirmation_resolver.py` wrapping `get_confirmation_for_operation()`
  from `config/loader.py`; parse conditional rule level strings (`retention_check:N`,
  `policy_impact_check:N`); evaluate against `context` dict values
- [ ] **REFACTOR**: Add type hints, docstring, ensure no side effects

### Depends On
- None

### Acceptance Criteria
- [ ] `check_confirmation("POST", "/vdbs/vdb-123/delete", {})` → `requires_confirmation=True`, `confirmation_level="manual"`
- [ ] `check_confirmation("GET", "/vdbs/search", {})` → `requires_confirmation=False`
- [ ] `retention_check:7` with `context={"retention_days": 3}` → `requires_confirmation=True`
- [ ] `retention_check:7` with `context={"retention_days": 30}` → `requires_confirmation=False`
- [ ] Unknown path returns `requires_confirmation=False` without error

---

## Task 2: OpenAPI Spec Cache Subsystem  [parallel][model:sonnet]

### Description
Creates `src/dct_mcp_server/tools/core/spec_cache.py` — a new, independent spec download
and disk-cache subsystem for `dynamic` mode. It is completely separate from the existing
`tool_factory.py` cache (different global, different purpose). Exposes `load_and_cache_spec()`
which returns the parsed spec dict for storage on `app.state`. Also provides `get_cached_spec()`
for tool access at request time.

Key decisions:
- Bundled fallback: `Path(__file__).parent.parent.parent.parent / "docs" / "api-external.yaml"`
  (same pattern as tool_factory.py)
- Download uses `requests` library matching `driver.py` / `tool_factory.py` convention
- Cache sidecar: `.cache-meta.json` adjacent to the cache file
- Single retry on download failure (not the full `DCT_MAX_RETRIES` chain)
- Must respect `DCT_VERIFY_SSL` and `DCT_TIMEOUT`
- Non-fatal if download fails (uses bundled spec + logs WARNING)
- Fatal (`MCPError("SPEC_LOAD_FAILED")`) only if bundled spec is also missing/unparseable

### Spec References
- FR-001 (AC-1 through AC-5): OpenAPI spec download and cache subsystem

### Sub-tasks (TDD)
- [ ] **RED**: Define interface: `load_and_cache_spec() -> dict`, `get_cached_spec() -> dict|None`,
  `clear_spec_cache()` — verify module can be imported standalone
- [ ] **GREEN**: Implement download path with age-check, YAML validation, disk write,
  `.cache-meta.json` sidecar, and in-memory cache; implement bundled fallback path;
  implement `MCPError` raise when neither source works
- [ ] **REFACTOR**: Extract `_read_cache_meta()`, `_write_cache_meta()`, `_validate_spec()` helpers;
  ensure all log messages use `get_logger(__name__)`

### Depends On
- None

### Acceptance Criteria
- [ ] Given a fresh cache (no file), `load_and_cache_spec()` returns a dict with `paths` key
- [ ] Given a cache file younger than `DCT_SPEC_MAX_AGE_HOURS`, no HTTP call is attempted
- [ ] Given a download failure, bundled spec is used and WARNING is logged
- [ ] Given bundled spec missing, `MCPError("SPEC_LOAD_FAILED")` is raised
- [ ] `.cache-meta.json` is written alongside the cached YAML file

---

## Task 3: Dynamic Tools Module (discovery + execute)  [model:sonnet]

### Description
Creates `src/dct_mcp_server/tools/core/dynamic.py` — implements the `discovery` and `execute`
MCP tool functions and the `register_dynamic_tools(app, dct_client)` entry point. Both tool
functions must be decorated with `@log_tool_execution`.

`discovery` actions:
- `list_tags` — extract unique tags from `app.state.openapi_spec` with operation counts
- `list_operations` — iterate operations with tag/method/keyword filtering + pagination (max 50/page)
- `get_operation_schema` — fully resolve `$ref` recursively (depth ≤ 10, `schema_truncated=true` on cycle),
  annotate with `requires_confirmation` from confirmation_resolver

`execute` actions:
- Resolve path params (`{paramName}` substitution)
- Lookup operation in cached spec (OPERATION_NOT_FOUND if absent or method mismatch)
- Validate required parameters → VALIDATION_ERROR
- Check confirmation gate → return `confirmation_required` dict if `confirmed=False`
- Classify operation type (GET→read, DELETE→destructive, others→mutating)
- Dispatch via `dct_client.make_request()` (async)
- Return `DCT_API_ERROR` on `DCTClientError`

Note: `execute` uses `dct_client` directly (async); `discovery` reads `app.state.openapi_spec`
set by `main.py`. Both use `endpoint_discovery.py` helpers for `list_operations` corpus building.

### Spec References
- FR-002 (AC-1 through AC-5): Discovery tool
- FR-003 (AC-1 through AC-6): Execute tool

### Sub-tasks (TDD)
- [ ] **RED**: Define `register_dynamic_tools(app, dct_client)` signature; verify it can be
  imported and called with a mock FastMCP app
- [ ] **GREEN**: Implement `discovery` tool (list_tags, list_operations, get_operation_schema)
  using spec from `get_cached_spec()` as fallback when `app.state` not available; implement
  `execute` tool with full validation → confirmation → dispatch pipeline
- [ ] **REFACTOR**: Extract `_resolve_refs(schema, spec, depth, visited)` helper; extract
  `_classify_operation_type(method)` helper; ensure pagination logic is isolated in
  `_paginate(items, page, page_size)` helper

### Depends On
- Task 1 (confirmation_resolver.py must exist)
- Task 2 (spec_cache.py must exist for spec access)

### Acceptance Criteria
- [ ] `discovery(action="list_tags")` returns `{"tags": [...], }` with operation counts
- [ ] `discovery(action="list_operations", tag="VDBs", method="GET")` returns paginated GET ops in VDBs tag
- [ ] `discovery(action="get_operation_schema", path="POST /vdbs/{vdbId}/delete")` returns `requires_confirmation=True`
- [ ] `discovery` with unknown path returns `{"status": "error", "code": "OPERATION_NOT_FOUND"}`
- [ ] `execute` with `confirmed=False` for destructive op returns `{"status": "confirmation_required"}`
- [ ] `execute` with missing required field returns `{"status": "error", "code": "VALIDATION_ERROR"}`
- [ ] Both `discovery` and `execute` are decorated with `@log_tool_execution`

---

## Task 4: Config Layer Updates  [parallel][model:haiku]

### Description
Modifies two config files:
1. `src/dct_mcp_server/config/config.py` — add `DCT_SPEC_CACHE_PATH` and `DCT_SPEC_MAX_AGE_HOURS`
   env var parsing; add `dynamic` to `print_config_help()` output
2. `src/dct_mcp_server/config/loader.py` — add `"dynamic"` as a valid toolset value in
   `get_configured_toolset()` (alongside `"auto"`); add `"dynamic"` entry in `TOOL_TO_MODULE`
   pointing to `"dynamic"` module; update `clear_cache()` to call `load_toolset_grouped_apis.cache_clear()`
   (it's already missing from the existing clear_cache implementation)

This task is parallel to Tasks 1 and 2 because it only modifies config files, not tool modules.

### Spec References
- FR-001 (AC-1 through AC-3): Env var inputs for spec cache
- FR-004 (AC-1): Loader integration

### Sub-tasks (TDD)
- [ ] **RED**: Verify `get_dct_config()` does not yet have `spec_cache_path` or `spec_max_age_hours` keys
- [ ] **GREEN**: Add both env vars to `get_dct_config()`; add `dynamic` branch to `get_configured_toolset()`;
  add `dynamic` → `"dynamic"` entry to `TOOL_TO_MODULE`; fix `clear_cache()` to also clear
  `load_toolset_grouped_apis`
- [ ] **REFACTOR**: Ensure default values are documented in `print_config_help()`

### Depends On
- None

### Acceptance Criteria
- [ ] `get_dct_config()` returns `spec_cache_path` (default `$TEMP/dct_mcp_tools/api-external.yaml`)
- [ ] `get_dct_config()` returns `spec_max_age_hours` (default 24, type int)
- [ ] `get_configured_toolset()` returns `"dynamic"` when `DCT_TOOLSET=dynamic`
- [ ] `TOOL_TO_MODULE` contains `"discovery": "dynamic"` and `"execute": "dynamic"`
- [ ] `print_config_help()` lists `dynamic` toolset option

---

## Task 5: Registration Wiring (main.py + tools/__init__.py)  [model:sonnet]

### Description
Wires the new `dynamic` mode into the startup sequence:
1. `src/dct_mcp_server/tools/__init__.py` — add `dynamic` branch in `register_all_tools()`:
   when `toolset == "dynamic"`, import and call `register_dynamic_tools(app, dct_client)` from
   `tools.core.dynamic`; skip the existing fixed-toolset module loop
2. `src/dct_mcp_server/main.py` — in `async_main()`, after the toolset mode check, detect
   `DCT_TOOLSET=dynamic` and call `await asyncio.to_thread(load_and_cache_spec)` from `spec_cache`;
   store the result on `app.state.openapi_spec`; the `generate_tools_from_openapi()` call must
   still run (it is not skipped) but its failure is still non-fatal

### Spec References
- FR-001 (AC-1, AC-2): Spec loaded at startup and stored on app.state
- FR-002 (AC-1): Spec available to discovery tool at request time
- FR-003 (AC-1, AC-2): Execute tool dispatches via registered dct_client

### Sub-tasks (TDD)
- [ ] **RED**: Verify that starting the server with `DCT_TOOLSET=dynamic` currently raises
  `ValueError: Invalid toolset: dynamic` (confirming the gate is missing)
- [ ] **GREEN**: Add `dynamic` branch to `register_all_tools()`; add spec cache loading sequence
  to `async_main()`; attach spec to `app.state.openapi_spec`
- [ ] **REFACTOR**: Extract a `_load_dynamic_spec(app)` helper in `main.py` for the loading sequence;
  ensure the spec-loading error path logs clearly

### Depends On
- Task 2 (load_and_cache_spec must exist)
- Task 3 (register_dynamic_tools must exist)
- Task 4 (config changes must exist — dynamic must be a valid toolset value)

### Acceptance Criteria
- [ ] Server starts with `DCT_TOOLSET=dynamic` without ValueError
- [ ] `app.state.openapi_spec` is a non-empty dict after startup
- [ ] `discovery` and `execute` tools appear in MCP tool list (2 tools registered)
- [ ] Existing toolsets (`auto`, `self_service`, etc.) are unaffected by this change

---

## Task 6: LLM Evaluation Harness  [parallel][model:sonnet]

### Description
Creates `evals/llm_eval_harness.py` — a developer-time CLI script (not on the server hot path).
Implements 10 pre-defined DCT workflow scenarios evaluated against `discovery` + `execute` tools.
Accepts `--dct-url`, `--api-key`, `--models`, `--dry-run` CLI flags. Writes results to
`docs/DLPXECO-13984/DLPXECO-13984-eval-results.md`.

The 10 scenarios cover:
1. Provision VDB by timestamp
2. Refresh VDB by snapshot
3. Create bookmark
4. Delete bookmark (confirmation flow)
5. Search environments
6. Search dSources
7. List all tags
8. Get operation schema for a destructive endpoint
9. List operations filtered by tag
10. Execute a read-only GET (no confirmation)

The harness uses `discovery` and `execute` by simulating tool calls directly (Python function
calls, not MCP transport). It does not need a live MCP server — it imports the functions and
calls them with mock/real spec data.

### Spec References
- FR-005 (AC-1 through AC-5): LLM evaluation harness
- FR-006 (AC-1 through AC-5): Decision-gate report generation

### Sub-tasks (TDD)
- [ ] **RED**: Verify `evals/` directory does not yet contain `llm_eval_harness.py`
- [ ] **GREEN**: Implement CLI script with argparse; define 10 scenario functions;
  implement `run_scenario(scenario_fn, dry_run)` runner that records steps/status;
  aggregate results and write `DLPXECO-13984-eval-results.md` and
  `DLPXECO-13984-decision-gate.md`
- [ ] **REFACTOR**: Extract `_write_report(results, output_path)` helper;
  extract `_compute_recommendation(success_rate)` helper

### Depends On
- Task 3 (dynamic.py discovery/execute functions must exist for dry-run scenarios)

### Acceptance Criteria
- [ ] Script runs with `--dry-run` flag without requiring live DCT instance
- [ ] Output file `docs/DLPXECO-13984/DLPXECO-13984-eval-results.md` is written
- [ ] Output file `docs/DLPXECO-13984/DLPXECO-13984-decision-gate.md` is written with ADOPT/INVESTIGATE/REVERT
- [ ] 10 scenario stubs are defined even if only executable in dry-run mode

---

## Execution Order

Task 1 (parallel), Task 2 (parallel), Task 4 (parallel) → Task 3 → Task 5 → Task 6 (parallel)

## Progress Tracker

| Task | Status |
|------|--------|
| Task 1: Confirmation Resolver | DONE |
| Task 2: Spec Cache Subsystem | DONE |
| Task 4: Config Layer Updates | DONE |
| Task 3: Dynamic Tools Module | DONE |
| Task 5: Registration Wiring | DONE |
| Task 6: LLM Evaluation Harness | DONE |
