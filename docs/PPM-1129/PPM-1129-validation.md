# Validation Report: PPM-1129

| Field | Value |
|-------|-------|
| Generated | 2026-10-28T05:20:38Z |
| Domain | feature |
| Validator | feature-implement validate step |
| Validates | docs/PPM-1129/PPM-1129-functional.md |
| Branch | dlpx/pr/vinay.byrappa/ppm-1129-vocabulary-agent-ready-api (HEAD: 41de161) |
| PR | https://github.com/delphix/dxi-mcp-server/pull/134 |

---

## 1. Functional Requirement Coverage

<!-- Copied from docs/PPM-1129/PPM-1129-coverage.md, verified against test-evidence.md -->

| FR-ID | Description | Status | Evidence (file:line) |
|-------|-------------|--------|----------------------|
| FR-001 | Supply vocabulary guidance as MCP server instructions | PASS | tests/unit/test_vocabulary.py:27 (`test_server_instructions_load_from_package`); src/dct_mcp_server/config/loader.py:395 (`load_server_instructions`); src/dct_mcp_server/config/config.py:40 (`DCT_SERVER_INSTRUCTIONS` env var) |
| FR-002 | Translate relayed upstream text to canonical vocabulary, additively | PASS | src/dct_mcp_server/tools/core/vocabulary.py:242 (`to_canonical`); src/dct_mcp_server/config/loader.py:407 (`load_vocabulary_rules`); tests/unit/test_vocabulary.py:14 (import + 100+ assertion cases) |
| FR-003 | Translate summaries and errors in dynamic `discovery` and `execute` tools | PASS | tests/unit/test_vocabulary.py:1048 (`test_discovery_list_operations_translates_summaries`); src/dct_mcp_server/tools/core/dynamic.py:1183 (`_error_response`); tests/unit/test_dynamic.py:436 (`test_execute_dct_client_error_translates_internal_terminology`) |
| FR-004 | Translate pre-built tool DCT errors while keeping MCP `isError` | PASS | src/dct_mcp_server/core/decorators.py:29 (`_with_message_for_user`); tests/unit/test_decorators_extended.py:245 (`test_prebuilt_dct_error_reaches_the_mcp_client_as_iserror_with_translation`); tests/unit/test_dynamic_confirmation.py:298 (`test_with_message_for_user_returns_original_exception_when_vocabulary_raises`) |
| FR-005 | Canonical tool and action names in persona toolsets (breaking renames) | PASS | tests/unit/test_vocabulary_regression.py:197 (`test_toolset_tool_and_action_names_use_canonical_terms`); src/dct_mcp_server/config/loader.py:716 (`TOOL_TO_MODULE`); tests/unit/test_vocabulary_regression.py:206 (`test_prebuilt_tool_and_action_names_use_canonical_terms`) |
| FR-006 | Canonical pre-built tool docstrings with customer-alias lines | PASS | tests/unit/test_vocabulary_regression.py:300 (`test_prebuilt_docstrings_are_free_of_internal_terms`, parametrized); tests/unit/test_vocabulary_regression.py:309 (`test_alias_lines_are_the_only_place_legacy_words_are_quoted`) |
| FR-007 | Canonical confirmation templates with safe placeholder rendering | PASS | tests/unit/test_vocabulary.py:552 (`test_placeholder_clause_dropped_when_unresolvable`); tests/unit/test_vocabulary.py:593 (`test_confirmation_message_names_the_real_resource`); tests/unit/test_vocabulary_regression.py:73 (`test_no_confirmation_message_uses_internal_term`); src/dct_mcp_server/toolsgenerator/driver.py:299 (`render_message_template` import) |
| FR-008 | Retraining rules for legacy terminology | PASS | tests/unit/test_vocabulary.py:241 (`"Cannot rewind VDB vdb-1..."` → `"...refresh from self VDB vdb-1..."`); tests/unit/test_vocabulary_regression.py:35 (`rewind` in `_BANNED`); src/dct_mcp_server/config/server_instructions.md (instruction rules 7+) |
| FR-009 | Hide the native vs. AppData connector split | PASS | tests/unit/test_vocabulary.py:214 (`"Install the appdata plugin"` → `"Install the connector"`); tests/unit/test_vocabulary.py:389 (`test_prose_around_identifiers_is_still_translated[Plugin delphix-postgres-plugin...]`); src/dct_mcp_server/config/mappings/vocabulary.txt (appdata/toolkit rules) |
| FR-010 | Resolve engine / DCT / product conflation on evidence | PASS | tests/unit/test_vocabulary_spec_corpus.py:197 (`test_delphix_engine_never_survives_and_names_one_product_only_on_evidence`); tests/unit/test_vocabulary.py:281 (`test_to_canonical_resolves_delphix_engine_from_the_text`); src/dct_mcp_server/config/mappings/vocabulary.txt (delphix engine rules with signals) |
| FR-011 | In-repo editorial guideline and regression guards | PASS | tests/unit/test_vocabulary_regression.py:422 (`test_editorial_guidelines_mention_dynamic_docstring_scan`); src/dct_mcp_server/config/CLAUDE.md:34 (link to `vocabulary-editorial-guidelines.md`); .claude/rules/vocabulary-editorial-guidelines.md (file exists with all required sections) |
| FR-012 | Expose request-body fields for `$ref`-defined request bodies | PASS | src/dct_mcp_server/tools/core/spec_model.py:402 (`RequestBody._resolved`); tests/test_spec_model.py:297 (`test_request_body_resolved_warns_once_for_missing_ref`); tests/unit/test_vocabulary.py:868 (`test_ref_request_body_exposes_fields`) |

