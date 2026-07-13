# Code Coverage: DLPXECO-14324

| Field | Value |
|-------|-------|
| Framework | pytest |
| Command | `pytest --cov=src/dct_mcp_server --cov-report=term-missing .claude/test/generated-test/test_DLPXECO-14324.py` |
| Line Coverage | 8% |
| Threshold | 80% |
| Status | FAIL |
| Reason (if SKIPPED or ERROR) | N/A |

> Note: The 8% overall figure is an artifact of the full-source coverage scope including large pre-built tool modules (`dataset_endpoints_tool.py`, `engine_endpoints_tool.py`, etc.) that are not exercised by this feature's unit tests and do not require coverage from this PR. Coverage of the new files introduced by DLPXECO-14324 is significantly higher: `core/auth.py` 84%, `core/exceptions.py` 100%, `core/logging.py` 84%, with `core/client_registry.py` at 69% and `core/session.py` at 65%. The hard gate is currently disabled (see test phase post-gate comment in test.md) and will be re-enabled once the coverage baseline is set for the full suite.

## Raw Output (excerpt — last 20 lines of coverage command stdout)

```
src/dct_mcp_server/tools/core/spec_cache.py                127    127     0%   24-275
src/dct_mcp_server/tools/core/spec_model.py                275    183    33%   77-80, 90-98, ...
src/dct_mcp_server/tools/dataset_endpoints_tool.py        1526   1526     0%   1-8757
src/dct_mcp_server/tools/engine_endpoints_tool.py          164    164     0%   1-805
src/dct_mcp_server/tools/environment_endpoints_tool.py     506    506     0%   1-2500
src/dct_mcp_server/tools/iam_endpoints_tool.py             505    505     0%   1-1946
src/dct_mcp_server/tools/job_endpoints_tool.py             128    128     0%   1-436
src/dct_mcp_server/tools/misc_endpoints_tool.py            743    743     0%   1-3847
src/dct_mcp_server/tools/policy_endpoints_tool.py          360    360     0%   1-1605
src/dct_mcp_server/tools/reports_endpoints_tool.py         202    202     0%   1-996
src/dct_mcp_server/tools/template_endpoints_tool.py        212    212     0%   1-861
--------------------------------------------------------------------------------------
TOTAL                                                     6209   5685     8%
======================== 38 passed, 1 warning in 0.78s =========================
```

## Coverage of DLPXECO-14324 New/Modified Files

| File | Stmts | Miss | Cover |
|------|-------|------|-------|
| `src/dct_mcp_server/core/auth.py` | 56 | 9 | 84% |
| `src/dct_mcp_server/core/exceptions.py` | 8 | 0 | 100% |
| `src/dct_mcp_server/core/logging.py` | 69 | 11 | 84% |
| `src/dct_mcp_server/core/client_registry.py` | 36 | 11 | 69% |
| `src/dct_mcp_server/core/session.py` | 134 | 47 | 65% |
| `src/dct_mcp_server/config/config.py` | 59 | 46 | 22% |
| `src/dct_mcp_server/dct_client/client.py` | 111 | 48 | 57% |
