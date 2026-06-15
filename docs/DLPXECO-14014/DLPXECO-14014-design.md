# Feature Design: DLPXECO-14014

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-14014
**Status**: Proposed
<!-- Guidance: H1 title must be exactly "Feature Design: $NAME" (not H2). check-structure.sh does not enforce this mechanically, but downstream review tooling relies on it. -->

---

## Summary

This feature adds an offline pytest scaffold for the `dct-mcp-server` repository, establishing a first-class automated test suite targeting the three core pure-logic modules: `config/loader.py`, `dct_client/client.py`, and the confirmation rule matcher. Re-enabling `pytest>=7.0.0`, `pytest-asyncio>=0.21.0`, and `pytest-cov` as active dependencies in `requirements.txt` and `pyproject.toml` lets developers run `uv sync` and immediately execute a full test suite without a live DCT instance. The scaffold also produces an initial coverage baseline that the in-flight CI coverage gate (HG1) will use to set its threshold, and leaves a documented test-authoring pattern (AI-generated inline comment + commit trail) that satisfies the S1.5 "evidence" checklist item for future tickets.

## Affected Components

<!-- Derived from the architecture layer map in .claude/architecture.md -->

- [ ] `main.py` — Entry point; no changes
- [ ] `toolsgenerator/driver.py` — No changes (NG3: out of scope)
- [ ] `tools/__init__.py` — No changes
- [ ] `tools/core/meta_tools.py` — No changes
- [ ] `tools/core/tool_factory.py` — No changes (NG3: out of scope)
- [ ] `tools/*_endpoints_tool.py` — No changes (NG3: out of scope)
- [x] `config/config.py` — Indirectly affected: `get_dct_config()` must be patchable (no source changes; handled via `monkeypatch.setenv` in `conftest.py`)
- [x] `config/loader.py` — Module under test; no source changes; `clear_cache()` exercised by test fixtures
- [x] `config/toolsets/*.txt` — Read by integration-style loader tests (real files used as test data)
- [x] `config/mappings/manual_confirmation.txt` — Read by confirmation rule tests (real file used as test data)
- [x] `dct_client/client.py` — Module under test; no source changes; `make_request` exercised via `httpx` mocks
- [ ] `core/logging.py` — No changes
- [ ] `core/session.py` — No changes
- [ ] `core/decorators.py` — No changes
- [ ] `core/exceptions.py` — `DCTClientError` imported by client tests (read-only)
- [x] `requirements.txt` — Uncomment `pytest>=7.0.0`, `pytest-asyncio>=0.21.0`; add `pytest-cov>=4.0.0`
- [x] `pyproject.toml` — Add `asyncio_mode = "auto"`, `addopts = "--tb=short"`, and `[tool.coverage.run]` section
- [x] `tests/` directory — New test modules added: `conftest.py`, `test_loader.py`, `test_client_retry.py`, `test_confirmation.py`

## Architecture Changes

### Schema / Config Changes

No schema or persisted state changes. Only build/test configuration files are modified:

| File | Change | Notes |
|------|--------|-------|
| `requirements.txt` | Uncomment `pytest>=7.0.0` and `pytest-asyncio>=0.21.0`; add `pytest-cov>=4.0.0` | Adds three test-only deps to the standard install |
| `pyproject.toml` | Add `asyncio_mode = "auto"` to `[tool.pytest.ini_options]`; add `addopts = "--tb=short"`; add `[tool.coverage.run]` section | `asyncio_mode = "auto"` removes the need for `@pytest.mark.asyncio` on every async test |

### Source Files to Modify