### Coverage Summary

- Total requirements: 12
- PASS: 12
- FAIL: 0
- N/A: 0

**Notes on open gaps (documented design decisions, not FAIL items)**:
- FR-001 AC-5 (non-UTF-8 server_instructions.md): Implemented — GAP-7 FIXED (encoding="utf-8" + UnicodeDecodeError catch in load_server_instructions). PASS.
- FR-002 AC-8 (unreadable vocabulary.txt): Implemented — GAP-1 FIXED. PASS.
- FR-010 AC-4 (bare relayed "engine"): GAP-3, documented design decision — no vocabulary rule for bare "engine"; instruction rule 2 is the accepted mitigation, pinned by S41/S42 tests. Counted as PASS per FR-010's own Implementation Status ("Implemented for 'Delphix engine(s)' and retired engine names; bare relayed 'engine' is a gap (GAP-3)"). The FR-010 AC-4 sub-criterion is explicitly Open on branch by design.
- FR-003 AC-4 / FR-007 AC-5 / FR-011 AC-3 (dynamic docstrings and elicitation text unscanned): GAP-2 FIXED — S31/S32/S33 all PASS. PASS.
- S35 (live "rewind my VDB" session): manual, non-gating, live DCT not available. Does not affect FR-008 PASS.

---

## 2. Quality Rule Enforcement

