# Feature Design: DLPXECO-13965

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13965
**Status**: Proposed
<!-- Guidance: H1 title must be exactly "Feature Design: $NAME" (not H2). check-structure.sh does not enforce this mechanically, but downstream review tooling relies on it. -->

---

## Summary
<!-- Guidance: One paragraph (3–5 sentences). What this feature does, who it is for, why it is being built now. Avoid implementation detail — that belongs in Architecture Changes below. -->

This feature adds four bulk VDB lifecycle actions (`bulk_start`, `bulk_stop`, `bulk_enable`, `bulk_disable`) to the DCT MCP Server so that AI assistants can apply the same lifecycle operation to a set of VDBs in a single tool call rather than issuing N sequential calls. The bulk actions fan out to existing per-VDB DCT API endpoints concurrently using `asyncio.Semaphore`, aggregate per-VDB outcomes into a single structured response, and surface partial failures without aborting the batch. Destructive bulk operations (`bulk_stop`, `bulk_disable`) require explicit confirmation when targeting more than 5 VDBs, reusing the existing confirmation response pattern. A new `DCT_BULK_CONCURRENCY` configuration variable (default 5, clamped 1–50) controls the maximum number of concurrent DCT requests, preventing accidental request storms against the DCT API.

## Affected Components
<!-- Guidance: Render the component checklist from .claude/architecture.md. Tick `[x]` for components this feature changes; leave `[ ]` for the rest. -->

- [x] `config/config.py` — adds `DCT_BULK_CONCURRENCY` env-var parsing, clamping, and validation
- [x] `config/toolsets/self_service.txt` — registers the four new bulk action entries under `vdb_tool`
- [x] `config/toolsets/continuous_data_admin.txt` — registers the same four bulk action entries under `data_tool`
- [x] `tools/vdb_endpoints_tool.py` — new file implementing the four bulk actions and the shared `_bulk_vdb_action` helper
- [x] `config/loader.py` — adds `"vdb_endpoints_tool"` to `TOOL_TO_MODULE` for the `vdb_tool` key
- [x] `tests/dlpxeco-13965-test.py` — new test file with all 19 required pytest scenarios
- [ ] `main.py` — no changes; startup flow unchanged
- [ ] `config/mappings/manual_confirmation.txt` — no changes; bulk confirmation is inline in the handler (see Assumption A2)
- [ ] `dct_client/client.py` — no changes; bulk actions call `DCTAPIClient.request` as-is
- [ ] `core/decorators.py` — no changes; `@log_tool_execution` already supports async functions
- [ ] `core/exceptions.py` — no changes; existing `DCTClientError` and `MCPError` are reused
- [ ] `tools/__init__.py` — no code changes; auto-discovery already loads any module with `register_tools()`
- [ ] `tools/core/meta_tools.py` — no changes; auto-mode meta-tools unaffected
- [ ] `tools/core/tool_factory.py` — no changes; dynamic generation unaffected

## Architecture Changes

### Schema / Config Changes
<!-- Guidance: Every change to schema files, config formats, or persisted state shapes. -->

| Field | Type | Object | Notes |
|-------|------|--------|-------|
| `DCT_BULK_CONCURRENCY` | integer env var | `config.py` `get_dct_config()` dict | New optional env var, default 5, valid range [1, 50]; clamped with WARNING if out of range; stored as `config["bulk_concurrency"]` |
| `bulk_start` | toolset action entry | `config/toolsets/self_service.txt` and `config/toolsets/continuous_data_admin.txt` | New `POST|/vdbs/bulk_start|bulk_start` line under the VDB tool section |
| `bulk_stop` | toolset action entry | same toolset files | New `POST|/vdbs/bulk_stop|bulk_stop` line |
| `bulk_enable` | toolset action entry | same toolset files | New `POST|/vdbs/bulk_enable|bulk_enable` line |
| `bulk_disable` | toolset action entry | same toolset files | New `POST|/vdbs/bulk_disable|bulk_disable` line |

