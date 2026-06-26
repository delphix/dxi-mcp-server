# Feature Design: DLPXECO-13984

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13984
**Status**: Proposed
<!-- Guidance: H1 title must be exactly "Feature Design: $NAME" (not H2). -->

---

## Summary

This feature delivers the Phase 1 "2-Tool Architecture" for the Delphix DCT API MCP Server — replacing the need for per-endpoint MCP code maintenance with two universal tools (`discovery` and `execute`) driven by the live DCT OpenAPI spec. A new `DCT_TOOLSET=dynamic` mode is added as an additive option alongside the existing persona-based toolsets. At startup, the server downloads and caches the DCT OpenAPI spec (`api-external.yaml`) from the configured DCT instance; if the download fails and no fresh on-disk cache exists, startup aborts with `SPEC_LOAD_FAILED` (there is no bundled-spec fallback — a failed download means DCT is unreachable). The `discovery` tool lets AI assistants browse the full DCT API surface (list tags, list operations with filters and pagination, retrieve fully resolved operation schemas). The `execute` tool validates parameters against the cached spec, applies the existing confirmation-gate resolver from `manual_confirmation.txt`, and dispatches the API call via `DCTAPIClient`. An LLM evaluation harness and a decision-gate report complete Phase 1, providing an evidence-based adopt/revert recommendation and explicit Phase 2 entry criteria.

## Affected Components

<!-- Every component listed in .claude/architecture.md is marked below. -->

- [x] Entry point (`main.py`) — new `dynamic` toolset branch in `async_main()`; spec cache loaded in lifespan
- [x] Config layer (`config/config.py`, `config/loader.py`) — new env vars `DCT_SPEC_CACHE_PATH`, `DCT_SPEC_MAX_AGE_HOURS`; `dynamic` added as a valid `DCT_TOOLSET` value; `TOOL_TO_MODULE` updated
- [ ] Toolset `.txt` files (`config/toolsets/*.txt`) — no changes; persona toolsets untouched
- [x] Confirmation rules (`config/mappings/manual_confirmation.txt`) — read-only consumption by new resolver; no changes to the file itself
- [x] Tool registration (`tools/__init__.py`) — new branch to register `discovery` and `execute` tools in `dynamic` mode
- [ ] Pre-built grouped tool modules (`tools/*_endpoints_tool.py`) — no changes; used only in persona-based mode
- [x] Auto mode meta-tools (`tools/core/meta_tools.py`) — no changes; `auto` mode unchanged
- [x] Dynamic tool generation (`tools/core/tool_factory.py`) — spec download/cache logic extracted and reused by new spec cache subsystem
- [x] Dynamic endpoint discovery (`tools/core/endpoint_discovery.py`) — existing corpus/scoring helpers reused by `discovery` tool
- [x] HTTP client (`dct_client/client.py`) — used as-is by `execute` tool; no client code changes
- [x] Infrastructure (`core/exceptions.py`) — no new exception types; existing `DCTClientError` and `MCPError` used
- [x] New module: `tools/core/spec_cache.py` — OpenAPI spec download, validation, disk cache, and in-memory representation
- [x] New module: `tools/core/dynamic.py` — `discovery` and `execute` tool implementations
- [x] New module: `tools/core/confirmation_resolver.py` — stateless confirmation-gate resolver (extracted from tool_factory.py for standalone use)
- [x] LLM evaluation harness: `evals/llm_eval_harness.py` — developer-time tool, not on server hot path
- [x] Decision-gate report: `docs/DLPXECO-13984/DLPXECO-13984-decision-gate.md` — human-readable output

## Architecture Changes

### Schema / Config Changes

| Field | Type | Object | Notes |
|-------|------|--------|-------|
| `DCT_SPEC_CACHE_PATH` | string (path) | env var | Optional. Default: `$TEMP/dct_mcp_tools/api-external.yaml`. Path where the downloaded spec is cached. |
| `DCT_SPEC_MAX_AGE_HOURS` | integer | env var | Optional. Default: `24`. Re-download triggered at next startup if cached spec is older than this. |
| `DCT_TOOLSET=dynamic` | string | env var | New accepted value for `DCT_TOOLSET`. Triggers `discovery` + `execute` tool registration. |
| `.cache-meta.json` | JSON file | sidecar to `DCT_SPEC_CACHE_PATH` | Records `{"downloaded_at": ISO-timestamp, "dct_base_url": str, "spec_path": str}`. Written by spec cache subsystem. |

