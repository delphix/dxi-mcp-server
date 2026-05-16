# Feature Design: DLPXECO-13985

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13985
**Status**: Proposed
<!-- Guidance: H1 title must be exactly "Feature Design: $NAME" (not H2). check-structure.sh does not enforce this mechanically, but downstream review tooling relies on it. -->

---

## Summary

This feature produces a formal architecture design document for a **3-tool Dynamic API mode** for the DCT MCP Server — introducing `list_dct_operations`, `get_dct_operation`, and `execute_dct_operation` as an opt-in `DCT_TOOLSET=dynamic` value. The design covers all six required areas (tool responsibilities, OpenAPI spec download-and-cache strategy, request/response schemas, confirmation gate flow, RBAC model, and LLM evaluation methodology) and includes a comparison table against the existing Auto mode. No implementation code is produced by this story; the deliverable is a `.docx` design document ready for PM (Nick/Geeta) and Ecosystem team sign-off as a prerequisite for the implementation epic (DLPXECO-13984). The design must integrate cleanly with the current architecture — existing toolset modes (`self_service`, `auto`, etc.) are unchanged.

## Affected Components

<!-- Derived from architecture.md layer map. Ticked components are touched by this design-doc feature only (generating docs/ artefacts). No production source files are modified by this story — those changes belong to the implementation epic. -->

- [ ] `main.py` — Entry point; lifespan, FastMCP setup (referenced in design; no changes in this story)
- [ ] `toolsgenerator/driver.py` — OpenAPI spec processor (referenced in cache strategy design)
- [ ] `tools/__init__.py` — Dynamic tool registration (referenced in dynamic mode section)
- [ ] `tools/core/meta_tools.py` — Auto-mode meta-tools (referenced in comparison table)
- [ ] `tools/core/tool_factory.py` — Runtime tool generation from OpenAPI spec (referenced in dynamic mode section)
- [ ] `tools/*_endpoints_tool.py` — Pre-built grouped tools (referenced as fallback pattern)
- [ ] `config/config.py` — Env var loading/validation (new `DCT_TOOLSET=dynamic` value referenced)
- [ ] `config/loader.py` — Toolset + confirmation rule loading (confirmation gate reuse referenced)
- [ ] `config/toolsets/*.txt` — Persona toolset definitions (no changes; dynamic mode bypasses these)
- [ ] `config/mappings/manual_confirmation.txt` — Confirmation rules (reused unchanged by Execute tool)
- [ ] `dct_client/client.py` — Async HTTP client with retry/backoff (reused unchanged by Execute tool)
- [ ] `core/logging.py`, `core/session.py`, `core/decorators.py`, `core/exceptions.py` — Infrastructure (reused unchanged)
- [x] `docs/DLPXECO-13985-architecture-design.docx` — New: formal design document (primary deliverable)
- [x] `docs/DLPXECO-13985-design.md` — New: machine-readable design spec (this file)

## Architecture Changes

### Schema / Config Changes

<!-- This story produces a design document only. The table below describes configuration changes that the implementation epic will introduce, so reviewers understand the full surface area of the design being signed off on. -->

| Field / Config Change | Type | Object / Location | Notes |
|----------------------|------|-------------------|-------|
| `DCT_TOOLSET=dynamic` | string enum value | `config/config.py` | New opt-in value; additive only — does not remove or alter existing values |
| `spec-cache.yaml` | YAML file | `$TEMP/dct_mcp_tools/spec-cache.yaml` | Written at startup on successful spec download; read by all three dynamic tools |
| Bundled fallback spec | YAML file | `docs/api-external.yaml` | Already present; also used as fallback in existing dynamic tool generation — no schema change, referenced by design |
| `_spec_loaded` | boolean flag | In-memory, module-level in dynamic tools module | Tracks whether spec is available; controls `SPEC_UNAVAILABLE` error path |
| `spec_version` | string | Logged at INFO level, included in all three tool responses | Sourced from `info.version` in the downloaded/cached OpenAPI spec |

### Source Files to Modify

<!-- This is a design-document-only story. No production source files are modified in this ticket.
     The table lists the files the IMPLEMENTATION epic (DLPXECO-13984) will need to create or change,
     derived from the functional requirements. This is intentionally forward-looking for design review. -->

