# Code Coverage: DLPXECO-14248

| Field | Value |
|-------|-------|
| Framework | pytest |
| Command | `uv run pytest tests/test_spec_model.py --cov=dct_mcp_server.tools.core.spec_model --cov-report=term-missing` |
| Line Coverage | 87% |
| Threshold | 80% |
| Status | PASS |
| Reason (if SKIPPED or ERROR) | N/A |

## Raw Output (excerpt)

```
Name                                          Stmts   Miss  Cover   Missing
---------------------------------------------------------------------------
src/dct_mcp_server/tools/core/spec_model.py     275     36    87%   77, 202, 205, 236, 248, 289, 293, 311, 316, 347, 351, 355, 359, 394, 400, 412, 415, 425, 430, 450-452, 456, 460, 464-469, 511, 514-516, 529-530
---------------------------------------------------------------------------
TOTAL                                           275     36    87%
============================== 13 passed in 0.72s ==============================
```

## Notes

- The test plan (S34) requires ≥ 85% line coverage. Measured 87% — threshold met.
- Uncovered lines (36 of 275) are mainly defensive branches in `SchemaObject._resolve()` for deeply nested allOf compositions and optional `Response` schema handling — these paths are not exercised by the synthetic spec fixture.
- Branch coverage is not separately reported by the default `pytest-cov` term-missing format; the 87% line coverage is consistent with the S34 pass requirement.
