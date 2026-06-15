# Vision: DLPXECO-14014

## Problem Statement

The `dct-mcp-server` repository has no automated test suite — `requirements.txt` has pytest commented out and `find . -name 'test_*.py'` returns zero results (excluding the recently-merged DLPXECO-13799 hook-normalisation test). CI cannot enforce a coverage baseline (HG1) against an empty suite, and the project checklist item S1.5 ("AI-generated tests as standard practice") remains unchecked. Without a scaffold, future contributors have no established pattern for writing regression tests, and regressions in the three most critical pure-logic modules (`config/loader.py`, `dct_client/client.py`, confirmation rules) go undetected until an MCP client session surfaces them.

## Goals

- G1: Enable `pytest` to collect and pass at least 15 tests against `config/loader.py`, `dct_client/client.py`, and confirmation-rule matching without requiring a live DCT instance.
- G2: Produce a recorded coverage baseline percentage (AC-2) by running `pytest --cov=src/dct_mcp_server` so the CI coverage gate (HG1 ticket) has a concrete starting threshold to enforce.
- G3: Establish a test-authoring pattern (AI-generated, documented with a comment + commit trail) that future tickets can follow to satisfy the S1.5 "evidence" requirement.
- G4: Re-enable `pytest` and `pytest-asyncio` as first-class dependencies in `requirements.txt` and `pyproject.toml` so `uv sync` / `pip install -r requirements.txt` sets up a test-ready environment.

## Non-Goals

- NG1: End-to-end or integration tests that spawn a live DCT server or MCP stdio transport — those belong to the test-infra and test phases.
- NG2: Achieving a specific coverage percentage target in this ticket — coverage measurement is the goal; enforcing a gate is the HG1 ticket's responsibility.
- NG3: Test coverage for `tools/*_endpoints_tool.py`, `main.py`, or the dynamic tool generator — those require a running FastMCP context and are out of scope for this scaffold.
- NG4: Refactoring the tested modules (`loader.py`, `client.py`) as part of this ticket — tests must pass against the code as-is.
- NG5: Setting up Docker-based integration test infrastructure — that is tracked separately in `.claude/test/test-infra.md`.

## Success Criteria

- SC1: Running `pytest tests/` from the repo root collects at least 15 test cases and all pass with no live DCT credentials present.
- SC2: Running `pytest --cov=src/dct_mcp_server tests/` produces a coverage report without error, and the overall percentage is recorded in `docs/DLPXECO-14014/DLPXECO-14014-eval-results.md`.
- SC3: At least one test function in each of the three new modules (`test_loader.py`, `test_client_retry.py`, `test_confirmation.py`) carries an `# AI-generated` comment and is referenced in the commit message.
- SC4: The team can cite at least one specific regression risk or latent bug identified by an AI-generated test (per checklist S1.5 evidence requirement).
- SC5: `pyproject.toml` and `requirements.txt` both reference `pytest>=7.0.0`, `pytest-asyncio>=0.21.0`, and `pytest-cov` without them being commented out.

## Stakeholders

| Stakeholder | Interest |
|-------------|----------|
| Development team | Automated safety net for future changes to loader, client, and confirmation logic without requiring a live environment |
| CI / platform (HG1 ticket) | A non-empty test suite to run a coverage gate against — this ticket is a hard prerequisite |
| AI tooling (checklist S1.5) | Evidence that AI-generated tests are standard practice in the repository |
| Code reviewers | Established test patterns to reference when reviewing PRs that touch config or client code |

## Constraints

- Tests must run without any live DCT instance, API key, or network access — `httpx` calls in `DCTAPIClient` must be mocked using `unittest.mock` or `respx`.
- `config/loader.py` uses `@lru_cache`; tests that exercise cache invalidation must call `clear_cache()` to reset state between test cases, or monkeypatch the cache.
- `DCTAPIClient.__init__` calls `get_dct_config()` which reads environment variables; tests must patch or inject `DCT_API_KEY` and `DCT_BASE_URL` to avoid `ValueError` on missing env vars.
- Must be compatible with Python 3.11+ (matches project runtime constraint).
- No new third-party test dependencies beyond `pytest>=7.0.0`, `pytest-asyncio>=0.21.0`, and `pytest-cov` — all are standard and require no security review.
- The existing test in `tests/test_tool_factory_hooks.py` must continue to pass — do not break it.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| `lru_cache` on `load_toolset_apis` causes test state leakage between runs | High | Medium | Call `clear_cache()` in a `pytest` autouse fixture and after each cache-invalidation test; document the pattern in a module docstring |
| `DCTAPIClient.__init__` triggers env var validation, causing collection failures | High | High | Set `DCT_API_KEY` and `DCT_BASE_URL` via `monkeypatch.setenv` in a session-scoped fixture; add a `conftest.py` that patches `get_dct_config` |
| `httpx.AsyncClient` mock complexity causes brittle retry tests | Medium | Medium | Use `respx` for structured route-level mocking, or patch `httpx.AsyncClient.request` directly; document the chosen approach so future test authors follow the same pattern |
| Real toolset `.txt` files contain edge cases (malformed lines, `@inherit` chains) not covered by synthetic test data | Low | Low | Include one integration-style test that parses the real `self_service.txt` file and asserts known tool names appear; this guards against accidental file corruption |
| Coverage percentage is lower than expected, causing immediate tension about the HG1 gate threshold | Medium | Low | Record the exact baseline before any gate is set; communicate to HG1 ticket owner that the gate threshold should be set at baseline+delta, not a fixed 80% |
| Async test framework version mismatch (`pytest-asyncio` strict/auto mode) causes collection warnings or failures | Low | Medium | Pin `asyncio_mode = "auto"` in `pyproject.toml [tool.pytest.ini_options]` and document why; validate against the pinned version in CI before merging |

---
<!-- Cross-reference: Goals (G1–G4) map to FR descriptions in the functional spec.
     Success Criteria (SC1–SC5) map to Acceptance Criteria in FR-* entries.
     Constraints and Risks inform the Quality Rules and Edge Cases sections. -->