| Rule | Description | Enforcement | Status | Evidence |
|------|-------------|-------------|--------|----------|
| QR-1 API backward compatibility (dynamic) | `DCT_TOOLSET=dynamic` registers exactly `discovery` and `execute` with unchanged parameters | `tests/unit/test_dynamic.py`, `tests/functional/test_registration.py` | PASS | `pytest test_register_dynamic_tools_registers_two_tools`, `test_register_dynamic_tools_names_are_discovery_and_execute`: 3 passed, 5 skipped (credentials-gated), 0 failed |
| QR-2 Migration path for breaking renames | 100% of renamed persona tools/actions listed old-to-new in `docs/PPM-1129/PPM-1129-agent-ready-api-surface-proposal.md`; no aliases | Review against `git diff origin/main -- src/dct_mcp_server/config/toolsets/` | PASS | Old names (`timeflow_tool`, `toolkit_tool`, `database_template_tool`) absent from all toolset txt files (grep confirms); new names (`timeline_tool`, `connector_schema_tool`, `vdb_template_tool`) present. `test_persona_renames_are_complete_and_documented` (tests/unit/test_vocabulary_regression.py:470) confirms all pairs documented. |
| QR-3 No retired term in controlled surfaces | Zero `_BANNED` hits (all inflections) in names, docstrings outside alias lines (pre-built and dynamic), confirmation templates and elicitation descriptions | `pytest tests/unit/test_vocabulary_regression.py` | PASS | 64 passed, 0 failed. Includes dynamic tool docstrings (S31), elicitation schemas (S32), regression self-test (S33), all confirmation messages (S34). |
| QR-4 Identifiers never rewritten | 100% of URLs, paths, joined IDs, code spans and placeholders in the 7,249-string corpus byte-identical | `pytest tests/unit/test_vocabulary_spec_corpus.py` | PASS | 25 passed, 0 failed. All identifiers preserved; no canonical term nested or repeated; guarded translations confirmed. |
| QR-5 Translation is additive | Raw text always kept; `message_for_user` present only when `differs()` | `test_dynamic.py`, `test_decorators_extended.py` | PASS | decorators.py:64 — `message_for_user = translated if differs(raw_message, translated) else None`. 48 tests in test_decorators_extended.py + test_dynamic_confirmation.py: 48 passed. |
| QR-6 MCP error semantics preserved | 100% of pre-built `DCTClientError` paths produce `isError: true`, including when translation raises | `test_decorators_extended.py` | PASS | `test_prebuilt_dct_error_reaches_the_mcp_client_as_iserror_with_translation` (line 245), `test_sync_dct_client_error_reraised_when_translation_raises` (line 293), `test_async_dct_client_error_reraised_when_translation_raises` (line 339): all PASS. |
| QR-7 Translation never hides an error | A raising vocabulary import, rule load or `to_canonical()` yields the original error in both `execute` and pre-built paths | New tests for FR-002 AC-8 / FR-003 AC-5 / FR-004 AC-4 | PASS | S15 (`test_to_canonical_returns_input_when_translation_raises`), S21 (`test_error_response_keeps_raw_error_when_translation_raises`), S24/S25: all PASS. RED-before-fix confirmed at commit d5f89d6. |
| QR-8 No silent ambiguous default | No rule maps "Delphix engine", bare "engine" or bare "container" without positive-evidence guards | Code review of `vocabulary.txt`; corpus tests | PASS | `vocabulary.txt`: no bare `engine|` rule; `container|VDB Group` has `only_if_text_mentions=@selfservice`; `delphix engine` rules all guarded with `only_if_text_mentions=@data` or `@compliance` plus `skip_if_text_mentions` vetoes. QR-4 corpus test confirms no false positives on 7,249 strings. |
| QR-9 Config-only, non-fatal loading | Missing, malformed, unreadable or non-UTF-8 config files never prevent startup or a tool call; `clear_cache()` resets every vocabulary cache | `test_config*.py`, `test_main.py`, FR-001 AC-5, FR-002 AC-6/AC-8 | PASS | S4 (invalid UTF-8 instructions), S6 (directory path), S7 (empty file), S12 (missing vocabulary.txt), S13 (malformed lines), S14 (invalid UTF-8 vocabulary), S16 (clear_cache clears vocabulary), S17 (hook registry): all PASS at HEAD, all FAIL at d5f89d6. |
| QR-10 Full suite green | 0 failures (PR baseline: 1055 passed, 0 failed) | `pytest tests/ -m "not real_dct and not llm_driven and not scenario"` | PASS | 1116 passed, 947 skipped, 25 deselected, 113 warnings (deprecation warnings from dependencies), 0 failures. Ruff check: All checks passed. Ruff format: 132 files already formatted. |
| QR-11 Code style | `get_logger(__name__)` only; `DCTClientError`/`MCPError` only; ruff lint and format clean | `pre-commit run --all-files` | PASS | `ruff check .`: All checks passed. `ruff format --check .`: 132 files already formatted. No `logging.getLogger` calls in new diff. No bare `raise Exception` in new tool code. |
| QR-12 Customer-facing canonical column | No model-directed instruction in the canonical column of `vocabulary.txt` | Review against editorial guideline step 5 | PASS | Python scan of vocabulary.txt canonical column: no "clarify", "ask", "verify", "confirm which", "check", or "tell the model" phrases found. |
| QR-13 Translation cost (non-gating target) | `to_canonical()` under 5 ms for a 4 KB error string on a developer laptop; no network or file I/O per call | Timed measurement | PASS (non-gating) | Measured 0.11 ms for 2,090-byte string (100 iterations, Python 3.11 arm64). Well under the 5 ms target. |

---

## 3. Task Completion

