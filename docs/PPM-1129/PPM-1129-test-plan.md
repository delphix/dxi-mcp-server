# Test Plan: PPM-1129

**Jira**: PPM-1129 -- PR https://github.com/delphix/dxi-mcp-server/pull/134
**Derived from**: `docs/PPM-1129/PPM-1129-design.md` `## Affected Components` and `## Version Compatibility`

<!-- Guidance: This file is the authoritative list of scenarios for the test-generation phase.
     Every row in `## Scenarios` becomes one test() / it() / def test_* block in `.claude/test/generated-test/`.
     If a scenario row cannot be expressed as a real assertion, refine the row — do not weaken the generated test. -->

**Scope**: dxi-mcp-server only. Every scenario runs in-process or against the local server
subprocess; none needs a live DCT.

**How to read the Scenarios table**: the `Status` prefix in each scenario name says whether a
test exists.

- `[EXISTS]` -- covered on the branch today; the test named in the row must stay green.
- `[NEW]` -- **missing test to add** in the implement phase (the gap-fix tests). The target
  module is given in the row. A `[NEW]` row for GAP-1, GAP-4, GAP-5 or GAP-7 must fail on the
  current branch head (`d5f89d6`) and pass after the fix (RED -> GREEN).

---

## Test Approach
<!-- Guidance: 1–2 sentences naming the framework, runner, and where tests will execute. Pull from .claude/test/testing.md if it exists.
     Example: Integration tests using the project's standard test framework; runner = `<project test command>`. -->

`pytest` + `pytest-asyncio`, in the existing `tests/unit/` CI layer (no DCT credentials); runner =
`pytest tests/ -m "not real_dct and not llm_driven and not scenario"` (equivalently
`dct-mcp-test --layer ci`), plus `pre-commit run --all-files`. New tests go into the existing
vocabulary/decorator/dynamic/loader test modules, not a new `tests/PPM-1129-test.py`, because
every gap is deterministic and in-process. One manual, non-gating Claude-driven check (S35)
follows `.claude/test/testing.md` Track 1.

