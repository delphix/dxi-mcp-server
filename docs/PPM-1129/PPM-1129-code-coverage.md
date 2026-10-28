# Code Coverage: PPM-1129

| Field | Value |
|-------|-------|
| Framework | pytest |
| Command | `uv run --with pytest-cov pytest tests/ -m "not real_dct and not llm_driven and not scenario" --cov=src/dct_mcp_server --cov-report=term-missing` |
| Line Coverage | 88% |
| Threshold | 80% |
| Status | PASS |

## Key PPM-1129 File Coverage

| File | Stmts | Miss | Cover | Uncovered Lines |
|------|-------|------|-------|----------------|
| `src/dct_mcp_server/config/loader.py` | 316 | 6 | 98% | 395, 507, 582-585 |
| `src/dct_mcp_server/tools/core/vocabulary.py` | 126 | 5 | 96% | 156-158, 310, 331 |
| `src/dct_mcp_server/core/decorators.py` | 96 | 4 | 96% | 22-23, 101, 139 |
| `src/dct_mcp_server/tools/core/dynamic_confirmation.py` | 55 | 5 | 91% | 126-127, 142-144 |
| `src/dct_mcp_server/tools/core/spec_model.py` | 292 | 28 | 90% | 83, 212, 246, 258, 359, 363, 367, 371, 419, 427, 444, 450, 462, 465, 475, 480, 503-505, 509, 513, 517-522, 565 |
| `src/dct_mcp_server/tools/core/dynamic.py` | 491 | 84 | 83% | 35-36, 124-128, 138, 141-147, 210, 478, 543-547, 561, 568, 583-584, 588, 598, 829-836, 865-955 (truncated) |

All PPM-1129 primary files are above the 80% threshold.

## Raw Output (last 20 lines of coverage command stdout)

```
src/dct_mcp_server/core/session.py                         137     13    91%   83-85, 142-146, 150-152, 262, 267
src/dct_mcp_server/dct_client/__init__.py                    1      0   100%
src/dct_mcp_server/dct_client/client.py                    112     12    89%   25, 27, 42-51, 121-122, 227
src/dct_mcp_server/main.py                                 138     36    74%   59-60, 126-142, 155-156, 174, 189-204, 222-232, 239, 276-278, 298
src/dct_mcp_server/testing/__init__.py                       0      0   100%
src/dct_mcp_server/testing/cli.py                          119     51    57%   60-68, 73-116, 212-213, 217, 223-244, 247, 307-320, 328
src/dct_mcp_server/tools/__init__.py                        93      3    97%   57-59
src/dct_mcp_server/tools/core/__init__.py                    3      0   100%
src/dct_mcp_server/tools/core/audit.py                      20      2    90%   73-76
src/dct_mcp_server/tools/core/confirmation_levels.py       104     13    88%   101-102, 196-201, 324-325, 333, 381, 385, 403, 409, 411, 415
src/dct_mcp_server/tools/core/confirmation_resolver.py     101      0   100%
src/dct_mcp_server/tools/core/confirmation_store.py        128      9    93%   54-55, 86-88, 188-189, 278-279
src/dct_mcp_server/tools/core/confirmation_token.py         30      1    97%   103
src/dct_mcp_server/tools/core/dynamic.py                   491     84    83%   ...
src/dct_mcp_server/tools/core/dynamic_confirmation.py       55      5    91%   126-127, 142-144
src/dct_mcp_server/tools/core/endpoint_discovery.py         83      0   100%
src/dct_mcp_server/tools/core/floor_operations.py           51      7    86%   37-38, 73, 77-78, 112, 127
src/dct_mcp_server/tools/core/spec_model.py                292     28    90%   ...
src/dct_mcp_server/tools/core/vocabulary.py                126      5    96%   156-158, 310, 331
TOTAL                                                     3006    373    88%
1119 passed, 947 skipped, 25 deselected, 113 warnings in 194.88s (0:03:14)
```