No changes to `config/toolsets/*.txt` files, `manual_confirmation.txt`, or any database/persistent schema.

### Source Files to Modify

| File | Purpose | Maps to FR |
|------|---------|------------|
| `src/dct_mcp_server/config/config.py` | Add `DCT_SPEC_CACHE_PATH` and `DCT_SPEC_MAX_AGE_HOURS` env var parsing; add `dynamic` to the valid `DCT_TOOLSET` values list and `print_config_help()` output | FR-001 |
| `src/dct_mcp_server/config/loader.py` | Add `dynamic` to `TOOL_TO_MODULE` pointing at `dynamic` module; add `clear_cache()` call coverage for new spec-cache cache entries | FR-001, FR-004 |
| `src/dct_mcp_server/main.py` | In `async_main()`: after existing tool generation, detect `DCT_TOOLSET=dynamic` and call `load_and_cache_spec()` from `spec_cache.py`; attach parsed spec to `app.state.openapi_spec`; register `discovery` and `execute` via `tools/__init__.py` in dynamic branch | FR-001, FR-002, FR-003 |
| `src/dct_mcp_server/tools/__init__.py` | Add `dynamic` mode branch in `register_all_tools()`; import and call `register_dynamic_tools(app, dct_client)` | FR-002, FR-003 |

### New Files (if any)

- `src/dct_mcp_server/tools/core/spec_cache.py` — OpenAPI spec download, YAML validation, disk cache (read/write), `.cache-meta.json` sidecar management, and in-memory parsed-spec builder. Exposes `load_and_cache_spec() -> dict` used by `main.py` lifespan. Reuses HTTP download pattern from `toolsgenerator/driver.py` but is independent of the existing tool-generation path.
- `src/dct_mcp_server/tools/core/dynamic.py` — Implements `discovery` and `execute` MCP tool functions; exposes `register_dynamic_tools(app, dct_client)`. Uses `spec_cache.get_cached_spec()`, `endpoint_discovery` helpers for `discovery`, and `confirmation_resolver.check_confirmation()` for `execute`.
- `src/dct_mcp_server/tools/core/confirmation_resolver.py` — Standalone, stateless confirmation resolver: `check_confirmation(method, path, context) -> dict`. Wraps `config/loader.py:get_confirmation_for_operation()` and adds support for `retention_check:N` and `policy_impact_check:N` conditional rule evaluation using caller-supplied `context`.
- `evals/llm_eval_harness.py` — Developer-time CLI script. Accepts `--dct-url`, `--api-key`, `--models`, `--dry-run` flags. Runs 10 pre-defined DCT workflow scenarios against `discovery` and `execute` tools, records per-step results, and writes `docs/DLPXECO-13984/DLPXECO-13984-eval-results.md`.

## Version Compatibility

<!-- This is a Python 3.11+ project with no version branching by DCT API version. -->

| Version | Supported? | Branch? | Notes |
|---------|-----------|---------|-------|
| Python 3.11 | Yes | No | Minimum required version; all new code uses only 3.11-compatible stdlib |
| Python 3.12+ | Yes | No | Forward-compatible; no deprecated APIs used |
| DCT API (any version with `api-external.yaml`) | Yes | No | Spec is version-agnostic; the discovery and execute tools operate on whatever spec is downloaded. Discovery returns `OPERATION_NOT_FOUND` for paths absent from the cached spec. |
| Existing persona toolsets (`self_service`, `continuous_data_admin`, `platform_admin`, `reporting_insights`, `self_service_provision`) | Yes | No | Completely unchanged; run as before when `DCT_TOOLSET` is set to any of these |
| `auto` mode | Yes | No | Completely unchanged; `DCT_TOOLSET=auto` still loads meta-tools; no interaction with `dynamic` mode |
| MCP clients (Claude Desktop, Cursor, VS Code Copilot, Continue.dev) | Yes | No | No client-side configuration changes required; `dynamic` mode registers exactly 2 tools on startup |

## Platform Behavior Notes

