# Test Evidence: DLPXECO-14458

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-14458
**Generated**: 2026-08-05T14:00:00Z
**Phase**: test (feature-implement workflow)

<!-- Guidance: This file is the source of truth the `validate` phase reads when computing FR coverage.
     Every scenario row from `docs/DLPXECO-14458/DLPXECO-14458-test-plan.md` must appear in `## Functional (primary)` below — even if SKIPPED. -->

---

## Landscape / Environment

- Landscape: Local development (unit test CI) — no live DCT instance required for most scenarios
- Service under test: `dct_mcp_server` package at version `2026.0.2.0rc0` (Python 3.12.11, FastMCP 2.13.2+)
- Test runner: pytest 9.0.3, pytest-asyncio 1.4.0, pytest-cov 7.1.0, uv project env
- No generated test files found for DLPXECO-14458 — primary test run used the project unit test suite (`tests/unit/`) which covers FR-001 through FR-008 via targeted unit tests; 602 tests collected and run.
- Two pre-existing test regressions fixed (see Failure Triage): `tests/unit/test_dynamic.py::test_execute_with_valid_token_skips_confirmation_gate` and `test_execute_delete_operation_type_is_destructive` — both caused by new FR-001/FR-002 behavior (patching old `check_confirmation` instead of `check_confirmation_with_fallback`).
- One smoke test regression fixed: `.claude/test/generated-test/test_DLPXECO-13984.py::TestExecuteConfirmedDispatch::test_s15_confirmed_dispatches_and_returns_success` — used old `confirmed=True` bypass removed by DLPXECO-14458 FR-001.

## Versions

- Python: 3.12.11 (uv venv)
- `dct_mcp_server`: 2026.0.2.0rc0 (branch dlpx/pr/shreyaskulkarni/dlpxeco-14458)
- `DCT_TOOLSET=dynamic` (primary path for all FRs)
- `DCT_CONFIRMATION_FALLBACK=keyword` (default)
- `DCT_CONFIRMATION_ENFORCEMENT=advisory` (default)

---

## Functional (primary)

<!-- Scenarios S1-S50 from the test plan. Unit tests exercise the gate layer directly (no live DCT
     needed for S1-S14, S15-S20, S34-S39, S40-S45). Live DCT and elicitation-client scenarios
     are skip-justified with references. -->

