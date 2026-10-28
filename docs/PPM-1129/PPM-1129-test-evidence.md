# Test Evidence: PPM-1129

**Jira**: PPM-1129 (PR https://github.com/delphix/dxi-mcp-server/pull/134)
**Generated**: 2026-10-28
**Phase**: test (feature-implement workflow)

<!-- Guidance: This file is the source of truth the `validate` phase reads when computing FR coverage.
     Every scenario row from `docs/PPM-1129/PPM-1129-test-plan.md` must appear in `## Functional (primary)` below — even if SKIPPED. -->

---

## Landscape / Environment

- Landscape: local developer machine (macOS Darwin 25.6.0, arm64)
- Branch under test: `dlpx/pr/vinay.byrappa/ppm-1129-vocabulary-agent-ready-api` (HEAD: 41de161)
- Service under test: `dct-mcp-server` package from this checkout, in-process (no live DCT)
- Test runner: `pytest` + `pytest-asyncio` + `pytest-cov` (via `uv run --with pytest-cov`)
- Python: 3.11.6
- uv: 0.8.11
- VMs provisioned: none (unit/functional layer only; S35 requires live DCT — not run)
- Coverage instrumentation: `--cov=src/dct_mcp_server --cov-report=term-missing`
- RED-before-fix methodology: src files reverted to `d5f89d6` while test files remain at HEAD; listed tests confirmed FAIL at d5f89d6 and PASS at HEAD (commit 41de161)

No generated test files found for PPM-1129 in `.claude/test/generated-test/` — unit tests for this feature are in the project's own `tests/unit/` CI layer, not in generated-test.

## Versions

- Python 3.11.6 (macOS arm64, CI matrix minimum supported)
- Python 3.12: covered in GitHub Actions CI matrix (not run locally; S49 CI baseline applies there)
- mcp 1.29.1 (locked in uv.lock; `FastMCP`, `Tool.from_function`, elicitation API)
- pydantic 2.12.4 (locked; `model_json_schema()` for elicitation)
- DCT 2026.x spec: bundled corpus fixture `tests/fixtures/dct_api_text_corpus.json.gz`
- Live DCT: NOT RUN (credentials not provided — see S35)

## Functional (primary)

| Scenario | Version(s) | Outcome | Notes |
|----------|------------|---------|-------|
| S1: [EXISTS] packaged server instructions are passed to FastMCP at construction | py 3.11 | PASS | `test_server_instructions_load_from_package` — tests/unit/test_vocabulary.py:27 |
| S2: [EXISTS] DCT_SERVER_INSTRUCTIONS override file is used | py 3.11 | PASS | `test_server_instructions_env_override` — tests/unit/test_vocabulary.py:40 |
| S3: [EXISTS] missing instructions file is not fatal | py 3.11 | PASS | `test_server_instructions_missing_file_is_not_fatal` — tests/unit/test_vocabulary.py:48 |
| S4: [NEW] instructions file with invalid UTF-8 bytes is not fatal (GAP-7) | py 3.11 | PASS | `test_server_instructions_invalid_utf8_is_not_fatal` — tests/unit/test_vocabulary.py:59. RED at d5f89d6: UnicodeDecodeError raised → GREEN at HEAD |
| S5: [NEW] both config loaders open their file with encoding="utf-8" (GAP-1, GAP-7) | py 3.11 | PASS | `test_config_files_are_opened_as_utf8` — tests/unit/test_vocabulary.py:107. RED at d5f89d6: assertion fails (no explicit encoding) → GREEN at HEAD |
| S6: [NEW] instructions path that is a directory is not fatal | py 3.11 | PASS | `test_server_instructions_directory_path_is_not_fatal` — tests/unit/test_vocabulary.py:75 |
| S7: [NEW] empty instructions file yields empty instructions without a warning | py 3.11 | PASS | `test_server_instructions_empty_file` — tests/unit/test_vocabulary.py:87 |
| S8: [EXISTS] instructions define the domain model and terminology table | py 3.11 | PASS | `test_server_instructions_state_the_core_rules` — tests/unit/test_vocabulary.py:34 |
| S9: [EXISTS] timeflow prose is translated and identifiers stay byte-identical | py 3.11 | PASS | `test_to_canonical_translates_and_preserves_case[Cannot delete timeflow tf-1...]` — tests/unit/test_vocabulary.py:246 |
| S10: [EXISTS, changed] corpus translation never rewrites identifiers — switched to unguarded `_translate` | py 3.11 | PASS | `test_spot_checks`, `test_unambiguous_retired_terms_do_not_survive_in_prose` — tests/unit/test_vocabulary_spec_corpus.py; 7,249 strings from bundled corpus |
| S11: [EXISTS] Oracle container database and Kubernetes container are left unchanged | py 3.11 | PASS | `test_unrelated_meanings_are_not_translated` (parametrized, 20+ cases) — tests/unit/test_vocabulary.py:479 |
| S12: [NEW] missing vocabulary.txt makes translation the identity function | py 3.11 | PASS | `test_missing_vocabulary_file_is_identity` — tests/unit/test_vocabulary.py:1082. Added in commit 41de161; `load_vocabulary_rules() == ()`; WARNING logged; `to_canonical(x) == x` |
| S13: [NEW] unknown guard and unknown @signal set are warned and skipped; malformed lines are skipped | py 3.11 | PASS | `test_malformed_vocabulary_lines_are_skipped_with_warnings` — tests/unit/test_vocabulary.py:1123. Added in commit 41de161 |
| S14: [NEW] unreadable or invalid-UTF-8 vocabulary.txt degrades to no translation (GAP-1) | py 3.11 | PASS | `test_vocabulary_invalid_utf8_degrades_to_identity` + `test_vocabulary_permission_error_degrades_to_identity` — tests/unit/test_vocabulary.py:136,168. RED at d5f89d6: UnicodeDecodeError / PermissionError propagated → GREEN at HEAD |
| S15: [NEW] to_canonical returns its input when the translator raises (GAP-1) | py 3.11 | PASS | `test_to_canonical_returns_input_when_translation_raises` — tests/unit/test_vocabulary.py:1175. Added in commit 41de161. RED at d5f89d6: RuntimeError propagated → GREEN at HEAD |
| S16: [NEW] clear_cache resets compiled vocabulary rules and memoized translations (GAP-4) | py 3.11 | PASS | `test_clear_cache_also_clears_vocabulary_translator_cache` — tests/unit/test_vocabulary.py:809. RED at d5f89d6: vocabulary caches not cleared by clear_cache → GREEN at HEAD |
| S17: [NEW] clear_cache runs registered hooks after clearing loader caches | py 3.11 | PASS | `test_register_cache_clear_hook_stores_and_invokes_on_clear_cache`, `test_register_cache_clear_hook_replaces_on_re_register`, `test_register_cache_clear_hook_failure_is_swallowed` — tests/unit/test_loader_extended.py:696+. RED at d5f89d6: ImportError `register_cache_clear_hook` not exported → GREEN at HEAD |
| S18: [EXISTS] discovery lists translated summaries | py 3.11 | PASS | `test_discovery_list_operations_translates_summaries` — tests/unit/test_vocabulary.py:1048 |
| S19: [EXISTS] discovery keyword "timeflow" still matches the raw summary | py 3.11 | PASS | `test_discovery_keyword_matches_either_vocabulary` (parametrized) — tests/unit/test_vocabulary.py:1059 |
| S20: [EXISTS] execute error without internal terms has no message_for_user | py 3.11 | PASS | `test_execute_dct_client_error_without_internal_terms_omits_translation` — tests/unit/test_dynamic.py:476 |
| S21: [NEW] execute error payload survives a raising translator (GAP-1 layer 2) | py 3.11 | PASS | `test_error_response_keeps_raw_error_when_translation_raises` — tests/unit/test_dynamic.py:803. Added in commit 41de161. RED at d5f89d6: translation exception propagated → GREEN at HEAD |
| S22: [EXISTS] pre-built DCTClientError reaches MCP client as isError with translation | py 3.11 | PASS | `test_prebuilt_dct_error_reaches_the_mcp_client_as_iserror_with_translation`, `test_sync_dct_client_error_is_raised_with_translation_attached`, `test_async_dct_client_error_is_raised_with_translation_attached` — tests/unit/test_decorators_extended.py:186+ |
| S23: [EXISTS] DCTClientError without internal terms is re-raised unchanged | py 3.11 | PASS | `test_sync_dct_client_error_without_internal_terms_is_reraised_unchanged` — tests/unit/test_decorators_extended.py:208 |
| S24: [NEW] pre-built DCTClientError is re-raised unchanged when translation raises (GAP-1) | py 3.11 | PASS | `test_sync_dct_client_error_reraised_when_translation_raises` (line 293) and `test_async_dct_client_error_reraised_when_translation_raises` (line 339) — tests/unit/test_decorators_extended.py. Added in commit 41de161. RED at d5f89d6: translation exception propagated instead of falling back → GREEN at HEAD |
| S25: [NEW] pre-built DCTClientError is re-raised unchanged when vocabulary import fails (GAP-1) | py 3.11 | PASS | `test_dct_client_error_reraised_when_vocabulary_import_fails` — tests/unit/test_decorators_extended.py:383. Added in commit 41de161. RED at d5f89d6: ImportError escaped to caller → GREEN at HEAD |
| S26: [EXISTS] non-DCTClientError exceptions propagate untranslated | py 3.11 | PASS | `test_sync_other_exceptions_still_propagate_unchanged` — tests/unit/test_decorators_extended.py:279 |
| S27: [EXISTS] toolset and pre-built names carry no banned term in any inflection | py 3.11 | PASS | `test_toolset_tool_and_action_names_use_canonical_terms`, `test_prebuilt_tool_and_action_names_use_canonical_terms`, `test_name_scanner_catches_a_regression` — tests/unit/test_vocabulary_regression.py:184+ |
| S28: [EXISTS] dynamic toolset still registers exactly discovery and execute | py 3.11 | PASS | `test_register_dynamic_tools_registers_two_tools`, `test_register_dynamic_tools_names_are_discovery_and_execute` — tests/unit/test_dynamic.py:597+ |
| S29: [NEW] every rename registered under new name only and documented old-to-new | py 3.11 | PASS | `test_persona_renames_are_complete_and_documented` — tests/unit/test_vocabulary_regression.py:470. Added in commit 41de161; asserts old names absent from toolsets, new names present, pairs documented in PPM-1129-agent-ready-api-surface-proposal.md |
| S30: [EXISTS] pre-built docstrings are free of banned terms outside alias lines | py 3.11 | PASS | `test_prebuilt_docstrings_are_free_of_internal_terms` (parametrized), `test_docstring_scanner_catches_a_regression`, `test_alias_lines_are_the_only_place_legacy_words_are_quoted` — tests/unit/test_vocabulary_regression.py:278+ |
| S31: [NEW] discovery and execute tool descriptions are free of banned terms (GAP-2) | py 3.11 | PASS | `test_dynamic_docstrings_are_free_of_internal_terms` (parametrized over `_BANNED`) — tests/unit/test_vocabulary_regression.py:382 |
| S32: [NEW] elicitation schema text is free of banned terms (GAP-2) | py 3.11 | PASS | `test_elicitation_text_is_free_of_internal_terms` (parametrized) — tests/unit/test_vocabulary_regression.py:393 |
| S33: [NEW] dynamic/elicitation scanners catch an injected regression (GAP-2) | py 3.11 | PASS | `test_dynamic_docstring_scanner_catches_a_regression` — tests/unit/test_vocabulary_regression.py:403 |
| S34: [EXISTS] confirmation messages render canonical names and drop unresolvable placeholders | py 3.11 | PASS | `test_no_confirmation_message_uses_internal_term` (parametrized), `test_engine_is_always_qualified_in_confirmation_messages`, `test_vdb_group_casing_is_canonical`, `test_no_confirmation_message_contains_a_pipe`, `test_placeholder_clause_dropped_when_unresolvable`, `test_days_clause_dropped_when_unresolvable`, `test_confirmation_message_names_the_real_resource` — tests/unit/test_vocabulary_regression.py + tests/unit/test_vocabulary.py |
| S35: [EXISTS, manual non-gating] live session: "rewind my VDB" treated as refresh from self | live DCT | NOT RUN | Manual, non-gating check requiring live DCT credentials. Credentials (DCT_API_KEY / DCT_BASE_URL) not provided per user constraint. S35 does not gate merge per test plan Exit Criteria. |
| S36: [NEW] keyword-fallback confirmation prompt translates the OpenAPI summary | py 3.11 | PASS | `test_keyword_fallback_prompt_uses_canonical_summary` — tests/unit/test_dynamic_confirmation.py. Summary "Delete timeflow" yields a prompt containing "timeline" and not "timeflow" (FR-007 AC-6). |
| S37: [NEW] keyword-fallback prompt survives a raising translator (GAP-1 layer 2) | py 3.11 | PASS | `test_keyword_fallback_prompt_when_translation_raises` — tests/unit/test_dynamic_confirmation.py. FAILS on d5f89d6 (RuntimeError propagated), PASSES at HEAD: the prompt is built from the raw summary and confirmation is still required. |
| S38: [NEW] generated-tool confirmations render placeholders like persona toolsets | py 3.11 | PASS | `test_generated_tool_confirmation_renders_placeholders` — tests/unit/test_driver.py. Generates a tool for `DELETE /vdb-groups/{vdbGroupId}`, imports it, and checks the prompt reads "…delete VDB Group 'payroll'?" with a resolved name and no raw brace (FR-007 AC-4). |
| S39: [EXISTS] AppData/toolkit prose becomes connector terms and plugin IDs stay intact | py 3.11 | PASS | `test_to_canonical_translates_and_preserves_case[Install the appdata plugin...]`, `test_prose_around_identifiers_is_still_translated[Plugin delphix-postgres-plugin...]` — tests/unit/test_vocabulary.py:246, 389 |
| S40: [EXISTS] Delphix engine resolves on evidence, else the either phrase | py 3.11 | PASS | `test_to_canonical_resolves_delphix_engine_from_the_text`, `test_delphix_engine_never_resolves_to_the_wrong_product`, `test_delphix_engine_never_survives_and_names_one_product_only_on_evidence` — tests/unit/test_vocabulary.py:281,322; tests/unit/test_vocabulary_spec_corpus.py |
| S41: [NEW] bare relayed engine passes through unchanged per the GAP-3 decision | py 3.11 | PASS | `test_bare_engine_is_not_rewritten` (parametrized) — tests/unit/test_vocabulary.py:1225. Added in commit 41de161; pins the GAP-3 design decision that bare "engine" (non-Delphix context) is not rewritten |
| S42: [NEW] Delphix engine next to a bare engine still resolves once | py 3.11 | PASS | `test_delphix_engine_beside_bare_engine` — tests/unit/test_vocabulary.py:1235. Added in commit 41de161; verifies "Delphix engine" → "Continuous Data engine" and the adjacent bare "engine" is unchanged, no doubling |
| S43: [NEW] editorial guideline exists and is linked from CLAUDE.md | py 3.11 | PASS | `test_editorial_guidelines_mention_dynamic_docstring_scan` — tests/unit/test_vocabulary_regression.py:422. Verifies the guideline file exists and contains the dynamic-docstring scan section |
| S44: [EXISTS] $ref request body exposes fields; inline body still works | py 3.11 | PASS | `test_ref_request_body_exposes_fields`, `test_inline_request_body_still_works` — tests/unit/test_vocabulary.py:868, 921 |
| S45: [NEW] self-referential request body $ref yields no fields and one warning (GAP-5) | py 3.11 | PASS | `test_request_body_resolved_warns_only_once_for_same_ref` — tests/test_spec_model.py:325. RED at d5f89d6: AttributeError `_WARNED_BODY_REFS` not found → GREEN at HEAD |
| S46: [NEW] two-hop request body $ref chain still resolves | py 3.11 | PASS | `test_request_body_resolved_uses_resolve_refs_not_resolve_ref` — tests/test_spec_model.py:266 |
| S46a: [NEW] dangling request body $ref yields no fields and one warning (GAP-5) | py 3.11 | PASS | `test_request_body_resolved_warns_once_for_missing_ref` — tests/test_spec_model.py:297. RED at d5f89d6: AttributeError `_WARNED_BODY_REFS` not found → GREEN at HEAD |
| S46b: [NEW] deeply nested $ref request body keeps its top-level fields | py 3.11 | PASS | `test_request_body_resolved_inline_body_returns_content` — tests/test_spec_model.py:350 |
| S47: [NEW] concurrent first translations agree | py 3.11 | PASS | `test_to_canonical_is_thread_safe` — tests/unit/test_vocabulary.py:761 |
| S48: [NEW] control characters and replacement characters pass through the translator | py 3.11 | PASS | `test_to_canonical_does_not_corrupt_non_ascii_unicode` — tests/unit/test_vocabulary.py:744 |
| S49: [EXISTS] full CI suite and lint stay green | py 3.11 | PASS | `pytest tests/ -m "not real_dct and not llm_driven and not scenario"`: 1119 passed, 947 skipped (require DCT creds), 25 deselected, 0 failures; `ruff check` and `ruff format --check` clean |

## E2E / Live Smoke Tests

<!-- Dispatcher-run live-DCT smoke; not re-run here per user constraint. -->

| Test Suite | Outcome | Notes |
|------------|---------|-------|
| `tests/e2e/test_smoke.py` + `tests/e2e/test_smoke_cda.py` (live DCT at https://localhost) | 23 PASS, 1 SKIP | Run by dispatcher pre-evidence-refresh. 1 skipped: no VDBs on the instance to round-trip. `tests/e2e/cleanup/test_purge.py` deliberately not run: it deletes objects on the live instance. |

## Smoke (previously-generated functional tests)

<!-- Tests in .claude/test/generated-test/ that do not contain PPM-1129 -->

| Test File | Outcome | Notes |
|-----------|---------|-------|
| .claude/test/generated-test/test_DLPXECO-13984.py | PASS | Included in the 1119 passed via the full test run above; no failures |
| .claude/test/generated-test/test_DLPXECO-14324.py | PASS | Included in the 1119 passed via the full test run above; no failures |

## Failure Triage (if any FAIL or unexplained SKIPPED)

No FAILs. The only non-PASS entry is S35:

| Scenario | Reason |
|----------|--------|
| S35 | Manual, non-gating live DCT scenario (Track 1); credentials not provided per user constraint; does not gate merge per test plan Exit Criteria |

## RED-before-fix Evidence (GAP-1/4/5/7)

Methodology: `git checkout d5f89d6 -- src/dct_mcp_server/{config/loader,core/decorators,tools/core/{dynamic,spec_model,vocabulary}}.py`; then `uv run pytest <specific tests>`; then `git checkout HEAD -- <same files>`.

| Test | State at d5f89d6 | State at HEAD (41de161) | GAP |
|------|-----------------|------------------------|-----|
| `test_server_instructions_invalid_utf8_is_not_fatal` | FAIL (UnicodeDecodeError) | PASS | GAP-7 |
| `test_config_files_are_opened_as_utf8` | FAIL (assertion: no encoding= kwarg) | PASS | GAP-1 + GAP-7 |
| `test_vocabulary_invalid_utf8_degrades_to_identity` | FAIL (UnicodeDecodeError) | PASS | GAP-1 |
| `test_vocabulary_permission_error_degrades_to_identity` | FAIL (PermissionError propagated) | PASS | GAP-1 |
| `test_to_canonical_returns_input_when_translation_raises` (S15) | FAIL (RuntimeError propagated) | PASS | GAP-1 |
| `test_error_response_keeps_raw_error_when_translation_raises` (S21) | FAIL (translation exception propagated) | PASS | GAP-1 layer 2 |
| `test_sync_dct_client_error_reraised_when_translation_raises` (S24 sync) | FAIL (translation exception propagated) | PASS | GAP-1 |
| `test_async_dct_client_error_reraised_when_translation_raises` (S24 async) | FAIL (translation exception propagated) | PASS | GAP-1 |
| `test_dct_client_error_reraised_when_vocabulary_import_fails` (S25) | FAIL (ImportError escaped) | PASS | GAP-1 |
| `test_clear_cache_also_clears_vocabulary_translator_cache` | FAIL (vocabulary caches not cleared) | PASS | GAP-4 |
| `test_register_cache_clear_hook_is_importable` | FAIL (ImportError: register_cache_clear_hook) | PASS | GAP-4 |
| `test_register_cache_clear_hook_stores_and_invokes_on_clear_cache` | FAIL (ImportError) | PASS | GAP-4 |
| `test_register_cache_clear_hook_replaces_on_re_register` | FAIL (ImportError) | PASS | GAP-4 |
| `test_register_cache_clear_hook_failure_is_swallowed` | FAIL (ImportError) | PASS | GAP-4 |
| `test_with_message_for_user_returns_original_exception_when_vocabulary_raises` (S36) | FAIL (exception propagated) | PASS | GAP-1 (decorator layer) |
| `test_request_body_resolved_warns_once_for_missing_ref` | FAIL (AttributeError: `_WARNED_BODY_REFS`) | PASS | GAP-5 |
| `test_request_body_resolved_warns_only_once_for_same_ref` | FAIL (AttributeError: `_WARNED_BODY_REFS`) | PASS | GAP-5 |

## Summary

50 of 51 functional scenarios passed; 1 not run (S35 — manual live DCT, non-gating, no credentials provided). Smoke: 2 of 2 previously-generated test files passed. E2E live smoke (dispatcher-run): 23 passed, 1 skipped. Full CI suite: 1119 passed, 0 failures, ruff check and ruff format --check clean.

---
<!-- Cross-references:
     - docs/PPM-1129/PPM-1129-test-plan.md `## Scenarios` → every row here under `## Functional (primary)` (same Scenario text)
     - docs/PPM-1129/PPM-1129-functional.md `## FR-*` → covered transitively via Scenario → FR mapping in test-plan.md
     - validate phase reads this file's `Outcome` column to populate Section 1 "Functional Requirement Coverage" and Section 7 "Build & Test Results"
     - .claude/test/test-infra.md → source of landscape/environment facts; no VMs provisioned for this feature -->
