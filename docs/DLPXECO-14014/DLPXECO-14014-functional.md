# Functional Specification: DLPXECO-14014

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-14014
**Generated from**: Acceptance criteria in Jira ticket + codebase analysis

---

## FR-001: Re-enable pytest dependencies

### Description
Uncomments and adds the required pytest packages in `requirements.txt` and adds the corresponding `[tool.pytest.ini_options]` and `[tool.coverage.run]` sections to `pyproject.toml` so that `uv sync` / `pip install` produces a test-ready environment.

### Input
- `requirements.txt` — current file with `pytest>=7.0.0` and `pytest-asyncio>=0.21.0` commented out
- `pyproject.toml` — current file with `[tool.pytest.ini_options]` section missing `asyncio_mode`, `addopts`, and `[tool.coverage.run]` absent

### Processing
1. In `requirements.txt`, uncomment `pytest>=7.0.0` and `pytest-asyncio>=0.21.0`; add `pytest-cov>=4.0.0` on a new line.
2. In `pyproject.toml`, confirm `[tool.pytest.ini_options]` has `testpaths = ["tests"]` and `pythonpath = ["src"]`; add `asyncio_mode = "auto"` to prevent `@pytest.mark.asyncio` on every async test.
3. Add `[tool.coverage.run]` section with `source = ["src/dct_mcp_server"]` and `omit = ["*/toolsgenerator/*", "*/tools/core/tool_factory.py"]`.
4. Verify `pytest --collect-only` completes without import errors after changes.

### Output
- Success: `requirements.txt` and `pyproject.toml` updated; `pytest --collect-only` exits 0.
- Failure: Import error or version conflict — resolve before continuing.
- Side effect: Developers running `pip install -r requirements.txt` or `uv sync` will now have pytest, pytest-asyncio, and pytest-cov installed.

### Acceptance Criteria
- [ ] AC-1: Given a clean virtual environment, when `pip install -r requirements.txt` is run, then `pytest`, `pytest-asyncio`, and `pytest-cov` are installed without errors.
- [ ] AC-2: Given the updated `pyproject.toml`, when `pytest --collect-only` is run with no test files present, then exit code is 0 (or 5 for no-tests-collected, not an import error).
- [ ] AC-3: Given the `asyncio_mode = "auto"` setting, when an async test function is written without `@pytest.mark.asyncio`, then pytest collects and runs it correctly.

---

## FR-002: Unit tests for config/loader.py

### Description
Creates `tests/test_loader.py` with AI-generated unit tests covering toolset parsing (positive cases, malformed input, inheritance chains), cache invalidation, and the `get_confirmation_for_operation` dispatch path.

### Input
- `src/dct_mcp_server/config/loader.py` — functions under test: `load_toolset_apis`, `load_toolset_grouped_apis`, `get_confirmation_for_operation`, `requires_confirmation`, `validate_toolset_config`, `clear_cache`
- Real `.txt` files in `src/dct_mcp_server/config/toolsets/` — used by integration-style tests
- `src/dct_mcp_server/config/mappings/manual_confirmation.txt` — used by confirmation rule tests

### Processing
1. Write a `conftest.py` or module-level fixture that calls `clear_cache()` before each test to prevent `lru_cache` leakage.
2. Implement the following test cases (minimum):
   - `test_load_toolset_apis_self_service_returns_nonempty` — loads `self_service` from the real file; asserts result is a non-empty tuple of dicts with `method`, `path`, `action` keys.
   - `test_load_toolset_apis_unknown_toolset_raises_value_error` — passes a non-existent name; asserts `ValueError` is raised.
   - `test_load_toolset_apis_skips_comment_and_blank_lines` — creates a temp file with comment lines and blank lines; asserts they do not appear in the result.
   - `test_load_toolset_apis_malformed_line_ignored` — line with fewer than 3 pipe-separated parts is silently skipped (no exception).
   - `test_load_toolset_inheritance_includes_parent_apis` — `self_service_provision` inherits from `self_service`; assert that known `self_service` action names appear in the result.
   - `test_load_toolset_inheritance_missing_parent_raises` — creates a temp file with `@inherit:nonexistent`; asserts `ValueError`.
   - `test_clear_cache_allows_fresh_reload` — loads a toolset, writes a modified temp file into the toolsets path (or monkeypatches `TOOLSETS_DIR`), calls `clear_cache()`, reloads; asserts the new data is returned.
   - `test_get_confirmation_for_operation_manual_level` — passes `POST /vdbs/vdb-123/delete`; asserts `level == "manual"`.
   - `test_get_confirmation_for_operation_no_match_returns_none` — passes `GET /vdbs/vdb-123`; asserts `level == "none"`.
   - `test_requires_confirmation_true_for_delete` — passes a known destructive path; asserts `True`.
   - `test_requires_confirmation_false_for_read` — passes a read path; asserts `False`.