- **API key prefix** (`apk ` prepended by `DCTAPIClient`): Affects — the spec download in `spec_cache.py` must use `DCTAPIClient` (or replicate the `Authorization: apk {key}` header) to authenticate the spec download request. Do not pass the raw key without `apk `.
- **SSL**: Affects — `spec_cache.py` must respect `DCT_VERIFY_SSL` when making the spec download HTTP request; default is `verify=false` matching the client.
- **Retries / backoff**: Affects — spec download should apply at most one retry (not the full `DCT_MAX_RETRIES` chain) because it runs in the startup hot path; failure is fatal (`MCPError("SPEC_LOAD_FAILED")`) unless a fresh on-disk cache is available — there is no bundled-spec fallback.
- **Toolset config cache (`@lru_cache`)**: Affects — `confirmation_resolver.py` calls `get_confirmation_for_operation()` which is already `@lru_cache`'d in `loader.py`; no additional caching layer needed.
- **Telemetry (`IS_LOCAL_TELEMETRY_ENABLED`)**: Affects — `discovery` and `execute` tool functions must be decorated with `@log_tool_execution` so tool calls are recorded in telemetry sessions when enabled.
- **`$TEMP/dct_mcp_tools/` directory**: Affects — `spec_cache.py` uses the same temp directory convention as `toolsgenerator/driver.py` for the cached spec. Directory must be created if absent; must not fail on read-only filesystems (degrade to in-memory only).
- **Generated tool priority**: N/A — `dynamic` mode does not use `$TEMP/dct_mcp_tools/` generated tool modules; it registers `discovery` and `execute` directly.

## Open Questions / Risks

- R: DCT OpenAPI spec quality is insufficient for automated operation — missing `description` fields, incorrect `required` arrays, or unresolved `$ref` cycles could degrade Discovery and Execute usability — Mitigation: `get_operation_schema` resolves `$ref` up to depth 10 (EC-4); returns `schema_truncated: true` on cycle detection; spec quality audit is an explicit Phase 1 deliverable (FR-006).
- R: LLM success rate falls below 80% on the 10-scenario harness — Mitigation: FR-005 explicitly tests two frontier models; failure analysis feeds into FR-006 decision-gate; adopt/revert decision is the designed outcome of Phase 1, not an assumption.
- R: Spec download at startup adds latency or blocks in air-gapped / CI environments — Mitigation: Download is non-blocking (timeout ≤ `DCT_TIMEOUT`, single retry); a fresh on-disk cache from a prior download is reused when present. There is no bundled-spec fallback: dynamic mode requires connectivity to the DCT instance, and a failed download means the server cannot serve DCT calls anyway, so it fails fast with `SPEC_LOAD_FAILED`.
- Q: Should `discovery` expose a `get_spec_chunk` action similar to the existing `get_spec_chunk` meta-tool in `auto` mode, or is `get_operation_schema` sufficient? — Owner: Shreyas Kulkarni. Current plan: `get_operation_schema` fully resolves `$ref` inline and returns a flat field list; `get_spec_chunk` (raw `$ref` resolution) is an `auto`-mode-only capability and is not re-exposed in `dynamic` mode.
- Q: Should `execute` persist a short-lived confirmation token (e.g. per session) to prevent replaying `confirmed=true` from a different call site, or is the stateless pass-through acceptable? — Owner: TBD. Current plan: stateless (EC-2 — each call is independent); the DCT API handles idempotency.
- R: Persona-based toolsets and `dynamic` mode are mutually exclusive at startup — registering both simultaneously would double the tool count and confuse LLM context — Mitigation: validated by the `DCT_TOOLSET` parser; only one mode is active per server process; existing toolsets are untouched.

## Acceptance Criteria

<!-- Derived from FR-001 through FR-006 acceptance criteria in functional.md -->

