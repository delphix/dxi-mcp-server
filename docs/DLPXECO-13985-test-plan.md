# Test Plan: DLPXECO-13985

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-13985
**Derived from**: `docs/DLPXECO-13985-design.md` `## Affected Components` and `## Version Compatibility`

<!-- Guidance: This file is the authoritative list of scenarios for the test-generation phase.
     Every row in `## Scenarios` becomes one test() / it() / def test_* block in `.claude/test/generated-test/`.
     If a scenario row cannot be expressed as a real assertion, refine the row — do not weaken the generated test. -->

---

## Test Approach

This story produces a design document artefact (`docs/DLPXECO-13985-architecture-design.docx`), not implementation code. Testing therefore focuses on verifying that the design document is complete, internally consistent, and satisfies all acceptance criteria. Two tracks apply:

1. **Document completeness check** — automated `check-structure.sh` run against the design doc; every FR-* maps to at least one architecture change; no placeholder text in required sections.
2. **Manual review** — PM (Nick/Geeta) and Ecosystem team review the `.docx` against AC-1 and record sign-off as a Jira comment on DLPXECO-13984.

For implementation-phase testing (when the dynamic tools are built in the implementation epic), the scenario table below provides the authoritative test matrix. Those tests will use `pytest` + `pytest-asyncio` + `fastmcp` client as described in `.claude/test/testing.md`.

## Environment / Landscape

- **For design doc verification**: local worktree at `.worktrees/dlpxeco-13985`; no DCT connectivity required
- **For implementation-phase testing** (future, tracked by implementation epic):
  - Landscape: live DCT instance with `DCT_API_KEY` and `DCT_BASE_URL` configured in `.claude/settings.local.json`
  - Service under test: `DCT_BASE_URL` (no `/dct` suffix)
  - Test runner: `pytest tests/ -v` after `uv sync`
  - Server under test started via `start_mcp_server_uv.sh` with `DCT_TOOLSET=dynamic`

## Versions to Cover

| Version | Why | Required? |
|---------|-----|-----------|
| Python 3.11 | Minimum supported runtime; all dynamic tool code must be compatible | Yes |
| Python 3.12 | Actively tested runtime; no branching expected | Yes |
| DCT API (live, healthy host) | Primary path — spec downloaded at startup | Yes |
| DCT API (unreachable host, prior cache present) | Fallback path 1 — cached spec used | Yes |
| DCT API (unreachable host, no cache) | Fallback path 2 — bundled spec used | Yes |
| `DCT_TOOLSET=dynamic` | New toolset mode being designed | Yes |
| Existing toolsets (`self_service`, `auto`, etc.) | Regression — must remain unaffected by design changes | Yes (smoke) |

## Scenarios

