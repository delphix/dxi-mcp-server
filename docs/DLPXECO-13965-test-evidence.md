# Test Evidence: DLPXECO-13965

**Date**: 2026-05-11
**Worktree**: `/Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965`
**Scope of this evidence**: **mocked pytest suite only**. Per the test plan, live-DCT smoke testing is reserved for the `validate` phase and is NOT performed here.

---

## Environment

| Property | Value |
|----------|-------|
| Python | 3.11.6 (`.venv/bin/python3`, managed by `uv`) |
| pytest | 9.0.3 |
| pytest-asyncio | 1.3.0 (Mode.STRICT) |
| fastmcp | 3.2.0 |
| dct-mcp-server | 2026.0.1.0rc0 (editable install from this worktree) |
| Test command | `uv run pytest tests/dlpxeco-13965-test.py -v` |
| DCT live instance | NOT contacted (mocked at `DCTAPIClient.make_request` level — verified in test file lines 1–80) |

---

## Result summary

| Metric | Value |
|--------|-------|
| Tests collected | 22 |
| Tests passed | **22** |
| Tests failed | 0 |
| Tests errored | 0 |
| Tests skipped | 0 |
| Warnings | 1 (benign — see below) |
| Wall-clock duration | **0.82 s** |
| Verdict | **PASS** |

---

## Per-test status

| # | Test | AC / Scenario | Result |
|---|------|---------------|--------|
| 1 | `test_bulk_start_all_success` | AC-1 — FR-001 AC-1 (all-success aggregate) | PASS |
| 2 | `test_bulk_start_partial_failure` | AC-2 — FR-001 AC-2 (partial-success aggregate) | PASS |
| 3 | `test_bulk_start_all_failed` | AC-3 — FR-001 AC-3 (all-failed aggregate) | PASS |
| 4 | `test_bulk_start_empty_list_raises` | AC-4 — FR-001 AC-4 (`vdbIds=[]` rejected; zero DCT calls) | PASS |
| 5 | `test_bulk_start_single_element` | AC-5 — FR-001 AC-5 (`total==1` fan-out) | PASS |
| 6 | `test_bulk_start_respects_concurrency_cap` | AC-6 — FR-005 AC-1 (semaphore cap honoured) | PASS |
| 7 | `test_bulk_stop_above_threshold_returns_confirmation` | AC-7 — FR-002 AC-1 (`> 5` → confirmation envelope; zero DCT calls) | PASS |
| 8 | `test_bulk_stop_above_threshold_with_confirmed` | AC-8 — FR-002 AC-2 (`confirmed=True` executes; count appears in message) | PASS |
| 9 | `test_bulk_stop_below_threshold_no_confirmation` | AC-9 — FR-002 AC-3 (`≤ 5` executes immediately) | PASS |
| 10 | `test_bulk_disable_above_threshold_returns_confirmation` | AC-10 — FR-004 AC-1 (bulk_disable gate symmetric with bulk_stop) | PASS |
| 11 | `test_bulk_enable_no_confirmation_even_at_size` | AC-11 — FR-003 AC-1 (bulk_enable never gated) | PASS |
| 12 | `test_unknown_bulk_action_rejected` | AC-12 — FR-009 AC-1 (unknown action → MCPError, zero DCT calls) | PASS |
| 13 | `test_vdbIds_must_be_list` | AC-13 — FR-009 AC-2 (string `vdbIds` rejected) | PASS |
| 14 | `test_response_schema_stable` | AC-14 — FR-007 AC-1 (exact key set) | PASS |
| 15 | `test_logging_one_info_n_debug` | AC-15 — FR-008 AC-1 (1 INFO + N DEBUG records) | PASS |
| 16 | `test_single_vdb_action_unchanged` | AC-16 — FR-010 AC-1 (single-VDB regression on `vdb_tool` / `data_tool`) | PASS |
| 17 | `test_self_service_exposes_vdb_bulk_tool` | AC-17 — FR-006 AC-1 (tool visible under `self_service`) | PASS |
| 18 | `test_continuous_data_admin_exposes_vdb_bulk_tool` | AC-18 — FR-006 AC-2 (tool visible under `continuous_data_admin`) | PASS |
| 19 | `test_reporting_insights_has_no_vdb_bulk_tool` | AC-19 — FR-006 AC-3 (tool absent under `reporting_insights`) | PASS |
| 20 | `test_bulk_stop_exactly_5_executes_no_confirmation` | Edge — boundary at the `> 5` threshold (5 items must execute without gate) | PASS |
| 21 | `test_DCT_BULK_CONCURRENCY_zero_falls_back_to_5` | Edge — invalid env var falls back to default 5 | PASS |
| 22 | `test_async_timeout_on_one_vdb_does_not_abort_batch` | Edge — per-task exception isolated by `return_exceptions=True` | PASS |

All 19 acceptance criteria from the design doc map 1:1 to tests 1–19, and the three edge-case tests (boundary, env-var-fallback, exception-isolation) all pass.

---

## Raw pytest output

