# Functional Specification: PPM-1129

**Ticket**: PPM-1129
**PR**: https://github.com/delphix/dxi-mcp-server/pull/134
**Generated from**: the server-affecting PPM-1129 outcomes (facts.json
`acceptance_criteria[0], [1], [2], [3], [5]`), reconciled against the implementation already on
branch `dlpx/pr/vinay.byrappa/ppm-1129-vocabulary-agent-ready-api`.
**Scope**: dxi-mcp-server only -- `src/dct_mcp_server`, its config files, its tests and in-repo
docs.

Each FR carries an **Implementation status** line: `Implemented` (code and tests on the
branch), `Partial`, or a named gap. Status is evidence for the design and validate phases, not a
sign-off. Server-side gaps are collected in the final **Open Server-Side Gaps** table.

---

## FR-001: Supply vocabulary guidance as MCP server instructions

**Implementation status**: Implemented, with gap GAP-7 (non-UTF-8 file stops startup). Files:
`config/server_instructions.md`, `config/loader.py:load_server_instructions()`, `main.py`,
`config/config.py`. Tests:
`tests/unit/test_main.py`, `tests/unit/test_config*.py`,
`tests/unit/test_vocabulary.py::test_server_instructions_load_from_package`,
`::test_server_instructions_state_the_core_rules`, `::test_server_instructions_env_override`,
`::test_server_instructions_missing_file_is_not_fatal`.

### Description
The server passes a domain-model and terminology document as the `instructions` field of the
MCP `initialize` response, giving every connected model one shared set of rules. This is the
main lever in `dynamic` mode, where there are no curated tool/action names.

### Input
- The packaged `src/dct_mcp_server/config/server_instructions.md`, or
- the file named by the optional `DCT_SERVER_INSTRUCTIONS` env var (whitespace stripped; empty
  means unset).

### Processing
1. `load_server_instructions()` resolves the path: the override if set, else
   `CONFIG_DIR / "server_instructions.md"`.
2. If the file is missing, or reading raises `OSError` (including a directory path), it logs a
   WARNING and returns `""`. An empty file returns `""` with no warning. **Required (GAP-7)**:
   read with `encoding="utf-8"` and also catch `UnicodeDecodeError`; today a non-UTF-8 file or
   locale raises at `FastMCP(instructions=...)` construction and stops startup.
3. It returns the stripped text, cached with `lru_cache(maxsize=1)` and cleared by
   `loader.clear_cache()`.
4. `main.py` passes it as `FastMCP(..., instructions=load_server_instructions())` at
   construction, because `FastMCP.instructions` is read-only afterwards.

### Output
- Success: the `initialize` response contains the instructions text.
- Missing/unreadable file: empty instructions plus a WARNING log line.
- `config.print_config_help()` lists `DCT_SERVER_INSTRUCTIONS`.

### Acceptance Criteria
- [ ] AC-1: Given the default config, when the server is constructed, then `FastMCP` receives the
      full packaged `server_instructions.md` as `instructions`.
      Source: facts.json acceptance_criteria[0] -- "MCP Server responses consistently use canonical Delphix terminology"
- [ ] AC-2: Given `DCT_SERVER_INSTRUCTIONS=/path/custom.md` exists, when the server starts, then
      that file's text is used.
      Source: derived -- operator override read by `loader.load_server_instructions()`
      (`get_dct_config()["server_instructions_path"]` is informational only)
- [ ] AC-3: Given `DCT_SERVER_INSTRUCTIONS` points at a missing file, when the server starts, then
      it logs a warning, passes `""`, and does not raise.
      Source: derived -- non-fatal startup (G6)
- [ ] AC-5: Given `DCT_SERVER_INSTRUCTIONS` points at a file containing invalid UTF-8 bytes, when
      the server starts, then a WARNING is logged, `instructions=""`, and startup completes.
      **Not met on branch (GAP-7).**
      Source: derived -- non-fatal startup (G6)
- [ ] AC-4: Given the packaged instructions, then they define the domain model (VDB, dSource, data
      source, snapshot/timeline, environment, VDB Group vs. dataset group, connector, DCT vs.
      Continuous Data and Continuous Compliance engines, bookmark, data asset vs. dataset, PaaS
      Root Source/PaaS DB, instance, cloud account) and a terminology table with canonical /
      accept-as-input / never-use-in-output columns.
      Source: facts.json acceptance_criteria[0]

---

## FR-002: Translate relayed upstream text to canonical vocabulary, additively

**Implementation status**: Implemented. Files: `config/mappings/vocabulary.txt` (38 rules + 3
`@signals` sets), `config/loader.py:load_vocabulary_rules()/load_vocabulary_map()`,
`tools/core/vocabulary.py:to_canonical()/differs()`. Tests: `tests/unit/test_vocabulary.py`,
`tests/unit/test_vocabulary_spec_corpus.py`. Gaps: no exception fallback (GAP-1); stale caches
after `clear_cache()` (GAP-4).

### Description
Text relayed from DCT (raw error bodies, OpenAPI summaries/descriptions) is rewritten from
internal to canonical terms. Only prose changes; machine identifiers are never touched; the
original is always kept.

### Input
- `text: str | None`: any relayed string.
- Rules from `vocabulary.txt`: `@signals name=w1,w2,...` declares a word set;
  `internal|canonical[|guard=w1,w2...]...` declares a rule, guard being one of
  `skip_if_preceded_by`, `skip_if_followed_by`, `only_if_text_mentions`,
  `skip_if_text_mentions`; `@name` in a guard expands to a declared set.

### Processing
1. The loader parses rules once (`lru_cache`), lazily on the first translation via
   `_compiled_rules()`, expands `@signal` references, warns on and skips
   unknown guards or signal sets, and sorts rules longest-internal-term first (stable).
