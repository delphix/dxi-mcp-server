# Test Plan: DLPXECO-14014

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-14014
**Derived from**: `docs/DLPXECO-14014/DLPXECO-14014-design.md` `## Affected Components` and `## Version Compatibility`

<!-- Guidance: This file is the authoritative list of scenarios for the test-generation phase.
     Every row in `## Scenarios` becomes one test() / it() / def test_* block in `.claude/test/generated-test/`.
     If a scenario row cannot be expressed as a real assertion, refine the row — do not weaken the generated test. -->

---

## Test Approach

Unit tests using `pytest>=7.0.0` with `pytest-asyncio>=0.21.0` (`asyncio_mode = "auto"`) and `pytest-cov>=4.0.0`. All tests run entirely offline — no live DCT instance, no real network I/O. `httpx.AsyncClient.request` is mocked with `unittest.mock.AsyncMock` for client tests. Coverage is measured with `pytest --cov=src/dct_mcp_server tests/`. Runner: `pytest tests/ -v` from the repo root.

## Environment / Landscape

- No network access to a DCT instance required
- Python 3.11+ interpreter
- Env vars: `DCT_API_KEY=test-key`, `DCT_BASE_URL=http://localhost:9999` (set by `conftest.py` session fixture)
- Real config files used as test data: `src/dct_mcp_server/config/toolsets/self_service.txt`, `src/dct_mcp_server/config/mappings/manual_confirmation.txt`

## Versions to Cover

| Version | Why | Required? |
|---------|-----|-----------|
| Python 3.11 | Project minimum runtime | Yes |
| Python 3.12 | In active CI use (pycache shows 3.12 bytecode) | Yes |

## Scenarios

| # | Scenario | Maps to FR | Versions | Expected outcome |
|---|----------|-----------|----------|------------------|
| S1 | `load_toolset_apis("self_service")` returns a non-empty tuple with at least one entry having `action == "search_vdbs"` | FR-002 | 3.11, 3.12 | Non-empty tuple; at least one dict with `action == "search_vdbs"` |
| S2 | `load_toolset_apis` called with a non-existent toolset name raises `ValueError` containing "Unknown toolset" | FR-002 | 3.11, 3.12 | `ValueError` raised; message contains "Unknown toolset" |
| S3 | `load_toolset_apis` with a file containing comment and blank lines skips those lines and returns only API entries | FR-002 | 3.11, 3.12 | Returned tuple contains no entries derived from comment or blank lines |
| S4 | `load_toolset_apis` with a malformed line (fewer than 3 pipe-separated parts) silently skips the malformed line | FR-002 | 3.11, 3.12 | No exception raised; valid lines in the same file are still returned |
| S5 | `load_toolset_apis("self_service_provision")` inherits from `self_service`; known `self_service` action names are present in result | FR-002 | 3.11, 3.12 | Tuple includes at least one entry with `action == "search_vdbs"` from the inherited parent |
| S6 | `load_toolset_apis` with an `@inherit:nonexistent` directive raises `ValueError` | FR-002 | 3.11, 3.12 | `ValueError` raised mentioning the missing parent toolset |
| S7 | After `clear_cache()`, re-calling `load_toolset_apis` re-reads from disk without error | FR-002 | 3.11, 3.12 | No exception; fresh data returned after cache clear |
| S8 | `get_confirmation_for_operation("POST", "/vdbs/vdb-123/delete")` against real `manual_confirmation.txt` returns `level == "manual"` | FR-002, FR-004 | 3.11, 3.12 | Returned dict has `level == "manual"` |
| S9 | `get_confirmation_for_operation("GET", "/vdbs/vdb-123")` returns `level == "none"` and `message is None` | FR-002, FR-004 | 3.11, 3.12 | Returned dict has `level == "none"` and `message is None` |
| S10 | `requires_confirmation("POST", "/vdbs/x/delete")` returns `True` | FR-002, FR-004 | 3.11, 3.12 | Returns `True` |
| S11 | `requires_confirmation("GET", "/vdbs/x")` returns `False` | FR-002, FR-004 | 3.11, 3.12 | Returns `False` |
| S12 | `DCTAPIClient.make_request` with a mocked HTTP 200 JSON response returns a dict matching the mocked JSON body | FR-003 | 3.11, 3.12 | Returned dict equals mocked JSON payload |
| S13 | `DCTAPIClient.make_request` with a mocked HTTP 200 non-JSON response returns `{"response": <text>}` | FR-003 | 3.11, 3.12 | Returned dict has key `response` with the mock's text body |
| S14 | `DCTAPIClient.make_request` with a mocked HTTP 404 raises `DCTClientError` after exactly 1 attempt (no retry) | FR-003 | 3.11, 3.12 | `DCTClientError` raised; mock called exactly 1 time |
| S15 | `DCTAPIClient.make_request` with a mocked HTTP 503 on every attempt and `max_retries=3` raises `DCTClientError` after exactly 3 attempts | FR-003 | 3.11, 3.12 | `DCTClientError` raised; mock called exactly 3 times |
| S16 | `DCTAPIClient.make_request` with HTTP 503 on attempt 1 and HTTP 200 on attempt 2 returns the successful response; mock called exactly 2 times | FR-003 | 3.11, 3.12 | Success returned; mock called 2 times |
| S17 | `asyncio.sleep` is called with `2**0` and `2**1` during two successive 5xx retries (backoff validation) | FR-003 | 3.11, 3.12 | Patched `asyncio.sleep` called with `1` and `2` respectively |
| S18 | `DCTAPIClient.make_request` with a mock that raises `httpx.ConnectError` raises `DCTClientError` after `max_retries` attempts | FR-003 | 3.11, 3.12 | `DCTClientError` raised; mock called `max_retries` times |
| S19 | `DCTAPIClient.__init__` sets `Authorization` header to a value starting with `"apk "` | FR-003 | 3.11, 3.12 | `self.headers["Authorization"]` starts with `"apk "` |
| S20 | `get_confirmation_for_operation("DELETE", "/bookmarks/bm-1")` returns `level == "manual"` | FR-004 | 3.11, 3.12 | Returned dict has `level == "manual"` |
| S21 | `get_confirmation_for_operation("POST", "/vdbs/search")` returns `level == "none"` | FR-004 | 3.11, 3.12 | Returned dict has `level == "none"` |
| S22 | `get_confirmation_for_operation("PATCH", "/snapshots/snap-1")` returns `conditional == True` and `threshold_days == 7` | FR-004 | 3.11, 3.12 | `conditional is True`; `threshold_days == 7` |
| S23 | `_path_matches("/vdbs/abc-123/delete", "/vdbs/{vdbId}/delete")` returns `True` | FR-004 | 3.11, 3.12 | Returns `True` |
| S24 | `_path_matches("/vdbs/search", "/vdbs/{vdbId}/delete")` returns `False` | FR-004 | 3.11, 3.12 | Returns `False` |
| S25 | `_path_matches("/vdbs/search", "/vdbs/search")` returns `True` (exact match, no path params) | FR-004 | 3.11, 3.12 | Returns `True` |
| S26 | A wildcard-method synthetic rule with method `*` matches both `GET` and `DELETE` calls on the same path | FR-004 | 3.11, 3.12 | `get_confirmation_for_operation` returns non-`none` level for both `GET` and `DELETE` |
| S27 | When two synthetic rules both match a request, the first rule's level is returned (first-match-wins) | FR-004 | 3.11, 3.12 | Returned `level` equals first rule's level, not second |
| S28 | pytest dependency re-enable: after `pip install -r requirements.txt`, `pytest`, `pytest-asyncio`, and `pytest-cov` are importable | FR-001 | 3.11, 3.12 | `import pytest`, `import pytest_asyncio`, `import pytest_cov` all succeed; no import error |
| S29 | `validate_toolset_config("self_service")` returns an empty error list | FR-002 | 3.11, 3.12 | Returns `[]` (empty list) |

