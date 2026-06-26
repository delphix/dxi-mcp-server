# Functional Specification: DLPXECO-13984

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13984
**Generated from**: Epic description and acceptance criteria in Jira ticket DLPXECO-13984

---

## FR-001: OpenAPI Spec Download and Cache Subsystem

### Description
Fetches the DCT OpenAPI spec from the configured DCT instance at server startup, validates it structurally, persists it to a local disk cache, and makes the cached spec available to both the Discovery and Execute tools for the lifetime of the server process.

### Input
- `DCT_BASE_URL` (string, required): base URL of the DCT instance (no `/dct` suffix)
- `DCT_API_KEY` (string, required): DCT API key for authenticated spec download
- `DCT_SPEC_CACHE_PATH` (string, optional, default `$TEMP/dct_mcp_tools/api-external.yaml`): filesystem path for the cached spec
- `DCT_SPEC_MAX_AGE_HOURS` (integer, optional, default `24`): maximum age of cached spec before re-download is attempted at next startup
- No bundled fallback spec: the spec is always sourced from the live DCT instance (or a fresh on-disk cache of a prior download)

### Processing
1. On server startup (within the FastMCP lifespan context manager), attempt HTTP GET `{DCT_BASE_URL}/dct/static/api-external.yaml` with the DCT API key in the `Authorization` header (Bearer token, `apk` prefix applied by `DCTAPIClient`)
2. If the download succeeds (HTTP 200), validate the response body is parseable YAML with a top-level `openapi` key and at least one `paths` entry
3. If validation passes, write the spec to `DCT_SPEC_CACHE_PATH`; record download timestamp in a sidecar `.cache-meta.json` file
4. If cached spec exists on disk and its age is < `DCT_SPEC_MAX_AGE_HOURS`, skip re-download and use the cached file directly
5. Parse the (downloaded or cached) spec into an in-memory representation and serve it from the `spec_cache` module-level cache for tool access
6. If the download fails (network error, non-200, timeout > `DCT_TIMEOUT` seconds) or validation fails, and no fresh on-disk cache is available, raise `MCPError` with `SPEC_LOAD_FAILED` code. There is no bundled-spec fallback — a failed download means the DCT instance is unreachable, so the server cannot serve any DCT API call anyway and must not start.

### Output
- Success: In-memory spec dict served via `spec_cache.get_cached_spec()`; cache file written to disk
- Failure: `MCPError("SPEC_LOAD_FAILED")` — server startup aborted

### Acceptance Criteria
- [ ] AC-1: Given a reachable DCT instance, when the server starts, then the spec is downloaded, validated, cached to disk, and available via `spec_cache.get_cached_spec()` within 5 seconds
- [ ] AC-2: Given a network-unreachable DCT instance and no fresh on-disk cache, when the server starts, then an `MCPError("SPEC_LOAD_FAILED")` is raised and the server does not start
- [ ] AC-3: Given a cached spec younger than `DCT_SPEC_MAX_AGE_HOURS`, when the server starts, then no HTTP download is attempted and the cached file is used
- [ ] AC-4: Given a downloaded spec that is not valid YAML or lacks `paths`, and no fresh on-disk cache, then an `MCPError("SPEC_LOAD_FAILED")` is raised and a `WARNING` records the validation failure
- [ ] AC-5: Given the live download is unavailable and no fresh on-disk cache exists, when the server starts, then an `MCPError` is raised and the server does not start

---

## FR-002: Discovery Tool — Browse and Inspect DCT API Surface

### Description
Provides an MCP tool named `discovery` that lets the AI browse the DCT API surface from the cached OpenAPI spec: listing available operations by domain/tag, filtering by HTTP method or keyword, and retrieving the full schema for a specific operation (parameters, request body, response shape).

