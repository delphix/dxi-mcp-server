# Functional Specification: DLPXECO-13985

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13985
**Generated from**: Acceptance criteria in Jira ticket (AC-1, AC-2) and vision Goals (G1–G4)

<!-- FR granularity: Each FR is one verifiable capability, testable independently in isolation. -->

---

## FR-001: Produce Architecture Design Document for 3-Tool Dynamic Mode

### Description
Produces a formal architecture design document (`.docx`) covering the List/Get/Execute tool model, the OpenAPI spec download-and-cache strategy, request/response schemas, confirmation gate flow, RBAC model, and LLM evaluation methodology — ready for PM and Ecosystem team sign-off before any implementation work begins.

### Input
- DCT OpenAPI spec endpoint: `{DCT_BASE_URL}/dct/static/api-external.yaml` (reference only, for schema understanding)
- Existing codebase: `src/dct_mcp_server/` architecture (tool patterns, confirmation rules, client behavior)
- Jira ticket DLPXECO-13985 requirements and PPM-1174 source context
- Stakeholder requirements: PM (Nick/Geeta) and Ecosystem team review criteria

### Processing
1. Analyse the existing grouped tool pattern and auto mode to understand current architecture baseline
2. Define the three tool responsibilities:
   - **List**: Reads the cached OpenAPI spec, returns a structured list of all available operation IDs, HTTP methods, paths, and one-line summaries; never returns full schemas to avoid token bloat
   - **Get**: Accepts an operation ID or path+method; returns the full operation schema (parameters, request body, response schemas, description) from the cached spec
   - **Execute**: Accepts an operation ID or path+method, a parameters dict, and an optional request body; validates inputs against the Get-returned schema; routes through the existing confirmation gate and RBAC checks; dispatches via `DCTAPIClient`; returns the raw DCT API response
3. Define the OpenAPI spec download-and-cache strategy:
   - On startup: attempt download from `{DCT_BASE_URL}/dct/static/api-external.yaml`; on success, write to `$TEMP/dct_mcp_tools/spec-cache.yaml` with a DCT version tag
   - On download failure: fall back to bundled `docs/api-external.yaml` shipped with the package
   - Cache TTL: spec is refreshed at server startup only; a `refresh_spec` meta-action on the Execute tool allows on-demand refresh
   - Version tracking: log spec version (DCT release tag from spec `info.version`) at startup
4. Define request/response schemas for all three tools (JSON Schema format)
5. Map the confirmation gate flow: Execute tool pre-checks every request path against `manual_confirmation.txt` rule engine before dispatching; returns `{"status": "confirmation_required", ...}` for matched rules; re-call with `confirmed=True` executes
6. Define RBAC model: Execute tool passes the API key through `DCTAPIClient` unchanged; DCT server enforces RBAC; MCP server does not replicate permission checks
7. Define LLM evaluation methodology: test matrix covering List→Get→Execute chained interactions, destructive operation confirmation flow, spec-unavailable fallback, and malformed-request self-correction
8. Produce the `.docx` document using the architecture decisions above
9. Attach / link the document to Jira epic DLPXECO-13984

### Output
- Success: `docs/DLPXECO-13985-architecture-design.docx` — complete design document with all six areas covered and no placeholder sections
- Failure (missing section): document flagged as incomplete; blocked from PM review until gap is filled
- Side effect: Design document linked from Jira epic DLPXECO-13984

### Acceptance Criteria
- [ ] AC-1: Given the DLPXECO-13985 scope, when the design document is published, then it explicitly covers all six areas: tool responsibilities, OpenAPI spec download-and-cache strategy, request/response schemas, confirmation gate flow, RBAC model, and LLM evaluation methodology — with no section left as a placeholder or stub
- [ ] AC-2: Given the design document, when reviewed by PM (Nick/Geeta) and the Ecosystem team, then it has explicit sign-off recorded as a comment on the epic (DLPXECO-13984) before any implementation ticket is opened

---

## FR-002: Define List Tool — DCT API Operation Discovery

### Description
Defines the `list_dct_operations` MCP tool that reads the cached OpenAPI spec and returns a paginated, filterable catalogue of all DCT API operations (operation ID, method, path, summary) without returning full schemas, keeping LLM context token usage bounded.