3. Each function AI-generated in this module must carry an `# AI-generated` inline comment on the first line of the function body.

### Output
- Success: `tests/test_loader.py` created; all tests pass; coverage for `config/loader.py` is recorded.
- Failure: Any test fails — fix the test or identify a real loader bug; document in AC-4 evidence.
- Side effect: `lru_cache` state is reset between test invocations via the fixture.

### Acceptance Criteria
- [ ] AC-1: Given the real `self_service.txt` file, when `load_toolset_apis("self_service")` is called, then it returns a non-empty tuple with at least one entry having `action == "search_vdbs"`.
- [ ] AC-2: Given a non-existent toolset name, when `load_toolset_apis` is called, then `ValueError` is raised with "Unknown toolset" in the message.
- [ ] AC-3: Given a malformed line (missing `|` separators), when `load_toolset_apis` parses the file, then the malformed line is silently skipped and valid lines are still returned.
- [ ] AC-4: Given `POST /vdbs/vdb-abc/delete` and the real `manual_confirmation.txt`, when `get_confirmation_for_operation` is called, then the returned dict has `level == "manual"`.
- [ ] AC-5: Given a call to `clear_cache()`, when `load_toolset_apis` is re-invoked, then the cache-miss reload executes without error.

---

## FR-003: Unit tests for dct_client/client.py retry and backoff behaviour

### Description
Creates `tests/test_client_retry.py` with AI-generated unit tests verifying that `DCTAPIClient.make_request` retries on 5xx responses with exponential backoff, does not retry on 4xx responses, and raises `DCTClientError` after exhausting all retries.

### Input
- `src/dct_mcp_server/dct_client/client.py` — `DCTAPIClient.make_request` under test
- `src/dct_mcp_server/core/exceptions.py` — `DCTClientError` (expected raise type)
- `src/dct_mcp_server/config/config.py` — `get_dct_config()` (must be patched)

### Processing
1. Create a `conftest.py` or module fixture that monkeypatches `DCT_API_KEY=test-key` and `DCT_BASE_URL=http://localhost:9999` before constructing `DCTAPIClient`.
2. Use `unittest.mock.AsyncMock` to patch `httpx.AsyncClient.request` for response control without network I/O.
3. Implement the following test cases (minimum):
   - `test_make_request_success_returns_json` — mock returns HTTP 200 with `Content-Type: application/json`; assert the returned dict matches the mocked JSON body.
   - `test_make_request_non_json_response_returns_response_key` — mock returns HTTP 200 with `Content-Type: text/plain`; assert returned dict is `{"response": <text>}`.
   - `test_make_request_4xx_raises_immediately_no_retry` — mock returns HTTP 404; assert `DCTClientError` is raised after exactly 1 attempt (not retried).
   - `test_make_request_5xx_retries_up_to_max` — mock always returns HTTP 503; with `max_retries=3`, assert `DCTClientError` raised and the mock was called exactly 3 times.
   - `test_make_request_5xx_succeeds_on_second_attempt` — mock returns 503 on attempt 1, 200 on attempt 2; assert success and that the mock was called exactly 2 times.
   - `test_make_request_exponential_backoff_called` — patch `asyncio.sleep`; assert it was called with `2**0` after the first failure and `2**1` after the second.
   - `test_make_request_connection_error_retries` — mock raises `httpx.ConnectError`; assert `DCTClientError` raised after `max_retries` attempts.
   - `test_authorization_header_prepends_apk` — inspect the `headers` dict after `DCTAPIClient.__init__`; assert `Authorization` value starts with `"apk "`.
4. Each function AI-generated in this module must carry an `# AI-generated` inline comment on the first line of the function body.

### Output
- Success: `tests/test_client_retry.py` created; all tests pass without network access.
- Failure: Test reveals an actual bug (e.g., 4xx is retried when it should not be) — document in AC-4 evidence and fix if within scope.
- Side effect: `asyncio.sleep` is patched in backoff tests to avoid real delays.