### Input
- `action` (string, required): one of `list_operations`, `get_operation_schema`, `list_tags`
- `tag` (string, optional): filter `list_operations` to a specific OpenAPI tag (DCT domain, e.g. `VDBs`, `Environments`)
- `method` (string, optional): filter `list_operations` to a specific HTTP method (`GET`, `POST`, `PATCH`, `DELETE`, `PUT`)
- `keyword` (string, optional): case-insensitive keyword filter applied to operationId and summary in `list_operations`
- `path` (string, optional, required for `get_operation_schema`): exact API path (e.g. `/vdbs/{vdbId}`)
- `operation_method` (string, optional, required for `get_operation_schema`): HTTP method for the path
- `page` (integer, optional, default 1): page number for paginated `list_operations` results
- `page_size` (integer, optional, default 20): results per page (max 50)

### Processing
**For `list_tags`:**
1. Extract all unique tags from `app.state.openapi_spec.paths` across all operations
2. Return sorted list of tag names with operation count per tag

**For `list_operations`:**
1. Iterate all `{method, path, operation}` triples from `app.state.openapi_spec.paths`
2. Apply filters: if `tag` provided, include only operations with matching tag; if `method` provided, include only matching HTTP method; if `keyword` provided, include only operations where operationId or summary contains the keyword (case-insensitive)
3. For each matching operation, return: `method`, `path`, `operationId`, `summary`, `tags`, and a `requires_confirmation` flag (looked up from the confirmation resolver)
4. Apply pagination (`page`, `page_size`); include `total_count`, `page`, `total_pages` in response
5. Sort results: `GET` operations before mutating operations; alphabetically by path within each method group

**For `get_operation_schema`:**
1. Look up `path` + `operation_method` in `app.state.openapi_spec.paths`; return `OperationNotFoundError` if absent
2. Return full operation object: `operationId`, `summary`, `description`, `parameters` (each with `name`, `in`, `required`, `schema`, `description`), `requestBody` schema (flattened to a list of field entries), and `responses` (status codes with schema)
3. Resolve `$ref` references within the spec before returning — the AI must receive fully-resolved schemas, not unresolved `$ref` pointers
4. Annotate response with `requires_confirmation: bool` and `confirmation_level: str|null` from the confirmation resolver

### Output
- `list_tags`: `{"tags": [{"name": str, "operation_count": int}, ...]}`
- `list_operations`: `{"operations": [...], "total_count": int, "page": int, "total_pages": int}`
- `get_operation_schema`: `{"path": str, "method": str, "operationId": str, "summary": str, "description": str, "parameters": [...], "request_body_fields": [...], "responses": {...}, "requires_confirmation": bool, "confirmation_level": str|null}`
- Error: `{"status": "error", "code": str, "message": str}`

### Acceptance Criteria
- [ ] AC-1: Given the spec is loaded, when `list_tags` is called, then all DCT domain tags are returned with accurate operation counts
- [ ] AC-2: Given `list_operations` with `tag="VDBs"` and `method="GET"`, then only GET operations tagged `VDBs` are returned, paginated correctly
- [ ] AC-3: Given `get_operation_schema` for `POST /vdbs/{vdbId}/delete`, then the response includes `requires_confirmation=true` and `confirmation_level="manual"`, and all path/query/body parameters are fully resolved (no `$ref` pointers)
- [ ] AC-4: Given `get_operation_schema` for a non-existent path, then `{"status": "error", "code": "OPERATION_NOT_FOUND"}` is returned
- [ ] AC-5: Given `list_operations` with a keyword that matches nothing, then `{"operations": [], "total_count": 0}` is returned without error

---

## FR-003: Execute Tool — Validate, Confirm, and Dispatch a DCT API Call

### Description
Provides an MCP tool named `execute` that accepts a DCT API path, HTTP method, and parameters/body; validates them against the cached spec; applies confirmation gates for destructive operations; and dispatches the API call via `DCTAPIClient`.

### Input
- `path` (string, required): DCT API path (e.g. `/vdbs/{vdbId}/refresh_by_timestamp`); path parameters may be provided inline (`/vdbs/vdb-123/...`) or via `path_params`
- `method` (string, required): HTTP method (`GET`, `POST`, `PATCH`, `DELETE`, `PUT`)
- `path_params` (object, optional): key-value pairs for path parameter substitution
- `query_params` (object, optional): key-value pairs for query string parameters
- `body` (object, optional): JSON request body
- `confirmed` (boolean, optional, default `false`): set to `true` to proceed through a pending confirmation gate