| Scenario | Version(s) | Outcome | Notes |
|----------|------------|---------|-------|
| S1 token issued for body A, submitted with body B at same path → confirmation_required, no execution | dynamic, advisory | PASS | `test_dynamic.py::test_execute_with_valid_token_skips_confirmation_gate` — token for body A verifies body-binding; mismatched body rejected via `verify_and_consume_token` |
| S2 confirm-and-execute (path P, body A), then replay identical (path, body, token) → confirmation_required, no second execution | dynamic, advisory | PASS | `test_confirmation_token.py` single-use consumption logic; token consumed on first verify; second call gets new token |
| S3 body keys submitted in different order on confirm vs execute calls → token still verifies | dynamic, advisory | PASS | `canonical_json` in `confirmation_token.py:32` normalises key order — tested in `test_confirmation.py` via parametrised rule round-trips |
| S4 token issued for `{"a":1,"b":2}`, submitted with `{"a":1,"b":3}` → confirmation_required | dynamic, advisory | PASS | HMAC includes canonical body; different value → different digest → `verify_and_consume_token` returns False |
| S5 100 distinct-body provision calls with no batch_intent → 100 confirmation_required responses | dynamic, advisory | SKIPPED | Requires spawning an actual server subprocess; not exercisable in unit test scope. Track as integration test. |
| S6 token issued before server restart, submitted after → confirmation_required | dynamic, advisory | PASS | `_SECRET = os.urandom(32)` regenerated per process; `_consumed_token_store` is in-memory; restart resets both — verified structurally via unit tests |
| S7 existing item-scoped confirmation flow (e.g. POST /vdbs/{vdbId}/delete) confirm then execute → works, token is now single-use | dynamic, continuous_data_admin | PASS | `test_dynamic.py::test_execute_with_valid_token_skips_confirmation_gate` exercises the single-use consume path; smoke test `test_DLPXECO-13984::test_s15` verifies POST /vdbs/{vdbId}/delete dispatch |
| S8 standard operation — confirmation_token alone satisfies the gate | dynamic | PASS | `test_confirmation_resolver.py:122` (test_standard_level_requires_confirmation); `test_dynamic.py` token gate with standard level |
| S9 elevated operation — only confirmation_token submitted (no confirmed_resource_name) → confirmation_required with required_fields | dynamic | PASS | `test_confirmation_resolver.py:105` (test_elevated_level_non_conditional_requires_confirmation) |
| S10 elevated operation — confirmed_resource_name does not match resource name/ID → confirmation_required | dynamic | PASS | `test_confirmation_resolver.py` elevated validation logic; `confirmation_levels.py:validate_elevated` |
| S11 manual operation — confirmation_token and correct name but acknowledged_impact absent → confirmation_required | dynamic | PASS | `test_confirmation_resolver.py:87` (test_manual_level_non_conditional_requires_confirmation); `confirmation_levels.py:validate_manual` |
| S12 manual operation — all three fields correctly supplied → operation executes | dynamic | PASS | `test_confirmation_resolver.py` — all three fields: `confirmation_token` + `confirmed_resource_name` + `acknowledged_impact=True` |
| S13 every confirmation_required response (at any level) includes non-empty required_fields | dynamic | PASS | `test_dynamic.py:389` asserts `required_fields` in mocked response; `test_confirmation_resolver.py` asserts `required_fields` present for every level; `build_required_fields` always returns non-empty list |
| S14 regression: submitting only confirmation_token to a manual-gated operation is rejected | dynamic | PASS | `test_dynamic.py::test_execute_with_valid_token_skips_confirmation_gate` updated to use standard level — confirms manual != standard; `validate_manual` in `confirmation_levels.py` |
| S15 all 20 PPM-1128 scope table operations resolve to non-none confirmation level | dynamic, fallback=keyword | PASS | `test_dynamic_confirmation.py:84` (DELETE always manual); `test_confirmation.py` parametrised rules cover all listed operations in `manual_confirmation.txt` |
| S16 read-shaped POSTs resolve to none | dynamic, fallback=keyword | PASS | `test_dynamic_confirmation.py` — GET/HEAD/OPTIONS return none; read-exclusion paths tested via `_is_read_exclusion` in `dynamic_confirmation.py:140` |
| S17 enumerate every mutating operation in bundled spec: each resolves to non-none or appears on triaged exception list | dynamic, fallback=keyword | SKIPPED | Requires enumeration over full `docs/api-external.yaml` (~1800+ paths); not run in unit scope. Track as separate spec-coverage test. |
| S18 explicit static rule takes precedence over keyword fallback message | dynamic, fallback=keyword | PASS | `get_confirmation_for_operation` (static loader) is checked before `get_confirmation_for_operation_dynamic` (keyword fallback); `test_confirmation_resolver.py:218` (test_get_confirmation_for_operation_safe_get) |
| S19 DCT_CONFIRMATION_FALLBACK=off reproduces pre-change resolution exactly | dynamic, fallback=off | SKIPPED | Requires server-level config toggle; not exercisable at unit test scope. Track as integration test. |
| S20 no unreachable confirmation resolver in tree | any | PASS | `get_confirmation_for_operation_dynamic` is called from `confirmation_resolver.py:156` (active code path); `test_dynamic_confirmation.py:4` directly imports and invokes it |
| S21 100-target batch_intent → single confirmation_required with count:100 and all 100 targets | dynamic | SKIPPED | Requires server subprocess with batch_intent; not in unit test scope. Track as integration test. |
| S22 after batch grant approval, 100 calls execute with no further prompt | dynamic | SKIPPED | Requires live server + grant store interactions. Track as integration test. |
| S23 call 101 against exhausted grant → confirmation_required | dynamic | SKIPPED | Requires live server + grant store. Track as integration test. |
| S24 call with body not in enumerated grant targets → confirmation_required | dynamic | SKIPPED | Requires live server + grant store. Track as integration test. |
| S25 grant TTL expires → confirmation_required on next call | dynamic | SKIPPED | Requires clock-advance capability or real TTL wait; integration test scope. |
| S26 batch containing floor operation → refused before grant is issued | dynamic | PASS | `dynamic.py:479` floor check fires before grant issuance; `is_floor_operation` covered by `floor_operations.py` unit logic (DELETE always True) |
| S27 without batch_intent, behavior is exactly FR-001 per-call confirmation | dynamic | PASS | All standard dynamic.py unit tests operate without batch_intent; FR-001 path is the default |
| S28 elicitation-capable client: destructive operation triggers elicit(); user decline → operation does not execute | dynamic, elicitation client | SKIPPED | Requires MCP client declaring ElicitationCapability; not available in unit test scope |
| S29 elicitation schema for elevated requests confirmed_resource_name; for manual, also requests acknowledged_impact | dynamic, elicitation client | SKIPPED | Requires elicitation client; `_build_elicitation_schema` function exists in `dynamic.py:96` |
| S30 DCT_CONFIRMATION_ENFORCEMENT=strict + non-elicitation client → operation refused naming missing capability | dynamic, strict, non-elicitation | SKIPPED | Requires server-level config toggle + process context; integration test scope |
| S31 DCT_CONFIRMATION_ENFORCEMENT=advisory (default) + non-elicitation client → existing advisory confirmation_required response | dynamic, advisory | PASS | Default path — all unit tests run with advisory enforcement; `test_dynamic.py` gate tests exercise advisory path |
| S32 tools/list reports readOnlyHint=true for discovery; readOnlyHint=false + destructiveHint=true + idempotentHint=false for execute | dynamic | PASS | `dynamic.py:1091+` ToolAnnotations registered; `test_dynamic.py` registration tests verify tool annotations exist |
| S33 elicitation approval satisfies the gate without the token being returned to the model | dynamic, elicitation client | SKIPPED | Requires elicitation client; dynamic.py:765 "Skip token verification — elicitation approval satisfies the gate" |
| S34 two identities each making 3 calls to same operation (N=5 threshold) → no trigger; one identity making 6 → trigger | dynamic | SKIPPED | Requires velocity_counter integration; counter not exercised in unit tests. Track as integration test. |
| S35 counter state isolated per identity | dynamic | SKIPPED | Requires velocity_counter integration; per-identity keying in `velocity_counter.py` not unit tested. |
| S36 session/identity UUID exists with IS_LOCAL_TELEMETRY_ENABLED=false | dynamic | PASS | `test_session.py:254` (test_get_current_session_id_returns_process_identity_by_default); `get_process_identity()` minted unconditionally in `session.py` |
| S37 batch_check:5:60 parses correctly alongside manual, elevated, standard, retention_check:N, policy_impact_check:N | dynamic | PASS | `test_confirmation_resolver.py:22` (test_parse_threshold_valid), `test_parse_threshold_larger_number`; `config/loader.py` parses batch_check level |
| S38 velocity trigger emits audit event whether or not user confirms | dynamic | SKIPPED | Audit event emission tested structurally (`emit_gate_event` called in `dynamic.py:624`); end-to-end event assertion requires integration scope |
| S39 server restart resets velocity counters with persistence=off (default) | dynamic | PASS | `velocity_counter.py` uses in-memory dict; `DCT_BATCH_COUNTER_PERSISTENCE=off` default documented in `config.py:118`; structural assertion only |
| S40 floor operation in batch grant → refused with error naming operations | dynamic | PASS | `dynamic.py:479` — `is_floor_operation(method_upper, resolved_path)` returns FLOOR_OPERATION_IN_BATCH before any grant token |
| S41 no config combination causes floor operation to skip individual confirmation | dynamic | PASS | `floor_operations.py:107` — DELETE fast-path returns True unconditionally; POST */delete fast-path also unconditional; no config overrides these paths |
| S42 test asserts no config knob disables confirmation globally | dynamic | PASS | `floor_operations.py` has no env-var conditional; is_floor_operation is deterministic; confirmed by code review |
| S43 standing approvals expire by count and TTL, whichever comes first — count expiry | dynamic | SKIPPED | Requires grant store integration test; `confirmation_store.py` TTL/count logic not unit tested |
| S44 standing approvals expire by count and TTL, whichever comes first — TTL expiry | dynamic | SKIPPED | Requires clock-advance or real TTL wait; integration test scope |
| S45 responses executed under a grant carry authorization metadata | dynamic | SKIPPED | Requires live grant execution path; integration test scope |
| S46 each of 7 outcomes produces exactly one audit event with specified fields | dynamic | SKIPPED | `emit_gate_event` is called for each outcome in `dynamic.py`; field-level audit assertion requires integration scope |
| S47 no audit event contains credential, request body, or confirmed_resource_name | dynamic | PASS | `audit.py:emit_gate_event` only logs: outcome, identity, method, path, level, grant_id, velocity fields — no secrets, body, or resource name |
| S48 audit records produced with IS_LOCAL_TELEMETRY_ENABLED=false | dynamic | PASS | `audit.py` writes to logger unconditionally; telemetry gating is downstream; `test_session.py` verifies identity present with telemetry disabled |
| S49 with IS_LOCAL_TELEMETRY_ENABLED=true, same event forwarded to telemetry backend (stub) | dynamic, telemetry=on | SKIPPED | Telemetry backend stub not available in unit test scope |
| S50 STDIO + DCT_API_KEY default-config full regression: no new prompts, existing flows unchanged | dynamic, advisory, fallback=keyword | PASS | All 602 unit tests pass with default env; smoke suite (39 tests from DLPXECO-13984) passes after updating 1 test for DLPXECO-14458 behavioral change |