- [ ] AC-001: Given a reachable DCT instance, when the server starts with `DCT_TOOLSET=dynamic`, then the OpenAPI spec is downloaded, validated, cached to disk, and available in-memory within 5 seconds (FR-001 AC-1)
- [ ] AC-002: Given a network-unreachable DCT instance and no fresh on-disk cache, when the server starts, then `MCPError("SPEC_LOAD_FAILED")` is raised and the server does not start (FR-001 AC-2)
- [ ] AC-003: Given a cached spec younger than `DCT_SPEC_MAX_AGE_HOURS`, when the server starts, then no HTTP download is attempted (FR-001 AC-3)
- [ ] AC-004: Given a downloaded spec that fails YAML validation or lacks `paths`, and no fresh on-disk cache, then `MCPError("SPEC_LOAD_FAILED")` is raised and a `WARNING` log entry records the reason (FR-001 AC-4)
- [ ] AC-005: Given the live download is unavailable and no fresh on-disk cache exists, server startup raises `MCPError("SPEC_LOAD_FAILED")` and does not start (FR-001 AC-5)
- [ ] AC-006: Given the spec is loaded, `discovery(action="list_tags")` returns all DCT domain tags with accurate operation counts (FR-002 AC-1)
- [ ] AC-007: Given `discovery(action="list_operations", tag="VDBs", method="GET")`, only GET operations tagged VDBs are returned, paginated correctly (FR-002 AC-2)
- [ ] AC-008: Given `discovery(action="get_operation_schema", path="POST /vdbs/{vdbId}/delete")`, the response includes `requires_confirmation=true`, `confirmation_level="manual"`, and fully resolved parameters with no `$ref` pointers (FR-002 AC-3)
- [ ] AC-009: Given `discovery(action="get_operation_schema")` for a non-existent path, `{"status": "error", "code": "OPERATION_NOT_FOUND"}` is returned (FR-002 AC-4)
- [ ] AC-010: Given `execute(path="/vdbs/{vdbId}/delete", method="POST", path_params={"vdbId": "vdb-123"}, confirmed=false)`, `{"status": "confirmation_required", "confirmation_level": "manual"}` is returned without making any HTTP call (FR-003 AC-1)
- [ ] AC-011: Given the same call with `confirmed=true`, the DELETE call is dispatched and `{"status": "success"}` is returned (FR-003 AC-2)
- [ ] AC-012: Given `execute(path="/vdbs/search", method="POST")`, `{"status": "success", "operation_type": "read"}` is returned (FR-003 AC-3)
- [ ] AC-013: Given `execute` with a missing required body field, `{"status": "error", "code": "VALIDATION_ERROR", "missing_fields": [...]}` is returned before any HTTP call (FR-003 AC-4)
- [ ] AC-014: Given `execute` for a path not in the cached spec, `{"status": "error", "code": "OPERATION_NOT_FOUND"}` is returned (FR-003 AC-5)
- [ ] AC-015: Confirmation resolver returns `requires_confirmation=true` with correct level for all operations currently in `manual_confirmation.txt` (FR-004 AC-1)
- [ ] AC-016: Confirmation resolver returns `requires_confirmation=false` for all GET operations (FR-004 AC-2)
- [ ] AC-017: `retention_check:N` and `policy_impact_check:N` conditional rules evaluate correctly against supplied `context` (FR-004 AC-3, AC-4)
- [ ] AC-018: LLM evaluation harness runs 10 workflow scenarios against at least two frontier models and produces a complete report with per-scenario and per-model success rates (FR-005 AC-1)
- [ ] AC-019: Decision-gate report exists at `docs/DLPXECO-13984/DLPXECO-13984-decision-gate.md` with ADOPT/INVESTIGATE/REVERT recommendation and supporting quantitative evidence (FR-006 AC-1, AC-2)
- [ ] AC-020: All existing persona-based toolsets (`self_service`, `continuous_data_admin`, etc.) continue to function identically after this change — verified by connecting an MCP client with each toolset and exercising at least one tool per toolset (Quality Rule: API backward compatibility)
- [ ] AC-021: `discovery` and `execute` tool functions are decorated with `@log_tool_execution` and appear in telemetry session logs when `IS_LOCAL_TELEMETRY_ENABLED=true` (Quality Rule: @log_tool_execution applied)

---
<!-- Cross-references checked by check-structure.sh during the design phase:
     - Every FR-* in docs/DLPXECO-13984/DLPXECO-13984-functional.md → at least one row in ### Source Files to Modify
       FR-001 → config.py, loader.py, main.py, spec_cache.py (new)
       FR-002 → dynamic.py (new), tools/__init__.py
       FR-003 → dynamic.py (new), tools/__init__.py
       FR-004 → confirmation_resolver.py (new), loader.py
       FR-005 → evals/llm_eval_harness.py (new)
       FR-006 → docs/DLPXECO-13984/DLPXECO-13984-decision-gate.md (new output file)
     - Non-Goals in vision.md → MUST NOT appear in Architecture Changes
       NG1 (Search tool, Execute sandbox) → not present
       NG2 (persona toolset changes) → not present
       NG3 (Docker Hub) → not present
       NG4 (OpenTelemetry) → not present
       NG5 (Streamable HTTP transport) → not present
       NG6 (per-tool RBAC) → not present
       NG7 (vocabulary translation) → not present
     Run: .claude/evals/check-structure.sh DLPXECO-13984 --step design -->