| File | Purpose | Maps to FR |
|------|---------|------------|
| `docs/DLPXECO-13985-architecture-design.docx` | **Primary deliverable** — formal architecture design document covering all six required areas (tool responsibilities, OpenAPI spec download-and-cache strategy, request/response schemas, confirmation gate flow, RBAC model, LLM evaluation methodology) plus comparison table vs Auto mode | FR-001, FR-002, FR-003, FR-004, FR-005, FR-006 |
| `docs/DLPXECO-13985-design.md` | Machine-readable design spec for workflow tooling (this file) | FR-001 through FR-006 |
| *(implementation epic)* `src/dct_mcp_server/tools/dynamic_tool.py` | New file — `list_dct_operations`, `get_dct_operation`, `execute_dct_operation` tool implementations | FR-002, FR-003, FR-004 |
| *(implementation epic)* `src/dct_mcp_server/tools/core/spec_cache.py` | New file — OpenAPI spec download, cache read/write, YAML parse/validate, $ref resolution | FR-005 |
| *(implementation epic)* `src/dct_mcp_server/config/config.py` | Add `dynamic` to the `DCT_TOOLSET` enum; validate at startup | FR-001, FR-005 |
| *(implementation epic)* `src/dct_mcp_server/tools/__init__.py` | Register dynamic tools when `DCT_TOOLSET=dynamic`; skip persona-based toolset loading | FR-002, FR-003, FR-004 |
| *(implementation epic)* `src/dct_mcp_server/main.py` | Call spec download/cache during FastMCP lifespan `__aenter__`; pass spec handle to dynamic tools | FR-005 |

### New Files (if any)

Documents produced by this story:
- `docs/DLPXECO-13985-architecture-design.docx` — Primary deliverable: formal design document (all six coverage areas)

Files the implementation epic will create (design-only reference):
- `src/dct_mcp_server/tools/dynamic_tool.py` — List, Get, Execute tool implementations
- `src/dct_mcp_server/tools/core/spec_cache.py` — Spec download-and-cache module with atomic in-memory swap

## Version Compatibility

<!-- The DCT MCP Server is a Python 3.11+ package targeting multiple DCT API versions.
     "Dynamic mode" is purely additive and does not alter behaviour for any existing DCT version.
     DCT API version compatibility is determined at runtime by which OpenAPI spec is loaded (live download vs bundled fallback). -->

| Version / Runtime | Supported? | Branch? | Notes |
|-------------------|-----------|---------|-------|
| Python 3.11 | Yes | No | Minimum supported runtime; all dynamic tool code must be compatible |
| Python 3.12 | Yes | No | Tested runtime; no branching required |
| FastMCP 2.13.2+ | Yes | No | Required framework version; no changes to MCP transport layer |
| DCT API (any version with OpenAPI spec) | Yes | No | Spec is downloaded from the live DCT host at startup; spec version drives tool discovery at runtime |
| DCT API (unreachable at startup) | Yes | No | Fallback to cached or bundled spec; tools remain functional with potentially stale schema |
| Existing toolsets (`self_service`, `auto`, etc.) | Yes (unchanged) | No | Dynamic mode is opt-in via `DCT_TOOLSET=dynamic`; all existing modes unaffected |

## Platform Behavior Notes

<!-- Cross-referenced against architecture.md ## Key Platform Behaviors -->

- **API key prefix (`apk `)** — Affects: `DCTAPIClient` prepends `apk ` automatically; the Execute tool must not modify the API key or introduce a second auth header. Design specifies Execute dispatches all requests through the unmodified `DCTAPIClient`.
- **SSL verification off by default** — Affects: spec download at startup uses the same `DCT_VERIFY_SSL` env var as all other DCT API calls; design specifies the spec download call passes `verify=DCT_VERIFY_SSL` to `httpx`.
- **Retry / exponential backoff** — Affects: spec download at startup uses `DCTAPIClient` retry logic (`DCT_MAX_RETRIES`); after exhausting retries, fallback chain (cache → bundled) activates. Execute tool dispatches through `DCTAPIClient`, so retries apply identically to existing grouped tool pattern.
- **Toolset config cache (`@lru_cache` in `loader.py`)** — N/A: Dynamic mode does not use `config/toolsets/*.txt` files or `loader.py` toolset parsing; confirmation rules in `manual_confirmation.txt` are still loaded via `loader.py` (its `@lru_cache` is unaffected).
- **Telemetry (opt-in)** — Affects: Execute tool must be decorated with `@log_tool_execution` so telemetry session logging applies identically to the dynamic tools as to existing grouped tools.
- **`$TEMP/dct_mcp_tools/` directory** — Affects: existing dynamic tool generation writes generated modules here; the spec cache also writes `spec-cache.yaml` to this directory. Design specifies the directory is created if absent at startup; write failure is non-fatal (WARNING logged, in-memory spec used).

