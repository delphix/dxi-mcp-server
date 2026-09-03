
### Step: implement

Eval check: `check-structure.sh DLPXECO-14609 --step implement`
Result: 1 passed, 0 failed — PASS (at least one non-docs file modified)

Post-gate:
- Modified files: src/dct_mcp_server/config/config.py, src/dct_mcp_server/tools/core/dynamic.py, tests/test_sensitive_input_gate.py
- All 744 unit tests pass (0 failures, 1 pre-existing warning)
- 16 new regression tests added in TestVerifyHostMarker and TestGateSecondLeg