### Input
- `filter` (string, optional): substring filter applied to operation ID, path, or summary; default returns all operations
- `tag` (string, optional): OpenAPI tag to filter by (e.g., `"VDBs"`, `"Environments"`)
- `page` (integer, optional, default 1): page number for pagination
- `page_size` (integer, optional, default 50): operations per page; maximum 200

### Processing
1. Load the cached OpenAPI spec from `$TEMP/dct_mcp_tools/spec-cache.yaml`; if absent, load bundled fallback spec
2. Parse all paths and operations from the spec's `paths` object
3. If `filter` is provided: include only operations where `operationId`, `path`, or `summary` contains the filter string (case-insensitive)
4. If `tag` is provided: include only operations whose `tags` array contains the specified tag
5. Sort results alphabetically by `operationId`
6. Apply pagination: return slice `[(page-1)*page_size : page*page_size]`
7. Return a structured list: `[{operationId, method, path, summary, tags}]`

### Output
- Success: JSON object `{operations: [{operationId, method, path, summary, tags}], total_count, page, page_size, spec_version}`
- Failure (spec not loaded): `{"status": "error", "code": "SPEC_UNAVAILABLE", "message": "OpenAPI spec could not be loaded from cache or fallback"}`
- Failure (invalid page): `{"status": "error", "code": "INVALID_PAGE", "message": "page must be >= 1"}`

### Acceptance Criteria
- [ ] AC-1: Given a healthy DCT server and a downloaded spec, when `list_dct_operations()` is called with no filters, then it returns all operations with `operationId`, `method`, `path`, `summary`, and `tags` for each — and `total_count` matches the actual number of paths in the spec
- [ ] AC-2: Given the filter `"vdb"`, when `list_dct_operations(filter="vdb")` is called, then only operations whose operationId, path, or summary contains "vdb" (case-insensitive) are returned
- [ ] AC-3: Given the spec is unavailable (cache missing and download failed), when `list_dct_operations()` is called, then it returns `status=error, code=SPEC_UNAVAILABLE` and does not raise an unhandled exception
- [ ] AC-4: Given `page_size=50`, when the spec contains 300 operations and `page=2` is requested, then exactly 50 operations are returned (items 51–100)

---

## FR-003: Define Get Tool — DCT Operation Schema Retrieval

### Description
Defines the `get_dct_operation` MCP tool that returns the full OpenAPI schema for a single DCT API operation (parameters, request body schema, response schemas, description), giving the LLM the exact contract needed to construct a valid Execute call.

### Input
- `operation_id` (string, optional): the OpenAPI `operationId` to look up (e.g., `"listVDBs"`)
- `method` (string, optional): HTTP method (`GET`, `POST`, `PUT`, `DELETE`, `PATCH`) — used together with `path` as an alternative to `operation_id`
- `path` (string, optional): API path (e.g., `"/vdbs/{vdbId}"`) — used together with `method`
- Constraint: exactly one of (`operation_id`) or (`method` + `path`) must be provided

### Processing
1. Load cached spec (same strategy as FR-002)
2. If `operation_id` is provided: scan all operations for a matching `operationId`; return `NOT_FOUND` if absent
3. If `method` + `path` is provided: look up `paths[path][method.lower()]`; return `NOT_FOUND` if absent
4. Extract and return the full operation object: `{operationId, method, path, summary, description, parameters, requestBody, responses, tags, security}`
5. Resolve any `$ref` references in parameters or requestBody schemas so the LLM receives a fully dereferenced schema
6. Include a `confirmation_required` flag set to `true` if the operation matches any rule in `manual_confirmation.txt` (checked without executing)

### Output
- Success: JSON object with the fully dereferenced operation schema plus `confirmation_required` (boolean) and `spec_version`
- Failure (not found): `{"status": "error", "code": "OPERATION_NOT_FOUND", "operationId": "...", "suggestion": "Call list_dct_operations to browse available operations"}`
- Failure (ambiguous input): `{"status": "error", "code": "AMBIGUOUS_INPUT", "message": "Provide either operation_id or both method and path"}`

