
### Step: implement

**POST-GATE checks — implement**

| Check | Result |
|-------|--------|
| At least one source file modified | PASS (4 source files + 1 new test file) |
| Lint (ruff check + format) | PASS |
| Unit tests: TestHostApprovalFlag (7 tests) | PASS |
| Integration tests: test_host_approval_levels (7 tests) | PASS |
| Full suite excl e2e + functional: 789 tests | PASS |
| Functional test failures (tests/functional/test_confirmation_handshake.py) | 7 pre-existing failures (confirmed same on main) |

**Files modified:**
- `src/dct_mcp_server/config/config.py` — added `confirmation_host_approval` env var + help text
- `src/dct_mcp_server/tools/core/confirmation_levels.py` — added `_host_approval_configured()`, modified `build_required_fields()`
- `src/dct_mcp_server/tools/core/dynamic.py` — imported `_host_approval_configured`, added guards at elevated/manual call sites
- `src/dct_mcp_server/config/mappings/manual_confirmation.txt` — removed all 44 `{name}` placeholders

**Files created:**
- `tests/integration/test_host_approval_levels.py` — 7 integration tests (S1–S7)
- `tests/test_sensitive_input_gate.py` (extended) — 7 unit tests for `TestHostApprovalFlag`
