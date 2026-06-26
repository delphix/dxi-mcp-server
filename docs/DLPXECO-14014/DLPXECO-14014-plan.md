# Implementation Tasks: DLPXECO-14014

**Spec**: docs/DLPXECO-14014/DLPXECO-14014-functional.md
**Design**: docs/DLPXECO-14014/DLPXECO-14014-design.md

---

<!-- Directives:
     [parallel]       = this task can run simultaneously with other [parallel] tasks because they modify different files
     [model:haiku]    = use the cheapest/fastest model (mechanical task with clear spec)
     [model:sonnet]   = use a standard model (integration or judgment required)
     [model:opus]     = use the most capable model (architecture or complex reasoning required)
     Omit [parallel] if this task modifies files that any other task also modifies. -->

## Task 1: Enable pytest dependencies in requirements.txt and pyproject.toml  [parallel][model:haiku]

### Description
Updates `requirements.txt` and `pyproject.toml` to re-enable pytest, pytest-asyncio, and pytest-cov as active dependencies. Also adds `asyncio_mode = "auto"`, `addopts = "--tb=short"`, and the `[tool.coverage.run]` section to `pyproject.toml`. Must run before any test tasks because the test runner must be installable.

### Spec References
- FR-001 (AC-1, AC-2, AC-3): Re-enable pytest dependencies — requirements.txt and pyproject.toml configuration

### Sub-tasks (TDD)
- [ ] **RED**: Verify current state — confirm `pytest>=7.0.0` is commented out in `requirements.txt` and `asyncio_mode` is absent from `pyproject.toml`
- [ ] **GREEN**:
  - In `requirements.txt`: uncomment `pytest>=7.0.0` and `pytest-asyncio>=0.21.0`; add `pytest-cov>=4.0.0` on a new line
  - In `pyproject.toml`: add `asyncio_mode = "auto"` and `addopts = "--tb=short"` to `[tool.pytest.ini_options]`; add `[tool.coverage.run]` section with `source = ["src/dct_mcp_server"]` and `omit = ["*/toolsgenerator/*", "*/tools/core/tool_factory.py"]`; also add `pytest-asyncio>=0.21.0` and `pytest-cov>=4.0.0` to `[project.optional-dependencies] dev`
- [ ] **REFACTOR**: Verify `pytest --collect-only` exits 0 after changes (no import errors)

### Depends On
- None

### Acceptance Criteria
- [ ] `requirements.txt` lists `pytest>=7.0.0`, `pytest-asyncio>=0.21.0`, `pytest-cov>=4.0.0` without being commented out
- [ ] `pyproject.toml` has `asyncio_mode = "auto"` and `[tool.coverage.run]` section
- [ ] `pytest --collect-only` exits 0 (or 5 for no-tests-collected, not an import error)

---

## Task 2: Create tests/conftest.py with shared fixtures  [parallel][model:haiku]

### Description
Creates `tests/conftest.py` with two fixtures: (1) a session-scoped autouse fixture that sets `DCT_API_KEY=test-key` and `DCT_BASE_URL=http://localhost:9999` before any test module is imported — preventing `ValueError` when `DCTAPIClient.__init__` calls `get_dct_config()`; (2) a function-scoped autouse fixture that calls `clear_cache()` before each test to prevent `lru_cache` state leakage between tests.

### Spec References
- FR-001 (AC-3): asyncio_mode = "auto" compatibility with no @pytest.mark.asyncio needed
- FR-002 (Processing step 1): clear_cache() autouse fixture
- FR-003 (Processing step 1): env var monkeypatching at session scope
- FR-004 (Processing step 1): clear_cache() fixture for confirmation rule tests

### Sub-tasks (TDD)
- [ ] **RED**: Note that without conftest.py, importing DCTAPIClient in any test file would fail with ValueError on missing DCT_API_KEY
- [ ] **GREEN**: Write `tests/conftest.py` with:
  - `set_env_vars` fixture (scope="session", autouse=True) setting DCT_API_KEY and DCT_BASE_URL via monkeypatch — must be compatible with session scope; use `os.environ` directly since monkeypatch session scope works differently
  - `reset_cache` fixture (scope="function", autouse=True) calling `clear_cache()` before each test
- [ ] **REFACTOR**: Add module docstring explaining why each fixture exists and documenting the lru_cache ordering requirement

### Depends On
- Task 1 (pytest must be installable before conftest.py can be validated)

### Acceptance Criteria
- [ ] `tests/conftest.py` exists with both fixtures
- [ ] `pytest --collect-only` collects without import errors when DCT_API_KEY is not set in the shell environment

---

## Task 3: Write tests/test_loader.py — unit tests for config/loader.py  [parallel][model:sonnet]

### Description
Creates `tests/test_loader.py` with 11+ AI-generated unit tests covering `load_toolset_apis`, `load_toolset_grouped_apis`, `get_confirmation_for_operation`, `requires_confirmation`, `validate_toolset_config`, and `clear_cache`. Uses real toolset `.txt` files for integration-style assertions and a `tmp_path` fixture for malformed/edge-case test data.