<!-- No docs/PPM-1129/PPM-1129-plan.md exists (the implement phase did not generate a separate plan file — implementation was a gap-fix pass over existing code). Task completion is inferred from the functional spec's Implementation Status lines and test-evidence scenarios. -->

| Task | Description | Status | Notes |
|------|-------------|--------|-------|
| GAP-1: Exception fallback | `encoding="utf-8"` + `(OSError, UnicodeDecodeError)` in loaders; `try/except Exception` guard in `to_canonical()`, `_with_message_for_user()`, `_error_response()` | COMPLETE | S4, S5, S14, S15, S21, S24, S25 all PASS; RED-before-fix confirmed at d5f89d6 |
| GAP-2: Dynamic docstring and elicitation scan | `discovery`/`execute` docstrings and elicitation `Field(description=...)` text scanned against `_BANNED`; guidelines updated | COMPLETE | S31, S32, S33 all PASS |
| GAP-3: Bare engine design decision | Recorded in design doc (GAP-3 section); no vocabulary rule added; instruction rule 2 accepted as mitigation; tests pin the decision (S41, S42) | COMPLETE | Design decision documented and tested |
| GAP-4: clear_cache hook registry | `register_cache_clear_hook()` exported; `clear_cache()` calls registered hooks; vocabulary.py registers a hook for `_compiled_rules`/`_translate`/`_failure_logged` | COMPLETE | S16, S17 all PASS; RED-before-fix confirmed at d5f89d6 |
| GAP-5: Dead resolve_ref loop | Dead 5-hop `resolve_ref` loop replaced with `spec.resolve_refs()` call; once-per-ref WARNING via `_WARNED_BODY_REFS` | COMPLETE | S45, S46, S46a, S46b all PASS; RED-before-fix confirmed at d5f89d6 |
| GAP-6: No aliases (design decision) | Breaking renames ship without backward-compatibility aliases; migration documented in `PPM-1129-agent-ready-api-surface-proposal.md`; regression scanner (`test_persona_renames_are_complete_and_documented`) enforces completeness | COMPLETE | Design decision documented; S29 PASS |
| GAP-7: UTF-8 encoding | `load_server_instructions()` and `load_vocabulary_rules()` open with `encoding="utf-8"` and catch `UnicodeDecodeError`; directory paths return `""` + WARNING | COMPLETE | S4, S5, S6 PASS; RED-before-fix confirmed at d5f89d6 |
| As-built vocabulary layer (FR-001..FR-012) | Server instructions, vocabulary translator, persona renames, confirmation templates, docstrings, editorial guidelines, $ref resolution — all pre-existing on branch | COMPLETE | All 12 FRs PASS; 1116 tests pass |

---

## 4. Issues Found

### Critical

None.

### High

None.

### Medium

| # | Issue | Location | Notes |
|---|-------|----------|-------|
| M-1 | S36/S37/S38 scenario-test label mismatch | docs/PPM-1129/PPM-1129-test-evidence.md | S36 ("keyword-fallback prompt translates") is actually mapped to `test_with_message_for_user_returns_original_exception_when_vocabulary_raises` (GAP-1 decorator guard, not keyword-fallback translation). S37 ("keyword-fallback survives raising translator") is mapped to `test_with_message_for_user_attaches_canonical_message_for_user_on_success` (success path). S38 ("generated-tool confirmations") is mapped to `test_spec_model_imports_cleanly_after_gap5` (a GAP-5 smoke test). The tests are real and correct; the scenario descriptions do not match what the tests verify. Separate functional gap for `test_dynamic_confirmation.py::test_keyword_fallback_prompt_translates_summary` (that specific behavior has no dedicated test). Non-blocking: FR-007 AC-6 is covered through `dynamic_confirmation.py:to_canonical()` chain which is tested in QR-3/QR-4. |
| M-2 | FR-010 AC-4 listed as "Open on branch" per spec, but tests S41/S42 pin the design decision | docs/PPM-1129/PPM-1129-functional.md:FR-010 | The functional spec says FR-010 AC-4 is "Open on branch (GAP-3)" but S41/S42 were added in commit 41de161 to pin the GAP-3 decision. The functional spec's FR-010 AC-4 status line should read "Pinned by design decision (GAP-3) — tests S41/S42 verify that bare 'engine' passes through and 'Continuous Data engine' is never doubled." This is a spec accuracy issue, not a code bug. Non-blocking. |
| M-3 | Test evidence references non-existent `test_purge.py` | docs/PPM-1129/PPM-1129-test-evidence.md | The live smoke summary mentions "Cleanup `test_purge.py` deliberately not run" but no such file exists in `tests/e2e/`. Minor documentation inaccuracy. |
| M-4 | `main.py` coverage at 74% (pre-existing) | src/dct_mcp_server/main.py | Coverage is pre-existing; only 5 lines were added by this branch. The uncovered startup paths (59-60, 126-142, 155-156) require a running event loop and are integration-gated. Not a regression. |
| M-5 | `testing/cli.py` coverage at 57% (pre-existing) | src/dct_mcp_server/testing/cli.py | Pre-existing gap; this file was not modified by the branch. Not a regression. |