### Acceptance Criteria
- [ ] AC-1: Given `operationId="searchVDBs"` exists in the spec, when `get_dct_operation(operation_id="searchVDBs")` is called, then the full operation schema including all `$ref`-resolved parameters and requestBody is returned with no unresolved `$ref` tokens
- [ ] AC-2: Given `method="DELETE"` and `path="/vdbs/{vdbId}"`, when `get_dct_operation(method="DELETE", path="/vdbs/{vdbId}")` is called, then `confirmation_required=true` is present in the response (because delete operations match manual_confirmation.txt rules)
- [ ] AC-3: Given an operationId that does not exist in the spec, when `get_dct_operation(operation_id="nonExistentOp")` is called, then `status=error, code=OPERATION_NOT_FOUND` is returned with a suggestion to call list_dct_operations
- [ ] AC-4: Given neither `operation_id` nor `method+path` is provided, when `get_dct_operation()` is called, then `status=error, code=AMBIGUOUS_INPUT` is returned immediately without spec lookup

---

## FR-004: Define Execute Tool — DCT API Dispatch with Safety Controls

### Description
Defines the `execute_dct_operation` MCP tool that validates an LLM-constructed API call against the OpenAPI schema, runs it through the existing confirmation gate, and dispatches it via `DCTAPIClient` — returning the DCT API response. This is the only tool that makes network calls to DCT.

### Input
- `operation_id` (string, optional): the OpenAPI `operationId` to execute
- `method` (string, optional): HTTP method — used with `path` as alternative to `operation_id`
- `path` (string, optional): API path with path parameters already substituted (e.g., `"/vdbs/vdb-123"`)
- `query_params` (object, optional): key-value map of query string parameters
- `request_body` (object, optional): JSON request body; must conform to the operation's requestBody schema
- `path_params` (object, optional): key-value map of path parameters for template substitution if `path` contains `{paramName}` tokens
- `confirmed` (boolean, optional, default false): set to `true` to execute a previously confirmed destructive operation

### Processing
1. Resolve the operation: look up by `operation_id` or `method+path` in the cached spec (same as FR-003 step 2–3)
2. Validate `request_body` and `query_params` against the resolved operation schema; return a structured validation error if any required parameter is missing or a type mismatch is detected
3. Substitute `path_params` into the path template if present
4. Check confirmation gate: pass `method`, resolved-path against `manual_confirmation.txt`; if matched and `confirmed=false`, return `{"status": "confirmation_required", "confirmation_level": "...", "message": "...", "operation": {...}}`
5. If gate passes or `confirmed=true`: invoke `DCTAPIClient.request(method, path, query_params, request_body)`
6. Return the DCT API response body as-is, with an added `_mcp_meta` envelope: `{status, http_status_code, operation_id, spec_version}`
7. On `DCTClientError`: return `{"status": "error", "code": "DCT_CLIENT_ERROR", "http_status": ..., "detail": ...}` — do not raise unhandled exceptions

### Output
- Success: `{status: "success", http_status_code: 200, data: <DCT API response body>, _mcp_meta: {...}}`
- Confirmation required: `{status: "confirmation_required", confirmation_level: "...", message: "...", operation: {method, path, operation_id}}`
- Validation error: `{status: "error", code: "VALIDATION_ERROR", errors: [{field, issue, expected}]}`
- DCT API error: `{status: "error", code: "DCT_CLIENT_ERROR", http_status: ..., detail: "..."}`
- Spec unavailable: `{status: "error", code: "SPEC_UNAVAILABLE", message: "..."}`

### Acceptance Criteria
- [ ] AC-1: Given a valid `operationId="searchVDBs"` and a conformant `request_body`, when `execute_dct_operation()` is called, then the request is dispatched to DCT and the DCT response is returned wrapped in `_mcp_meta`
- [ ] AC-2: Given `operationId="deleteVDB"` (a destructive operation), when `execute_dct_operation(confirmed=False)` is called, then `status=confirmation_required` is returned with `confirmation_level=manual` and the operation is NOT dispatched to DCT
- [ ] AC-3: Given `operationId="deleteVDB"`, when `execute_dct_operation(confirmed=True)` is called after viewing the confirmation prompt, then the DELETE request IS dispatched to DCT and the response is returned
- [ ] AC-4: Given a `request_body` missing a required field (per the OpenAPI schema), when `execute_dct_operation()` is called, then `status=error, code=VALIDATION_ERROR` is returned with field-level error details before any DCT network call is made
- [ ] AC-5: Given the DCT server returns HTTP 403, when `execute_dct_operation()` dispatches the call, then `status=error, code=DCT_CLIENT_ERROR, http_status=403` is returned and no unhandled Python exception is raised