```
============================= test session starts ==============================
platform darwin -- Python 3.11.6, pytest-9.0.3, pluggy-1.6.0 -- /Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965/.venv/bin/python3
cachedir: .pytest_cache
rootdir: /Users/vinay.byrappa/Documents/GitHub/dxi-mcp-server/.worktrees/dlpxeco-13965
configfile: pyproject.toml
plugins: anyio-4.11.0, asyncio-1.3.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 22 items

tests/dlpxeco-13965-test.py::test_bulk_start_all_success PASSED          [  4%]
tests/dlpxeco-13965-test.py::test_bulk_start_partial_failure PASSED      [  9%]
tests/dlpxeco-13965-test.py::test_bulk_start_all_failed PASSED           [ 13%]
tests/dlpxeco-13965-test.py::test_bulk_start_empty_list_raises PASSED    [ 18%]
tests/dlpxeco-13965-test.py::test_bulk_start_single_element PASSED       [ 22%]
tests/dlpxeco-13965-test.py::test_bulk_start_respects_concurrency_cap PASSED [ 27%]
tests/dlpxeco-13965-test.py::test_bulk_stop_above_threshold_returns_confirmation PASSED [ 31%]
tests/dlpxeco-13965-test.py::test_bulk_stop_above_threshold_with_confirmed PASSED [ 36%]
tests/dlpxeco-13965-test.py::test_bulk_stop_below_threshold_no_confirmation PASSED [ 40%]
tests/dlpxeco-13965-test.py::test_bulk_disable_above_threshold_returns_confirmation PASSED [ 45%]
tests/dlpxeco-13965-test.py::test_bulk_enable_no_confirmation_even_at_size PASSED [ 50%]
tests/dlpxeco-13965-test.py::test_unknown_bulk_action_rejected PASSED    [ 54%]
tests/dlpxeco-13965-test.py::test_vdbIds_must_be_list PASSED             [ 59%]
tests/dlpxeco-13965-test.py::test_response_schema_stable PASSED          [ 63%]
tests/dlpxeco-13965-test.py::test_logging_one_info_n_debug PASSED        [ 68%]
tests/dlpxeco-13965-test.py::test_single_vdb_action_unchanged PASSED     [ 72%]
tests/dlpxeco-13965-test.py::test_self_service_exposes_vdb_bulk_tool PASSED [ 77%]
tests/dlpxeco-13965-test.py::test_continuous_data_admin_exposes_vdb_bulk_tool PASSED [ 81%]
tests/dlpxeco-13965-test.py::test_reporting_insights_has_no_vdb_bulk_tool PASSED [ 86%]
tests/dlpxeco-13965-test.py::test_bulk_stop_exactly_5_executes_no_confirmation PASSED [ 90%]
tests/dlpxeco-13965-test.py::test_DCT_BULK_CONCURRENCY_zero_falls_back_to_5 PASSED [ 95%]
tests/dlpxeco-13965-test.py::test_async_timeout_on_one_vdb_does_not_abort_batch PASSED [100%]

=============================== warnings summary ===============================
tests/dlpxeco-13965-test.py::test_DCT_BULK_CONCURRENCY_zero_falls_back_to_5
  tests/dlpxeco-13965-test.py:481: PytestWarning: The test <Function test_DCT_BULK_CONCURRENCY_zero_falls_back_to_5> is marked with '@pytest.mark.asyncio' but it is not an async function. Please remove the asyncio mark. If the test is not marked explicitly, check for global marks applied via 'pytestmark'.
    def test_DCT_BULK_CONCURRENCY_zero_falls_back_to_5(monkeypatch) -> None:

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 22 passed, 1 warning in 0.82s =========================
```

---

## Warning analysis (single, benign)

```
tests/dlpxeco-13965-test.py:481: PytestWarning: The test
<Function test_DCT_BULK_CONCURRENCY_zero_falls_back_to_5> is marked with
'@pytest.mark.asyncio' but it is not an async function.
```

**Cause**: `test_DCT_BULK_CONCURRENCY_zero_falls_back_to_5` is a synchronous function — it just calls a sync helper inside the bulk module — but it carries an `@pytest.mark.asyncio` decorator left over from a copy-paste during test authoring.

**Impact**: None — pytest-asyncio simply ignores the mark on a sync function. The test still runs and asserts the fallback behaviour (env var = `0` → cap = 5). The functional check is correct; only the decorator annotation is redundant.

**Action**: Cosmetic-only; can be cleaned up in a follow-up if desired. NOT a build failure and NOT a test failure. The post-test gate does not require remediating warnings.

---

## What was NOT tested in this phase (deferred to validate)

Per the test-plan addendum recorded during the design phase, the following are explicitly **deferred to the `validate` phase** and were NOT exercised here:

- Live-DCT smoke against a real DCT instance (would require `DCT_API_KEY` + `DCT_BASE_URL` and a server with real VDBs).
- End-to-end test through a real MCP client (Claude Desktop / Cursor / VS Code Copilot).
- Stress / scaling test beyond N=20 vdbIds.
- Cross-toolset tool listing through `list_tools()` over MCP from a live `fastmcp.Client` subprocess (AC-17 / AC-18 / AC-19 are covered here against the loader directly; the validate phase will run the same check through the MCP transport).

All four are scheduled for `validate` per the design open-questions section.

---

## Artifacts

- This file: `docs/DLPXECO-13965-test-evidence.md`
- Raw pytest stdout (also captured here in full): `/tmp/dlpxeco-13965-pytest.txt`
- Test source: `tests/dlpxeco-13965-test.py`
- No coverage report was generated for this run (`pytest-cov` is not in the dev-dep set and was not invoked).

---

## Verdict

**PASS — 22/22 mocked tests green. Proceeding to the post-test confirmation gate (do NOT auto-advance to `validate` per task instructions).**