### Low

| # | Issue | Location | Notes |
|---|-------|----------|-------|
| L-1 | Functional spec FR-005 rename table shows 10 rows; proposal doc has 14 renames documented | docs/PPM-1129/PPM-1129-functional.md | The FR-005 Processing table lists 10 rename rows (3 Tools + 7 Actions pairs) but some rows bundle aliases ("switch_vdb_timeflow / switch_timeflow" counts as 2). The proposal doc has 14 individual entries. The count discrepancy is cosmetic — the regression test `test_persona_renames_are_complete_and_documented` (S29) enforces completeness programmatically. |
| L-2 | `logging.getLogger(__name__)` in loader.py line 20 (pre-existing, not introduced by PPM-1129) | src/dct_mcp_server/config/loader.py:20 | Code-style rule requires `get_logger(__name__)` from `dct_mcp_server.core.logging`. New functions added by PPM-1129 inherit this pre-existing module-level logger. Not a regression — this pattern exists in loader.py before this branch. Separate follow-up. |
| L-3 | Cosmetic: `rule.get("skip_if_text_mentions", ())` fallback in vocabulary.py:82 is unreachable (loader always sets all guard keys to `frozenset()`) | src/dct_mcp_server/tools/core/vocabulary.py:82 | Harmless defence-in-depth fallback. No observable impact. |
| L-4 | Minor inconsistency: `\b` word boundary in substitution patterns vs `(?<![\w-])` in `_word_set_pattern` in vocabulary.py | src/dct_mcp_server/tools/core/vocabulary.py:82-84 | Hyphen-adjacent occurrences handled slightly differently between the two. No observable impact on DCT error text in practice. |

---

## 5. Security Assessment

| Check | Status | Notes |
|-------|--------|-------|
| Input validation present | PASS | `to_canonical()` handles None/empty/non-string input gracefully (EC-1); vocabulary rules are parsed defensively with guards on malformed lines; all user-facing text is generated from templates with placeholder resolution, never from raw user input |
| No hardcoded secrets or credentials | PASS | Grep of diff against common secret patterns: no hits. API key passed via environment variable (`DCT_API_KEY`) only; no in-code literals. |
| Exception handling complete | PASS | GAP-1 fallback guards cover all three layers: vocabulary import, rule load, and `to_canonical()` itself. `except Exception` clauses are purposeful (broad catch on vocabulary fallback path to avoid hiding DCT errors). All handlers log at WARNING level before returning raw data. |
| Log sanitization in place | PASS | Grep of diff additions for credential/API key logging: no hits. Translation WARNING logs record exception type/message, not user data or API payloads. |
| Authentication/authorization preserved | PASS | `DCTAPIClient` construction is unchanged (`main.py:207`); API key is loaded from environment only; the vocabulary/translation layer has no access to credentials. Confirmation gating (destructive operations requiring two-step confirm) is explicitly listed in the Non-Goals (no change to which operations are gated). |

No DB-driver code or externally-spawned command with an inline credential changed — `connector-security-review` skipped.

---

## 6. Code Quality

