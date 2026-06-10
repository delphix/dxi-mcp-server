# Functional Spec — DLPXECO-13921

> Companion to [`DLPXECO-13921-vision.md`](./DLPXECO-13921-vision.md). Defines the testable requirements for the new fuzzy endpoint-discovery meta-tool in `auto` mode.

---

## FR-1 — `find_endpoint` meta-tool exists in auto mode

**As** the LLM driving an MCP client in `DCT_TOOLSET=auto`
**I want** a single meta-tool that takes a user-intent string and an HTTP method filter and returns ranked candidate endpoints
**So that** I can move from a free-text user request to a callable `(toolset, tool, action)` triple in one round-trip.

**Acceptance criteria**

- **AC-1.1** When `DCT_TOOLSET=auto`, the MCP tool list contains a tool named `find_endpoint` alongside the existing 6 meta-tools (total: 7 meta-tools).
- **AC-1.2** When `DCT_TOOLSET` is anything other than `auto`, `find_endpoint` is **not** registered.
- **AC-1.3** `find_endpoint` is decorated with `@log_tool_execution` and writes a telemetry entry per call (consistent with all other tools).
- **AC-1.4** `find_endpoint` is included in the response of `list_available_toolsets`' `instructions` text (so the LLM knows it exists without needing an out-of-band hint).

## FR-2 — Method-type pre-filter

**Acceptance criteria**

- **AC-2.1** `find_endpoint(query, method_types=["GET"])` returns only endpoints whose HTTP method is in `method_types`.
- **AC-2.2** `method_types` accepts a list of strings; comparison is case-insensitive.
- **AC-2.3** When `method_types` includes `"GET"`, `POST` endpoints whose path ends with `/search` are also included (read-equivalent).
- **AC-2.4** When `method_types` is omitted or empty, no method filter is applied (all methods considered).
- **AC-2.5** An invalid method (e.g. `"FOO"`) is silently dropped from the filter list with a warning logged; if the resulting list is empty after dropping, AC-2.4 applies.

## FR-3 — Fuzzy ranking over OpenAPI spec

**Acceptance criteria**

- **AC-3.1** The candidate corpus is the union of `(method, path, summary, description)` tuples from `tool_factory.get_cached_spec()`.
- **AC-3.2** Each candidate gets a numeric `score` in `[0.0, 1.0]` computed from a weighted combination of:
  - keyword-overlap score (query tokens vs. path + summary + description tokens),
  - `difflib.SequenceMatcher` ratio of `query` vs. `path`,
  - a hot-keyword boost when any of `{snapshot, vdb, dsource, bookmark, engine, environment, report, tag, policy, job, source, dataset, replication, namespace}` appears in both query and candidate.
- **AC-3.3** Results are sorted by `score` descending; ties broken by shorter path first (more specific endpoints win).
- **AC-3.4** Candidates with `score < min_score` (default `0.15`, tunable) are dropped.
- **AC-3.5** The result list is capped at `limit` (default `10`, tunable, hard upper bound `25`).

## FR-4 — Each candidate resolves to a callable triple

**Acceptance criteria**

- **AC-4.1** Each returned candidate is an object with: `score` (float), `method` (str), `path` (str), `summary` (str), `toolset` (str|None), `tool` (str|None), `action` (str|None), `confirmation_level` (str: `none|standard|elevated|manual|retention_check|policy_impact_check`), `executable_via` (str: `execute_action` | `enable_then_call` | `none`).
- **AC-4.2** `toolset/tool/action` are populated by reverse-lookup against `load_toolset_grouped_apis(<toolset>)` for every available toolset; the **first** toolset whose grouped APIs contain `(method, path)` wins. Lookup order is the alphabetical order of toolsets so the answer is deterministic.
- **AC-4.3** When the `(method, path)` is found in any toolset, `executable_via = "execute_action"`.
- **AC-4.4** When the `(method, path)` is **not** present in any toolset, `toolset/tool/action` are `None` and `executable_via = "none"`. The candidate also includes `hint = "Endpoint not exposed via any toolset; not currently callable through the MCP server."`.
- **AC-4.5** `confirmation_level` is the `"level"` value returned by `get_confirmation_for_operation(method, path)`.

## FR-5 — Graceful no-spec fallback

**Acceptance criteria**

- **AC-5.1** If `get_cached_spec()` returns `None`, `find_endpoint` enters fallback mode: it searches over the union of all toolsets' grouped APIs (path + action name + tool description) instead of the OpenAPI spec.
- **AC-5.2** The fallback response includes `source: "toolset_files"` and a top-level `warning: "OpenAPI spec unavailable; results limited to entries in toolset .txt files."`.
- **AC-5.3** When the spec **is** available, the response includes `source: "openapi_spec"`.

## FR-6 — Empty / no-match handling

**Acceptance criteria**

- **AC-6.1** When `query` is empty / whitespace-only, `find_endpoint` returns `{"error": "query is required", "hint": "Provide a free-text user intent, e.g. 'find vdb with most snapshots'"}` and does not raise.
- **AC-6.2** When no candidates clear `min_score`, the response is `{"candidates": [], "source": <source>, "hint": "No fuzzy match. Try list_available_toolsets to browse personas, or refine the query."}`.

## FR-7 — Discoverability from existing meta-tools

**Acceptance criteria**

- **AC-7.1** `list_available_toolsets`' `instructions` field mentions `find_endpoint` as the recommended first call for a single-intent request.
- **AC-7.2** `get_toolset_tools` is unchanged in shape and behaviour (regression guard).

## FR-8 — Telemetry & logging

**Acceptance criteria**

- **AC-8.1** Every `find_endpoint` call logs (at INFO) the query, method filter, returned-candidate count, and source (`openapi_spec` or `toolset_files`).
- **AC-8.2** Errors during ranking (per-candidate exceptions) are caught and logged at WARNING; the failing candidate is skipped, the rest of the ranking proceeds.

## FR-9 — Determinism & idempotence

**Acceptance criteria**

- **AC-9.1** Two `find_endpoint` calls with identical args, against the same cached spec, return byte-identical JSON output.
- **AC-9.2** No global state in `meta_tools.py` is mutated by `find_endpoint`. (Contrast: `enable_toolset` mutates `_current_toolset` and `_registered_tool_names`.)

## Quality rules

- **Q-1** All new code paths have a corresponding entry in `.claude/rules/testing/auto.md` so MCP-client testing covers them. The new prompts are appended at the end of the file under a new section heading; existing prompts are not renumbered.
- **Q-2** No bare `Exception` raises. Use `MCPError` for tool-layer failures, `DCTClientError` only if a DCT call is involved (none expected for discovery).
- **Q-3** Use `get_logger(__name__)` from `dct_mcp_server.core.logging` — never `logging.getLogger`.
- **Q-4** Apply `@log_tool_execution` to the new tool function (per `.claude/rules/code-style.md`).
- **Q-5** No edits to auto-generated files in `$TEMP/dct_mcp_tools/`.