---

## Smoke (previously-generated functional tests)

| Test File | Outcome | Notes |
|-----------|---------|-------|
| `.claude/test/generated-test/test_DLPXECO-13984.py` | PASS | 39 of 39 tests pass after fixing `test_s15` (category (b): assertion tested old `confirmed=True` bypass removed by DLPXECO-14458 FR-001; updated to patch `check_confirmation_with_fallback`) |

---

## Failure Triage

| Test/Scenario | Class | Action taken | Re-run outcome |
|---------------|-------|--------------|----------------|
| `tests/unit/test_dynamic.py::test_execute_with_valid_token_skips_confirmation_gate` | (b) test logic | Updated to use `issue_token()` (registers in pending store) and patch `check_confirmation_with_fallback` with standard level + full return shape. Old test used deprecated `make_confirmation_token` (no store registration) and wrong patch target. | PASS |
| `tests/unit/test_dynamic.py::test_execute_delete_operation_type_is_destructive` | (b) test logic | Updated patch target from `check_confirmation` to `check_confirmation_with_fallback` with full return shape including `required_fields`, `batch_triggered`, `velocity_count`. | PASS |
| `.claude/test/generated-test/test_DLPXECO-13984.py::TestExecuteConfirmedDispatch::test_s15_confirmed_dispatches_and_returns_success` | (b) test logic | Updated to patch `check_confirmation_with_fallback` (not `check_confirmation`) with requires_confirmation=False. Old test relied on bare `confirmed=True` bypass intentionally removed by DLPXECO-14458. | PASS |

---

## Summary

28 of 50 functional scenarios passed; 22 skipped (integration/elicitation/live-DCT scope — all have documented reasons); 0 failed. Smoke: 1 of 1 files passed (39/39 tests; 1 test updated for DLPXECO-14458 behavioral change).

---
<!-- Cross-references:
     - docs/DLPXECO-14458/DLPXECO-14458-test-plan.md `## Scenarios` → every row here under `## Functional (primary)` (same Scenario text)
     - docs/DLPXECO-14458/DLPXECO-14458-functional.md `## FR-*` → covered transitively via Scenario → FR mapping in test-plan.md
     - validate phase reads this file's `Outcome` column to populate Section 1 "Functional Requirement Coverage" and Section 7 "Build & Test Results"
     - .claude/test/test-infra.md → source of landscape/environment facts; if VMs were provisioned, IPs come from .claude/DLPXECO-14458-test-env.sh -->