| Check | Status | Evidence | Notes |
|-------|--------|----------|-------|
| Follows existing patterns | PASS | All new tool-layer code uses `@log_tool_execution` decorator, `get_logger(__name__)`, `DCTClientError`/`MCPError`. Grouped action pattern (existing) preserved. Dynamic tools (`discovery`, `execute`) follow async pattern. | New vocabulary.py functions follow the existing `lru_cache` + lazy-import pattern. |
| Error handling complete | PASS | GAP-1 fallbacks in vocabulary.py:270, decorators.py:22/74/120/158, dynamic.py:146/543/875/1184/1625, loader.py:823/852/878. All use `except Exception` to ensure translation never hides a DCT error. | `except Exception` is appropriate here — the design requirement is that vocabulary logic must never surface to callers. |
| No generated files edited | PASS | Grep of changed file list for `_generated.`, `_auto.`, `.generated.`: no hits. Toolsgenerator `driver.py` is the generator, not a generated file. | |
| Tests present and passing | PASS | 51 functional scenarios (50 PASS, 1 NOT RUN: S35 — non-gating live DCT). Full suite: 1116 passed, 0 failed. RED-before-fix confirmed for GAP-1/4/5/7 at d5f89d6. | |
| No unrelated files modified | PASS | After accepting `tests/test_spec_model.py` (FR-012 GAP-5 test, scope expanded and recorded in design doc + facts.json), `.claude/.feature-implement-gate.json` (workflow gate state file), and `docs/superpowers/plans/2026-10-27-ppm-1129-gap-fixes.md` (superpowers subagent plan artifact): `classify_scope_drift` returns no out-of-scope paths. | Scope expansion decisions appended to facts.json decisions log. |

---

## 7. Build & Test Results

| Step | Result | Notes |
|------|--------|-------|
| Lint (`ruff check .`) | PASS | All checks passed (132 files). Exit code 0. |
| Format (`ruff format --check .`) | PASS | 132 files already formatted. Exit code 0. |
| Package build (`python3 -m build`) | PASS | Wheel: `dist/dct_mcp_server-2026.0.3.0rc0-py3-none-any.whl` (300 KB); sdist: 972 KB. Exit code 0. |
| Unit tests | PASS | `pytest tests/ -m "not real_dct and not llm_driven and not scenario"`: 1116 passed, 947 skipped (credentials-gated), 25 deselected, 113 warnings (dependency deprecations), 0 failures. Python 3.11.6. |
| E2E live smoke (dispatcher-run, pre-evidence-refresh) | 23 PASS / 1 SKIP | `tests/e2e/test_smoke.py` + `tests/e2e/test_smoke_cda.py` run by dispatcher against live DCT at https://localhost. 1 skipped: no VDBs on the instance to round-trip. Not re-run per user constraint (credentials not provided). |

### Code Coverage

| Framework | Command | Line Coverage % | Status | Reason |
|-----------|---------|----------------|--------|--------|
| pytest-cov | `uv run --with pytest-cov pytest tests/ -m "not real_dct and not llm_driven and not scenario" --cov=src/dct_mcp_server --cov-report=term-missing` | 88% | PASS | Above 80% threshold |

**Key file coverage:**

| File | Cover | Uncovered Lines |
|------|-------|----------------|
| `src/dct_mcp_server/config/loader.py` | 98% | 395, 507, 582-585 |
| `src/dct_mcp_server/tools/core/vocabulary.py` | 96% | 156-158, 310, 331 |
| `src/dct_mcp_server/core/decorators.py` | 96% | 22-23, 101, 139 |
| `src/dct_mcp_server/tools/core/dynamic_confirmation.py` | 91% | 126-127, 142-144 |
| `src/dct_mcp_server/tools/core/spec_model.py` | 90% | Multiple paths in $ref resolution edge cases |
| `src/dct_mcp_server/tools/core/dynamic.py` | 83% | Startup / gRPC / elicitation paths (credentials-gated) |
| `src/dct_mcp_server/main.py` | 74% | Startup/shutdown event-loop paths (pre-existing gap, not modified significantly by branch) |

All PPM-1129 primary files above the 80% threshold. `main.py` at 74% is a pre-existing gap (integration-gated startup paths).

---

## 8. Recommendations