---

## FR-005: Define OpenAPI Spec Download-and-Cache Strategy

### Description
Specifies how the MCP server downloads, caches, validates, and refreshes the DCT OpenAPI spec to back the List, Get, and Execute tools — ensuring availability even when the DCT host is unreachable at startup.

### Input
- `DCT_BASE_URL` env var: base URL of the DCT instance (no `/dct` suffix)
- Spec endpoint: `{DCT_BASE_URL}/dct/static/api-external.yaml`
- Cache path: `$TEMP/dct_mcp_tools/spec-cache.yaml`
- Bundled fallback: `docs/api-external.yaml` (shipped with the package)

### Processing
1. At MCP server startup (in the FastMCP lifespan `__aenter__`):
   a. Attempt GET `{DCT_BASE_URL}/dct/static/api-external.yaml` with `DCT_TIMEOUT` and `DCT_VERIFY_SSL` settings
   b. On success (HTTP 200): parse YAML, validate it is a valid OpenAPI 3.x document (has `openapi`, `info`, `paths` keys); write to `$TEMP/dct_mcp_tools/spec-cache.yaml`; log `spec_version` from `info.version`
   c. On download failure (network error, non-200, parse error): log a WARNING; check if `spec-cache.yaml` already exists from a prior run; if yes, load from cache; if no, load bundled fallback; log which fallback was used
   d. After loading (any source): set `_spec_loaded = True` and store parsed spec in memory
2. On-demand refresh: Execute tool supports `operation_id="refresh_spec"` as a reserved meta-action; repeats steps 1a–1d without restarting the server
3. Cache invalidation: no TTL — spec is refreshed only at startup or via explicit meta-action; DCT API version is tracked via the spec `info.version` field

### Output
- Success: spec loaded into memory; `spec_version` logged at INFO level; `_spec_loaded=True`
- Fallback (cache hit): spec loaded from prior cached file; log at WARNING `"Using cached spec from previous run — version may be stale"`
- Fallback (bundled): spec loaded from bundled `docs/api-external.yaml`; log at WARNING `"Using bundled fallback spec — version may not match live DCT"`
- Failure (all sources exhausted): log at ERROR; `_spec_loaded=False`; all three tools return `SPEC_UNAVAILABLE`

### Acceptance Criteria
- [ ] AC-1: Given `DCT_BASE_URL` points to a reachable DCT instance, when the MCP server starts, then the spec is downloaded, parsed, and the `info.version` value is logged at INFO level
- [ ] AC-2: Given the DCT host is unreachable at startup but a prior `spec-cache.yaml` exists, when the server starts, then the cached spec is loaded and a WARNING is logged indicating stale spec usage
- [ ] AC-3: Given neither the DCT host nor the cache is available, when the server starts, then the bundled `docs/api-external.yaml` is loaded, a WARNING is logged, and the three tools remain functional (using bundled spec)
- [ ] AC-4: Given `execute_dct_operation(operation_id="refresh_spec")` is called, when the DCT host is reachable, then the spec is re-downloaded and the in-memory copy is updated without restarting the server

---

## FR-006: Define Comparison Table — Dynamic Mode vs Auto Mode

### Description
Produces a structured comparison table in the design document contrasting the 3-tool Dynamic mode against the existing Auto mode across key dimensions: token economics, tool count, latency, maintenance burden, security posture, and client compatibility — culminating in a recommended approach.

### Input
- Existing Auto mode behavior: 5 meta-tools at startup; AI enables toolsets dynamically; pre-built grouped tool modules
- Proposed Dynamic mode behavior: 3 tools (List, Get, Execute); live OpenAPI spec; no pre-mapped tool modules needed
- Token economics data: estimated tokens consumed per typical LLM interaction in each mode