## Architecture Design — Content Outline for `.docx` Deliverable

<!-- This section enumerates exactly what the `.docx` design document must cover, mapped to FR-001 AC-1.
     It serves as the review checklist for PM and Ecosystem team sign-off. -->

### 1. Tool Responsibilities

**List tool (`list_dct_operations`)**
- Reads cached OpenAPI spec in memory; no DCT network calls
- Returns paginated, filterable catalogue: `[{operationId, method, path, summary, tags}]`
- Inputs: `filter` (substring, case-insensitive over operationId/path/summary), `tag` (OpenAPI tag), `page` (default 1), `page_size` (default 50, max 200)
- Output: `{operations: [...], total_count, page, page_size, spec_version}`
- Error outputs: `SPEC_UNAVAILABLE`, `INVALID_PAGE`
- Token budget target: ≈ 1500–3000 tokens for 50 unfiltered results

**Get tool (`get_dct_operation`)**
- Reads cached OpenAPI spec in memory; no DCT network calls
- Returns fully $ref-resolved operation schema for a single operation
- Inputs: `operation_id` OR (`method` + `path`) — exactly one lookup strategy required
- Output: `{operationId, method, path, summary, description, parameters, requestBody, responses, tags, security, confirmation_required, spec_version}`
- The `confirmation_required` flag is derived by checking `method` + `path` against `manual_confirmation.txt` — no side effects
- $ref resolution is recursive up to depth 10; cycles return `SCHEMA_PARSE_ERROR`
- Error outputs: `OPERATION_NOT_FOUND` (with suggestion to call list), `AMBIGUOUS_INPUT`
- Token budget target: ≈ 500–1500 tokens per single operation schema

**Execute tool (`execute_dct_operation`)**
- The only tool that makes DCT network calls
- Inputs: `operation_id` OR (`method` + `path`), `query_params`, `request_body`, `path_params`, `confirmed` (default false)
- Steps: (1) resolve operation from spec, (2) validate request against schema, (3) substitute path params, (4) check confirmation gate, (5) dispatch via `DCTAPIClient`, (6) return response with `_mcp_meta` envelope
- Reserved meta-action: `operation_id="refresh_spec"` triggers on-demand spec refresh without server restart
- All DCT calls pass through existing `DCTAPIClient` — auth, retry, SSL settings unchanged
- Output variants: success, confirmation_required, VALIDATION_ERROR, DCT_CLIENT_ERROR, SPEC_UNAVAILABLE

### 2. OpenAPI Spec Download-and-Cache Strategy

- **Startup sequence** (in FastMCP lifespan `__aenter__`):
  1. Attempt GET `{DCT_BASE_URL}/dct/static/api-external.yaml` (respects `DCT_TIMEOUT`, `DCT_VERIFY_SSL`, `DCT_MAX_RETRIES`)
  2. On HTTP 200: parse YAML, validate OpenAPI 3.x structure (`openapi`, `info`, `paths` keys present), write to `$TEMP/dct_mcp_tools/spec-cache.yaml`, log `info.version` at INFO
  3. On failure: check for existing `spec-cache.yaml`; if present, load it (log WARNING: "Using cached spec from previous run"); if absent, load bundled `docs/api-external.yaml` (log WARNING: "Using bundled fallback spec")
  4. All sources: set `_spec_loaded=True` and store parsed spec dict in memory as a module-level reference
- **Atomic refresh**: spec reference is updated via a single assignment after successful parse; in-flight List/Get/Execute calls see either the old or new spec atomically — no partial-spec state
- **Cache invalidation**: no TTL; refresh occurs at startup or via `refresh_spec` meta-action only
- **Cache write failure**: if `$TEMP/dct_mcp_tools/` is not writable, log WARNING and continue with in-memory spec; next startup will re-download
- **Spec validation**: HTML error pages and malformed YAML both trigger fallback; spec must pass `yaml.safe_load()` and contain `openapi`, `info`, `paths` before being accepted

### 3. Request / Response Schemas (JSON Schema format)

Full JSON Schema definitions for all three tools' inputs and outputs are included in the `.docx` document. Key shapes:

| Tool | Input schema | Output schema |
|------|-------------|---------------|
| List | `{filter?: string, tag?: string, page?: int≥1, page_size?: int[1–200]}` | `{operations: [{operationId, method, path, summary, tags}], total_count, page, page_size, spec_version}` |
| Get | `{operation_id?: string} XOR {method: string, path: string}` | `{operationId, method, path, summary, description, parameters, requestBody, responses, tags, security, confirmation_required, spec_version}` |
| Execute | `{operation_id?: string, method?: string, path?: string, query_params?: object, request_body?: object, path_params?: object, confirmed?: bool}` | success / confirmation_required / error variants (see FR-004) |

### 4. Confirmation Gate Flow

- Execute tool passes `(method, resolved_path)` to the same confirmation rule engine that grouped tools use (`manual_confirmation.txt` loaded via `loader.py`)
- If matched and `confirmed=false`: return `{"status": "confirmation_required", "confirmation_level": "<level>", "message": "<template>", "operation": {method, path, operation_id}}` — no DCT call made
- If matched and `confirmed=true`: proceed to DCT dispatch
- If not matched: proceed directly to DCT dispatch (confirmed flag ignored harmlessly per ERR-4)
- Confirmation levels (`standard`, `elevated`, `manual`, `retention_check:N`, `policy_impact_check:N`) are handled identically to the existing grouped tool pattern — no new logic

### 5. RBAC Model

- Execute tool passes the `DCT_API_KEY` through `DCTAPIClient` unchanged — the `apk ` prefix is applied automatically by `DCTAPIClient.request()`
- DCT server enforces all RBAC; the MCP server does not replicate permission checks
- The Execute tool cannot call arbitrary external URLs: the base URL is always `DCT_BASE_URL` as set in the environment; no caller-controlled base URL override is accepted
- Path traversal is mitigated: `path_params` values are URL-encoded by `httpx` before substitution; DCT API returns 404/400 for invalid paths
- No new unauthenticated attack surface is introduced: all three tools are registered identically to existing grouped tools — they require the same MCP session auth model

### 6. LLM Evaluation Methodology

Test matrix for evaluating LLM (Claude) behaviour with the 3-tool Dynamic mode:

| Scenario | Expected LLM behaviour | Pass criterion |
|----------|----------------------|----------------|
| Discover VDB endpoints | LLM calls `list_dct_operations(filter="vdb")`, reads result, does not need human guidance | Returns filtered list without error |
| Inspect VDB delete schema | LLM calls `get_dct_operation(method="POST", path="/vdbs/{vdbId}/delete")`, reads `confirmation_required=true` | Schema returned with `confirmation_required=true` |
| Execute VDB delete — confirmation flow | LLM calls `execute_dct_operation(operation_id="deleteVDB", confirmed=false)` → sees `confirmation_required`, re-calls with `confirmed=true` | First call: `status=confirmation_required`; second call: `status=success` |
| Self-correct malformed request | LLM sends request body missing a required field; receives `VALIDATION_ERROR` with field details; LLM corrects and retries | Retry succeeds without human intervention |
| Spec unavailable at startup | LLM receives `SPEC_UNAVAILABLE` error on List/Get; escalates to user | Error returned; no server crash |
| On-demand spec refresh | LLM calls `execute_dct_operation(operation_id="refresh_spec")`; retries List to see updated operations | Spec refreshed; new operations visible in List |

### 7. Dynamic Mode vs Auto Mode — Comparison

| Dimension | Auto Mode (`DCT_TOOLSET=auto`) | Dynamic Mode (`DCT_TOOLSET=dynamic`) |
|-----------|-------------------------------|--------------------------------------|
| Tools exposed to LLM at startup | 5 meta-tools (enable/disable toolsets) | 3 fixed tools (List, Get, Execute) |
| Tools after toolset enable | 5 meta + up to ~70 per enabled toolset | Always 3 |
| Token cost — operation discovery | ~500–2000 tokens to enable a toolset (full tool descriptions sent) | ~1500–3000 tokens for 50-op List (summaries only) |
| Token cost — single operation detail | ~300–1200 tokens (full grouped-tool schema for resource domain) | ~500–1500 tokens (one operation schema, fully dereferenced) |
| Token cost — execute | Similar in both modes | Similar in both modes |
| Extra LLM round-trips for unknown endpoints | 0 (if toolset already enabled) or 1 (enable_toolset) | 1–2 (List then Get before Execute) |
| Maintenance burden | Must update Python tool files + toolset .txt configs per new DCT endpoint | No code changes when DCT adds endpoints; spec drives discovery |
| DCT version lag | Manual update cycle after each DCT release | Auto-updated at startup via live spec download |
| Security posture | Confirmation gate + DCTAPIClient; no schema validation at call time | Confirmation gate + DCTAPIClient + OpenAPI schema validation before dispatch |
| Client compatibility | `tools/list_changed` MCP notifications needed for hot-switch | No dynamic tool list changes; 3 tools always present |
| VS Code Copilot | Requires chat restart after `enable_toolset` | No restart needed; all operations accessible via 3 static tools |
| Recommended for | Known toolsets, high-frequency repeated interactions, token-optimised workflows | New DCT deployments, exploratory workflows, reduced maintenance overhead |