### Acceptance Criteria
- [ ] AC-1: Given an HTTP 200 response with a JSON body, when `make_request` is called, then the returned dict matches the JSON payload.
- [ ] AC-2: Given an HTTP 404 response (client error), when `make_request` is called, then `DCTClientError` is raised and the mock is called exactly once (no retry).
- [ ] AC-3: Given an HTTP 503 response on every attempt with `max_retries=3`, when `make_request` is called, then `DCTClientError` is raised and the mock was called exactly 3 times.
- [ ] AC-4: Given HTTP 503 on attempt 1 and HTTP 200 on attempt 2, when `make_request` is called, then the successful response is returned and the mock was called exactly 2 times.
- [ ] AC-5: Given `asyncio.sleep` patched, when retries occur, then `sleep` is called with `2**0` and `2**1` for the first and second backoff intervals respectively.

---

## FR-004: Unit tests for manual_confirmation.txt rule matching

### Description
Creates `tests/test_confirmation.py` with AI-generated unit tests verifying all five confirmation levels (`standard`, `elevated`, `manual`, `retention_check`, `policy_impact_check`) match and do not match the expected request patterns.

### Input
- `src/dct_mcp_server/config/loader.py` — `get_confirmation_for_operation`, `requires_confirmation`, `_path_matches`, `load_manual_confirmation_rules`
- `src/dct_mcp_server/config/mappings/manual_confirmation.txt` — real rules file used for integration tests; also synthetic data for isolated unit tests

### Processing
1. Write a fixture that calls `clear_cache()` before each test to reset the `lru_cache` on `load_manual_confirmation_rules`.
2. Implement the following test cases (minimum):
   - `test_manual_confirmation_delete_vdb` — `POST /vdbs/any-id/delete` → `level == "manual"`.
   - `test_manual_confirmation_delete_bookmark` — `DELETE /bookmarks/bm-1` → `level == "manual"`.
   - `test_no_confirmation_get_vdb_search` — `POST /vdbs/search` → `level == "none"`.
   - `test_no_confirmation_get_vdb_details` — `GET /vdbs/vdb-1` → `level == "none"`.
   - `test_retention_check_level_parsed` — `PATCH /snapshots/snap-1` → `level == "retention_check"` with `conditional == True` and `threshold_days == 7`.
   - `test_path_matches_with_path_param` — `_path_matches("/vdbs/abc-123/delete", "/vdbs/{vdbId}/delete")` → `True`.
   - `test_path_matches_no_match` — `_path_matches("/vdbs/search", "/vdbs/{vdbId}/delete")` → `False`.
   - `test_path_matches_exact_path_no_params` — `_path_matches("/vdbs/search", "/vdbs/search")` → `True`.
   - `test_requires_confirmation_true_for_destructive` — `requires_confirmation("POST", "/vdbs/x/delete")` → `True`.
   - `test_requires_confirmation_false_for_read` — `requires_confirmation("GET", "/vdbs/x")` → `False`.
   - `test_wildcard_method_matches_any` — create a synthetic rule with method `*`; verify it matches both `GET` and `DELETE`.
   - `test_first_matching_rule_wins` — create synthetic rules where two patterns match; verify first rule's level is returned.
3. Each function AI-generated in this module must carry an `# AI-generated` inline comment.

### Output
- Success: `tests/test_confirmation.py` created; all tests pass.
- Failure: A mismatch in rule ordering or path pattern logic reveals a real bug — document as AC-4 evidence.
- Side effect: `clear_cache()` called in fixture to prevent `lru_cache` test contamination.

### Acceptance Criteria
- [ ] AC-1: Given `POST /vdbs/any-uuid/delete` against the real `manual_confirmation.txt`, when `get_confirmation_for_operation` is called, then `level == "manual"`.
- [ ] AC-2: Given `GET /vdbs/any-uuid` (no matching rule), when `get_confirmation_for_operation` is called, then `level == "none"` and `message is None`.
- [ ] AC-3: Given `PATCH /snapshots/snap-1` against the real file, when `get_confirmation_for_operation` is called, then `conditional == True` and `threshold_days == 7`.
- [ ] AC-4: Given `_path_matches("/vdbs/abc-123/delete", "/vdbs/{vdbId}/delete")`, then the function returns `True`.
- [ ] AC-5: Given two synthetic rules where the first matches and the second also matches, when `get_confirmation_for_operation` is called, then the first rule's level is returned.

---

## Quality Rules