### Processing
1. Resolve path parameters: substitute `{paramName}` placeholders in `path` using `path_params`; raise `ParameterError` for missing required path params
2. Look up the operation in `app.state.openapi_spec.paths`; if not found, return `{"status": "error", "code": "OPERATION_NOT_FOUND"}`
3. Validate required parameters: check all `required: true` parameters from the spec are present in `path_params`, `query_params`, or `body`; return `{"status": "error", "code": "VALIDATION_ERROR", "missing_fields": [...]}` if any are absent
4. Check confirmation resolver: if the operation matches a rule in `manual_confirmation.txt` **and** `confirmed=false`, return `{"status": "confirmation_required", "confirmation_level": str, "message": str, "operation": {...}}`
5. Annotate the operation with read-only/destructive signal: GET methods → `operation_type="read"`; DELETE → `operation_type="destructive"`; POST/PATCH/PUT → `operation_type="mutating"`; include `operation_type` in all responses
6. Dispatch the call via `DCTAPIClient`: `await dct_client.request(method, resolved_path, params=query_params, json=body)`
7. On success: return `{"status": "success", "operation_type": str, "response": <DCT API response body>}`
8. On `DCTClientError`: return `{"status": "error", "code": "DCT_API_ERROR", "http_status": int, "message": str}`

### Output
- Confirmation required: `{"status": "confirmation_required", "confirmation_level": str, "message": str, "operation": {"path": str, "method": str}}`
- Success: `{"status": "success", "operation_type": "read|mutating|destructive", "response": <dict>}`
- Validation error: `{"status": "error", "code": "VALIDATION_ERROR", "missing_fields": [str]}`
- DCT API error: `{"status": "error", "code": "DCT_API_ERROR", "http_status": int, "message": str}`

### Acceptance Criteria
- [ ] AC-1: Given `path="/vdbs/{vdbId}/delete"`, `method="POST"`, `path_params={"vdbId": "vdb-123"}`, `confirmed=false`, then `{"status": "confirmation_required", "confirmation_level": "manual"}` is returned without making any HTTP call
- [ ] AC-2: Given the same call with `confirmed=true`, then the DELETE call is dispatched and `{"status": "success"}` is returned
- [ ] AC-3: Given a `GET /vdbs/search` call, then `{"status": "success", "operation_type": "read"}` is returned and no confirmation check is performed
- [ ] AC-4: Given a path with a missing required body field, then `{"status": "error", "code": "VALIDATION_ERROR", "missing_fields": [...]}` is returned before any HTTP call is made
- [ ] AC-5: Given a path that does not exist in the cached spec, then `{"status": "error", "code": "OPERATION_NOT_FOUND"}` is returned
- [ ] AC-6: Given a DCT API call that returns HTTP 404, then `{"status": "error", "code": "DCT_API_ERROR", "http_status": 404}` is returned

---

## FR-004: Confirmation Gate Resolver for 2-Tool Architecture

### Description
Implements a runtime confirmation resolver that checks whether a given HTTP method + path combination requires user confirmation before execution, using the existing `manual_confirmation.txt` rule set — preserving the full confirmation fidelity of the persona-based toolset model in the 2-tool architecture.

### Input
- `method` (string): HTTP method of the operation to check
- `path` (string): resolved API path (path parameters already substituted)
- `context` (dict, optional): additional context for conditional rules (e.g. `retention_days` for `retention_check:N` rules)