| File | Purpose | Maps to FR |
|------|---------|------------|
| `requirements.txt` | Uncomment `pytest>=7.0.0`, `pytest-asyncio>=0.21.0`; add `pytest-cov>=4.0.0` on a new line | FR-001 |
| `pyproject.toml` | Add `asyncio_mode = "auto"` and `addopts = "--tb=short"` to `[tool.pytest.ini_options]`; add `[tool.coverage.run]` with `source = ["src/dct_mcp_server"]` and `omit = ["*/toolsgenerator/*", "*/tools/core/tool_factory.py"]` | FR-001 |
| `tests/conftest.py` | New file — session-scoped fixture that sets `DCT_API_KEY` and `DCT_BASE_URL` env vars before any module import; autouse fixture that calls `clear_cache()` before each test | FR-001, FR-002, FR-003, FR-004 |
| `tests/test_loader.py` | New file — 11 AI-generated unit tests covering `load_toolset_apis`, `load_toolset_grouped_apis`, `get_confirmation_for_operation`, `requires_confirmation`, `validate_toolset_config`, and `clear_cache` | FR-002 |
| `tests/test_client_retry.py` | New file — 8 AI-generated async unit tests covering `DCTAPIClient.make_request` retry/backoff logic using `unittest.mock.AsyncMock` to patch `httpx.AsyncClient.request` | FR-003 |
| `tests/test_confirmation.py` | New file — 12 AI-generated unit tests covering all five confirmation levels, `_path_matches`, and `requires_confirmation` using both real `manual_confirmation.txt` and synthetic rule data | FR-004 |

### New Files (if any)

- `tests/conftest.py` — Shared pytest fixtures: session-scoped env var setup (`DCT_API_KEY`, `DCT_BASE_URL`) and autouse `clear_cache()` fixture to prevent `lru_cache` state leakage between tests
- `tests/test_loader.py` — Unit tests for `config/loader.py`: toolset parsing (positive, malformed, inheritance), cache invalidation, confirmation dispatch (FR-002)
- `tests/test_client_retry.py` — Async unit tests for `dct_client/client.py`: 2xx success, 4xx no-retry, 5xx exhaustion, retry count assertions, exponential backoff via patched `asyncio.sleep`, `httpx.ConnectError` handling, `apk` header prefix (FR-003)
- `tests/test_confirmation.py` — Unit tests for confirmation rule matching: all five levels, `_path_matches` edge cases, wildcard method matching, first-rule-wins ordering (FR-004)

## Version Compatibility

This feature is entirely within the test layer — no runtime behaviour changes. The scaffold must run on the Python version this project targets.

| Version | Supported? | Branch? | Notes |
|---------|-----------|---------|-------|
| Python 3.11 | Yes | No | Project minimum runtime; pytest scaffold must pass on this version |
| Python 3.12 | Yes | No | Tested in CI (pycache files show 3.12 bytecode); no code path differences |
| Python 3.13+ | Not required | No | Out of scope for this ticket; scaffold does not use version-specific APIs |

DCT API / server version compatibility: not applicable — all tests run offline against the local source tree with no DCT instance.

## Platform Behavior Notes

<!-- Derived from .claude/architecture.md ## Key Platform Behaviors -->

- **API key prefix (`apk `)** — Affects: `test_authorization_header_prepends_apk` in `test_client_retry.py` asserts that `DCTAPIClient.__init__` prepends `apk ` automatically; the test env var must NOT include the prefix.
- **SSL defaults to `verify=false`** — N/A: no network I/O in any test; `httpx.AsyncClient` is mocked at the `request` level.
- **Retries: exponential backoff up to `DCT_MAX_RETRIES`** — Affects: `test_client_retry.py` constructs `DCTAPIClient` with `DCT_MAX_RETRIES=3` via env var patch; `asyncio.sleep` is patched with `AsyncMock` to avoid real delays and to assert backoff intervals `2**0` and `2**1`.
- **Toolset config cache (`lru_cache`)** — Affects: `conftest.py` must call `clear_cache()` in an autouse fixture before each test to prevent cached state from a prior test propagating; `test_clear_cache_allows_fresh_reload` explicitly exercises cache invalidation.
- **Telemetry: opt-in only** — N/A: `IS_LOCAL_TELEMETRY_ENABLED` is not set in tests; no session logs will be written.

