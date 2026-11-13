# APIGW-31432 — Test Evidence

## Landscape / Environment

Lite mode — `test` phase not run; evidence generated from the pr-phase smoke check below.

- Python: 3.11
- Test runner: `uv run pytest`
- Environment: local macOS (darwin); no live DCT connection required (all tests are mocked)

## Functional (primary)

Not applicable — lite mode has no test-plan.md scenarios (test-generation/test phases are not part of this workflow).

## Smoke (previously-generated functional tests)

| File | Outcome | Pass | Fail | Note |
|------|---------|------|------|------|
| `.claude/test/generated-test/test_DLPXECO-13984.py` | PASS | 35 | 0 | Dynamic 2-Tool Architecture tests — no regressions |
| `.claude/test/generated-test/test_DLPXECO-14324.py` | PASS | 27 | 0 | Stdio-only embedded auth tests — no regressions (requires `DCT_API_KEY=test-key DCT_BASE_URL=http://localhost`) |

Additionally, full unit test suite (`tests/unit/`) executed:

| Suite | Outcome | Pass | Fail | Note |
|-------|---------|------|------|------|
| `tests/unit/` (986 tests) | PASS | 986 | 0 | Includes `test_vocabulary_regression.py` and `test_vocabulary.py` for APIGW-31432 |

Vocabulary regression tests added in this PR:
- `test_compliance_node_alias_is_registered` — passes; confirms `compliance node` is present in `server_instructions.md`
- `test_to_canonical_translates_and_preserves_case[compliance node → Continuous Compliance engine]` — passes
- `test_to_canonical_translates_and_preserves_case[compliance nodes → Continuous Compliance engines]` — passes

## Failure Triage

None. All smoke and unit tests passed.

## Summary

Lite mode: no functional test-plan (test phase skipped); smoke: 2 of 2 generated-test files passed (62 tests total) + full unit suite 986/986. APIGW-31432 vocabulary regression tests all pass.