| # | Scenario | Maps to FR | Versions | Expected outcome |
|---|----------|-----------|----------|------------------|
| S1 | Design doc `docs/DLPXECO-13985-architecture-design.docx` exists and contains all six required sections (tool responsibilities, spec cache strategy, request/response schemas, confirmation gate flow, RBAC model, LLM evaluation methodology) | FR-001 | N/A (doc review) | File present; all six section headings found; no section contains placeholder or stub text |
| S2 | Design doc comparison table contains all required dimensions with numeric estimates (tool count, token cost, maintenance burden, latency, security posture, client compatibility) | FR-006 | N/A (doc review) | Table present; all six dimensions populated with concrete values or ranges; `### Recommendation` subsection present |
| S3 | `list_dct_operations()` with no filters returns all operations from a healthy spec — each result has `operationId`, `method`, `path`, `summary`, `tags`, and `total_count` matches operation count in spec | FR-002 | Python 3.11, 3.12 / DCT live | Returned object has `operations` list, `total_count` > 0, `spec_version` present; each item has all five fields |
| S4 | `list_dct_operations(filter="vdb")` returns only operations whose operationId, path, or summary contains "vdb" (case-insensitive) | FR-002 | Python 3.11, 3.12 / DCT live | Returned operations all match filter; operations not containing "vdb" are absent |
| S5 | `list_dct_operations(page=2, page_size=50)` when spec has >50 operations returns exactly 50 items (items 51–100) | FR-002 | Python 3.11, 3.12 / DCT live | `len(operations) == 50`; items are from the second page of the sorted list |
| S6 | `list_dct_operations()` when spec is unavailable (cache missing, download failed, bundled spec absent) returns `status=error, code=SPEC_UNAVAILABLE` | FR-002, FR-005 | Python 3.11, 3.12 / no spec | `status == "error"` and `code == "SPEC_UNAVAILABLE"`; no unhandled Python exception raised |
| S7 | `list_dct_operations(page_size=0)` returns `status=error, code=INVALID_PAGE` | FR-002 | Python 3.11, 3.12 / DCT live | Error response with `code=INVALID_PAGE`; no spec lookup performed |
| S8 | `list_dct_operations(filter="vdb", tag="VDBs")` returns only operations matching BOTH the filter substring AND the specified tag (AND combination) | FR-002 | Python 3.11, 3.12 / DCT live | Operations returned all have tag "VDBs" and contain "vdb" in operationId/path/summary |
| S9 | `get_dct_operation(operation_id="searchVDBs")` returns the full operation schema with all `$ref` tokens resolved — no `$ref` strings appear in the response | FR-003 | Python 3.11, 3.12 / DCT live | Response has `parameters`, `requestBody`, `responses`; no `"$ref"` key present in any nested object |
| S10 | `get_dct_operation(method="DELETE", path="/vdbs/{vdbId}")` returns `confirmation_required=true` because the path matches a rule in `manual_confirmation.txt` | FR-003 | Python 3.11, 3.12 / DCT live | `confirmation_required == True` in response; no DCT network call made |
| S11 | `get_dct_operation(operation_id="nonExistentOp")` returns `status=error, code=OPERATION_NOT_FOUND` with a suggestion to call `list_dct_operations` | FR-003 | Python 3.11, 3.12 / DCT live | `code == "OPERATION_NOT_FOUND"`; `suggestion` field references `list_dct_operations` |
| S12 | `get_dct_operation()` with neither `operation_id` nor `method+path` returns `status=error, code=AMBIGUOUS_INPUT` | FR-003 | Python 3.11, 3.12 / DCT live | `code == "AMBIGUOUS_INPUT"`; no spec lookup performed |
| S13 | `execute_dct_operation(operation_id="searchVDBs", request_body={...conformant...})` dispatches to DCT and returns response wrapped in `_mcp_meta` | FR-004 | Python 3.11, 3.12 / DCT live | `status == "success"`; `_mcp_meta` envelope present with `operation_id` and `spec_version` fields |
| S14 | `execute_dct_operation(operation_id="deleteVDB", vdbId="vdb-123", confirmed=False)` returns `status=confirmation_required, confirmation_level=manual` and does NOT dispatch to DCT | FR-004 | Python 3.11, 3.12 / DCT live | `status == "confirmation_required"`; no HTTP call made to DCT delete endpoint |
| S15 | `execute_dct_operation(operation_id="deleteVDB", vdbId="vdb-123", confirmed=True)` (after viewing confirmation prompt) dispatches the DELETE to DCT | FR-004 | Python 3.11, 3.12 / DCT live | `status == "success"` (or DCT API response); DCT delete endpoint was called |
| S16 | `execute_dct_operation()` with a `request_body` missing a required field returns `status=error, code=VALIDATION_ERROR` with field-level errors before any DCT network call | FR-004 | Python 3.11, 3.12 / DCT live | `code == "VALIDATION_ERROR"`; `errors` list contains at least one item with `field` and `issue` keys; no DCT HTTP call |
| S17 | `execute_dct_operation()` when DCT returns HTTP 403 returns `status=error, code=DCT_CLIENT_ERROR, http_status=403` with no unhandled Python exception | FR-004 | Python 3.11, 3.12 / DCT live | `code == "DCT_CLIENT_ERROR"` and `http_status == 403`; exception not propagated |
| S18 | `execute_dct_operation()` when DCT returns HTTP 5xx — after `DCT_MAX_RETRIES` retries — returns `status=error, code=DCT_CLIENT_ERROR` | FR-004 | Python 3.11, 3.12 / DCT live | `code == "DCT_CLIENT_ERROR"`; `detail` mentions retries exhausted |
| S19 | MCP server starts with `DCT_BASE_URL` pointing to a reachable DCT instance: spec is downloaded, parsed, and `info.version` is logged at INFO level | FR-005 | Python 3.11, 3.12 / DCT live | Log contains INFO line with spec version; `spec-cache.yaml` written to `$TEMP/dct_mcp_tools/` |
| S20 | MCP server starts with DCT host unreachable but `spec-cache.yaml` exists from a prior run: cached spec loaded and WARNING logged | FR-005 | Python 3.11, 3.12 / no DCT | Log contains WARNING mentioning "cached spec"; no startup crash |
| S21 | MCP server starts with neither DCT host nor cache available: bundled `docs/api-external.yaml` loaded and WARNING logged; three dynamic tools remain functional | FR-005 | Python 3.11, 3.12 / no DCT | Log contains WARNING mentioning "bundled fallback spec"; List/Get tools return results from bundled spec |
| S22 | `execute_dct_operation(operation_id="refresh_spec")` when DCT host is reachable: spec re-downloaded and in-memory copy updated; subsequent `list_dct_operations` reflects new spec | FR-005 | Python 3.11, 3.12 / DCT live | No error; new `spec_version` returned by List matches refreshed spec |
| S23 | `execute_dct_operation()` with `confirmed=True` on an operation NOT in `manual_confirmation.txt`: `confirmed` flag is ignored; operation proceeds normally | FR-004 | Python 3.11, 3.12 / DCT live | `status == "success"`; no `INVALID_PARAMETER` or error from superfluous `confirmed` flag |
| S24 | Existing `self_service` toolset unaffected — server starts with `DCT_TOOLSET=self_service` and grouped tools register normally after dynamic mode design changes are implemented | FR-001 (regression) | Python 3.11, 3.12 / DCT live | `self_service` grouped tools present in MCP tool list; no import errors |
| S25 | `spec-cache.yaml` is corrupted (partial write): server falls back to bundled spec at startup and logs at ERROR; no crash | FR-005 (EC-5) | Python 3.11, 3.12 / DCT live | ERROR log line; bundled spec loaded; List returns results |