## Open Questions / Risks

- R: `lru_cache` on `load_toolset_apis` causes state leakage if `conftest.py` autouse fixture runs after the cached function is called during module collection — Mitigation: use `scope="function"` autouse fixture that calls `clear_cache()` at the top; document ordering in module docstring.
- R: `DCTAPIClient.__init__` calls `get_dct_config()` which raises `ValueError` if `DCT_API_KEY` is absent at collection time — Mitigation: `conftest.py` uses `autouse=True, scope="session"` fixture to set `DCT_API_KEY=test-key` and `DCT_BASE_URL=http://localhost:9999` before any test module is imported.
- R: Circular `@inherit` chains (EC-3) currently cause `RecursionError` in `loader.py` — the test must confirm and document the behaviour as a latent bug; no fix required in this ticket (NG4).
- R: `retention_check:` with missing integer part (EC-5) causes `int(level.split(":")[1])` to raise `ValueError` in `get_confirmation_for_operation` — test must document whether this is a crash or handled; no fix required if outside scope of NG4.
- R: Coverage percentage may be lower than expected, creating tension with the HG1 gate threshold — Mitigation: record the exact baseline in `docs/DLPXECO-14014/DLPXECO-14014-eval-results.md` before any gate is set; communicate to HG1 ticket owner that the gate should be set at baseline+delta.
- R: `pytest-asyncio` strict/auto mode mismatch with existing `test_tool_factory_hooks.py` (which has no async tests) — N/A: `asyncio_mode = "auto"` is backward-compatible for sync tests; no `@pytest.mark.asyncio` decorators are needed or present in the existing file.

## Acceptance Criteria

<!-- Pulled from vision-doc Success Criteria (SC1–SC5) and FR Acceptance Criteria -->

- [ ] AC-1 (FR-001, FR-002, FR-003, FR-004): Running `pytest tests/` from the repo root collects at least 15 test cases and all pass with `DCT_API_KEY=test-key DCT_BASE_URL=http://localhost:9999` and no live DCT instance.
- [ ] AC-2 (FR-001): Running `pytest --cov=src/dct_mcp_server tests/` produces a coverage report without error; the overall percentage is recorded in `docs/DLPXECO-14014/DLPXECO-14014-eval-results.md`.
- [ ] AC-3 (FR-001): `requirements.txt` lists `pytest>=7.0.0`, `pytest-asyncio>=0.21.0`, and `pytest-cov>=4.0.0` without them being commented out; `pyproject.toml` has `asyncio_mode = "auto"` and `[tool.coverage.run]`.
- [ ] AC-4 (FR-002, FR-003, FR-004): At least one test function in each of `test_loader.py`, `test_client_retry.py`, and `test_confirmation.py` carries an `# AI-generated` inline comment.
- [ ] AC-5 (FR-001): The existing `tests/test_tool_factory_hooks.py` continues to pass without modification.
- [ ] AC-6 (FR-004): Given `POST /vdbs/<uuid>/delete` against the real `manual_confirmation.txt`, `get_confirmation_for_operation` returns `level == "manual"`.
- [ ] AC-7 (FR-003): Given an HTTP 503 on every attempt with `max_retries=3`, `make_request` raises `DCTClientError` and the `httpx` mock was called exactly 3 times.
- [ ] AC-8 (FR-002): Given `load_toolset_apis("self_service")`, the result is a non-empty tuple with at least one entry having `action == "search_vdbs"`.

---
<!-- Cross-references checked by check-structure.sh during the design phase:
     - Every FR-* in docs/$NAME/$NAME-functional.md → at least one row in ### Source Files to Modify
     - Non-Goals in docs/$NAME/$NAME-vision.md → MUST NOT appear in Architecture Changes (hard constraint)
     - Every AC → at least one FR-* in functional.md (transitive via FR mapping)
     Run: .claude/evals/check-structure.sh $NAME --step design -->