### Spec References
- FR-002 (AC-1 through AC-5): All loader unit tests
- Edge cases EC-1, EC-3 from functional spec

### Sub-tasks (TDD)
- [ ] **RED**: Verify the 11 required test function names do not yet exist
- [ ] **GREEN**: Write `tests/test_loader.py` with all required tests (each carrying `# AI-generated` comment):
  1. `test_load_toolset_apis_self_service_returns_nonempty` — loads real self_service.txt, asserts non-empty tuple with method/path/action keys
  2. `test_load_toolset_apis_unknown_toolset_raises_value_error` — passes non-existent name, asserts ValueError with "Unknown toolset"
  3. `test_load_toolset_apis_skips_comment_and_blank_lines` — creates temp toolset file with only comments/blanks, asserts empty result
  4. `test_load_toolset_apis_malformed_line_ignored` — line with 2 pipe-separated parts; valid lines still returned
  5. `test_load_toolset_inheritance_includes_parent_apis` — self_service_provision inherits self_service; known self_service action names appear in result
  6. `test_load_toolset_inheritance_missing_parent_raises` — temp file with @inherit:nonexistent; asserts ValueError
  7. `test_clear_cache_allows_fresh_reload` — loads toolset, writes modified temp file, patches TOOLSETS_DIR via monkeypatch, calls clear_cache(), asserts new data
  8. `test_get_confirmation_for_operation_manual_level` — POST /vdbs/vdb-123/delete → level == "manual"
  9. `test_get_confirmation_for_operation_no_match_returns_none` — GET /vdbs/vdb-123 → level == "none"
  10. `test_requires_confirmation_true_for_delete` — known destructive path → True
  11. `test_requires_confirmation_false_for_read` — GET path → False
  12. `test_validate_toolset_config_returns_empty_for_valid` — validate self_service → empty errors list
  13. `test_validate_toolset_config_returns_error_for_empty_toolset` — validate toolset with no APIs → non-empty errors
- [ ] **REFACTOR**: Add module docstring; group tests with comments; verify `# AI-generated` comment on each function

### Depends On
- Task 2 (conftest.py must exist for clear_cache fixture to work)

### Acceptance Criteria
- [ ] All 13+ tests in test_loader.py pass
- [ ] Each test function has `# AI-generated` on its first line of body
- [ ] `load_toolset_apis("self_service")` returns at least one entry (integration test passes against real file)
- [ ] `clear_cache()` test exercises cache invalidation correctly

---

## Task 4: Write tests/test_client_retry.py — async tests for DCTAPIClient retry/backoff  [parallel][model:sonnet]

### Description
Creates `tests/test_client_retry.py` with 8 AI-generated async tests verifying that `DCTAPIClient.make_request` retries correctly on 5xx responses, does NOT retry on 4xx, raises `DCTClientError` after exhausting retries, and uses exponential backoff. Uses `unittest.mock.AsyncMock` to patch `httpx.AsyncClient.request` to avoid network I/O.

### Spec References
- FR-003 (AC-1 through AC-5): All client retry/backoff tests

### Sub-tasks (TDD)
- [ ] **RED**: Verify test_client_retry.py does not yet exist; confirm DCTAPIClient raises ValueError without DCT_API_KEY (which conftest.py fixes)
- [ ] **GREEN**: Write `tests/test_client_retry.py` with all required async tests (each carrying `# AI-generated` comment):
  1. `test_make_request_success_returns_json` — mock HTTP 200 with JSON; assert returned dict matches body
  2. `test_make_request_non_json_response_returns_response_key` — mock HTTP 200 with text/plain; assert {"response": text}
  3. `test_make_request_4xx_raises_immediately_no_retry` — mock HTTP 404; assert DCTClientError raised and mock called exactly once
  4. `test_make_request_5xx_retries_up_to_max` — always 503, max_retries=3; assert DCTClientError raised and mock called exactly 3 times
  5. `test_make_request_5xx_succeeds_on_second_attempt` — 503 then 200; assert success and mock called exactly twice
  6. `test_make_request_exponential_backoff_called` — patch asyncio.sleep; assert called with 2**0 then 2**1
  7. `test_make_request_connection_error_retries` — mock raises httpx.ConnectError; assert DCTClientError after max_retries
  8. `test_authorization_header_prepends_apk` — inspect client headers; assert Authorization starts with "apk "
- [ ] **REFACTOR**: Add module docstring explaining mock approach; ensure asyncio.sleep is always patched so tests complete instantly

### Depends On
- Task 2 (conftest.py must set DCT_API_KEY before DCTAPIClient can be instantiated)

### Acceptance Criteria
- [ ] All 8 tests in test_client_retry.py pass without network I/O
- [ ] httpx.AsyncClient.request is mocked — no real requests sent
- [ ] asyncio.sleep is patched in backoff tests — suite completes in under 5 seconds total
- [ ] Each test function has `# AI-generated` on its first line of body

