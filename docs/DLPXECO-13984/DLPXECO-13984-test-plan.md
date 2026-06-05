# Test Plan: DLPXECO-13984

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13984
**Derived from**: `docs/DLPXECO-13984/DLPXECO-13984-design.md` `## Affected Components` and `## Version Compatibility`

<!-- Guidance: This file is the authoritative list of scenarios for the test-generation phase. -->

---

## Test Approach

Manual integration testing via MCP client (Claude Desktop or Cursor) connected to a locally running server with `DCT_TOOLSET=dynamic`. Automated unit/functional tests for `spec_cache.py`, `confirmation_resolver.py`, and `dynamic.py` using Python's `unittest.mock` to isolate HTTP calls and file I/O. The LLM evaluation harness (`evals/llm_eval_harness.py`) serves as a separate developer-time acceptance gate and is not part of the automated suite. A pytest runner is configured in `pyproject.toml` (`[tool.pytest.ini_options]`, with a `dev` extra providing pytest) and unit tests live under `tests/`; additional MCP-client and log-inspection evidence is still collected per `.claude/rules/testing.md`.

## Environment / Landscape

- Landscape: Local development environment (`./start_mcp_server_uv.sh`) + live DCT instance
- Service under test: `DCT_BASE_URL=<live-dct-host>` with `DCT_TOOLSET=dynamic`
- MCP client: Claude Desktop (primary); Cursor (secondary, for confirmation-flow validation)
- Fallback spec: `api-external.yaml` at the repo root in a source checkout, shipped as `dct_mcp_server/api-external.yaml` inside the installed wheel (must always be present)
- Air-gapped path: server started with `DCT_BASE_URL` pointing to an unreachable host to exercise the fallback logic

## Versions to Cover

| Version | Why | Required? |
|---------|-----|-----------|
| Python 3.11 | Minimum required runtime | Yes |
| Python 3.12+ | Current dev environment; forward-compat check | Yes (smoke-only) |
| DCT API (live spec) | Primary test path: spec downloaded and cached from live instance | Yes |
| Bundled fallback spec (`docs/api-external.yaml`) | Verified when live download fails or host unreachable | Yes |

## Scenarios