## Out of Scope

- End-to-end tests that spawn a live DCT server or MCP stdio transport (Non-Goal NG1 — tracked in test-infra / test phases)
- Coverage for `tools/*_endpoints_tool.py`, `main.py`, or `toolsgenerator/` (Non-Goal NG3 — requires running FastMCP context; omitted from `[tool.coverage.run]` via `omit`)
- Achieving a specific coverage percentage target (Non-Goal NG2 — coverage measurement is the goal; gate threshold is HG1 ticket's responsibility)
- Refactoring `loader.py` or `client.py` source code to make them more testable (Non-Goal NG4)
- Docker-based integration test infrastructure (Non-Goal NG5 — tracked in `.claude/test/test-infra.md`)
- Circular inheritance cycle detection test causes Python `RecursionError` in current code — test documents the behaviour but no fix is applied

## Test Data Requirements

- Real `src/dct_mcp_server/config/toolsets/self_service.txt` must exist and contain at least one `POST|/vdbs/search|search_vdbs` entry
- Real `src/dct_mcp_server/config/toolsets/self_service_provision.txt` must use `@inherit:self_service`
- Real `src/dct_mcp_server/config/mappings/manual_confirmation.txt` must contain `POST|/vdbs/{vdbId}/delete|manual|...` and `PATCH|/snapshots/{snapshotId}|retention_check:7|...` rules
- No external fixtures required; `conftest.py` sets env vars at session scope

## Exit Criteria

- All Required scenarios above PASS on Python 3.11 and 3.12
- `pytest tests/ -v` exits 0 with at least 15 test cases collected and passing (SC1)
- `pytest --cov=src/dct_mcp_server tests/` exits 0 and overall coverage percentage is recorded in `docs/DLPXECO-14014/DLPXECO-14014-eval-results.md` (SC2)
- `tests/test_tool_factory_hooks.py` (pre-existing) continues to pass (AC-5)
- No scenario marked SKIPPED without a documented reason

---
<!-- Cross-references:
     - Each Scenario row → drives one test block in .claude/test/generated-test/$NAME.spec.* (test-generation phase)
     - Each FR in docs/$NAME/$NAME-functional.md → at least one scenario here (otherwise the FR is untested)
     - Versions column → must be a subset of docs/$NAME/$NAME-design.md ## Version Compatibility "Supported = Yes"
     Validation: feature-executor.md Phase: test-generation Step 2 treats this file as authoritative. -->
