# Code Coverage: DLPXECO-13635

| Field | Value |
|-------|-------|
| Framework | pytest |
| Command | `uv run pytest .claude/test/generated-test/test_DLPXECO-13635.py --cov=src --cov-report=term-missing -v --tb=short` |
| Line Coverage | 0% |
| Threshold | 80% |
| Status | SKIPPED |
| Reason (if SKIPPED or ERROR) | This feature adds a Dockerfile, .dockerignore, and README section — it does not add or modify any Python source files under `src/`. All 19 test scenarios exercise Docker image behavior via `docker run` subprocess calls and static file checks; no Python server code is executed in the test process. pytest-cov reports 0% because the source under test runs inside a Docker container, not in the pytest process. Line coverage via pytest-cov is not applicable for Docker image validation tests. FR coverage is fully documented in `DLPXECO-13635-coverage.md`. |

## Raw Output (excerpt)

```
Name                                                     Stmts   Miss  Cover   Missing
--------------------------------------------------------------------------------------
src/dct_mcp_server/__init__.py                               7      7     0%   8-20
...
TOTAL                                                     6299   6299     0%

/path/to/coverage/control.py:958: CoverageWarning: No data was collected. (no-data-collected)
  self._warn("No data was collected.", slug="no-data-collected")

================== 16 passed, 3 skipped, 2 warnings in 28.99s ==================
```

Note: The 0% line coverage is expected and correct for this feature. The `src/` directory is unchanged — `git diff src/` is empty. The Docker image tests (S1–S18) run `docker run` subprocesses and do not import or execute Python server code within the pytest process.
