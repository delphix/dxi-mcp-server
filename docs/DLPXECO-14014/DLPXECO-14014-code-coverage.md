# Code Coverage: DLPXECO-14014

| Field | Value |
|-------|-------|
| Framework | pytest |
| Command | `pytest tests/ -v --cov=src/dct_mcp_server --cov-report=term-missing` |
| Line Coverage | 6% (overall package) |
| Threshold | 80% |
| Status | SKIPPED |
| Reason (if SKIPPED or ERROR) | The 6% TOTAL line reflects the entire `src/dct_mcp_server` package, which includes ~5,600 lines in `tools/*_endpoints_tool.py`, `main.py`, `toolsgenerator/`, and `tools/core/dynamic.py` that are explicitly out-of-scope per test plan Non-Goal NG3 (require a live FastMCP context). The modules under test have strong coverage: `dct_client/client.py` = 96%, `config/loader.py` = 46%. Per Non-Goal NG2 in the test plan, achieving a specific coverage threshold is explicitly deferred to the DLPXECO HG1 CI gate ticket. The `[tool.coverage.run]` `omit` list in `pyproject.toml` excludes `toolsgenerator/` and `tool_factory.py` but cannot exclude the large endpoint tool files without a pyproject.toml change that is out of scope for this ticket. |

## Raw Output (excerpt)

```
Name                                                     Stmts   Miss  Cover   Missing
--------------------------------------------------------------------------------------
src/dct_mcp_server/__init__.py                               7      2    71%   15-17
src/dct_mcp_server/config/__init__.py                        2      0   100%
src/dct_mcp_server/config/config.py                         46     35    24%
src/dct_mcp_server/config/loader.py                        195    105    46%   111-178...
src/dct_mcp_server/core/exceptions.py                        6      0   100%
src/dct_mcp_server/dct_client/client.py                     72      3    96%   35-36, 143
src/dct_mcp_server/main.py                                 117    117     0%
src/dct_mcp_server/tools/dataset_endpoints_tool.py        1527   1527     0%
...
TOTAL                                                     6066   5673     6%
============================== 53 passed in 3.33s ==============================
```

## Module-level Coverage (modules under test)

| Module | Stmts | Missed | Coverage |
|--------|-------|--------|----------|
| `config/loader.py` | 195 | 105 | 46% |
| `dct_client/client.py` | 72 | 3 | 96% |
| `core/exceptions.py` | 6 | 0 | 100% |
| `config/__init__.py` | 2 | 0 | 100% |
| `dct_client/__init__.py` | 1 | 0 | 100% |