| Rule | Description | Enforcement | Status | Evidence |
|------|-------------|-------------|--------|----------|
| QR-1: No live network in tests | All `httpx` calls must be mocked; no real DCT API key or URL required | `pytest` must pass with `DCT_API_KEY=test-key DCT_BASE_URL=http://localhost:9999`; CI has no network access to DCT | Pending | — |
| QR-2: Cache isolation between tests | `clear_cache()` called in a pytest autouse fixture before each test involving `lru_cache`'d functions | Code review: confirm `conftest.py` has the fixture; `pytest -v` output shows no test-order dependency failures | Pending | — |
| QR-3: API backward compatibility | The test scaffold must not modify the signatures or behaviour of `loader.py`, `client.py`, or confirmation logic — tests are additive only | PR diff must show zero changes to `src/` except `config/loader.py` cache fixture (if needed) and dependency files | Pending | — |
| QR-4: Migration path documented | `requirements.txt` and `pyproject.toml` changes must be backward-compatible — existing CI that runs `pip install -r requirements.txt` must not break | `pip check` in CI; verify no version conflicts with existing dependencies | Pending | — |
| QR-5: AI-generation evidence | At least one test per module carries an `# AI-generated` comment; commit message references S1.5 | Grep CI check: `grep -r "# AI-generated" tests/` → at least 3 matches; PR description links to S1.5 checklist | Pending | — |

---

## Edge Cases

- EC-1: `load_toolset_apis` called with a toolset name that is an empty string → must raise `ValueError` (the file path `.txt` would not match any valid toolset).
- EC-2: A toolset `.txt` file that contains only comments and blank lines (no API entries) → `load_toolset_apis` returns an empty tuple; `validate_toolset_config` returns a non-empty errors list.
- EC-3: Circular `@inherit` chain (toolset A inherits B which inherits A) → currently no cycle detection in `loader.py`; test must confirm whether this causes infinite recursion and document the behaviour; if it causes a `RecursionError`, that is a latent bug to note in AC-4 evidence.
- EC-4: `DCTAPIClient.make_request` called with `json=None` and `data=None` → `json_data = None`; the request is sent with no body; verify no `TypeError` is raised.
- EC-5: `manual_confirmation.txt` rule where `level` contains a colon but the integer part is missing (e.g., `retention_check:`) → `int(level.split(":")[1])` raises `ValueError`; test must verify `get_confirmation_for_operation` handles this gracefully or documents the crash as a known limitation.
- EC-6: Path with multiple path parameters (e.g., `/access-groups/{groupId}/scopes/{scopeId}`) → `_path_matches` regex expansion must handle both parameters correctly.
- EC-7: `DCTAPIClient` constructed with `DCT_MAX_RETRIES=1` → single attempt; `make_request` should raise `DCTClientError` on the first 5xx without calling `asyncio.sleep`.
- EC-8: `load_manual_confirmation_rules` called when `manual_confirmation.txt` does not exist → returns an empty tuple (no exception); `requires_confirmation` returns `False` for all paths.

## Error Scenarios

- ERR-1: `pytest` import fails due to missing package after `pip install -r requirements.txt` → check for version pinning conflicts; the `dev` extras in `pyproject.toml` and `requirements.txt` must be consistent.
- ERR-2: `asyncio_mode = "auto"` in `pyproject.toml` conflicts with an explicit `@pytest.mark.asyncio` decorator on a test → pytest-asyncio ≥0.21 emits a warning but still runs; remove redundant decorators.
- ERR-3: `lru_cache` not cleared before a test that patches `TOOLSETS_DIR` → stale cached data causes test to use the old file path; fixture must call `clear_cache()` before monkeypatching, not after.
- ERR-4: `DCTAPIClient.__init__` raises `ValueError` during collection phase because env vars are absent → `conftest.py` must set env vars at session scope before any test module is imported; use `pytest` `autouse=True, scope="session"` fixture.
- ERR-5: `asyncio.sleep` not patched in retry tests → test takes `2**0 + 2**1 = 3` real seconds per run; patch `asyncio.sleep` with `AsyncMock` to make tests instant.

## Performance Considerations

- Tests must complete in under 5 seconds for the entire suite (no real I/O, no real `asyncio.sleep`); if total runtime exceeds 5 seconds the async mocks are not being applied correctly.
- `lru_cache` on `load_toolset_apis` and `load_manual_confirmation_rules` means the first test in a session that loads a toolset will read from disk; subsequent tests hit the cache. Cache-invalidation tests must account for this ordering.
- Coverage collection with `pytest-cov` adds ~10–20% overhead; total suite wall-clock time with coverage should stay under 10 seconds.

---
<!-- Cross-reference: FR descriptions map to Goals (G1–G4) in the vision doc.
     FR Acceptance Criteria satisfy Success Criteria (SC1–SC5) in the vision doc.
     Quality Rules and Edge Cases address Constraints and Risks from the vision doc.
     FR-IDs here are referenced in the design and tasks specs. -->