### Source Files to Modify
<!-- Guidance: One row per file. The path must exist in the repo. Group by component. -->

| File | Purpose | Maps to FR |
|------|---------|------------|
| `src/dct_mcp_server/config/config.py` | Add `DCT_BULK_CONCURRENCY` env var: `int(os.getenv("DCT_BULK_CONCURRENCY", "5"))` with try/except `ValueError`, clamped to [1, 50] with WARNING log; add `"bulk_concurrency"` key to the returned config dict; update `print_config_help()` to document the new var | FR-006 |
| `src/dct_mcp_server/config/toolsets/self_service.txt` | Append four new action lines under `# TOOL 1: vdb_tool`: `POST\|/vdbs/bulk_start\|bulk_start`, `POST\|/vdbs/bulk_stop\|bulk_stop`, `POST\|/vdbs/bulk_enable\|bulk_enable`, `POST\|/vdbs/bulk_disable\|bulk_disable` | FR-001 |
| `src/dct_mcp_server/config/toolsets/continuous_data_admin.txt` | Append the same four action lines under the VDB section of `# TOOL 1: data_tool` | FR-001 |
| `src/dct_mcp_server/config/loader.py` | Add `"vdb_tool": "vdb_endpoints_tool"` entry to `TOOL_TO_MODULE` in `get_modules_for_toolset()` so that the `vdb_tool` key correctly maps to the new pre-built module | FR-001 |
| `src/dct_mcp_server/tools/vdb_endpoints_tool.py` | **New file** — implements `register_tools(app, dct_client)` with a single `vdb_tool` MCP tool (async def); handles `bulk_start` (FR-002), `bulk_stop` (FR-003), `bulk_enable` (FR-004), `bulk_disable` (FR-005); includes the shared `_bulk_vdb_action` async helper with semaphore-bounded fan-out, aggregated response, partial-failure handling, and logging; validates `vdbIds` before fan-out; applies `@log_tool_execution` decorator | FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007 |
| `tests/dlpxeco-13965-test.py` | **New file** — all 19 required pytest scenarios; module-scoped `mcp_client` fixture using `fastmcp.Client` with `StdioServerParameters`; function-scoped `mock_dct` fixture patching `DCTAPIClient.request`; covers all FR acceptance criteria; concurrency cap test using counter-based in-flight tracking | FR-008 |

### New Files (if any)
<!-- Guidance: Path + one-line purpose. -->

- `src/dct_mcp_server/tools/vdb_endpoints_tool.py` — New pre-built grouped tool module implementing all four bulk VDB lifecycle actions with semaphore-bounded async fan-out.
- `tests/dlpxeco-13965-test.py` — Pytest test file with all 19 scenarios covering bulk action behavior, confirmation gate, concurrency cap, validation, logging, and toolset config sync checks.

## Version Compatibility
<!-- Guidance: Pull the version table from .claude/architecture.md and mark whether this feature requires branching per version. -->

This feature operates exclusively at the MCP server layer — it fans out to existing per-VDB DCT API endpoints (`POST /vdbs/{vdbId}/start`, `stop`, `enable`, `disable`) that have been stable across all supported DCT releases. No DCT API version branching is required.

| Version | Supported? | Branch? | Notes |
|---------|-----------|---------|-------|
| DCT API (all versions) | Yes | No | Bulk actions fan out to per-VDB endpoints that exist in all supported DCT versions; no server-side batch API required |
| Python 3.11+ | Yes | No | `asyncio.Semaphore`, `asyncio.gather`, and `async def` tool functions are all standard library; no version-specific behavior |
| FastMCP 2.13.2+ | Yes | No | `@app.tool()` decorator and `async def` tool registration are both supported in this version range; no API branch required |

## Platform Behavior Notes
<!-- Guidance: Flag each "Non-Obvious Platform Behavior" from CLAUDE.md / architecture.md that this feature interacts with. -->