**Recommendation**: Dynamic mode is preferred for new deployments and exploratory use cases because it eliminates maintenance lag when DCT adds API endpoints and reduces per-operation token cost for discovery workflows. Auto mode remains preferable for high-frequency production workflows where the LLM repeatedly calls the same known grouped-tool actions, as it avoids the List+Get round-trips before each Execute. Operators should choose based on their primary use pattern; both modes are fully supported and co-exist as `DCT_TOOLSET` values.

### Pros and Cons

**Auto Mode (`DCT_TOOLSET=auto`)**

| | Detail |
|---|---|
| **Pro** | Token-efficient for high-frequency known operations — no List+Get round-trips; LLM calls grouped tool directly |
| **Pro** | Curated tool descriptions give the LLM richer context about related operations (e.g., all VDB actions in one tool) |
| **Pro** | Lower interaction latency — 1 LLM call instead of 2–3 for a known operation |
| **Pro** | Battle-tested in production; existing toolsets are well-exercised and validated |
| **Pro** | Full VS Code Copilot support without restart limitations for fixed toolset use |
| **Con** | Requires manual code changes (Python + `.txt` config) every time DCT adds new API endpoints |
| **Con** | Lags DCT API releases; new endpoints inaccessible until the next MCP server release cycle |
| **Con** | Tool count balloons after enabling multiple toolsets (~70+ tools exposed simultaneously), increasing LLM context size |
| **Con** | Not suited for exploratory workflows ("what can this DCT deployment support?") |
| **Con** | `tools/list_changed` MCP notifications required for runtime toolset hot-switching; VS Code Copilot requires chat restart |

**Dynamic Mode (`DCT_TOOLSET=dynamic`)**

| | Detail |
|---|---|
| **Pro** | Zero maintenance when DCT adds new endpoints — OpenAPI spec drives discovery automatically at startup |
| **Pro** | Always reflects the live DCT API surface; no MCP server update needed after DCT releases |
| **Pro** | Fixed tool count (always 3) regardless of DCT API scope — no context window bloat |
| **Pro** | Schema validation before dispatch catches malformed LLM requests before any DCT network call |
| **Pro** | No hot-switch complexity; 3 static tools always present; fully compatible with VS Code Copilot without restart |
| **Con** | Extra LLM round-trips (1–2 List+Get calls) before Execute for operations the LLM hasn't seen in the session |
| **Con** | Higher token cost for discovery phase (~1500–3000 tokens for a List call) compared to a direct grouped-tool call |
| **Con** | LLM must interpret raw OpenAPI schema (from Get) rather than curated, human-written tool descriptions |
| **Con** | Requires DCT host reachability at startup for freshest spec (mitigated by cache and bundled fallback, but adds startup dependency) |
| **Con** | New approach — less battle-tested than the existing Auto mode toolsets; evaluation matrix needed before broad rollout |

### 8. Migration Path (QR-2 Compliance)

Operators migrating from Auto mode to Dynamic mode:

1. Set `DCT_TOOLSET=dynamic` (replaces `DCT_TOOLSET=auto`)
2. Restart the MCP server — the spec download runs automatically during startup
3. Optional: pre-warm the cache by verifying `$TEMP/dct_mcp_tools/spec-cache.yaml` exists after first start
4. Update MCP client configuration if it relied on specific toolset-enable prompts (not required for most clients)
5. Verify the three tools (`list_dct_operations`, `get_dct_operation`, `execute_dct_operation`) appear in the MCP tool list

No data migration, no API key changes, no downtime beyond the normal server restart.

## Open Questions / Risks