## Out of Scope

- Testing the `.docx` rendering pipeline (Mermaid diagram generation, pandoc conversion) — tracked as an operational concern, not an automated test scenario
- Load / performance testing of List tool at 1000+ operations — Non-Goal; tracked separately if needed
- UI changes to any MCP client (Claude Desktop, Cursor, VS Code Copilot) — NG4 from vision
- DCT API authentication redesign — NG5 from vision
- Transport layer or FastMCP version changes — NG3 from vision
- Concurrent Execute calls stress testing (EC-4) — out of scope for initial implementation; noted as a design consideration, not a test requirement

## Test Data Requirements

- **For document completeness tests (S1–S2)**: the `docs/DLPXECO-13985-architecture-design.docx` file must be generated before the test phase; no live DCT required
- **For implementation-phase tests (S3–S25)**: `DCT_API_KEY` and `DCT_BASE_URL` must be present in `.claude/settings.local.json` under `mcpServers.dct.env`; DCT instance must have at least one VDB for delete-confirmation tests (S14, S15)
- **For fallback tests (S6, S20, S21)**: `DCT_BASE_URL` must be set to an unreachable host (e.g., `http://127.0.0.1:9999`) to simulate DCT unavailability; for S21, additionally remove/rename `spec-cache.yaml`
- **For cache corruption test (S25)**: write `"not: valid: yaml: [["` to `$TEMP/dct_mcp_tools/spec-cache.yaml` before starting the server
- **Bundled spec**: `docs/api-external.yaml` must exist in the repo (used as fallback in S21, S25); the implementation epic must ensure this file is shipped

## Exit Criteria

- All Required scenarios PASS on all Required versions
- S1 and S2 (document completeness) PASS before the design document is circulated for PM review
- Smoke suite (existing toolset tests) PASSes — specifically: `self_service` grouped tools register without error (S24)
- No scenario marked SKIPPED without a documented reason
- PM (Nick/Geeta) and Ecosystem team sign-off recorded as a Jira comment on DLPXECO-13984 before the implementation epic is opened

---
<!-- Cross-references:
     - Each Scenario row → drives one test block in .claude/test/generated-test/DLPXECO-13985.spec.* (test-generation phase)
     - Each FR in docs/DLPXECO-13985-functional.md → at least one scenario here:
       FR-001 → S1, S24; FR-002 → S3–S8; FR-003 → S9–S12; FR-004 → S13–S18, S23; FR-005 → S19–S22, S25; FR-006 → S2
     - Versions column → subset of docs/DLPXECO-13985-design.md ## Version Compatibility "Supported = Yes"
     Validation: feature-executor.md Phase: test-generation Step 2 treats this file as authoritative. -->
