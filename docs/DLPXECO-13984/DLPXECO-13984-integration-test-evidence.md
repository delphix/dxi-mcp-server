# DLPXECO-13984 — Integration Test Evidence (Dynamic Mode)

- **Date**: 2026-06-03 15:29
- **Mode**: `DCT_TOOLSET=dynamic`
- **DCT instance**: `https://localhost` (live)
- **API key**: redacted
- **Spec**: downloaded from live DCT — 811 paths
- **Scope**: read-only — spec download, discovery browsing, GET reads, confirmation-gate (no dispatch), and polling an existing job. No data was created, mutated, or deleted.

**Summary:** 9 PASS · 0 FAIL · 0 other (WARN/SKIP) of 9 scenarios.

| ID | FR | Scenario | Result | Detail |
|----|----|----------|--------|--------|
| S1 | FR-001 | Spec download + cache from live DCT | **PASS** | 811 paths cached |
| S2 | FR-002 | discovery(list_tags) | **PASS** | 85 tags; sample=['Accounts', 'AiGenerate', 'AiManagement', 'Algorithms', 'Authorization'] |
| S3 | FR-002 | discovery(list_operations, keyword=engine, GET) | **PASS** | total_count=16 ; first=/historical-storage-summary-aggregate |
| S4 | FR-002 | discovery(get_operation_schema /management/engines GET) | **PASS** | ["path", "method", "operationId", "summary", "description", "parameters", "request_body_fields", "responses", "requires_confirmation", "confirmation_level", "schema_truncated"] |
| S5 | FR-003 | execute(GET /management/engines) | **PASS** | status=success ; operation_type=read ; engines=1 |
| S6 | FR-004 | execute destructive w/o confirmed -> gated (no dispatch) | **PASS** | status=confirmation_required ; level=manual |
| S7 | §5.1 | poll job e6cb72f9aea441f19787203cb55290ea to terminal state | **PASS** | final job status=COMPLETED |
| S8 | FR-003 | execute(unknown path) -> OPERATION_NOT_FOUND | **PASS** | code=OPERATION_NOT_FOUND |
| S9 | additivity | auto mode unchanged; dynamic tools do not leak | **PASS** | auto tools=8 ; leaked=[] |

## Layer B — LLM-client transcript (manual addendum)

The programmatic results above cover the deterministic API-level behaviour. To also evidence the end-user (LLM-driven) flow — including automatic async-job polling — connect Claude Desktop/Cursor to the server in `DCT_TOOLSET=dynamic` and run test queries, each prefixed with the standard pre-prompt:

> *"Poll the job if it is async and let me know if it succeeds."*

Paste the client transcript/screenshots here.