---

## Task 5: Write tests/test_confirmation.py — rule matching tests  [parallel][model:sonnet]

### Description
Creates `tests/test_confirmation.py` with 12 AI-generated tests verifying all five confirmation levels (`standard`, `elevated`, `manual`, `retention_check`, `policy_impact_check`) match and do not match expected paths; also tests `_path_matches`, wildcard method handling, and first-rule-wins ordering. Uses both real `manual_confirmation.txt` and synthetic rule data.

### Spec References
- FR-004 (AC-1 through AC-5): All confirmation rule matching tests
- Edge cases EC-5, EC-6 from functional spec

### Sub-tasks (TDD)
- [ ] **RED**: Verify test_confirmation.py does not yet exist
- [ ] **GREEN**: Write `tests/test_confirmation.py` with all required tests (each carrying `# AI-generated` comment):
  1. `test_manual_confirmation_delete_vdb` — POST /vdbs/any-id/delete → level == "manual"
  2. `test_manual_confirmation_delete_bookmark` — DELETE /bookmarks/bm-1 → level == "manual"
  3. `test_no_confirmation_get_vdb_search` — POST /vdbs/search → level == "none"
  4. `test_no_confirmation_get_vdb_details` — GET /vdbs/vdb-1 → level == "none"
  5. `test_retention_check_level_parsed` — PATCH /snapshots/snap-1 → level == "retention_check" with conditional == True and threshold_days == 7
  6. `test_path_matches_with_path_param` — _path_matches("/vdbs/abc-123/delete", "/vdbs/{vdbId}/delete") → True
  7. `test_path_matches_no_match` — _path_matches("/vdbs/search", "/vdbs/{vdbId}/delete") → False
  8. `test_path_matches_exact_path_no_params` — _path_matches("/vdbs/search", "/vdbs/search") → True
  9. `test_requires_confirmation_true_for_destructive` — requires_confirmation("POST", "/vdbs/x/delete") → True
  10. `test_requires_confirmation_false_for_read` — requires_confirmation("GET", "/vdbs/x") → False
  11. `test_wildcard_method_matches_any` — synthetic rule with method *; verify matches GET and DELETE
  12. `test_first_matching_rule_wins` — synthetic rules where two patterns match; verify first rule's level returned
  13. `test_path_matches_multiple_path_params` — /access-groups/{groupId}/scopes/{scopeId} pattern handles both params (EC-6)
- [ ] **REFACTOR**: Add module docstring; add helper for creating synthetic rule fixtures

### Depends On
- Task 2 (conftest.py clear_cache fixture)

### Acceptance Criteria
- [ ] All 13 tests in test_confirmation.py pass
- [ ] Tests use both real manual_confirmation.txt and synthetic data
- [ ] Each test function has `# AI-generated` on its first line of body
- [ ] `_path_matches` edge cases (EC-6: multiple path params) are covered

---

## Task 6: Run full test suite and record coverage baseline  [model:sonnet]

### Description
Runs `pytest tests/ -v` to confirm all tests pass (including existing `test_tool_factory_hooks.py`), then runs `pytest --cov=src/dct_mcp_server tests/` to generate the coverage report, and records the overall coverage percentage in `docs/DLPXECO-14014/DLPXECO-14014-eval-results.md`.

### Spec References
- FR-001 (AC-1, AC-2): Coverage baseline recording

### Sub-tasks (TDD)
- [ ] **RED**: N/A — this is a verification-only task
- [ ] **GREEN**:
  - Run `pytest tests/ -v` — fix any failing tests
  - Run `pytest --cov=src/dct_mcp_server tests/ --cov-report=term-missing`
  - Record overall coverage % in docs/DLPXECO-14014/DLPXECO-14014-eval-results.md under a new `## Coverage Baseline` section
- [ ] **REFACTOR**: Verify total test count >= 15 and all pass

### Depends On
- Task 1, Task 2, Task 3, Task 4, Task 5

### Acceptance Criteria
- [ ] `pytest tests/` exits 0; total tests >= 15
- [ ] `test_tool_factory_hooks.py` all pass (no regressions)
- [ ] Coverage percentage recorded in docs/DLPXECO-14014/DLPXECO-14014-eval-results.md
- [ ] `grep -r "# AI-generated" tests/` returns at least 3 matches (one per new module)

---

## Execution Order

Task 1 (parallel), Task 2 (parallel) → Task 3 (parallel), Task 4 (parallel), Task 5 (parallel) → Task 6

## Progress Tracker

| Task | Status |
|------|--------|
| Task 1: Enable pytest dependencies | PENDING |
| Task 2: Create tests/conftest.py | PENDING |
| Task 3: Write tests/test_loader.py | PENDING |
| Task 4: Write tests/test_client_retry.py | PENDING |
| Task 5: Write tests/test_confirmation.py | PENDING |
| Task 6: Run test suite and record coverage | PENDING |