| # | Scenario | Maps to FR | Versions | Expected outcome |
|---|----------|------------|----------|-----------------|
| S1 | Spec download succeeds on first startup from reachable DCT instance | FR-001 | Python 3.11 | Spec written to `DCT_SPEC_CACHE_PATH`; `.cache-meta.json` sidecar exists; `WARNING` not logged; server starts with 2 tools |
| S2 | Cached spec younger than `DCT_SPEC_MAX_AGE_HOURS` is reused — no HTTP download | FR-001 | Python 3.11 | No outbound HTTP to spec URL; cached file mtime is unchanged; server starts normally |
| S3 | Spec download fails (unreachable host) — bundled fallback is used | FR-001 | Python 3.11 | `WARNING` log entry includes failure reason; `app.state.openapi_spec` is non-empty (loaded from bundled file); server starts within 5 seconds |
| S4 | Downloaded spec is invalid YAML — bundled fallback is used | FR-001 | Python 3.11 | `WARNING` log entry references YAML parse failure; bundled spec loaded; server starts normally |
| S5 | Both live download and bundled spec unavailable — server does not start | FR-001 | Python 3.11 | `MCPError("SPEC_LOAD_FAILED")` raised; server exits with non-zero code; error message includes reinstall instruction |
| S6 | Cached spec on disk is corrupted (truncated YAML) — re-download triggered | FR-001 | Python 3.11 | Re-download attempted once; if re-download succeeds, cached file is overwritten; if re-download fails, bundled spec used |
| S7 | `discovery(action="list_tags")` returns all DCT domain tags with operation counts | FR-002 | Python 3.11 | Response is `{"tags": [...]}` where each entry has `name` and `operation_count`; count matches operations in the spec for that tag; no `$ref` in response |
| S8 | `discovery(action="list_operations", tag="VDBs", method="GET")` returns paginated GET-only VDB operations | FR-002 | Python 3.11 | All returned operations have method=GET and tag=VDBs; `total_count` matches unfiltered count for that combination; pagination fields present |
| S9 | `discovery(action="list_operations", keyword="refresh")` returns only operations whose operationId or summary contains "refresh" | FR-002 | Python 3.11 | All returned operations contain "refresh" (case-insensitive) in operationId or summary; no-match keyword returns `{"operations": [], "total_count": 0}` |
| S10 | `discovery(action="list_operations")` with `page_size=50` on a spec with >50 operations returns first page and correct `total_pages` | FR-002 | Python 3.11 | Response contains exactly 50 operations; `total_pages` = ceil(total_count / 50); subsequent page returns remaining operations |
| S11 | `discovery(action="get_operation_schema", path="/vdbs/{vdbId}/delete", operation_method="POST")` returns fully resolved schema with confirmation metadata | FR-002 | Python 3.11 | Response includes `requires_confirmation=true`, `confirmation_level="manual"`; `request_body_fields` list has no `$ref` pointers; all path parameters listed |
| S12 | `discovery(action="get_operation_schema")` for non-existent path returns OPERATION_NOT_FOUND | FR-002 | Python 3.11 | `{"status": "error", "code": "OPERATION_NOT_FOUND"}` |
| S13 | `discovery(action="get_operation_schema")` for path with circular `$ref` returns `schema_truncated=true` instead of recursing infinitely | FR-002 | Python 3.11 | Response includes `schema_truncated: true`; tool completes without stack overflow; other non-circular fields are still resolved |
| S14 | `execute(path="/vdbs/{vdbId}/delete", method="POST", path_params={"vdbId":"vdb-123"}, confirmed=false)` returns confirmation_required without making HTTP call | FR-003 | Python 3.11 | `{"status": "confirmation_required", "confirmation_level": "manual", "message": <non-empty>}`; DCT API not called (verifiable via mock or request log) |
| S15 | `execute` same call with `confirmed=true` dispatches the POST and returns success | FR-003 | Python 3.11 | `{"status": "success", "operation_type": "destructive", "response": <DCT response>}` |
| S16 | `execute(path="/vdbs/search", method="POST")` returns success with operation_type=read | FR-003 | Python 3.11 | `{"status": "success", "operation_type": "read"}` (POST /search treated as read); no confirmation gate triggered |
| S17 | `execute` with missing required body field returns VALIDATION_ERROR before HTTP call | FR-003 | Python 3.11 | `{"status": "error", "code": "VALIDATION_ERROR", "missing_fields": [...]}` listing the absent field names; DCT API not called |
| S18 | `execute` for path not in spec returns OPERATION_NOT_FOUND | FR-003 | Python 3.11 | `{"status": "error", "code": "OPERATION_NOT_FOUND"}` |
| S19 | `execute` for path with wrong method returns OPERATION_NOT_FOUND with helpful available-methods message | FR-003 | Python 3.11 | `{"status": "error", "code": "OPERATION_NOT_FOUND", "available_methods": [...]}` listing valid methods for that path |
| S20 | `execute` for path with unresolved path parameter placeholder returns VALIDATION_ERROR | FR-003 | Python 3.11 | `{"status": "error", "code": "VALIDATION_ERROR", "missing_path_params": [<param>]}` |
| S21 | `execute` dispatches GET call and returns success with operation_type=read | FR-003 | Python 3.11 | `{"status": "success", "operation_type": "read", "response": <DCT response>}` |
| S22 | `execute` when DCT API returns HTTP 404 returns DCT_API_ERROR with http_status=404 | FR-003 | Python 3.11 | `{"status": "error", "code": "DCT_API_ERROR", "http_status": 404}` |
| S23 | `execute` when DCT API returns non-JSON response returns DCT_API_ERROR with descriptive message | FR-003 | Python 3.11 | `{"status": "error", "code": "DCT_API_ERROR", "message": "Non-JSON response from DCT"}` |
| S24 | Confirmation resolver returns requires_confirmation=true with correct level for POST /vdbs/{vdbId}/delete | FR-004 | Python 3.11 | `{"requires_confirmation": true, "confirmation_level": "manual"}` |
| S25 | Confirmation resolver returns requires_confirmation=false for GET /vdbs/search | FR-004 | Python 3.11 | `{"requires_confirmation": false, "confirmation_level": null}` |
| S26 | `retention_check:7` rule triggers when context.retention_days=3 and does not trigger when retention_days=30 | FR-004 | Python 3.11 | retention_days=3 → requires_confirmation=true; retention_days=30 → requires_confirmation=false |
| S27 | `policy_impact_check:N` rule triggers when affected_object_count > N | FR-004 | Python 3.11 | count > N → requires_confirmation=true; count <= N → requires_confirmation=false |
| S28 | Confirmation resolver returns requires_confirmation=false for unknown path with no matching rule | FR-004 | Python 3.11 | `{"requires_confirmation": false}` without error |
| S29 | LLM eval harness dry run (--dry-run) evaluates all 10 scenario schemas without making live DCT API calls | FR-005 | Python 3.11 | All 10 scenarios produce discovery-based schema quality assessments; `DCTAPIClient.make_request` not called; partial report written |
| S30 | LLM eval harness reports overall success rate ≥ 80% → recommendation field = "adopt" | FR-005 | Python 3.11 | `{"overall_success_rate": ≥0.8, "recommendation": "adopt"}` in summary report |
| S31 | LLM eval harness reports overall success rate < 80% → recommendation field = "investigate" or "revert" | FR-005 | Python 3.11 | `{"overall_success_rate": <0.8, "recommendation": "investigate" or "revert"}` with failure analysis |
| S32 | Decision-gate report file exists at expected path after Phase 1 validation completes | FR-006 | Python 3.11 | `docs/DLPXECO-13984/DLPXECO-13984-decision-gate.md` is non-empty; contains Executive Summary, Recommendation, and Phase 2 Entry Criteria sections |
| S33 | All existing persona-based toolsets start and serve tools correctly after code changes | Quality rule | Python 3.11 | `DCT_TOOLSET=self_service`: `vdb_tool` appears in MCP client; `DCT_TOOLSET=auto`: 5 meta-tools appear; no regressions in confirmation flows |
| S34 | `discovery` and `execute` tool calls appear in session telemetry log when IS_LOCAL_TELEMETRY_ENABLED=true | Quality rule | Python 3.11 | `logs/sessions/{id}.log` contains JSON entries for `discovery` and `execute` tool calls |