- **API key prefix (`apk `)**: Affects — `DCTAPIClient` prepends `apk ` automatically. The bulk handler passes `DCTAPIClient.request` calls through normally; no special handling needed.
- **SSL verification defaults to `false`**: N/A — bulk actions make the same HTTPS calls as single-VDB actions; no new SSL surface.
- **Retry/backoff on transient failures**: Affects — the DCT client already retries up to `DCT_MAX_RETRIES` per individual VDB call inside the bulk fan-out. No second retry layer is added in the bulk wrapper (Non-Goal NG4). The semaphore stays acquired across the retry attempts within `DCTAPIClient.request`, which is acceptable because retries are fast (exponential backoff up to a few seconds).
- **Toolset config cache (`@lru_cache`)**: Affects — the four new action entries are added to the `.txt` files that `loader.py` caches. If the server is already running and `clear_cache()` has not been called, the new actions will not be visible until restart. This is the existing behavior for all toolset config changes and is documented.
- **Dynamic tool generation priority**: Affects — `tools/__init__.py` prioritizes generated modules from `$TEMP/dct_mcp_tools/` over pre-built `*_endpoints_tool.py` files. If the DCT API spec includes VDB lifecycle endpoints, a generated `vdb_endpoints_tool`-equivalent may shadow the new file. In practice the generated module will also handle single-VDB actions; bulk actions (which are MCP-layer fan-outs with no real DCT endpoint) will be missing from the generated module. Mitigation: the `TOOL_TO_MODULE` mapping ensures the pre-built `vdb_endpoints_tool` is loaded as a fallback when generation fails or produces a module without bulk support.
- **Telemetry (opt-in)**: Affects — `@log_tool_execution` records each `vdb_tool` invocation in the session telemetry log. No VDB ID list or DCT credentials appear in the telemetry record (QR-4).
- **`asyncio` event loop conflict**: Affects — `vdb_tool` is declared `async def`; `asyncio.run()` is explicitly prohibited inside the tool body to avoid `RuntimeError` in FastMCP's already-running event loop (Assumption A1, Risk in vision.md). The `@log_tool_execution` decorator already supports async functions (per `decorators.py` inspection).

## Open Questions / Risks
<!-- Guidance: One bullet per item. Format: "Q: <question>" or "R: <risk> — Mitigation: <action>". Keep blocking items at the top. -->

- R: `loader.py` currently maps `"vdb_tool"` to `"dataset_endpoints_tool"`. After this feature, `vdb_tool` must map to `"vdb_endpoints_tool"` instead. If `dataset_endpoints_tool` also registers `vdb_tool`-named actions, there may be a naming conflict during dynamic module discovery. Mitigation: confirm that `dataset_endpoints_tool` does not expose a function named `vdb_tool` and that `tools/__init__.py` deduplicates by tool name (inspect `__init__.py` before implementing).
- R: Dynamic tool generation from the OpenAPI spec may produce a competing `vdb_tool` registration that does not include bulk actions. Mitigation: since bulk actions have no real DCT endpoint (they are MCP-layer fan-outs), they will never appear in the generated spec; the pre-built `vdb_endpoints_tool` must be loaded alongside (or as a fallback to) any generated VDB tool.
- Q: Does `dataset_endpoints_tool.py` currently register a function named `vdb_tool`? If yes, the new `vdb_endpoints_tool.py` must use a different approach (e.g., register only the bulk actions and let `dataset_endpoints_tool` handle single-VDB actions, merged under the same tool name at the MCP layer). Owner: implementer — check before coding.
- Q: Does the GitHub Actions CI workflow exist at `.github/workflows/`? If no workflow file exists, FR-008 AC-3 (adding the test step to CI) cannot be fulfilled as-is. The implementer should create the CI workflow file if absent, or document that CI is out of scope for this PR. Owner: implementer.
- R: `asyncio.CancelledError` must not be swallowed by the per-VDB `except DCTClientError` clause; using bare `except Exception` would catch `CancelledError` (QR-8). Mitigation: the `except` clause in `_bulk_vdb_action` must be `except DCTClientError` specifically; verified by code review.
- R: Assumption A6 (deduplication of `vdbIds`) conflicts with the edge-case wording in EC-2 (no deduplication applied). The functional spec defines both; design resolves in favor of A6 (deduplication with DEBUG log) since it prevents double-operations on the same VDB within a single bulk call. This must be documented in the implementation and reflected in the test (EC-2 scenario should assert deduplication, not double-invocation).