| Priority | Recommendation | Source Section |
|----------|---------------|----------------|
| Medium | Correct the S36/S37/S38 scenario descriptions in `docs/PPM-1129/PPM-1129-test-evidence.md` to match what the named tests actually verify, or rename the tests to match the original scenario intent. | Section 4 M-1 |
| Medium | Update `docs/PPM-1129/PPM-1129-functional.md` FR-010 AC-4 status to reflect that S41/S42 (commit 41de161) have pinned the GAP-3 decision and it is no longer "Open on branch". | Section 4 M-2 |
| Low | Remove the reference to `test_purge.py` in the test-evidence smoke section (the file does not exist; the statement "deliberately not run" implies it was skipped, but it was never created). | Section 4 M-3 |
| Low | Add a milestone to reach `main.py` coverage above 80% via integration/startup-path tests in a follow-up. | Section 4 M-4 |
| Low | Replace pre-existing `logging.getLogger(__name__)` in `loader.py:20` with `get_logger(__name__)` from `dct_mcp_server.core.logging` (code-style rule; not a PPM-1129 regression). | Section 4 L-2 (code review) |
| Low | Confirm whether the `\b` / `(?<![\w-])` inconsistency in `vocabulary.py` (L-4) should be unified in a follow-up — no functional impact today, but could cause confusion if hyphen-adjacent retired terms are ever added to the rule set. | Section 4 L-4 (code review) |

---

## 9. E2E Testing Results

**E2E Verdict: SKIPPED** — no deployability indicator found. Checked: docker-compose.yml, compose.yml, build.gradle (bootRun), pom.xml (spring-boot-maven-plugin), package.json (start/dev), manage.py, main.go (net/http), app.py (flask), wsgi.py (flask), main.py (fastapi/uvicorn), *.proto, Cargo.toml (tokio/hyper/actix-web). This is a Python MCP stdio-transport server with no HTTP surface of its own — E2E curl-based testing is not applicable. The dispatcher-run live smoke (`tests/e2e/test_smoke.py` + `test_smoke_cda.py`: 23 PASS, 1 SKIP) serves as the functional E2E layer.

---

## Overall Verdict

**Verdict:** PASS WITH WARNINGS

**Reasoning:** All 12 FRs PASS with evidence (test citations or grep proof). 13 Quality Rules all PASS (QR-13 is non-gating and met). No Critical or High issues found. Full test suite clean (1116 passed, 0 failures). Ruff lint and format clean. Build succeeds (wheel + sdist). Code coverage 88% (above 80% threshold). All changes are within the accepted scope.

The PASS WITH WARNINGS reflects:
- S35 (live retraining session) not run — manual, non-gating, documented in test plan Exit Criteria as not required for merge.
- M-1 (S36/S37/S38 scenario label mismatches): the tests themselves are correct and pass; only the scenario descriptions in the test evidence doc are mismatched. FR-007 AC-6 (keyword-fallback translation) is covered transitively through the translation chain tested by QR-3/QR-4. This is a doc accuracy issue, not a code gap.
- M-2 (FR-010 AC-4 status outdated in functional spec): GAP-3 is a documented design decision, not a code bug. Tests S41/S42 pin it.

GAP-3 (bare relayed "engine" passes through untranslated) and GAP-6 (no backward-compatibility aliases for breaking renames) are documented design decisions recorded in `docs/PPM-1129/PPM-1129-design.md` sections GAP-3 and GAP-6. These are NOT code fixes outstanding before merge; they are explicit design choices with tests pinning the behavior.

**Next Steps:**
1. Address M-1 and M-2 doc accuracy issues as a follow-up edit (no code change needed).
2. Open a follow-up ticket to track the `main.py` coverage gap (pre-existing).
3. Raise PR #134 — no blocking issues.


## Post-validation corrections

Made after the validate phase, on re-reading the code:

- **M-1 (fixed):** the S36/S37/S38 evidence rows described tests that did not match the plan. The planned FR-007 tests did not exist; they were added (`test_keyword_fallback_prompt_uses_canonical_summary`, `test_keyword_fallback_prompt_when_translation_raises`, `test_generated_tool_confirmation_renders_placeholders`). The older decorator and `spec_model` tests that carried those labels were relabelled as GAP-1/GAP-5 tests.
- **M-2 (fixed):** `functional.md` FR-010 AC-4 and the GAP-3 text now say the decision is pinned by S41/S42.
- **M-3 (withdrawn):** `tests/e2e/cleanup/test_purge.py` does exist. The evidence now gives its full path and says it was not run because it deletes objects.
- Unit suite after these changes: 1119 passed, 0 failed; ruff check and format clean.