<!-- Items requiring resolution before or during implementation. Blocking items first. -->

- R: `.docx` production requires a Mermaid-to-PNG render step (for architecture diagrams) before using `pandoc` to convert to `.docx`. The MEMORY.md entry confirms the workflow: `npx @mermaid-js/mermaid-cli` to render PNG, then `pandoc` to produce `.docx`. This must be executable in the local dev environment — Owner: Vinay Byrappa.
- Q: Should the bundled fallback spec (`docs/api-external.yaml`) be versioned and updated with each DCT release, or is it acceptable to ship one fixed baseline version and rely on live download for currency? — Owner: Nick/Geeta (PM decision)
- Q: Does the Ecosystem team require a specific DCT API version matrix in the LLM evaluation methodology section (e.g., test against DCT 16.x and 17.x separately), or is a single-version test matrix sufficient for sign-off? — Owner: Ecosystem Engineering Team
- R: Stakeholder sign-off is recorded as a Jira comment on DLPXECO-13984; if the epic does not yet have the correct watchers set, the PM review may be missed — Mitigation: confirm DLPXECO-13984 watchers before circulating the `.docx`.
- R: EC-2 ($ref cycles in DCT OpenAPI spec) — the design caps resolution depth at 10 levels. If the live DCT spec contains legitimate deeply-nested schemas beyond 10 levels, the Get tool would erroneously return `SCHEMA_PARSE_ERROR`. The implementation epic must audit the actual DCT spec for max $ref depth before finalising the cap — Owner: implementation team.

## Acceptance Criteria

<!-- Pulled from FR-001 through FR-006 acceptance criteria and vision Success Criteria SC1–SC5. -->

- [ ] AC-1 (FR-001): Given the DLPXECO-13985 scope, when the design document is published, then it explicitly covers all six areas — tool responsibilities, OpenAPI spec download-and-cache strategy, request/response schemas, confirmation gate flow, RBAC model, and LLM evaluation methodology — with no section left as a placeholder or stub
- [ ] AC-2 (FR-001): Given the design document, when reviewed by PM (Nick/Geeta) and the Ecosystem team, then it has explicit sign-off recorded as a comment on the epic (DLPXECO-13984) before any implementation ticket is opened
- [ ] AC-3 (FR-002): Given a healthy DCT server and a downloaded spec, when `list_dct_operations()` is called with no filters, then it returns all operations with `operationId`, `method`, `path`, `summary`, and `tags` for each — and `total_count` matches the actual operation count; when the spec is unavailable, it returns `status=error, code=SPEC_UNAVAILABLE`
- [ ] AC-4 (FR-003): Given `operationId="searchVDBs"` exists in the spec, when `get_dct_operation(operation_id="searchVDBs")` is called, then the full operation schema is returned with all `$ref` tokens resolved; a DELETE operation returns `confirmation_required=true`; a non-existent operationId returns `status=error, code=OPERATION_NOT_FOUND`
- [ ] AC-5 (FR-004): The Execute tool dispatches valid requests to DCT, returns `status=confirmation_required` for destructive operations when `confirmed=False`, returns `status=error, code=VALIDATION_ERROR` for schema-invalid requests before any DCT call, and returns `status=error, code=DCT_CLIENT_ERROR` for DCT HTTP errors — with no unhandled Python exceptions
- [ ] AC-6 (FR-005): Given a reachable DCT host, when the MCP server starts, then the spec is downloaded, parsed, and `info.version` is logged at INFO; given an unreachable host, the cached or bundled spec is used with a WARNING; `execute_dct_operation(operation_id="refresh_spec")` triggers on-demand spec refresh without server restart
- [ ] AC-7 (FR-006): Given the design document, when the comparison table is reviewed, then it contains at minimum tool count, token cost per interaction (with numeric estimates), maintenance burden, latency impact, security posture, and client compatibility — with concrete values or ranges; the `### Recommendation` subsection clearly states which mode is preferred and why, referencing at least two dimensions

---
<!-- Cross-references checked by check-structure.sh during the design phase:
     - Every FR-* in docs/DLPXECO-13985-functional.md → at least one row in ### Source Files to Modify
     - Non-Goals in docs/DLPXECO-13985-vision.md → MUST NOT appear in Architecture Changes (hard constraint)
     - Every AC → at least one FR-* in functional.md (transitive via FR mapping)
     Run: .claude/evals/check-structure.sh DLPXECO-13985 --step design -->