### Processing
1. Enumerate comparison dimensions:
   - **Tool count exposed to LLM**: Auto = 5 meta + up to N toolset-specific tools; Dynamic = always 3
   - **Token cost (List call)**: Dynamic mode sends operation summaries only (estimated 100–500 tokens for filtered list); Auto mode sends full toolset tool descriptions at enable time (estimated 500–2000 tokens per toolset)
   - **Token cost (Get call)**: Dynamic mode sends one operation schema (estimated 200–800 tokens); Auto mode sends full grouped tool schema for the resource domain (estimated 300–1200 tokens)
   - **Token cost (Execute call)**: similar in both modes — request payload + response body
   - **Maintenance burden**: Auto mode requires updating Python tool files + toolset `.txt` configs for each new DCT endpoint; Dynamic mode requires no code changes when DCT adds endpoints
   - **Latency**: Dynamic mode adds one extra LLM round-trip (List then Get before Execute) for unknown endpoints; Auto mode allows direct calls for known grouped tool actions
   - **Security posture**: both modes route through `DCTAPIClient` and confirmation gates; Dynamic mode has additional schema validation at Execute time
   - **Client compatibility**: both modes work with all MCP clients; Dynamic mode has no `tools/list_changed` notifications needed
2. Write the table in Markdown and include it in the `.docx` design document
3. State the recommended approach with rationale (token efficiency vs. maintenance trade-off)

### Output
- Section in design document: `## Dynamic Mode vs Auto Mode — Comparison` containing the full table and a `### Recommendation` subsection

### Acceptance Criteria
- [ ] AC-1: Given the design document is published, when the comparison table is reviewed, then it contains at minimum: tool count, token cost per interaction (with numeric estimates), maintenance burden, latency impact, security posture, and client compatibility — with concrete values or ranges, not vague descriptions
- [ ] AC-2: Given the comparison table, when the `### Recommendation` subsection is read, then it clearly states which mode is preferred and why, referencing at least two dimensions from the table as justification

---

## Quality Rules

| Rule | Description | Enforcement | Status | Evidence |
|------|-------------|-------------|--------|----------|
| QR-1: API backward compatibility preserved | The design must not break existing toolset modes (`self_service`, `auto`, etc.); Dynamic mode is additive via a new `DCT_TOOLSET=dynamic` value | Design review checklist item: confirm `DCT_TOOLSET` value list is additive only; no existing toolset removed | Pending | — |
| QR-2: Migration path provided | The design document must include a section describing how operators migrate from Auto mode to Dynamic mode (env var change, restart procedure, spec-cache pre-warm) | Design review checklist item: migration section present and non-empty | Pending | — |
| QR-3: No new unauthenticated attack surface | The Execute tool must route all DCT API calls through `DCTAPIClient` (with API key auth); the design must explicitly state that the Execute tool cannot be used to call arbitrary external URLs | Security review checklist during design sign-off | Pending | — |
| QR-4: Confirmation gate parity | The Execute tool's confirmation behavior must be functionally identical to the existing grouped tool pattern for all operations covered by `manual_confirmation.txt` | Design review: confirmation gate flow section maps to every confirmation level in `manual_confirmation.txt` | Pending | — |
| QR-5: Spec validation before use | The design must specify that downloaded or cached specs are validated as OpenAPI 3.x before use; malformed specs must fall back gracefully | Design review: spec download-and-cache strategy section includes validation step | Pending | — |

---

## Edge Cases

