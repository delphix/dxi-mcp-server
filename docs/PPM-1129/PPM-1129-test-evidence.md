# Test Evidence: PPM-1129

**Jira**: PPM-1129 (PR https://github.com/delphix/dxi-mcp-server/pull/134)
**Generated**: 2026-10-28
**Phase**: test (feature-implement workflow)

<!-- Guidance: This file is the source of truth the `validate` phase reads when computing FR coverage.
     Every scenario row from `docs/PPM-1129/PPM-1129-test-plan.md` must appear in `## Functional (primary)` below — even if SKIPPED. -->

---

## Landscape / Environment

- Landscape: local developer machine (macOS Darwin 25.6.0 / macOS-26.7.1-arm64-arm-64bit)
- Branch under test: `dlpx/pr/vinay.byrappa/ppm-1129-vocabulary-agent-ready-api` (HEAD: e8cab64)
- Service under test: `dct-mcp-server` package from this checkout, in-process (unit/CI) and via stdio MCP client (live MCP flow)
- Test runner: `pytest` + `pytest-asyncio` + `pytest-cov` (via `uv run --with pytest-cov`)
- Python: 3.11.6
- uv: 0.8.11
- VMs provisioned: none (unit/functional layer only; S35 requires live DCT — not run)
- Coverage instrumentation: `--cov=src/dct_mcp_server --cov-report=term-missing`
- RED-before-fix methodology: src files reverted to `d5f89d6` while test files remain at HEAD; listed tests confirmed FAIL at d5f89d6 and PASS at HEAD (commit 41de161)
- Live DCT for e2e/MCP flow: https://localhost (DCT_VERIFY_SSL=false), credentials referenced as $DCT_API_KEY

No generated test files found for PPM-1129 in `.claude/test/generated-test/` — unit tests for this feature are in the project's own `tests/unit/` CI layer, not in generated-test.

## Versions

- Python 3.11.6 (macOS arm64, CI matrix minimum supported)
- Python 3.12: covered in GitHub Actions CI matrix (not run locally; S49 CI baseline applies there)
- mcp 1.29.1 (locked in uv.lock; `FastMCP`, `Tool.from_function`, elicitation API)
- pydantic 2.12.4 (locked; `model_json_schema()` for elicitation)
- DCT 2026.x spec: bundled corpus fixture `tests/fixtures/dct_api_text_corpus.json.gz`
- Live DCT: https://localhost — exercised for e2e smoke tests and manual MCP flow (S35 excluded; credentials redacted in all evidence)

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
| S35: [EXISTS, manual non-gating] live session: "rewind my VDB" treated as refresh from self | live DCT | NOT RUN | Manual, non-gating check requiring live DCT credentials and an LLM-in-the-loop. Excluded per user constraint ("only things affecting dxi mcp server should be used") — does not gate merge per test plan Exit Criteria. |
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
| S49: [EXISTS] full CI suite and lint stay green | py 3.11 | PASS | `pytest tests/ -m "not real_dct and not llm_driven and not scenario" --cov=src/dct_mcp_server`: **1126 passed**, 947 skipped, 25 deselected, 0 failures; `ruff check` and `ruff format --check` both clean (HEAD: e8cab64) |

## E2E / Live Smoke Tests

<!-- Live e2e smoke; run at HEAD e8cab64 against local DCT https://localhost (DCT_VERIFY_SSL=false, $DCT_API_KEY). -->

| Test Suite | Outcome | Notes |
|------------|---------|-------|
| `tests/e2e/test_smoke.py` (8 tests) | 7 PASS, 1 SKIP | `test_server_boots_and_registers_self_service` PASS; `test_read_only_search_returns_well_shaped_response` PASS for all 6 tools (vdb_tool, vdb_group_tool, dsource_tool, snapshot_tool, bookmark_tool, job_tool, timeline_tool); `test_vdb_get_roundtrip_if_any_exist` SKIPPED — no VDBs on empty instance |
| `tests/e2e/test_smoke_cda.py` (16 tests) | 16 PASS | `test_cda_registers_all_configured_tools` PASS; `test_cda_read_only_search_well_shaped` PASS for all 14 tools (cdb_dsource_tool, connector_schema_tool, data_connection_tool, engine_tool, group_tool, hook_template_tool, job_tool, replication_tool, staging_cdb_tool, staging_source_tool, tag_tool, timeline_tool, vdb_template_tool, virtualization_policy_tool) |
| `tests/e2e/cleanup/test_purge.py` | NOT RUN | Deliberately excluded — deletes objects on the live DCT instance |

## Manual MCP Client Flow

<!-- Exercised via a Python stdio MCP client (mcp.ClientSession + StdioServerParameters) against the
     worktree's .venv/bin/dct-mcp-server entry point with $DCT_API_KEY and DCT_BASE_URL=https://localhost.
     Script written to scratchpad (not in repo). 18/18 checks passed. -->

### (a) Initialize — vocabulary instructions

| Check | Outcome | Notes |
|-------|---------|-------|
| `initialize` returns instructions containing "timeline" | PASS | instructions length=13518 chars; all five required terms present |
| "VDB Group" present in instructions | PASS | |
| "Continuous Data engine" present in instructions | PASS | |
| "connector" present in instructions | PASS | |
| "dSource" present in instructions | PASS | |

### (b) Discovery

| Check | Outcome | Notes |
|-------|---------|-------|
| `discovery(action="list_tags")` returns tag list | PASS | 105 tags returned; sample: Accounts, AiGenerate, AiManagement |
| `discovery(action="list_operations", keyword="timeflow")` — prose summaries canonical (no "timeflow" prose) | PASS | 20 operations returned; zero summaries contained uncanonical "timeflow" prose; identifiers/paths correctly untranslated |
| `discovery(action="list_operations", keyword="toolkit")` — no "toolkit" in summaries | PASS | 10 operations; zero summaries contained "toolkit" |
| `discovery(action="get_operation_schema", method="GET", path="/vdbs")` returns schema | PASS | Schema payload non-empty |

### (c) Execute GET reads

| Check | Outcome | Notes |
|-------|---------|-------|
| `execute(method="GET", path="/vdbs")` succeeds | PASS | isError=False; response key present; empty items (instance has no VDBs) |
| `execute(method="GET", path="/environments")` succeeds | PASS | isError=False |
| `execute(method="GET", path="/vdb-groups")` succeeds | PASS | isError=False |
| `execute(method="GET", path="/dsources")` succeeds | PASS | isError=False |

### (d) DCT error translation (commit e8cab64 JSON-error-body fix)

| Check | Outcome | Notes |
|-------|---------|-------|
| GET /timeflows/{timeflowId} timeflowId=no-such-tf → raw `message` preserved | PASS | `message='HTTP 404: {"error":"failed","error_description":"Timeflow not found."}'` — raw JSON body intact |
| GET /timeflows/{timeflowId} timeflowId=no-such-tf → `message_for_user` canonical | PASS | `message_for_user='HTTP 404: {"error":"failed","error_description":"Timeline not found."}'` — "Timeflow" translated to "Timeline" in the user-facing field |
| GET /vdbs/{vdbId} vdbId=no-such-vdb → raw `message` preserved | PASS | `message='HTTP 404: {"error":"failed","error_description":"Unable to find object matching the provided ID."}'` |

### (e) Confirmation gate

| Check | Outcome | Notes |
|-------|---------|-------|
| POST /vdbs/{vdbId}/delete vdbId=no-such-vdb body={} (no token) → `status=confirmation_required` | PASS | Returned `"status": "confirmation_required"` |
| Confirmation `level=manual` | PASS | `"confirmation_level": "manual"` |
| Confirmation message canonical (no banned terms) | PASS | `"Are you sure you want to permanently delete VDB 'no-such-vdb'? This action cannot be undone."` — no timeflow/container/inventory/rewind present. Call NOT re-issued with a token. |

### (f) Persona toolset: self_service

| Check | Outcome | Notes |
|-------|---------|-------|
| `timeline_tool` registered (not `timeflow_tool`) | PASS | Tools: vdb_tool, vdb_group_tool, dsource_tool, snapshot_tool, bookmark_tool, timeline_tool, job_tool (7 tools total) |
| `timeflow_tool` absent | PASS | Not in registered tool list |
| `timeline_tool(action="list")` read action succeeds | PASS | Returned `{"items": [], "response_metadata": {"total": 0}}` (empty instance). Corrected after review: the first run called a non-existent action `list_timeflows`, which the server answers with an `Unknown action` error body and `isError=False`, so that earlier PASS was invalid. Re-run by the dispatcher with the real action name. |
| Post-run tracked file state | PASS | `git checkout -- src/dct_mcp_server/tools/` restored all regenerated `*_endpoints_tool.py` files; `git status` shows no tracked modifications after restore |

## Smoke (previously-generated functional tests)

<!-- Tests in .claude/test/generated-test/ that do not contain PPM-1129 -->

| Test File | Outcome | Notes |
|-----------|---------|-------|
| .claude/test/generated-test/test_DLPXECO-13984.py | PASS | Included in the 1126 passed via the full test run |
| .claude/test/generated-test/test_DLPXECO-14324.py | PASS | Included in the 1126 passed via the full test run |

## Failure Triage (if any FAIL or unexplained SKIPPED)

No FAILs. The only non-PASS entries are:

| Scenario | Reason |
|----------|--------|
| S35 | Manual, non-gating live DCT scenario (Track 1); excluded per user constraint (requires LLM-in-the-loop); does not gate merge per test plan Exit Criteria |
| `test_vdb_get_roundtrip_if_any_exist` (e2e smoke) | SKIPPED — no VDBs exist on the empty local DCT instance; the test explicitly skips when no VDBs are present |

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

50 of 51 functional scenarios passed; 1 not run (S35 — manual live DCT/LLM check, non-gating, excluded per user constraint). Smoke: 2 of 2 previously-generated test files passed. E2E live smoke (run at e8cab64): 23 passed, 1 skipped (no VDBs on instance). Manual MCP client flow: 18/18 checks passed (all vocabulary, discovery, execute, error-translation, confirmation-gate, and persona-toolset checks). Full CI suite: **1126 passed**, 0 failures, ruff check and ruff format --check clean.

---
<!-- Cross-references:
     - docs/PPM-1129/PPM-1129-test-plan.md `## Scenarios` → every row here under `## Functional (primary)` (same Scenario text)
     - docs/PPM-1129/PPM-1129-functional.md `## FR-*` → covered transitively via Scenario → FR mapping in test-plan.md
     - validate phase reads this file's `Outcome` column to populate Section 1 "Functional Requirement Coverage" and Section 7 "Build & Test Results"
     - .claude/test/test-infra.md → source of landscape/environment facts; no VMs provisioned for this feature -->