## Acceptance Criteria
<!-- Guidance: Pull directly from the Jira ticket "Acceptance Criteria" section if present, else derive from vision-doc Goals. Each AC must be testable and map to at least one FR-* in functional.md. -->

- [ ] AC-1 (from SC1): A single `vdb_tool(action="bulk_start", vdbIds=[...])` call returns `{"status": "success", "total": N, "succeeded": [...], "failed": [], "jobs": [...]}` within wall-clock time proportional to `ceil(N / DCT_BULK_CONCURRENCY)` × average DCT call latency. Maps to FR-002.
- [ ] AC-2 (from SC2): Partial failures do not abort the batch — the response always contains the complete list of per-VDB outcomes regardless of individual errors. `status="partial_success"` when at least one VDB succeeds and at least one fails. Maps to FR-002, FR-003, FR-004, FR-005.
- [ ] AC-3 (from SC3): `vdb_tool(action="bulk_stop", vdbIds=[...])` with more than 5 VDBs and no `confirmed=True` returns `{"status": "confirmation_required", "confirmation_level": "manual", ...}` without making any DCT call; re-calling with `confirmed=True` executes the batch. Maps to FR-003, FR-005.
- [ ] AC-4 (from SC4): At most `DCT_BULK_CONCURRENCY` (default 5) concurrent DCT API requests are in-flight at any time during a bulk action; verified by a unit test using a mock client with a concurrency counter. Maps to FR-006, FR-002.
- [ ] AC-5 (from SC5): All four bulk actions (`bulk_start`, `bulk_stop`, `bulk_enable`, `bulk_disable`) appear in both the `self_service` and `continuous_data_admin` toolset `.txt` files and are loaded correctly when `loader.py` parses those files. Maps to FR-001.
- [ ] AC-6 (from SC6): All 19 required pytest scenarios in `tests/dlpxeco-13965-test.py` pass with exit code 0 and coverage of `vdb_endpoints_tool.py` is measurable via `--cov`. Maps to FR-008.
- [ ] AC-7 (from QR-1): Existing single-VDB `start`, `stop`, `enable`, `disable` actions in `self_service` continue to work unchanged; no regression to existing action branches. Maps to FR-002 (QR-1).
- [ ] AC-8 (from QR-5): Toolset config action names in `.txt` files match the handler branch names in `vdb_endpoints_tool.py` exactly; verified by tests 17, 18, 19. Maps to FR-001, FR-008.
- [ ] AC-9 (from FR-007): Each bulk action invocation emits exactly 1 INFO log line (`"bulk_{action}: fanning out to N VDBs with concurrency=C"`) and exactly N DEBUG log lines (`"bulk_{action}: vdbId={id} status={ok|error}"`); no DCT credentials appear in any log line at any level. Maps to FR-007.

---
<!-- Cross-references checked by check-structure.sh during the design phase:
     - Every FR-* in docs/$NAME-functional.md → at least one row in ### Source Files to Modify
     - Non-Goals in docs/$NAME-vision.md → MUST NOT appear in Architecture Changes (hard constraint)
     - Every AC → at least one FR-* in functional.md (transitive via FR mapping)
     Run: .claude/evals/check-structure.sh $NAME --step design -->