2. `to_canonical()` returns `None`/empty input unchanged.
3. It computes protected spans: URLs, tokens containing `/` or `\`, hyphen/dot/`@`-joined IDs,
   `code spans`, `{placeholders}`.
4. Per rule, it matches case-insensitive whole words (a space in a phrase also matches a hyphen),
   skips matches in protected spans or blocked by a guard; among lines sharing an internal
   term, the first whose text-level conditions hold wins.
5. It renders the replacement with casing preserved, merges overlaps so a term is never doubled,
   and corrects a/an only next to a replaced term.
6. `differs(original, translated)` reports whether anything changed. Results are memoized
   (`_translate`, `lru_cache(maxsize=8192)`); compiled patterns are cached in
   `_compiled_rules` (`lru_cache(maxsize=1)`).
7. **Required (GAP-4)**: `loader.clear_cache()` must also clear `vocabulary._compiled_rules` and
   `vocabulary._translate`, so a rules reload takes effect without a restart.

### Output
- The translated string, identical to the input when no rule applied.
- No exception for any `str` input is expected; callers must still not depend on that (FR-003,
  FR-004, GAP-1).

### Acceptance Criteria
- [ ] AC-1: Given "Timeflow tf-1 not found at /timeflows/tf-1", when translated, then the prose
      word becomes "Timeline" and `tf-1` and `/timeflows/tf-1` are byte-identical.
      Source: facts.json acceptance_criteria[0]
- [ ] AC-2: Given the 7,249-string DCT API corpus, when translated, then no identifier changes,
      no canonical term is repeated or nested, "VDB inventory report" is never called a rule
      set, and bare "container" is translated only with positive Self-Service evidence.
      Source: facts.json acceptance_criteria[0], [5] -- canonical output, guarded against regression
- [ ] AC-3: Given "Oracle container database" or a Kubernetes "container" with no Self-Service
      signal, when translated, then the text is unchanged.
      Source: derived -- false-positive guard (editorial guideline step 6)
- [ ] AC-4: Given `vocabulary.txt` is absent, when rules load, then `()` is returned with a warning
      and `to_canonical()` is the identity function.
      Source: derived -- non-fatal config loading (G6)
- [ ] AC-5: Given a rule line with an unknown guard key, when loading, then that guard is ignored
      with a WARNING and the rest of the rule applies.
      Source: derived -- loader behaviour on the branch
- [ ] AC-7: Given a line with fewer than two `|` parts or an empty term, when loading, then that
      line is skipped and the other rules load; given a guard referencing an undeclared
      `@signal`, then a WARNING is logged.
      Source: derived -- loader behaviour on the branch (EC-13)
- [ ] AC-8: Given `vocabulary.txt` is unreadable or contains invalid UTF-8, when the first
      translation runs, then rules degrade to `()` with a WARNING and no exception escapes.
      **Not met on branch (GAP-1)**: `load_vocabulary_rules()` opens the file with no
      try/except and no `encoding=`.
      Source: derived -- G6
- [ ] AC-6: Given rules were compiled and a translation memoized, when `loader.clear_cache()` is
      called and `vocabulary.txt` content changes, then the next `to_canonical()` call uses the
      new rules. **Not met on branch (GAP-4).**
      Source: derived -- G6, cache consistency

---

## FR-003: Translate summaries and errors in the dynamic `discovery` and `execute` tools

**Implementation status**: Implemented, with gaps GAP-1 and GAP-2. File: `tools/core/dynamic.py`.
Tests: `tests/unit/test_vocabulary.py::test_discovery_list_operations_translates_summaries`,
`::test_discovery_keyword_matches_either_vocabulary`,
`::test_discovery_operation_schema_translates_summary_and_description`;
`tests/unit/test_dynamic.py` (error-payload tests).

### Description
In `dynamic` mode, OpenAPI summaries/descriptions listed by `discovery` and DCT error bodies
returned by `execute` pass through `to_canonical()`. Keyword search still matches raw text, so
a legacy term still finds the operation.

### Input
- Operations from the connected DCT spec (`operationId`, `summary`, `description`, `path`,
  `tags`).
- DCT error responses (raw message, HTTP status).

### Processing
1. In `discovery`, the shown `summary` (and `description` where shown) is `to_canonical(raw)`.
2. The keyword filter matches `operationId`, the raw summary **and** the translated summary.
3. In `execute`, `_error_response(raw_message, http_status)` builds
   `{message: raw, http_status, ...}` and adds `message_for_user` only when
   `differs(raw, translated)`. The generic `except Exception` path also uses it.
4. **Required (GAP-1)**: if the vocabulary import, rule loading or `to_canonical()` raises
   inside `_error_response()`, log a WARNING and return the raw-error payload without
   `message_for_user`.
5. The `discovery` and `execute` docstrings are written in canonical vocabulary with
   alias-routing guidance. **Required (GAP-2)**: they are scanned against `_BANNED` like
   pre-built docstrings (today `test_tool_docstrings_are_free_of_internal_jargon` checks only
   implementation jargon).

### Output
- `discovery` entries with canonical summaries.
- `execute` error payloads with raw `message` and, when translation changed it,
  `message_for_user`.

### Acceptance Criteria
- [ ] AC-1: Given an operation summary "Switch timeflow", when `discovery` lists it, then the
      summary shown is "Switch timeline".
      Source: facts.json acceptance_criteria[0]
- [ ] AC-2: Given keyword "timeflow", when `discovery` filters, then operations whose raw summary
      contains "timeflow" are returned.
      Source: facts.json acceptance_criteria[1] -- "Customers using legacy terms get appropriate, non-confusing responses..."
- [ ] AC-3: Given a DCT error with no internal term, when `execute` returns it, then there is no
      `message_for_user` key.
      Source: derived -- additive-only contract
- [ ] AC-4: Given the `discovery` and `execute` docstrings, when scanned for each `_BANNED` term,
      then there are no hits outside alias guidance. **Not tested on branch (GAP-2).**
      Source: facts.json acceptance_criteria[0], [5]
- [ ] AC-5: Given `to_canonical` patched to raise, when `execute` handles a DCT failure, then the
      response still contains the raw `message` and `http_status`, has no `message_for_user`,
      and a WARNING is logged. **Not met on branch (GAP-1).**
      Source: derived -- G6

---

## FR-004: Translate pre-built tool DCT errors while keeping MCP `isError`

**Implementation status**: Implemented, with gap GAP-1. File:
`core/decorators.py:_with_message_for_user()`. Tests: `tests/unit/test_decorators_extended.py`
(4 tests fail on the regressed revision 132aae8, pass after 9079a02).

### Description
Every pre-built `*_endpoints_tool.py` function is wrapped by `@log_tool_execution`. On
`DCTClientError`, the decorator logs, records telemetry and **re-raises**, so FastMCP still
reports `isError: true`; when translation changes the text, a `message_for_user:` line is
appended.

### Input
- A `DCTClientError` raised inside a sync or async pre-built tool.

### Processing
1. Log the error, set `tool_data.status="failure"`, call `log_tool_call`.
2. `raw_message = str(exc)`; parse `HTTP (\d{3})` into `http_status`.
3. `translated = to_canonical(raw_message)` (lazy import avoids a circular import). If nothing
   differs, re-raise the same exception object, with `raw_message`, `message_for_user=None`
   and `http_status` attributes attached.
4. Otherwise raise `type(exc)(f"{raw}\nmessage_for_user: {translated}")` from the original, with
   the same three attributes.
5. **Required (GAP-1)**: if the lazy import, rule loading or `to_canonical()` raises, log a
   WARNING and re-raise the original `DCTClientError`.
6. Scope limit: only `DCTClientError` is translated; other exceptions are re-raised untouched.

### Output
- Always a raised `DCTClientError` (same type); MCP clients see `isError: true`; text starts with
  the raw message.

### Acceptance Criteria
- [ ] AC-1: Given a pre-built tool raising `DCTClientError("HTTP 404: Timeflow not found")`, when
      called through MCP, then the result has `isError: true` and text starting with the raw
      message followed by `message_for_user: HTTP 404: timeline not found`.
      Source: facts.json acceptance_criteria[0]
- [ ] AC-2: Given an error with no internal terms, then the same exception object is re-raised
      with no appended line and `message_for_user is None`.
      Source: derived -- additive-only contract
- [ ] AC-3: Given any `DCTClientError`, the decorator never returns a value in place of raising.
      Source: derived -- guards the 132aae8 regression
- [ ] AC-4: Given `to_canonical` patched to raise, when a pre-built tool raises `DCTClientError`,
      then the original exception is re-raised unchanged and a WARNING is logged. **Not met on
      branch (GAP-1).**
      Source: derived -- G6

---

## FR-005: Canonical tool and action names in persona toolsets (breaking renames)

**Implementation status**: Implemented; no aliases by design (GAP-6 tracks the migration
documentation). Files: `config/toolsets/*.txt` (5 files), `config/loader.py` tool-to-module
map, `tools/*_endpoints_tool.py`. Tests: `tests/unit/test_vocabulary_regression.py` plus updated
functional/integration/e2e tests (`tests/functional/workflows/test_timeline.py`, formerly
`test_timeflow.py`).

### Description
Every persona-toolset tool and action whose name carried a retired term is renamed. DCT API
paths are unchanged.

### Input
- Toolset lines `METHOD|/path|action_name` and `@app.tool()` functions in pre-built modules.

### Processing
Apply the rename table (also in `docs/PPM-1129/PPM-1129-agent-ready-api-surface-proposal.md`):

| Kind | Old | New |
|---|---|---|
| Tool | `timeflow_tool` | `timeline_tool` |
| Tool | `toolkit_tool` | `connector_schema_tool` |
| Tool | `database_template_tool` | `vdb_template_tool` |
| Action | `upload_toolkit` / `delete_toolkit` | `upload_connector_schema` / `delete_connector_schema` |
| Action | `dsource_link_appdata[_defaults]` | `dsource_link_connector[_defaults]` |
| Action | `update_appdata_dsource` | `update_connector_dsource` |
| Action | `switch_vdb_timeflow` / `switch_timeflow` | `switch_vdb_timeline` / `switch_timeline` |
| Action | `create_appdata_source` / `update_appdata_source` | `create_connector_source` / `update_connector_source` |
| Action | `get_snapshot_timeflow_range` / `get_timeflow_range` | `get_snapshot_timeline_range` / `get_timeline_range` |
| Action | `check_database_connectivity` | `check_connectivity` |

### Output
- Toolsets register only canonical names; an old name fails as unknown tool/action.

### Acceptance Criteria
- [ ] AC-1: Given any `config/toolsets/*.txt` or pre-built module, when scanned, then no tool or
      action name contains a `_BANNED` term in any inflection.
      Source: facts.json acceptance_criteria[0]
- [ ] AC-2: Given `DCT_TOOLSET=continuous_data_admin`, when tools register, then `timeline_tool`,
      `connector_schema_tool` and `vdb_template_tool` exist and `timeflow_tool` does not.
      Source: derived -- rename table
- [ ] AC-3: Given `DCT_TOOLSET=dynamic`, then the registered tool set (`discovery`, `execute`) is
      unchanged.
      Source: derived -- breaking change limited to persona toolsets
- [ ] AC-4: Given the rename table and `git diff origin/main -- src/dct_mcp_server/config/toolsets/`,
      then every renamed name appears old-to-new in
      `docs/PPM-1129/PPM-1129-agent-ready-api-surface-proposal.md`.
      Source: derived -- migration path (GAP-6)

---

## FR-006: Canonical pre-built tool docstrings with customer-alias lines

**Implementation status**: Implemented. Files: `tools/*_endpoints_tool.py` (dataset, environment,
engine, iam, job, misc, policy, reports, template). Tests:
`test_vocabulary_regression.py::test_prebuilt_docstrings_are_free_of_internal_terms`,
`::test_alias_lines_are_the_only_place_legacy_words_are_quoted`.

### Description
Pre-built docstrings use canonical terms; legacy/alias words appear only on a dedicated
customer-alias line so the model can route legacy phrasing without echoing it.

### Input
- Docstrings of every pre-built `@app.tool()` function.

### Processing
1. Replace internal terms in docstring prose.
2. Put accepted aliases only on the designated alias line.

### Output
- Docstrings with no `_BANNED` term outside alias lines.

### Acceptance Criteria
- [ ] AC-1: Given every pre-built docstring, when scanned for each `_BANNED` term (including
      inflections and irregular forms such as "rewound"), then no hits outside alias lines.
      Source: facts.json acceptance_criteria[0]
- [ ] AC-2: Given the scanner, when fed a docstring containing "timeflows", then it reports a
      violation (self-test).
      Source: facts.json acceptance_criteria[5] -- "Editorial guidelines in place for future action additions, preventing regression"

---

## FR-007: Canonical confirmation templates with safe placeholder rendering

**Implementation status**: Implemented, with gap GAP-2 (elicitation text unscanned). Files:
`config/mappings/manual_confirmation.txt` (79 rules),
`tools/core/confirmation_resolver.py:render_message_template()/_resolve_resource_name()`,
`tools/core/confirmation_levels.py`, `tools/core/dynamic_confirmation.py`,
`toolsgenerator/driver.py`, and the elicitation schemas in `tools/core/dynamic.py`
(`_StandardConfirmationSchema`, `_ElevatedConfirmationSchema`, `_ManualConfirmationSchema`).
Tests: `test_vocabulary_regression.py`, `tests/functional/test_confirmation_handshake.py`,
`tests/integration/test_host_approval_levels.py`.

### Description
Confirmation messages use canonical terms and name the real resource. `{name}`, `{days}` and
`{count}` render in every toolset; an unresolvable placeholder drops its clause. Gating and
levels are unchanged.

### Input
- A matched rule `METHOD|path_pattern|level|message_template` plus request
  path/path-template/body.

### Processing
1. Resolve the resource name via `_resolve_resource_name()`, falling back to
   `_extract_resource_id(path, path_template)`.
2. `render_message_template()` substitutes known placeholders and removes clauses with
   unresolvable ones.
3. Keyword-fallback prompts built from OpenAPI summaries pass through `to_canonical()`.

### Output
- A message with no `{...}`, no `|`, no `_BANNED` term, "VDB Group" casing, and "engine" always
  qualified.

### Acceptance Criteria
- [ ] AC-1: Given `DELETE /vdb-groups/{vdbGroupId}` for group "payroll", when confirmation is
      required, then the message reads "...delete VDB Group 'payroll'?".
      Source: facts.json acceptance_criteria[0]
- [ ] AC-2: Given a template with `{days}` and no retention value, when rendered, then the clause
      is dropped and no brace appears.
      Source: derived -- `render_message_template()` contract
- [ ] AC-3: Given every rule in `manual_confirmation.txt`, then no message uses a `_BANNED` term,
      an unqualified "engine", or a pipe.
      Source: facts.json acceptance_criteria[0], [3]
- [ ] AC-4: Given a tool generated by `toolsgenerator/driver.py`, when its confirmation triggers,
      then placeholders render as in persona toolsets.
      Source: derived -- driver.py change on the branch
- [ ] AC-5: Given the elicitation schema `Field(description=...)` text, when scanned for each
      `_BANNED` term and unqualified "engine", then there are no hits. **Not tested on branch
      (GAP-2).**
      Source: facts.json acceptance_criteria[0], [5]
- [ ] AC-6: Given an ungated mutating operation whose OpenAPI summary is "Delete timeflow", when
      the keyword-fallback prompt is built (`tools/core/dynamic_confirmation.py`), then it says
      "timeline".
      Source: facts.json acceptance_criteria[0]

---

## FR-008: Retraining rules for legacy terminology

**Implementation status**: Implemented (instruction-level). File: `config/server_instructions.md`
"Additional rules" 1-12 and the terminology table. Test:
`tests/unit/test_vocabulary.py::test_server_instructions_state_the_core_rules`.

### Description
The instructions tell the model to accept legacy words and answer with canonical terms:
ordinary aliases silently, retired or confusable terms with one explicit note.

### Input
- A user utterance containing an alias or retired term (as seen by the model).

### Processing
1. Silent canonical answer for ordinary aliases (rule 5).
2. Explicit note for: container -> VDB Group (rule 4), rewind -> refresh from self (rule 7),
   inventory -> rule set (rule 9), CC domain -> data class / classification (rule 12), DCT
   conflated with an engine (rule 2).
3. Clarify rather than map "reset" (rule 8); never conflate lineage/timeline, data
   source/dSource, or dataset group/VDB Group (rules 10-11).

### Output
- Model guidance only; the server does not transform user input (NG6).

### Acceptance Criteria
- [ ] AC-1: Given the packaged instructions, then each rule contains its retraining sentence:
      rule 4 "VDB Group is the current term."; rule 7 "Rewind is retired Delphix terminology —
      the current term is refresh from self."; rule 9 "Rule set is the current term; inventory
      is retired Continuous Compliance terminology."; rule 12 "Domain is being migrated to data
      class / classification in Delphix vocabulary."
      Source: facts.json acceptance_criteria[1] -- "Customers using legacy terms get appropriate, non-confusing responses that retrain them toward canonical terms"
- [ ] AC-2: Given the packaged instructions, then rule 5 says to answer ordinary aliases
      canonically without correcting the user and lists the exceptions.
      Source: facts.json acceptance_criteria[1]
- [ ] AC-3 (manual check, non-gating -- model output is not deterministic): Given a live MCP
      client session in which the user says "rewind my VDB", then the model treats it as
      refresh from self and gives the rule 7 note. Not run on branch.
      Source: facts.json acceptance_criteria[1]

---

## FR-009: Hide the native vs. AppData connector split

**Implementation status**: Implemented. Files: `server_instructions.md` rule 1,
AppData/plugin/toolkit entries in `vocabulary.txt`, renames (FR-005), docstrings (FR-006).
Tests: `tests/unit/test_vocabulary_regression.py`, `tests/unit/test_vocabulary.py`.

### Description
Every data platform is presented as a "connector"; "AppData", "plugin" and "toolkit" never
appear as customer-facing concepts.

### Input
- Names, docstrings, instructions, and relayed prose.

### Processing
1. Instruction rule 1 forbids the words and organising answers around the split.
2. Renames (`toolkit_tool` -> `connector_schema_tool`, `*_appdata_*` -> `*_connector_*`).
3. `vocabulary.txt` translates them in relayed prose; identifiers such as
   `delphix-postgres-plugin` or `toolkit@1.0.0` are protected.

### Output
- No user-facing AppData/plugin/toolkit wording outside protected identifiers.

### Acceptance Criteria
- [ ] AC-1: Given every tool/action name and docstring, then "appdata", "plugin" and "toolkit" do
      not occur (regression scanner).
      Source: facts.json acceptance_criteria[2] -- "Native vs AppData connector split is not exposed to users by default"
- [ ] AC-2: Given the upstream error "AppData toolkit delphix-postgres-plugin failed", when
      translated, then prose terms become connector terms and `delphix-postgres-plugin` is
      unchanged.
      Source: facts.json acceptance_criteria[2]

---

## FR-010: Resolve engine / DCT / product conflation on evidence

**Implementation status**: Implemented for "Delphix engine(s)" and retired engine names; bare
relayed "engine" is a pinned design decision (GAP-3: no rule; instruction rule 2 is the mitigation). Files: `server_instructions.md` rule 2, the
`delphix engine(s)` / `virtualization engine` / `masking engine` / `cloud engine(s)` entries in
`vocabulary.txt`. Tests:
`test_vocabulary_spec_corpus.py::test_delphix_engine_never_survives_and_names_one_product_only_on_evidence`,
`test_vocabulary_regression.py::test_engine_is_always_qualified_in_confirmation_messages`.

### Description
The server never authors a bare "engine". Relayed "Delphix engine" names one product only on
whole-word evidence (contrary evidence vetoes); otherwise it renders "Continuous Data or
Continuous Compliance engine". Retired names map directly. Bare relayed "engine" currently has
no rule and passes through; `engine_tool` keeps its name because bare `engine` is not in
`_BANNED`.

### Input
- Relayed text containing "engine", "Delphix engine", "Virtualization Engine", "Masking Engine"
  or "Cloud Engine".

### Processing
1. Virtualization Engine -> Continuous Data engine; Masking Engine -> Continuous Compliance
   engine; Cloud Engine -> Continuous Data engine with Elastic Data.
2. "Delphix engine" takes the first rule whose `only_if_text_mentions=@<product>` matches and no
   `skip_if_text_mentions` vetoes; else the "either" fallback.
3. Bare "engine": no rule, by design (GAP-3). Evidence-gated rules were rejected because
   "engine" is also a real DCT object name and is often already qualified nearby; instruction
   rule 2 is the accepted mitigation, and S41/S42 pin the current behaviour.

### Output
- A qualified engine phrase or the explicit "either" phrase for "Delphix engine" and retired
  names; bare "engine" per the GAP-3 decision.

### Acceptance Criteria
- [ ] AC-1: Given "Delphix engine failed to provision the VDB", when translated, then the result
      says "Continuous Data engine".
      Source: facts.json acceptance_criteria[3] -- "Engine / DCT / product conflation in customer language is addressed at the MCP Server voice layer"
- [ ] AC-2: Given "Delphix engine is unreachable" with no product evidence, when translated, then
      the result says "Continuous Data or Continuous Compliance engine".
      Source: facts.json acceptance_criteria[3]
- [ ] AC-3: Given the real corpus, then no translated string contains "Delphix engine".
      Source: facts.json acceptance_criteria[3]
- [ ] AC-4: Given relayed text with bare "engine" and Continuous Data evidence, when translated,
      then the outcome matches the GAP-3 design decision and a test pins it (including that
      "Continuous Data engine" is never doubled). **Pinned (GAP-3):** `test_bare_engine_is_not_rewritten` and
      `test_delphix_engine_beside_bare_engine` in `tests/unit/test_vocabulary.py`.
      Source: facts.json acceptance_criteria[3]

---

## FR-011: In-repo editorial guideline and regression guards

**Implementation status**: Implemented for pre-built surfaces; dynamic-mode docstrings and
elicitation text unscanned (GAP-2). Files: `.claude/rules/vocabulary-editorial-guidelines.md`
(linked from `CLAUDE.md`), `src/dct_mcp_server/config/CLAUDE.md` (vocabulary.txt syntax),
`tests/unit/test_vocabulary_regression.py` (`_BANNED`, which includes `mssql` and
`cloud engine` for prose scans; `_NAME_BANNED` leaves `mssql` out of name scans because action
names mirror the `/dsources/mssql` API paths; `_IRREGULAR`; `_NAME_EXCEPTIONS` /
`_PROSE_EXCEPTIONS`),
`tests/unit/test_vocabulary_spec_corpus.py`.

### Description
A written checklist for anyone adding or renaming a tool, action, docstring, message or
translation rule, backed by tests that fail when a retired term returns, plus a corpus test
that catches translator false positives on real API text.

### Input
- Any change to toolsets, pre-built tools, dynamic tools, docstrings, confirmation templates,
  elicitation schemas or `vocabulary.txt`.

### Processing
1. The guideline requires using canonical terms, never adding a retired term, resolving
   ambiguity from evidence, keeping `message_for_user` customer-facing, and adding a
   regression test.
2. Regression tests scan confirmation messages, toolset names, pre-built names and docstrings
   for inflection-aware `_BANNED` terms; scanner self-tests prove the scanner can fail.
   **Required (GAP-2)**: extend the scan to `discovery`/`execute` docstrings and elicitation
   field descriptions.
3. The corpus fixture regenerates from a DCT `api-external.yaml` via
   `python -m tests.unit.test_vocabulary_spec_corpus <spec>`.

### Output
- The test suite fails on any reintroduced retired term or translator corruption.

### Acceptance Criteria
- [ ] AC-1: Given a new action named `refresh_timeflows`, when the suite runs, then
      `test_toolset_tool_and_action_names_use_canonical_terms` fails.
      Source: facts.json acceptance_criteria[5] -- "Editorial guidelines in place for future action additions, preventing regression"
- [ ] AC-2: Given `.claude/rules/vocabulary-editorial-guidelines.md`, then it covers the
      before-change checklist, the "where a rule belongs" table, the after-change steps and the
      definition of done, and `CLAUDE.md` links it.
      Source: facts.json acceptance_criteria[5]
- [ ] AC-3: Given "timeflow" inserted into the `execute` docstring or an elicitation
      `Field(description=...)`, when the suite runs, then a regression test fails. **Not met on
      branch (GAP-2).**
      Source: facts.json acceptance_criteria[5]

---

## FR-012: Expose request-body fields for `$ref`-defined request bodies

**Implementation status**: Implemented (GAP-5 fixed). File:
`tools/core/spec_model.py` (`RequestBody._resolved()`, uses `spec.resolve_refs()`).
Tests: `tests/test_spec_model.py::test_request_body_*`,
`::test_request_body_resolved_uses_resolve_refs_not_resolve_ref`,
`::test_request_body_resolved_warns_once_for_missing_ref`.

### Description
An operation whose `requestBody` is a `$ref` to `components/requestBodies/X` previously exposed
zero body fields (238 operations in DCT 2026.x, including all `/search` endpoints and therefore
`filter_expression`). The body-level `$ref` is now followed via `spec.resolve_refs()` which
provides cycle detection and nesting depth up to 10.

### Input
- An OpenAPI operation whose `requestBody` is `{"$ref": "#/components/requestBodies/..."}`.

### Processing
1. Call `spec.resolve_refs(raw)` on the request body (GAP-5: the former 5-hop
   `resolve_ref` loop was dead code — `OpenAPISpec` has no `resolve_ref` method,
   so `hasattr` always returned `False` and the loop exited on the first iteration).
2. `resolve_refs()` handles cycle detection and nesting depth up to 10.
3. Read `required` and `content` from the resolved body.
4. Log a one-time WARNING (via `_WARNED_BODY_REFS`) when the `$ref` resolves to an
   error marker or truncated result.

### Output
- Body schema fields visible to `discovery` for those operations.
- Cycle / depth exceeded: `$ref_truncated` marker dict, WARNING logged once per ref.
- Missing `$ref` target: `SCHEMA_REF_NOT_FOUND` marker dict, WARNING logged once per ref.

### Acceptance Criteria
- [x] AC-1: Given a `/vdbs/search` operation with a `$ref` request body, when `discovery`
      describes it, then `filter_expression` appears among the body fields.
      Source: derived -- server-side agent-readiness fix
- [x] AC-2: Given a self-referential body-level `$ref`, when resolved, then cycle detection
      stops resolution and a WARNING is logged (not silent zero fields).
      Source: derived -- bounded-loop guard. Fixed by GAP-5.

---

## Open Server-Side Gaps

| ID | Gap | Location | Tracked by |
|----|-----|----------|-----------|
| GAP-1 | **FIXED** Layered exception fallback added: `encoding="utf-8"` + `except (OSError, UnicodeDecodeError)` in loader; `try/except Exception` in `to_canonical()`, `_with_message_for_user()`, `_error_response()` | `config/loader.py`, `tools/core/vocabulary.py`, `core/decorators.py`, `tools/core/dynamic.py` | FR-002 AC-8, FR-003 AC-5, FR-004 AC-4 |
| GAP-2 | **FIXED** `discovery`/`execute` docstrings and elicitation `Field(description=...)` text now scanned against `_BANNED`; guidelines updated | `tests/unit/test_vocabulary_regression.py`, `.claude/rules/vocabulary-editorial-guidelines.md` | FR-003 AC-4, FR-007 AC-5, FR-011 AC-3 |
| GAP-3 | Bare relayed "engine" passes through untranslated (no rule, not in `_BANNED`); pinned by design (instruction rule 2 + tests) | `config/mappings/vocabulary.txt` | FR-010 AC-4 |
| GAP-4 | **FIXED** `loader.clear_cache()` now calls registered hooks; `vocabulary.py` registers a hook that clears `_compiled_rules` / `_translate` and resets `_failure_logged` | `config/loader.py`, `tools/core/vocabulary.py` | FR-002 AC-6 |
| GAP-5 | **FIXED** Dead 5-hop loop replaced with single `spec.resolve_refs()` call; once-per-ref WARNING via `_WARNED_BODY_REFS`; tested in `tests/test_spec_model.py` | `tools/core/spec_model.py` | FR-012 AC-2 |
| GAP-6 | Breaking persona-toolset renames ship with no aliases; migration relies on the in-repo rename table; regression scanner added in `test_vocabulary_regression.py` | `config/toolsets/*.txt`, `docs/PPM-1129/PPM-1129-agent-ready-api-surface-proposal.md` | FR-005 AC-4 |
| GAP-7 | **FIXED** `load_server_instructions()` and `load_vocabulary_rules()` now open files with `encoding="utf-8"` and catch `UnicodeDecodeError`; directory paths return `""` + WARNING | `config/loader.py` | FR-001 AC-5 |

---

## Quality Rules

| Rule | Description | Enforcement | Status | Evidence |
|------|-------------|-------------|--------|----------|
| QR-1 API backward compatibility (dynamic) | `DCT_TOOLSET=dynamic` registers exactly `discovery` and `execute` with unchanged parameters | `tests/unit/test_dynamic.py`, `tests/functional/test_registration.py` | | |
| QR-2 Migration path for breaking renames | 100% of renamed persona tools/actions listed old-to-new in `docs/PPM-1129/PPM-1129-agent-ready-api-surface-proposal.md`; no aliases | Review against `git diff origin/main -- src/dct_mcp_server/config/toolsets/` | | |
| QR-3 No retired term in controlled surfaces | Zero `_BANNED` hits (all inflections) in names, docstrings outside alias lines (pre-built **and** dynamic), confirmation templates and elicitation descriptions | `pytest tests/unit/test_vocabulary_regression.py` | | |
| QR-4 Identifiers never rewritten | 100% of URLs, paths, joined IDs, code spans and placeholders in the 7,249-string corpus byte-identical | `pytest tests/unit/test_vocabulary_spec_corpus.py` | | |
| QR-5 Translation is additive | Raw text always kept; `message_for_user` present only when `differs()` | `test_dynamic.py`, `test_decorators_extended.py` | | |
| QR-6 MCP error semantics preserved | 100% of pre-built `DCTClientError` paths produce `isError: true`, including when translation raises | `test_decorators_extended.py` | | |
| QR-7 Translation never hides an error | A raising vocabulary import, rule load or `to_canonical()` yields the original error in both `execute` and pre-built paths | New tests for FR-002 AC-8 / FR-003 AC-5 / FR-004 AC-4 | | |
| QR-8 No silent ambiguous default | No rule maps "Delphix engine", bare "engine" or bare "container" without positive-evidence guards | Code review of `vocabulary.txt`; corpus tests | | |
| QR-9 Config-only, non-fatal loading | Missing, malformed, unreadable or non-UTF-8 `server_instructions.md` / `vocabulary.txt` never prevents startup or a tool call; both read with `encoding="utf-8"`; `clear_cache()` resets every vocabulary cache | `test_config*.py`, `test_main.py`, tests for FR-001 AC-5, FR-002 AC-6/AC-8 | | |
| QR-10 Full suite green | 0 failures (PR baseline: 1055 passed, 0 failed) | `pytest tests/ -m "not real_dct and not llm_driven and not scenario"` | | |
| QR-11 Code style | `get_logger(__name__)` only; `DCTClientError`/`MCPError` only; ruff lint and format clean | `pre-commit run --all-files` | | |
| QR-12 Customer-facing canonical column | No model-directed instruction in the canonical column of `vocabulary.txt` | Review against editorial guideline step 5 | | |
| QR-13 Translation cost (non-gating target) | `to_canonical()` under 5 ms for a 4 KB error string on a developer laptop; no network or file I/O per call | Timed measurement in the validate phase; not a CI gate | | |

Status and Evidence columns are filled in by the validate phase.

---

## Edge Cases

- EC-1: `to_canonical(None)` or `""` returns the input unchanged.
- EC-2: A term inside a URL, path (`/timeflows/{id}`, `C:\toolkit\x`), hyphen/dot/@ ID (`tf-1`,
  `toolkit@1.0.0`), code span or `{placeholder}` is never translated.
- EC-3: All-caps match (`TIMEFLOW`) yields an all-caps replacement; a sentence-initial match is
  capitalised; a title-cased match mid-sentence takes the canonical casing ("VDB Group",
  "timeline"). A ":" does not start a sentence, so "HTTP 404: Timeflow not found" becomes
  "HTTP 404: timeline not found".
- EC-4: Text already partly spelling the canonical term is merged, never doubled
  ("Self-Service VDB containers" -> "Self-Service VDB Groups"); without Self-Service evidence,
  "VDB containers" is unchanged.
- EC-5: Unrelated meanings are left alone: Kubernetes/Docker "container", Oracle "container
  database", "VDB inventory report", text already saying rule set.
- EC-6: "Delphix engine" with evidence for both products, or neither, renders the "either"
  phrase.
- EC-7: A legacy keyword ("timeflow") in `discovery` still matches via the raw summary.
- EC-8: An a/an article next to a replaced term is corrected; one next to an untouched word is
  never changed.
- EC-9: An unresolvable confirmation placeholder drops its clause; no `{name}` reaches the user.
- EC-10: A self-referential body-level `$ref` stops after 5 hops and yields zero body fields
  (GAP-5).
- EC-11: Concurrent tool calls share the cached rule tuple read-only (immutable tuples and
  frozensets; no lock needed). `lru_cache` is thread-safe, but two calls racing on the first
  miss may both compute the result; this is harmless (identical output), not exactly-once.
- EC-12: A multi-KB error body is translated in one pass per precompiled rule; embedded paths
  stay intact; memoization keeps up to 8192 distinct bodies.
- EC-13: A malformed `vocabulary.txt` line (fewer than two `|` parts, empty term, unknown guard
  or unknown `@signal`) is skipped or partially ignored with a warning; startup continues.
- EC-14: Bare "engine" in a relayed error or a keyword search passes through untranslated
  (GAP-3).
- EC-15: `clear_cache()` is called at runtime after `vocabulary.txt` changes; until GAP-4 is
  closed, translation keeps the old compiled rules and memoized results.
- EC-16: An error body that is not valid UTF-8 or contains control characters reaches
  `to_canonical()` as a decoded `str`; it must translate or pass through without raising.
- EC-17: `DCT_SERVER_INSTRUCTIONS` points at a directory: `IsADirectoryError` (an `OSError`) is
  caught, WARNING, `instructions=""`.
- EC-18: `DCT_SERVER_INSTRUCTIONS` points at an empty file: `instructions=""` with no warning.
- EC-19: `DCT_SERVER_INSTRUCTIONS` points at a non-UTF-8 file: startup fails today (GAP-7).
- EC-20: A pre-built tool raises an exception other than `DCTClientError`: re-raised
  untranslated, no `message_for_user` (scope limit).

## Error Scenarios

- ERR-1: `server_instructions.md` missing or unreadable (`OSError`): WARNING,
  `instructions=""`; other levers still apply. Recovery: fix the path or unset
  `DCT_SERVER_INSTRUCTIONS` and restart. A non-UTF-8 file currently stops startup (GAP-7).
- ERR-2: `vocabulary.txt` missing: rules are `()`, translation is identity, raw message still
  returned. Unreadable or non-UTF-8: currently raises on the first translation (GAP-1);
  required behaviour is the same degradation as "missing".
- ERR-3: Malformed `vocabulary.txt` lines skipped with warnings; valid rules still load.
- ERR-4 (GAP-1, unmitigated on branch): the vocabulary import, rule loading or `to_canonical()`
  raising inside
  `_with_message_for_user()` or `_error_response()` would replace the DCT error. Required
  recovery: catch, log WARNING, return/re-raise the raw error without `message_for_user`.
- ERR-5: Wrong resource name in a confirmation for paths matching no template
  (`_extract_resource_id` positional fallback). Confirmation is still required; only the
  displayed name is wrong. Follow-up.
- ERR-6: A breaking rename hits a client with "unknown tool/action". Recovery: use the new name
  from the rename table. Rollback: pin the previous server version (no runtime alias by
  design).
- ERR-7: Stale vocabulary after `clear_cache()` (GAP-4). Recovery today: restart the server.
- ERR-8: Feature rollback is a git revert of the branch merge; all behaviour is config- and
  code-local with no persisted state or migration.

## Performance Considerations

- Rules are parsed and compiled once per process (`lru_cache(maxsize=1)` on the loaders and
  `_compiled_rules`). No per-call file I/O and no network calls.
- Translation is O(rules x text length) with precompiled regexes; 38 rules is negligible next to
  a DCT round trip (default `DCT_TIMEOUT` 30 s). Target: under 5 ms per typical error string or
  discovery page (QR-13).
- `discovery` translates every operation that passes tag/method filters **before** pagination
  (up to about 1,044 summaries per call); the `_translate` memo (8192 entries) amortises this
  after the first listing.
- `load_server_instructions()` runs once at construction; the text (about 200 lines) is sent
  once per `initialize`.
- Memory is bounded by 8192 memoized inputs; optionally skip memoizing very large strings.

## Assumptions

- Only the server-affecting ticket outcomes (facts.json acceptance_criteria[0], [1], [2], [3],
  [5]) are traced, per the user's scope constraint. FR numbering is new in this revision.
- FR-005: breaking renames are accepted without aliases; persona toolsets are opt-in surfaces.
- FR-010: bare "engine" gets no rule; recorded as a design decision and pinned by tests (GAP-3).
- FR-012: included as a server-side agent-readiness fix although no ticket outcome names it.
- Implementation status and test names come from the branch at `d5f89d6` and PR #134's
  description (1055 passed, 972 skipped, 0 failed); GAP-1, GAP-4, GAP-5 and GAP-7 were
  re-checked against the source in this phase.
- Both config files are assumed to be UTF-8; the fix for GAP-1/GAP-7 makes that explicit with
  `encoding="utf-8"`. This phase did not re-run tests and did not
  modify production code.

---
<!-- Cross-reference: G1 -> FR-001..FR-007; G2 -> FR-008, FR-003 AC-2; G3 -> FR-009;
     G4 -> FR-010; G5 -> FR-011; G6 -> FR-001 AC-3/AC-5, FR-002 AC-4/AC-6/AC-8, FR-003 AC-5,
     FR-004 AC-4; G7 -> FR-012.
     SC1 -> FR-005/006/007; SC2 -> FR-001; SC3 -> FR-003/004; SC4 -> FR-002; SC5 -> FR-008, FR-003;
     SC6 -> FR-009; SC7 -> FR-010; SC8 -> FR-011; SC9 -> FR-001 AC-5, FR-002 AC-8, FR-003 AC-5,
     FR-004 AC-4; SC10 -> FR-012. -->