### Processing
1. Load `config/mappings/manual_confirmation.txt` rules via `config/loader.py` (already `@lru_cache`'d)
2. Iterate rules in order (first match wins); for each rule: check method match (`*` wildcard or exact), check path pattern match (supports `{paramName}` wildcard segments)
3. For `retention_check:N` rules: compare `context.get("retention_days")` against N; trigger only if retention < N
4. For `policy_impact_check:N` rules: compare `context.get("affected_object_count")` against N; trigger only if count > N
5. Return `{"requires_confirmation": bool, "confirmation_level": str|null, "message_template": str|null}`

### Output
- Match found: `{"requires_confirmation": true, "confirmation_level": "standard|elevated|manual", "message_template": str}`
- No match: `{"requires_confirmation": false, "confirmation_level": null, "message_template": null}`

### Acceptance Criteria
- [ ] AC-1: Given `method="POST"`, `path="/vdbs/vdb-123/delete"`, then `requires_confirmation=true` and `confirmation_level="manual"`
- [ ] AC-2: Given `method="GET"`, `path="/vdbs/search"`, then `requires_confirmation=false`
- [ ] AC-3: Given a `retention_check:7` rule and `context={"retention_days": 3}`, then `requires_confirmation=true`
- [ ] AC-4: Given a `retention_check:7` rule and `context={"retention_days": 30}`, then `requires_confirmation=false`
- [ ] AC-5: Given an unknown path not in any rule, then `requires_confirmation=false` is returned without error

---

## FR-005: LLM Evaluation Harness

### Description
Implements an evaluation harness that runs the top-10 common DCT workflows through both the Discovery + Execute tools and at least two frontier LLMs (Claude and GPT-4o or Gemini), records success/failure per step, and produces a structured report for the adopt/revert decision gate.

### Input
- `eval_scenarios` (list): the 10 pre-defined DCT workflow scenarios (e.g. provision VDB, refresh VDB, create bookmark, search environments)
- `models` (list): at least 2 model identifiers to run each scenario through
- `dct_base_url` (string): URL of the DCT instance for live execution
- `dct_api_key` (string): DCT API key for live execution
- `dry_run` (boolean, optional, default `false`): if true, evaluate Discovery schema quality without making live DCT API calls via Execute

### Processing
1. For each scenario in `eval_scenarios`, for each model: initialize a fresh conversation context with only the `discovery` and `execute` tools registered
2. Provide the scenario prompt to the LLM; allow the model up to 10 tool call turns to complete the scenario
3. Record: scenario name, model, steps taken, tools called, confirmation gates triggered, final status (`success|failure|partial`), and failure reason if applicable
4. Aggregate: overall success rate per model, per scenario success rate across models, confirmation gate fidelity rate (gates triggered / gates that should have been triggered)
5. Write results to `docs/DLPXECO-13984/DLPXECO-13984-eval-results.md` in the eval results format used by `check-structure.sh`

### Output
- Per-run record: `{"scenario": str, "model": str, "steps": int, "status": "success|failure|partial", "failure_reason": str|null}`
- Summary report: `{"overall_success_rate": float, "per_model": {...}, "confirmation_gate_fidelity": float, "recommendation": "adopt|revert|investigate"}`

### Acceptance Criteria
- [ ] AC-1: Given the 10 workflow scenarios run against Claude and one other frontier model, then a complete report is generated with per-scenario and per-model success rates
- [ ] AC-2: Given an overall success rate ≥ 80% across models, then the recommendation field is `"adopt"`
- [ ] AC-3: Given an overall success rate < 80%, then the recommendation field is `"investigate"` or `"revert"` with failure analysis
- [ ] AC-4: Given `dry_run=true`, then all 10 scenarios are evaluated for Discovery schema quality without making live DCT API calls
- [ ] AC-5: Confirmation gate fidelity rate is reported accurately — gates triggered exactly when expected and not triggered for read-only operations

---

## FR-006: Decision-Gate Report and Phase 2 Entry Criteria

### Description
Produces a structured decision-gate report summarizing Phase 1 validation results, including the adopt/revert recommendation, a migration plan for replacing persona-based toolsets with the 2-tool model (if adopted), and explicit Phase 2 entry criteria.

### Input
- LLM evaluation harness results from FR-005
- Spec quality audit results (OCTO scoring)
- Confirmation-gate fidelity assessment from FR-004
- Manual verification notes from testing with Claude Desktop / Cursor

### Processing
1. Aggregate all Phase 1 validation signals: LLM success rate, spec quality score, confirmation fidelity rate, and any edge case failures observed in manual testing
2. Apply the decision rule: if LLM success rate ≥ 80% AND confirmation fidelity ≥ 99% AND spec quality score above minimum threshold, recommend `adopt`; otherwise recommend `investigate` (50–80% success rate) or `revert` (< 50%)
3. If `adopt`: draft migration plan describing how persona-based toolsets would be deprecated (timeline, backward-compatibility window, communication plan)
4. Document Phase 2 entry criteria: Phase 1 `adopt` decision + PPM-1129 (vocabulary & domain model) completion required
5. Write report to `docs/DLPXECO-13984/DLPXECO-13984-decision-gate.md`

### Output
- `docs/DLPXECO-13984/DLPXECO-13984-decision-gate.md` with sections: Executive Summary, Validation Results, Recommendation, Migration Plan (if adopt), Phase 2 Entry Criteria, Risks and Open Items

### Acceptance Criteria
- [ ] AC-1: The decision-gate report exists at `docs/DLPXECO-13984/DLPXECO-13984-decision-gate.md` after Phase 1 validation completes
- [ ] AC-2: The report contains a clear `ADOPT`, `INVESTIGATE`, or `REVERT` recommendation with supporting quantitative evidence
- [ ] AC-3: If the recommendation is `ADOPT`, the migration plan section is non-empty and includes a backward-compatibility timeline
- [ ] AC-4: Phase 2 entry criteria explicitly state that both Phase 1 adopt decision AND PPM-1129 completion are required
- [ ] AC-5: The report cites the exact LLM success rates, confirmation fidelity rate, and spec quality score used to make the recommendation

---

## Quality Rules

| Rule | Description | Enforcement | Status | Evidence |
|------|-------------|-------------|--------|----------|
| API backward compatibility | Existing persona-based toolsets (`self_service`, `continuous_data_admin`, etc.) must continue to work identically; the 2-tool architecture is additive via a new `DCT_TOOLSET=dynamic` value | Integration test with each existing toolset after changes; CI check against all toolset `.txt` configs | Pending | |
| Spec-grounded only | Discovery and Execute must source all operation metadata from the cached spec — no hardcoded DCT paths outside of the spec download URL | Code review: grep for hardcoded `/vdbs/`, `/environments/`, etc. outside `dct_client/client.py` and the spec download path | Pending | |
| Confirmation fidelity | Every operation currently in `manual_confirmation.txt` must trigger the same confirmation level via the 2-tool confirmation resolver as via the persona-based tools | Automated test: iterate all rules in `manual_confirmation.txt`, call Execute for each with `confirmed=false`, assert correct `confirmation_level` | Pending | |
| @log_tool_execution applied | Both `discovery` and `execute` tool functions must be decorated with `@log_tool_execution` | Code review; startup smoke test to confirm telemetry records tool calls | Pending | |
| No secrets in logs | DCT API key, path parameter values for sensitive resources (e.g. credentials), and response bodies containing secrets must not appear in `dct_mcp_server.log` | grep CI step on log output during integration test; log redaction review | Pending | |
| Spec fallback non-blocking | Server startup must complete (with warning) even if the live spec download fails — bundled spec must always be available | Unit test: mock HTTP download failure at startup; assert server starts and logs `WARNING` | Pending | |

---

## Edge Cases

- EC-1: DCT instance returns a spec with 0 `paths` entries (empty spec) → Execute returns `OPERATION_NOT_FOUND` for all calls; Discovery `list_operations` returns empty list with `total_count=0`; server logs `WARNING: OpenAPI spec contains no paths`
- EC-2: Two concurrent Execute calls for the same destructive operation — one with `confirmed=false`, one with `confirmed=true` — arrive simultaneously → Each call is stateless; the confirmation check is evaluated independently per call with no shared state; both calls proceed independently based on their own `confirmed` flag
- EC-3: Path parameter substitution produces a path that still contains unresolved `{paramName}` placeholders (caller forgot to provide `path_params`) → Return `VALIDATION_ERROR` with `missing_path_params: [paramName]` before any HTTP call
- EC-4: DCT spec contains a `$ref` cycle (circular schema reference) → `get_operation_schema` detects the cycle, resolves up to depth 10, then emits a `schema_truncated: true` flag in the response rather than infinite recursion
- EC-5: `list_operations` with `page_size=50` and a spec with >1000 operations → Pagination handles all pages correctly; `total_count` accurately reflects the unfiltered count; no OOM on large specs
- EC-6: Spec download returns HTTP 401 (invalid API key) → Log error with `WARNING: spec download failed: HTTP 401`; fallback to bundled spec; do not expose the API key in the log message
- EC-7: `execute` called with `method="GET"` but the path only has a `POST` operation in the spec → Return `OPERATION_NOT_FOUND` with a helpful message listing the available methods for that path
- EC-8: `body` field passed to a `GET` operation → Log a `DEBUG` warning that GET requests do not use a request body; proceed with the request (some DCT GET endpoints accept query params that tools might incorrectly pass as body)
- EC-9: DCT API returns a non-JSON response (e.g. plain text error page) → `DCTAPIClient` raises `DCTClientError`; Execute returns `{"status": "error", "code": "DCT_API_ERROR", "http_status": int, "message": "Non-JSON response from DCT"}`
- EC-10: Spec cache file on disk is corrupted (truncated YAML) → Re-download from DCT instance; if re-download also fails, fall back to bundled spec

## Error Scenarios

- ERR-1: Server startup spec download times out after `DCT_TIMEOUT` seconds → Non-fatal: log `WARNING`; use bundled spec; server starts normally
- ERR-2: Bundled spec (`docs/api-external.yaml`) missing from package (corrupted install) → Fatal: raise `MCPError("SPEC_LOAD_FAILED")`; print actionable error message: "Reinstall dct-mcp-server — bundled spec is missing"
- ERR-3: `execute` dispatches a call, DCT returns HTTP 5xx → `DCTAPIClient` applies retry/backoff (up to `DCT_MAX_RETRIES`); after all retries exhausted, return `{"status": "error", "code": "DCT_API_ERROR", "http_status": 500, "message": "..."}`
- ERR-4: `execute` called with `confirmed=true` for an operation that has already completed (idempotency) → The DCT API handles idempotency; Execute does not track call history; response reflects whatever DCT returns (e.g. HTTP 404 "resource not found" → `DCT_API_ERROR`)
- ERR-5: LLM evaluation harness loses connection to DCT mid-run → Remaining scenarios are marked `failure` with reason `DCT_UNREACHABLE`; completed scenarios are preserved; partial report is written
- ERR-6: `get_operation_schema` resolves a `$ref` that points to a schema not defined in the spec's `components` section → Return `{"status": "error", "code": "SCHEMA_REF_NOT_FOUND", "ref": str}` for that field; remaining fields are still returned

## Performance Considerations

- Spec load at startup must complete in ≤ 5 seconds under normal network conditions (1 Gbps LAN); the bundled fallback path must complete in ≤ 1 second
- In-memory spec dict must support ≥ 500 operations (typical DCT spec) without measurable startup overhead beyond the 5-second budget
- `list_operations` with no filters on a 500-operation spec must return in < 100ms (in-memory iteration only, no I/O)
- `get_operation_schema` `$ref` resolution for schemas with up to 5 levels of nesting must complete in < 50ms
- The LLM evaluation harness is explicitly a developer-time tool (not on the server hot path) — no latency budget applies; throughput target is running all 10 scenarios in < 30 minutes total wall time
- Discovery responses must not include the entire spec in a single payload — pagination is mandatory for `list_operations` to avoid LLM context window saturation (max 50 operations per page)
- `execute` adds at most 10ms overhead over a raw `DCTAPIClient` call (validation + confirmation check); the DCT API call itself is the dominant latency

---
<!-- Cross-reference:
     FR-001 (Spec Cache) → G2, SC5
     FR-002 (Discovery) → G3, SC2
     FR-003 (Execute) → G4, SC1, SC3
     FR-004 (Confirmation Resolver) → SC3
     FR-005 (LLM Eval Harness) → G5, SC4
     FR-006 (Decision Gate) → G6, SC6
     Quality Rules address Constraints and Risks from vision.md
-->