## Environment / Landscape
<!-- Guidance: Name the test landscape and any preconditions. If .claude/test/test-infra.md describes VMs, list them here; the test-infra phase will provision them before the test phase runs. Use placeholder names (`<engine-host>`, `<staging-host>`) — concrete host names belong in .claude/test/test-infra.md, not here.
     Example:
     - Landscape: <name of integration environment>
     - Service under test: <host or URL — pulled from .claude/test/test-infra.md>
     - VMs to provision (per .claude/test/test-infra.md ## VMs): <vm-name> (group: <group>) -->

- Landscape: local developer machine or GitHub Actions `ci.yml` runner.
- Service under test: `dct_mcp_server` package from this checkout (`uv sync` or
  `pip install -e .`); in-process for unit tests, including the in-memory MCP client session
  (`create_connected_server_and_client_session`) used in `test_decorators_extended.py`.
- VMs to provision: none.
- Optional for S35 only: a DCT instance `<dct-host>` with credentials in
  `.claude/settings.local.json` per `.claude/test/test-infra.md`.

## Versions to Cover
<!-- Guidance: List every version branch this feature must be exercised on. Pull from the design doc `## Version Compatibility` table — only versions marked "Supported = Yes" appear here.
     Example:
     | Version | Why | Required? |
     |---------|-----|-----------|
     | v1.x | Backward compatibility branch | Yes |
     | v2.0+ | Modern API path | Yes |
     | v0.9  | Deprecated but still in some environments | No (smoke-only) | -->

| Version | Why | Required? |
|---------|-----|-----------|
| Python 3.11 | Minimum supported; CI matrix | Yes |
| Python 3.12 | CI matrix | Yes |
| mcp >=1.28.1,<2 (locked 1.29.1; `mcp.server.fastmcp.FastMCP`) | `instructions=`, `Tool.from_function`, elicitation | Yes |
| pydantic 2.x (locked 2.12.4) | Elicitation `model_json_schema()` | Yes |
| DCT 2026.x spec (bundled corpus fixture) | Translator corpus test | Yes |
| Non-UTF-8 host locale | GAP-1 / GAP-7 explicit-encoding behaviour | Yes (covered by S5's `encoding="utf-8"` spy and invalid-byte files; `LC_ALL=C` is not a real non-UTF-8 locale under Python's C-locale coercion, so no separate CI job) |
| Live DCT (any supported) | Manual model-behaviour check | No (manual, non-gating) |

## Scenarios
<!-- Guidance: One row per testable scenario. Map each scenario to at least one FR-* from docs/$NAME/$NAME-functional.md.
     "Expected outcome" must be observable — a returned value, an HTTP status, a row in a log, a UI element appearing.
     Format the scenario name so it can become a test() title verbatim ("acquiring a lock on a free schema succeeds").
     Minimum 1 scenario per FR; minimum 1 negative/failure scenario overall.
     Example:
     | # | Scenario | Maps to FR | Versions | Expected outcome |
     |---|----------|-----------|----------|------------------|
     | S1 | acquire() on a free schema returns a lock token within 100ms | FR-001 | v1.x, v2.0+ | Returned object has non-empty `token` and `expiry` fields |
     | S2 | acquire() on a held schema returns LockConflictError | FR-002 | v2.0+      | Exception type = LockConflictError; holder_id present in message |
     | S3 | Lock held by crashed coordinator is reclaimed after TTL + 60s | FR-003 | v2.0+      | New acquire() succeeds after the reclaim window | -->

Versions column: "py" = Python 3.11 and 3.12.

| # | Scenario | Maps to FR | Versions | Expected outcome |
|---|----------|-----------|----------|------------------|
| S1 | [EXISTS] packaged server instructions are passed to FastMCP at construction (`test_main.py`; `test_vocabulary.py::test_server_instructions_load_from_package`) | FR-001 | py | `FastMCP(...)` receives the full stripped packaged text as `instructions` |
| S2 | [EXISTS] DCT_SERVER_INSTRUCTIONS override file is used (`::test_server_instructions_env_override`) | FR-001 | py | Returned text equals the override file's content |
| S3 | [EXISTS] missing instructions file is not fatal (`::test_server_instructions_missing_file_is_not_fatal`) | FR-001 | py | Returns `""`; WARNING logged; no exception |
| S4 | [NEW] instructions file with invalid UTF-8 bytes is not fatal -- `test_vocabulary.py::test_server_instructions_invalid_utf8_is_not_fatal` (write `b"\xff\xfe bad"`, set env, `clear_cache()`) | FR-001 | py | Returns `""`; one WARNING mentioning the path; no `UnicodeDecodeError`. Fails on `d5f89d6` (GAP-7) |
| S5 | [NEW] both config loaders open their file with encoding="utf-8" -- `test_vocabulary.py::test_config_files_are_opened_as_utf8` (spy on `builtins.open` within `dct_mcp_server.config.loader` while calling `load_server_instructions()` and `load_vocabulary_rules()` after `clear_cache()`). Patching `locale.getpreferredencoding` does not change `open()`'s default and must not be used | FR-001, FR-002 | py | Every `open` call for the two files passes `encoding="utf-8"`. Fails on `d5f89d6` (GAP-1, GAP-7) |
| S6 | [NEW] instructions path that is a directory is not fatal -- `::test_server_instructions_directory_path_is_not_fatal` | FR-001 | py | Returns `""`; WARNING logged (EC-17) |
| S7 | [NEW] empty instructions file yields empty instructions without a warning -- `::test_server_instructions_empty_file` | FR-001 | py | Returns `""`; no WARNING record (EC-18) |
| S8 | [EXISTS] instructions define the domain model and terminology table (`::test_server_instructions_state_the_core_rules`) | FR-001, FR-008 | py | Text contains each domain term and the three table columns |
| S9 | [EXISTS] timeflow prose is translated and identifiers stay byte-identical (`test_vocabulary.py`) | FR-002 | py | "Timeflow tf-1 not found at /timeflows/tf-1" -> "Timeline tf-1 not found at /timeflows/tf-1" |
| S10 | [EXISTS, changed] corpus translation never rewrites identifiers, never doubles terms, never renames "VDB inventory report" (`test_vocabulary_spec_corpus.py`) -- switch its helper from `to_canonical` (`:31`, `:86`) to the unguarded `vocabulary._translate` | FR-002, FR-010 | py | All corpus assertions pass over 7,249 strings; a translator exception fails the run instead of being swallowed by the GAP-1 guard |
| S11 | [EXISTS] Oracle container database and Kubernetes container are left unchanged (`test_vocabulary.py`) | FR-002 | py | Output equals input |
| S12 | [NEW] missing vocabulary.txt makes translation the identity function -- `test_vocabulary.py::test_missing_vocabulary_file_is_identity` (monkeypatch `MAPPINGS_DIR` to an empty tmp dir) | FR-002 | py | `load_vocabulary_rules() == ()`; WARNING; `to_canonical(x) == x` |
| S13 | [NEW] unknown guard and unknown @signal set are warned and skipped; malformed lines are skipped -- `test_vocabulary.py::test_malformed_vocabulary_lines_are_skipped_with_warnings` (tmp vocabulary.txt with `a`, `|x`, `timeflow|timeline|bogus=x`, `container|VDB Group|only_if_text_mentions=@nope`) | FR-002 | py | Other rules still load; WARNING records name the guard/set |
| S14 | [NEW] unreadable or invalid-UTF-8 vocabulary.txt degrades to no translation -- `test_vocabulary.py::test_vocabulary_invalid_utf8_degrades_to_identity` (monkeypatch `MAPPINGS_DIR` to a tmp dir whose vocabulary.txt has more than 8 KB of valid rule lines followed by `b"\xff\xfe"`, so the failure happens mid-parse; plus a variant patching `open` to raise `PermissionError`) | FR-002 | py | `load_vocabulary_rules() == ()` (no partial rule set); one WARNING; `to_canonical("Timeflow")` returns `"Timeflow"`; no exception. Fails on `d5f89d6` (GAP-1) |
| S15 | [NEW] to_canonical returns its input when the translator raises -- `::test_to_canonical_returns_input_when_translation_raises` (patch `_compiled_rules` to raise `RuntimeError`) | FR-002, FR-003, FR-007 | py | Returns input unchanged; first failure logged at WARNING with traceback, second at DEBUG only (GAP-1) |
| S16 | [NEW] clear_cache resets compiled vocabulary rules and memoized translations -- `::test_clear_cache_reloads_vocabulary` (translate "Timeflow" with rule A, rewrite tmp vocabulary.txt to map timeflow->"history", `loader.clear_cache()`, translate again) | FR-002 | py | Second call returns the new canonical term. Fails on `d5f89d6` (GAP-4) |
| S17 | [NEW] clear_cache runs registered hooks after clearing loader caches -- `test_loader_extended.py::test_clear_cache_runs_registered_hooks` | FR-002 | py | A registered hook is called once per `clear_cache()`; registering the same hook twice still calls it once; hook sees loader caches already cleared |
| S18 | [EXISTS] discovery lists translated summaries (`::test_discovery_list_operations_translates_summaries`) | FR-003 | py | Summary "Switch timeflow" shown as "Switch timeline" |
| S19 | [EXISTS] discovery keyword "timeflow" still matches the raw summary (`::test_discovery_keyword_matches_either_vocabulary`) | FR-003, FR-008 | py | Operation returned for both "timeflow" and "timeline" |
| S20 | [EXISTS] execute error without internal terms has no message_for_user (`test_dynamic.py`) | FR-003 | py | Payload has `message`, `http_status`; no `message_for_user` key |
| S21 | [NEW] execute error payload survives a raising translator -- `test_dynamic.py::test_error_response_keeps_raw_error_when_translation_raises` (patch `dct_mcp_server.tools.core.dynamic.to_canonical`, the name bound at `dynamic.py:46`, to raise) | FR-003 | py | Payload `{"status":"error","code":"DCT_API_ERROR","http_status":404,"message":<raw>}`; no `message_for_user`; WARNING logged. Fails on `d5f89d6` (GAP-1) |
| S22 | [EXISTS] pre-built DCTClientError reaches the MCP client as isError with translation (`test_decorators_extended.py::test_prebuilt_dct_error_reaches_the_mcp_client_as_iserror_with_translation`, in-memory `create_connected_server_and_client_session`; plus `::test_sync_dct_client_error_is_raised_with_translation_attached` and `::test_async_dct_client_error_is_raised_with_translation_attached`) | FR-004 | py | `isError: true`; text starts with the raw `HTTP 409: timeflow 'tf-1' is locked`, then `message_for_user: HTTP 409: timeline 'tf-1' is locked` |
| S23 | [EXISTS] DCTClientError without internal terms is re-raised unchanged (`::test_sync_dct_client_error_without_internal_terms_is_reraised_unchanged`) | FR-004 | py | Same exception object; `message_for_user is None` |
| S24 | [NEW] pre-built DCTClientError is re-raised unchanged when translation raises -- `test_decorators_extended.py::test_sync_dct_client_error_reraised_when_translation_raises` and `::test_async_dct_client_error_reraised_when_translation_raises` (patch `dct_mcp_server.tools.core.vocabulary.to_canonical`; the decorator imports it lazily) | FR-004 | py | `pytest.raises(DCTClientError)` catches the **same** object; `message_for_user is None`; `http_status` parsed; WARNING logged. Fails on `d5f89d6` (GAP-1) |
| S25 | [NEW] pre-built DCTClientError is re-raised unchanged when the vocabulary import fails -- `::test_dct_client_error_reraised_when_vocabulary_import_fails` (`monkeypatch.setitem(sys.modules, "dct_mcp_server.tools.core.vocabulary", None)`) | FR-004 | py | Original `DCTClientError` raised; WARNING logged; no `ImportError` escapes (GAP-1) |
| S26 | [EXISTS] non-DCTClientError exceptions propagate untranslated (`::test_sync_other_exceptions_still_propagate_unchanged`) | FR-004 | py | Same `ValueError` re-raised; no `message_for_user` (EC-20) |
| S27 | [EXISTS] toolset and pre-built names carry no banned term in any inflection (`test_vocabulary_regression.py::test_toolset_tool_and_action_names_use_canonical_terms`, `::test_prebuilt_tool_and_action_names_use_canonical_terms`, `::test_name_scanner_catches_a_regression`) | FR-005, FR-009, FR-011 | py | No offenders; scanner self-test flags `refresh_timeflows` |
| S28 | [EXISTS] dynamic toolset still registers exactly discovery and execute (`test_dynamic.py::test_register_dynamic_tools_registers_two_tools`, `tests/functional/test_registration.py`) | FR-005 | py | Exactly two tools, unchanged parameters (QR-1) |
| S29 | [NEW] every rename is registered under its new name only and documented old-to-new -- `test_vocabulary_regression.py::test_persona_renames_are_complete_and_documented` (`_RENAMES` = FR-005 table) | FR-005 | py | Every new name present in some `config/toolsets/*.txt` (or `TOOL_TO_MODULE` for tools); no old name present; every pair appears in `docs/PPM-1129/PPM-1129-agent-ready-api-surface-proposal.md` (GAP-6) |
| S30 | [EXISTS] pre-built docstrings are free of banned terms outside alias lines (`::test_prebuilt_docstrings_are_free_of_internal_terms`, `::test_docstring_scanner_catches_a_regression`, `::test_alias_lines_are_the_only_place_legacy_words_are_quoted`) | FR-006, FR-009 | py | No offenders; self-test flags "timeflows", "rewound", "timeflow-specific" |
| S31 | [NEW] discovery and execute tool descriptions are free of banned terms and unqualified engine -- `test_vocabulary_regression.py::test_dynamic_tool_descriptions_are_free_of_internal_terms` (parametrized over `_BANNED`; record the functions passed to a `MagicMock` `app.add_tool`, build `mcp.server.fastmcp.tools.Tool.from_function(fn, name=...)`, scan `.description` lines and any `.parameters` descriptions) | FR-003, FR-011 | py | No offenders outside alias lines (GAP-2) |
| S32 | [NEW] elicitation schema text is free of banned terms and unqualified engine -- `::test_elicitation_schema_text_is_free_of_internal_terms` (walk `model_json_schema()` of the three `_*ConfirmationSchema` classes) | FR-007, FR-011 | py | No offenders (GAP-2) |
| S33 | [NEW] dynamic/elicitation scanners catch an injected regression -- `::test_dynamic_prose_scanner_catches_a_regression` (feed the schema helper a throwaway `BaseModel` subclass with `Field(description="Type the timeflows name")`, and the tool-prose helper a throwaway function whose docstring mentions "timeflows"; do not mutate the shared `Field` objects -- pydantic copies them) | FR-011 | py | Each helper reports exactly the injected line (GAP-2) |
| S34 | [EXISTS] confirmation messages render canonical names and drop unresolvable placeholders (`test_vocabulary_regression.py::test_no_confirmation_message_uses_internal_term`, `::test_engine_is_always_qualified_in_confirmation_messages`, `::test_vdb_group_casing_is_canonical`, `::test_no_confirmation_message_contains_a_pipe`; `test_vocabulary.py::test_confirmation_message_names_the_real_resource`, `::test_placeholder_clause_dropped_when_unresolvable`, `::test_days_clause_dropped_when_unresolvable`; `tests/functional/test_confirmation_handshake.py`; `tests/integration/test_host_approval_levels.py`) | FR-007 | py | `DELETE /vdb-groups/{id}` for "payroll" reads "...delete VDB Group 'payroll'?"; no `{`, `|`, banned term or bare engine; a `{days}` clause with no value is dropped |
| S35 | [EXISTS, manual non-gating] live session: "rewind my VDB" is treated as refresh from self with the rule 7 note | FR-008 | live DCT | Model answer uses "refresh from self" and states rewind is retired (Track 1, recorded in the PR test report) |
| S36 | [NEW] keyword-fallback confirmation prompt translates the OpenAPI summary -- `test_dynamic_confirmation.py::test_keyword_fallback_prompt_uses_canonical_summary` (operation summary "Delete timeflow") | FR-007 | py | Prompt contains "timeline" and not "timeflow" (FR-007 AC-6) |
| S37 | [NEW] keyword-fallback prompt survives a raising translator -- `test_dynamic_confirmation.py::test_keyword_fallback_prompt_when_translation_raises` (patch `vocabulary._compiled_rules` to raise) | FR-007 | py | Prompt is built from the raw summary; confirmation still required; no exception (GAP-1 layer 2) |
| S38 | [NEW] generated-tool confirmations render placeholders like persona toolsets -- `test_driver.py::test_generated_tool_confirmation_renders_placeholders` (generate from a minimal spec with `DELETE /vdb-groups/{vdbGroupId}`, call the generated `check_confirmation`) | FR-007 | py | Generated message reads "...delete VDB Group 'payroll'?"-style with the resolved name; no `{name}` (FR-007 AC-4) |
| S39 | [EXISTS] AppData/toolkit prose becomes connector terms and plugin IDs stay intact (`test_vocabulary.py`) | FR-009 | py | "AppData toolkit delphix-postgres-plugin failed" -> connector terms; `delphix-postgres-plugin` unchanged |
| S40 | [EXISTS] Delphix engine resolves on evidence, else the either phrase (`test_vocabulary.py`; `test_vocabulary_spec_corpus.py::test_delphix_engine_never_survives_and_names_one_product_only_on_evidence`) | FR-010 | py | "...provision the VDB" -> "Continuous Data engine"; no evidence -> "Continuous Data or Continuous Compliance engine" |
| S41 | [NEW] bare relayed engine passes through unchanged per the GAP-3 decision -- `test_vocabulary.py::test_bare_engine_is_not_rewritten` (cases: "engine cd-01 is unreachable", "The engine failed to provision the VDB", "Continuous Data engine is offline") | FR-010 | py | Every output equals its input; "Continuous Data engine" never doubled (pins GAP-3) |
| S42 | [NEW] Delphix engine next to a bare engine still resolves once -- `::test_delphix_engine_beside_bare_engine` ("The Delphix engine failed; check the engine logs for the VDB") | FR-010 | py | "Delphix engine" -> "Continuous Data engine"; the second bare "engine" unchanged; no "engine engine" |
| S43 | [NEW] editorial guideline exists and is linked from CLAUDE.md -- `test_vocabulary_regression.py::test_editorial_guideline_exists_and_is_linked` | FR-011 | py | File contains headings for the before-change checklist, "Where a vocabulary rule belongs", "After making the change" and "What done looks like"; `CLAUDE.md` contains its relative path (FR-011 AC-2) |
| S44 | [EXISTS] $ref request body exposes fields; inline body still works (`::test_ref_request_body_exposes_fields`, `::test_inline_request_body_still_works`) | FR-012 | py | `/vdbs/search` body fields include `filter_expression` |
| S45 | [NEW] self-referential request body $ref yields no fields and one warning -- `test_vocabulary.py::test_self_referential_request_body_ref_is_reported_once` (real `OpenAPISpec` with `components/requestBodies/A = {"$ref": "#/components/requestBodies/A"}`; access `required`, `content`, `fields()` repeatedly) | FR-012 | py | Zero body fields; no exception; exactly one WARNING naming the ref and `cycle_detected`. Fails on `d5f89d6` (no WARNING today; GAP-5) |
| S46 | [NEW] two-hop request body $ref chain still resolves -- `::test_two_hop_request_body_ref_resolves` (real `OpenAPISpec`, `A -> B -> inline body`) | FR-012 | py | Fields of the final body are exposed; no WARNING |
| S46a | [NEW] dangling request body $ref yields no fields and one warning -- `::test_dangling_request_body_ref_is_reported` (ref to a missing `components/requestBodies/X`) | FR-012 | py | Zero body fields; no exception; one WARNING naming the ref and `SCHEMA_REF_NOT_FOUND` (GAP-5) |
| S46b | [NEW] deeply nested $ref request body keeps its top-level fields -- `::test_deeply_nested_ref_body_keeps_fields` (real `OpenAPISpec`; body-level `$ref` to a body whose schema nests more than `DEFAULT_MAX_REF_DEPTH` dict levels) | FR-012 | py | Top-level fields exposed; no WARNING (guards against rejecting on the nested `truncated` flag) |
| S47 | [NEW] concurrent first translations agree -- `test_vocabulary.py::test_concurrent_first_translation_is_consistent` (`clear_cache()`, 8 threads translate the same string) | FR-002 | py | All 8 results identical and correct; no exception (EC-11) |
| S48 | [NEW] control characters and replacement characters pass through the translator -- `::test_control_characters_do_not_break_translation` ("Timeflow\x00� tf-1") | FR-002 | py | No exception; "Timeline" substituted; the control/replacement chars and `tf-1` byte-identical (EC-16) |
| S49 | [EXISTS] full CI suite and lint stay green | FR-001..FR-012 | py | `pytest tests/ -m "not real_dct and not llm_driven and not scenario"` 0 failures (baseline 1055 passed); `pre-commit run --all-files` clean (QR-10, QR-11) |

## Out of Scope
<!-- Guidance: Scenarios the test plan deliberately skips, with a one-line reason. Pull from vision-doc Non-Goals. Prevents reviewers asking "why isn't X tested?".
     Example:
     - Lock contention under >10k concurrent acquirers (Non-Goal NG2 — load testing tracked separately) -->

- Which operations require confirmation and at which level (NG1 -- unchanged; covered by the
  existing confirmation suites, not re-tested here).
- MCP tool annotations / reader extraction (NG2, PPM-1127).
- DCT API path, operationId or tag renames (NG3) -- only asserted indirectly: identifiers stay
  byte-identical (S9, S10).
- Continuous Compliance terminology beyond already-retired terms (NG4).
- Compatibility aliases for renamed tools (NG5) -- S29 asserts the old names are *absent*.
- Server-side rewriting of user input (NG6) -- retraining is instruction-level; S35 is a manual
  model-behaviour check only.
- Ticket outcomes outside this repository (BYO AI provider notice, post-GA documentation page) --
  excluded by the user's scope constraint.
- Generated-tool docstrings in `$TEMP/dct_mcp_tools/` (relayed spec text; design Open Question).
- QR-13 translation latency -- measured once in the validate phase, not a CI test.

## Test Data Requirements
<!-- Guidance: What data or fixture state must exist before tests run? If the test-infra phase seeds it, say so. If a fixture file lives in the repo, link it.
     Example:
     - Lock registry starts empty (test-infra phase truncates the registry before each run)
     - Two schemas (`schema-a`, `schema-b`) exist on the target service — seeded by `.claude/test/fixtures/schemas.sql` -->

- `tests/fixtures/dct_api_text_corpus.json.gz` (in repo; regenerating it needs a DCT
  `api-external.yaml` from outside the repo:
  `python -m tests.unit.test_vocabulary_spec_corpus <api-external.yaml>`).
- `$ref` request-body tests (S44-S46b) use small inline specs built in the test, not a spec file.
- Temporary files via `tmp_path` for invalid-UTF-8, empty, directory and rewritten
  `vocabulary.txt`/instructions files (S4-S7, S14, S16); monkeypatch `MAPPINGS_DIR` /
  `DCT_SERVER_INSTRUCTIONS`.
- **Cache isolation**: every test that changes config files or patches the translator must call
  `loader.clear_cache()` in setup and teardown (an autouse fixture in the affected modules), and
  after GAP-4 that also resets `_compiled_rules`, `_translate` and `_failure_logged`. Without it a
  `[NEW]` test leaks a degraded rule set into later tests.
- Log assertions use `caplog` on the module logger names (`dct_mcp_server.config.loader`,
  `dct_mcp_server.tools.core.vocabulary`, `dct_mcp_server.core.decorators` (new module-level logger, per design GAP-1),
  `dct_mcp_server.tools.core.dynamic`, `dct_mcp_server.tools.core.spec_model`).
- S35 only: DCT credentials in `.claude/settings.local.json`.

## Exit Criteria
<!-- Guidance: How the test phase decides "done". Be specific about pass thresholds.
     Example:
     - Smoke suite (existing tests in .claude/test/generated-test/ excluding $NAME) PASSes
     - No new error log lines containing "LockReclaim" during the run -->
- All Required scenarios PASS on all Required versions
- Smoke suite PASSes (or "first feature in repo — smoke skipped" note)
- No scenario marked SKIPPED without a documented reason
- Every `[NEW]` row for GAP-1, GAP-4, GAP-5 and GAP-7 (S4, S14, S16, S21, S24, S25, S45) was shown
  failing on `d5f89d6` before its fix (RED evidence recorded in the test evidence file)
- Full CI suite: 0 failures, pass count >= 1055 + number of `[NEW]` tests added; ruff/pre-commit
  clean
- Line coverage of `tools/core/vocabulary.py`, `config/loader.py` vocabulary/instructions
  functions and `core/decorators.py:_with_message_for_user` >= 80% (facts.json
  `coverage_threshold`)
- S35 recorded in the PR test report as PASS / FAIL / SKIPPED-with-reason; it does not gate merge

---
<!-- Cross-references:
     - Each Scenario row → drives one test block in .claude/test/generated-test/$NAME.spec.* (test-generation phase)
     - Each FR in docs/$NAME/$NAME-functional.md → at least one scenario here (otherwise the FR is untested)
     - Versions column → must be a subset of docs/$NAME/$NAME-design.md ## Version Compatibility "Supported = Yes"
     Validation: feature-executor.md Phase: test-generation Step 2 treats this file as authoritative. -->
<!-- FR coverage: FR-001 S1-S8; FR-002 S9-S17, S47, S48; FR-003 S15, S18-S21, S31; FR-004 S22-S26;
     FR-005 S27-S29; FR-006 S30; FR-007 S15, S32, S34, S36-S38; FR-008 S8, S19, S35;
     FR-009 S27, S30, S39; FR-010 S10, S40-S42; FR-011 S27, S31-S33, S43; FR-012 S44-S46b. -->