- EC-1: OpenAPI spec `info.version` field is absent or malformed → log at WARNING with message "spec version unknown"; continue loading spec normally; tools remain functional
- EC-2: DCT API returns a path in the spec that contains unresolved `$ref` cycles → Get tool detects the cycle after 10 dereference levels and returns `{"status": "error", "code": "SCHEMA_PARSE_ERROR", "detail": "circular $ref detected at <path>"}` rather than hanging
- EC-3: LLM calls Execute with a path that is valid in the spec but not reachable in the specific DCT instance (endpoint added in a newer DCT version than deployed) → DCT returns 404; Execute tool propagates `{"status": "error", "code": "DCT_CLIENT_ERROR", "http_status": 404, ...}`; design must note this is expected behavior
- EC-4: Two concurrent Execute calls for the same destructive operation (e.g., delete the same VDB) — one with `confirmed=True`, one without → each call independently evaluated against the confirmation gate; the unconfirmed call returns `confirmation_required`; the confirmed call proceeds; no shared state between concurrent requests
- EC-5: Spec cache file is corrupted (e.g., partial write due to disk full during prior refresh) → YAML parser raises an exception; server falls back to bundled spec and logs at ERROR; no startup crash
- EC-6: `page_size` parameter for List tool set to 0 or negative → return `{"status": "error", "code": "INVALID_PAGE", "message": "page_size must be >= 1 and <= 200"}`
- EC-7: Execute called with `path_params` containing an injection attempt (e.g., `{"vdbId": "../../../etc/passwd"}`) → the value is URL-encoded by `DCTAPIClient`; DCT API returns 404 or 400; no server-side path traversal vulnerability
- EC-8: List tool called with both `filter` and `tag` → both filters are AND-combined; only operations matching both filter substring AND the specified tag are returned
- EC-9: Spec downloaded successfully but DCT server returns an HTML error page instead of YAML (reverse proxy auth redirect) → YAML parser fails; server logs WARNING and falls back to cached/bundled spec

## Error Scenarios

- ERR-1: DCT host times out during spec download at startup → `DCTAPIClient` respects `DCT_TIMEOUT`; after timeout, fallback chain (cache → bundled) activates; startup completes without blocking indefinitely
- ERR-2: `$TEMP/dct_mcp_tools/` directory does not exist or is not writable → spec download succeeds but cache write fails; server logs WARNING and continues with in-memory spec only; next startup will re-download
- ERR-3: Execute call dispatched to DCT returns HTTP 5xx → `DCTAPIClient` retries up to `DCT_MAX_RETRIES` times with exponential backoff; if all retries exhausted, returns `{"status": "error", "code": "DCT_CLIENT_ERROR", "http_status": 503, "detail": "max retries exceeded"}`
- ERR-4: Execute call with `confirmed=True` on an operation that is not in the confirmation gate → the confirmed flag is ignored harmlessly; the operation proceeds normally (no error for superfluous confirmed flag)
- ERR-5: Get tool called while spec is being refreshed concurrently (via refresh_spec meta-action) → design must specify that spec is loaded atomically (swap reference after successful parse); in-flight Get calls use the prior spec version; no partial-spec state visible to callers
- ERR-6: LLM sends an operationId that matches a path in the spec but the path's HTTP method does not exist (e.g., `GET /vdbs/{vdbId}/refresh`) → Get returns `NOT_FOUND`; LLM should retry with `list_dct_operations` to discover the correct method

## Performance Considerations

- The List tool must complete within 500ms for a spec containing up to 1000 operations (local parse + filter, no network call); pagination ensures response payload stays bounded
- The Get tool must complete within 200ms for schema retrieval and $ref resolution (local parse, no network call); recursive $ref resolution depth is capped at 10 to prevent unbounded processing
- The Execute tool's pre-dispatch validation must add no more than 50ms overhead above the raw DCT API call latency; schema validation is performed against the in-memory parsed spec, not re-parsing from disk
- Spec refresh (on-demand via refresh_spec meta-action) is permitted to take up to `DCT_TIMEOUT` seconds; it must not block concurrent List/Get/Execute calls — spec is updated atomically via reference swap after successful download and parse
- Token budget design targets: List result (50 ops, no filter) ≈ 1500–3000 tokens; Get for a single operation ≈ 500–1500 tokens; Execute response ≈ depends on DCT API response payload; combined List+Get+Execute for a typical workflow ≈ 3000–7000 tokens vs Auto mode estimate of 4000–8000 tokens per equivalent workflow

---
<!-- Cross-reference: FR-001 → G3 (design doc); FR-002 → G1 (List tool); FR-003 → G1 (Get tool); FR-004 → G1 (Execute tool); FR-005 → G2 (cache strategy); FR-006 → G4 (comparison table).
     SC-1 satisfied by FR-001 AC-1; SC-2 satisfied by FR-006 AC-1; SC-3 satisfied by FR-001 AC-2; SC-4 by FR-001; SC-5 by FR-004 AC-2,3. -->