## Out of Scope

- Phase 2 features: Search tool (semantic NL→endpoint matching) and Execute sandbox mode — Non-Goal NG1
- Changes to persona-based toolsets (self_service, continuous_data_admin, etc.) — Non-Goal NG2
- Docker Hub image promotion — Non-Goal NG3
- OpenTelemetry integration — Non-Goal NG4
- Streamable HTTP transport — Non-Goal NG5
- Per-tool RBAC / additional authorization layers — Non-Goal NG6
- Vocabulary translation / canonical domain model — Non-Goal NG7
- Load/stress testing of discovery with >1000-operation specs (no latency budget for developer tools)
- Multi-model LLM harness execution in CI (developer-time gate only; not automated in pipeline)

## Test Data Requirements

- Live DCT instance reachable at `DCT_BASE_URL` with a valid `DCT_API_KEY` (for S1, S7–S23, S30–S31)
- At least one VDB, dSource, and bookmark existing on the live DCT instance (for execute integration scenarios S14–S23)
- Bundled spec `docs/api-external.yaml` present in the repo (always true; used for S3–S6)
- A corrupted YAML file (for S6): created transiently by test setup, not stored in repo
- A mock or patched `httpx.AsyncClient` that returns HTTP 404 or non-JSON body (for S22–S23): applied in unit test scope via `unittest.mock.patch`

## Exit Criteria

- All Required scenarios above PASS on Python 3.11
- Backward-compatibility check (S33) passes for all persona toolsets
- Telemetry scenario (S34) passes
- No scenario marked SKIPPED without a documented reason
- LLM eval harness dry-run (S29) passes without making live DCT API calls
- `docs/DLPXECO-13984/DLPXECO-13984-decision-gate.md` produced and reviewed (S32)

---
<!-- Cross-references:
     - Each Scenario row → drives one test block in .claude/test/generated-test/DLPXECO-13984.spec.* (test-generation phase)
     - Each FR in docs/DLPXECO-13984/DLPXECO-13984-functional.md → at least one scenario here:
       FR-001 → S1–S6
       FR-002 → S7–S13
       FR-003 → S14–S23
       FR-004 → S24–S28
       FR-005 → S29–S31
       FR-006 → S32
     - Versions column → subset of docs/DLPXECO-13984/DLPXECO-13984-design.md ## Version Compatibility "Supported = Yes"
     Validation: feature-executor.md Phase: test-generation Step 2 treats this file as authoritative. -->
