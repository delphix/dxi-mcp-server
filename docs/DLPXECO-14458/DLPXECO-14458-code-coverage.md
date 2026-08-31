# Code Coverage: DLPXECO-14458

| Field | Value |
|-------|-------|
| Framework | pytest |
| Command | pytest tests/unit/ --cov=src/dct_mcp_server --cov-report=term-missing -m 'not real_dct and not llm_driven and not scenario' |
| Line Coverage | 75% |
| Threshold | 80% |
| Status | FAIL |
| Reason (if SKIPPED or ERROR) | n/a |

**Note**: The 80% threshold gate is currently DISABLED (see test.md `<!-- DISABLED: coverage hard gate -->`). Coverage is recorded for tracking. New modules for DLPXECO-14458 (FR-004 through FR-007) have lower initial coverage because their primary execution paths require a live server subprocess:
- `floor_operations.py` (24%): pattern loading via `@lru_cache` not exercised in unit scope
- `velocity_counter.py` (31%): sliding-window counter not directly unit-tested
- `confirmation_store.py` (52%): grant store methods not directly unit-tested
- `confirmation_levels.py` (28%): elevated/manual validation not unit-tested end-to-end
- `dynamic.py` (65%): batch_intent, elicitation, and grant paths not reached in unit scope

These paths are covered structurally (code imports clean, functions exist, gate events fired) and by integration/functional tests.

## Per-Module Coverage (key new files)

| Module | Stmts | Miss | Cover | Low-coverage reason |
|--------|-------|------|-------|---------------------|
| `tools/core/audit.py` | 20 | 9 | 55% | Telemetry upload path (lines 72-75, 88, 91-96) not exercised without telemetry backend |
| `tools/core/confirmation_levels.py` | 53 | 38 | 28% | validate_elevated, validate_manual end-to-end paths only exercised via integration tests |
| `tools/core/confirmation_store.py` | 91 | 44 | 52% | Grant store create/consume/expire paths not unit-tested |
| `tools/core/confirmation_token.py` | 30 | 6 | 80% | Deprecated verify_confirmation_token (line 121-123) not in primary test path |
| `tools/core/dynamic.py` | 366 | 128 | 65% | batch_intent block (449-517), grant_token block (531-596), elicitation block (657-764) not reached |
| `tools/core/floor_operations.py` | 51 | 39 | 24% | get_floor_patterns (34-53), pattern matching (72-82, 104-129) not directly unit-tested |
| `tools/core/velocity_counter.py` | 78 | 54 | 31% | All counter increment/check/persist paths not unit-tested |

## Raw Output (excerpt — last 20 lines of coverage command stdout)

```
src/dct_mcp_server/tools/core/confirmation_resolver.py      58      8    86%   166-175
src/dct_mcp_server/tools/core/confirmation_store.py         91     44    52%   54-55, 76-80, 86-88, 107, 121-131, 149-179, 183-190, 194-197
src/dct_mcp_server/tools/core/confirmation_token.py         30      6    80%   45, 103, 106, 121-123
src/dct_mcp_server/tools/core/dynamic.py                   366    128    65%   33-34, 102-106, 116, 119-125, 188, 427, 442-445, 449-517, 531-596, ...
src/dct_mcp_server/tools/core/dynamic_confirmation.py       53      5    91%   125-126, 141-143
src/dct_mcp_server/tools/core/endpoint_discovery.py         83      0   100%
src/dct_mcp_server/tools/core/floor_operations.py           51     39    24%   34-53, 72-82, 104-129
src/dct_mcp_server/tools/core/meta_tools.py                 78      9    88%   50-51, 135-137, 228-231
src/dct_mcp_server/tools/core/spec_cache.py                127     13    90%   141, 146-147, 158-160, 175-176, 234-239, 255, 266-268
src/dct_mcp_server/tools/core/spec_model.py                275     95    65%   78, 110, 114, 150-197, ...
src/dct_mcp_server/tools/core/velocity_counter.py           78     54    31%   51, 59-107, 114-125, 153-176, 184-189, 224, 233
--------------------------------------------------------------------------------------
TOTAL                                                     2308    585    75%
======================== 602 passed, 1 warning in 3.00s ========================
```
