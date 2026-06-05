# Code Coverage: DLPXECO-13984

| Field | Value |
|-------|-------|
| Framework | pytest |
| Command | `PYTHONPATH=src pytest .claude/test/generated-test/test_DLPXECO-13984.py --cov=dct_mcp_server.tools.core.spec_cache --cov=dct_mcp_server.tools.core.dynamic --cov=dct_mcp_server.tools.core.confirmation_resolver --cov-report=term-missing` |
| Line Coverage | 77% (across the 3 new feature modules: 489 stmts, 112 missed) |
| Threshold | 80% |
| Status | FAIL |
| Reason (if SKIPPED or ERROR) | Coverage is 77% against the 80% threshold when measuring only the three new feature modules (`spec_cache.py` 80%, `confirmation_resolver.py` 85%, `dynamic.py` 75%). The 3 percentage-point gap is due to the `register_dynamic_tools()` function body (lines 53–65) and some `_get_spec()` fallback branches (lines 78–80) which require a live FastMCP app instance to exercise. Per the `## POST-GATE` in test.md, the coverage hard gate is disabled (`<!-- DISABLED: coverage hard gate -->`); this result is recorded for informational purposes only and does not block phase completion. |

## Per-Module Breakdown

| Module | Stmts | Missed | Coverage | Uncovered Lines |
|--------|-------|--------|----------|-----------------|
| `spec_cache.py` | 148 | 30 | 80% | 132, 152, 155, 160-161, 168, 172-174, 189-190, 196, 204-206, 219-220, 255-262, 267, 274-275, 281-285, 296-298 |
| `confirmation_resolver.py` | 40 | 6 | 85% | 101-102, 125, 132-134 |
| `dynamic.py` | 301 | 76 | 75% | 53-65, 78-80, 123, 147, 153, 165, 217, 313-318, 345-347 (and others) |
| **TOTAL (feature surface)** | **489** | **112** | **77%** | — |

## Raw Output (excerpt)

```
src/dct_mcp_server/tools/core/confirmation_resolver.py      40      6    85%   101-102, 125, 132-134
src/dct_mcp_server/tools/core/dynamic.py                   301     76    75%   53-65, 78-80, 123, 147, 153, 165, 217, 313-318, 345-347, ...
src/dct_mcp_server/tools/core/spec_cache.py                148     30    80%   132, 152, 155, 160-161, 168, ...
TOTAL                                                      489    112    77%
```

## Notes

- The 80% hard gate is disabled per `test.md` (`<!-- DISABLED: coverage hard gate -->`).
- `dynamic.py` uncovered lines are primarily in `register_dynamic_tools()` (requires live FastMCP app), `_get_spec()` app.state exception path, and some deep `$ref` resolution branches.
- `spec_cache.py` uncovered lines include some `_write_cache_meta` exception paths and the `_DEFAULT_CACHE_DIR` mkdir codepath.
- All 34 automatable scenarios from the test plan passed; overall test count 39/39.
