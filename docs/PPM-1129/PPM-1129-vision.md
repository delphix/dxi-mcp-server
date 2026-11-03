# Vision: PPM-1129

**Ticket**: PPM-1129 -- Vocabulary & Domain Model Guidance (dxi-mcp-server scope)
**Branch**: `dlpx/pr/vinay.byrappa/ppm-1129-vocabulary-agent-ready-api` (PR delphix/dxi-mcp-server#134)
**Scope**: This spec covers only what affects the dxi-mcp-server repository: code under
`src/dct_mcp_server`, its config files, its tests, and in-repo docs. It is written after the
fact for a change already built by hand on the branch. Where the branch has a server-side gap,
the gap is stated so the design and validate phases can track it. Nothing here claims a gap is
closed.

## Problem Statement

The DCT MCP Server is a product voice channel, not just a pass-through to the DCT API. What an
AI agent tells a user is shaped by four surfaces this server controls or relays: tool and action
names, tool docstrings, the instructions it gives the model, and the error and confirmation
text it returns. Before this change, all four exposed internal terms:

- **timeflow** instead of timeline
- **container** for a VDB Group (now reads as Kubernetes/Docker)
- **AppData / plugin / toolkit**, which exposes the native vs. AppData connector split
- bare **engine** or **Delphix engine**, conflated with DCT and ambiguous between the
  Continuous Data and Continuous Compliance engines
- **rewind** and **inventory**, retired terms
- **data source** used as a synonym for dSource

The server also passed no `instructions=` to `FastMCP(...)`, so the model had no domain model
telling it that VDB, clone, copy and virtual database are the same object, or that "dataset
group" and "VDB Group" differ.

The model repeats this vocabulary verbatim. Because `DCT_TOOLSET` defaults to `dynamic`, most
of what the model reads comes from the connected DCT's OpenAPI spec and raw DCT error bodies,
which the server relays but does not author. A rename-only pass over the server's config would
therefore miss most of the text users see; the server must also translate relayed text.

## Goals

- G1: Emit canonical terminology on every surface the server controls: server instructions,
  persona tool and action names, pre-built tool docstrings, confirmation templates, and the
  upstream text it relays (raw DCT errors and OpenAPI summaries/descriptions shown by
  `discovery`).
  Source: facts.json acceptance_criteria[0] -- "MCP Server responses consistently use canonical Delphix terminology"
- G2: Give the model rules (in `server_instructions.md`) to accept every legacy or alias term,
  answer with the canonical term, and add an explicit retraining note only for retired or
  easily confused terms (container, rewind, inventory, Continuous Compliance domain, DCT
  conflated with an engine). Keyword search in `discovery` must still match legacy terms.
  Source: facts.json acceptance_criteria[1] -- "Customers using legacy terms get appropriate, non-confusing responses that retrain them toward canonical terms"
- G3: Never surface the native vs. AppData connector split in server names, docstrings,
  instructions or translated text. Every data platform is a "connector".
  Source: facts.json acceptance_criteria[2] -- "Native vs AppData connector split is not exposed to users by default"
- G4: Never author a bare "engine" in server-controlled text. Name the Continuous Data or
  Continuous Compliance engine in translated text only on whole-word evidence; otherwise say
  plainly that the source did not specify, rather than silently picking one.
  Source: facts.json acceptance_criteria[3] -- "Engine / DCT / product conflation in customer language is addressed at the MCP Server voice layer"
- G5: Keep an in-repo editorial checklist (`.claude/rules/vocabulary-editorial-guidelines.md`)
  backed by tests, so any future tool, action, docstring, message or translation rule that
  reintroduces a retired term or corrupts relayed text fails the test suite.
  Source: facts.json acceptance_criteria[5] -- "Editorial guidelines in place for future action additions, preventing regression"
- G6: Make the server robust to the vocabulary layer itself: translation must never hide the
  original DCT error, never break MCP error semantics, and never block startup.
  Source: derived -- server-side gaps found in the branch review (translator exception path,
  config-file decoding at startup, loader cache reset)
- G7: Expose request-body fields to the model for operations whose request body is a `$ref`
  (including all `/search` endpoints and their `filter_expression`), with a bounded, tested
  resolution loop.
  Source: derived -- server-side agent-readiness fix on the branch; no ticket outcome names it

## Non-Goals

- NG1: Changing which operations are gated by confirmation, or at which level. Only the
  **wording** and placeholder rendering of existing templates change.
  Source: facts.json constraints[1], [3].
- NG2: Adding MCP tool annotations or reader extraction.
  Source: facts.json constraints[2].
- NG3: Renaming DCT API endpoints, paths, operationIds or OpenAPI tags. Paths, URLs and IDs are
  never translated by the server.
  Source: facts.json constraints[4].
- NG4: Reconciling Continuous Compliance terminology beyond the CC terms already marked retired
  (Masking Engine, Delphix Masking, inventory, domain).
  Source: facts.json constraints[0].
- NG5: Compatibility aliases for renamed persona-toolset tools/actions. Deliberately omitted,
  because an alias keeps the retired word in the surface the model reads.
- NG6: Server-side rewriting of user input. Retraining is instruction-level guidance only.

## Success Criteria

- SC1: No retired term from `_BANNED` (any inflection, including irregular forms such as
  "rewound") appears in any `config/toolsets/*.txt` tool or action name, pre-built tool/action
  name, pre-built docstring outside alias lines, or `manual_confirmation.txt` template.
  Enforced by `tests/unit/test_vocabulary_regression.py`. The dynamic-mode docstrings and
  elicitation text are covered by SC8.
  Source: facts.json acceptance_criteria[0]
- SC2: The MCP `initialize` response carries `config/server_instructions.md` (or the file named
  by `DCT_SERVER_INSTRUCTIONS`) as `instructions`.
  Source: facts.json acceptance_criteria[0], [1]
- SC3: When a DCT call fails with text containing an internal term, the dynamic `execute`
  result and the pre-built tool error keep the raw message verbatim and add a
  `message_for_user` rendering. A pre-built tool failure still surfaces as MCP `isError: true`.
  Source: facts.json acceptance_criteria[0]
- SC4: Translating the 7,249-string DCT API text corpus
  (`tests/fixtures/dct_api_text_corpus.json.gz`) leaves every identifier byte-identical, never
  doubles or nests a canonical term, never renames "VDB inventory report" or Oracle "container
  database", and never lets "Delphix engine" survive. Enforced by
  `tests/unit/test_vocabulary_spec_corpus.py`.
  Source: facts.json acceptance_criteria[0], [3]
- SC5: `server_instructions.md` contains explicit retraining rules for container, rewind,
  inventory, CC domain and DCT/engine conflation, plus a "retrain gently" rule for ordinary
  aliases; `discovery` keyword filtering matches raw (legacy) summaries.
  Source: facts.json acceptance_criteria[1]
- SC6: No server name, docstring, confirmation template or instruction guidance uses "AppData",
  "plugin" or "toolkit" as a customer-facing concept, and `vocabulary.txt` translates them in
  relayed prose.
  Source: facts.json acceptance_criteria[2]
- SC7: Relayed "Delphix engine" resolves to a single product only on whole-word evidence,
  otherwise to "Continuous Data or Continuous Compliance engine". Bare relayed "engine" is a
  documented open gap (see Risks) until design decides on a rule.
  Source: facts.json acceptance_criteria[3]
- SC8: `.claude/rules/vocabulary-editorial-guidelines.md` exists, is linked from `CLAUDE.md`,
  and names the tests that fail when a retired term is reintroduced. The dynamic-mode
  `discovery`/`execute` docstrings and elicitation field descriptions are scanned by those
  tests too (**not met on branch**).
  Source: facts.json acceptance_criteria[5]
- SC9: A failure anywhere in the vocabulary layer (lazy import, rule loading, translation) never
  replaces the DCT error a user sees, and a non-UTF-8 or unreadable instructions or vocabulary
  file never stops startup or tool calls (**not met on branch**: GAP-1, GAP-7).
  Source: derived -- G6
- SC10: `/vdbs/search` exposes `filter_expression` among its body fields in `discovery`, and a
  self-referential body-level `$ref` is proven bounded by a test (**bound untested on
  branch**: GAP-5).
  Source: derived -- G7

## Stakeholders

| Stakeholder | Interest |
|-------------|----------|
| dxi-mcp-server maintainers | Vocabulary changes stay config-driven and guarded by regression tests; future additions follow the in-repo checklist |
| Persona-toolset users (scripts, saved prompts, agent configs) | Breaking tool/action renames are documented old-to-new before they upgrade |
| Users of any MCP client connected to the server | Answers use canonical terms; retired terms are corrected; ordinary aliases are understood |
| Server operators | `DCT_SERVER_INSTRUCTIONS` override works; a missing or malformed vocabulary file never blocks startup |

## Constraints

- `FastMCP.instructions` is read-only and captured at construction, so instructions must be
  passed as `FastMCP(instructions=...)` in `main.py`. No FastMCP version bump (`fastmcp>=2.13.2`
  already supports it).
- In `dynamic` mode the server relays the connected DCT's spec and error text. Translation must
  happen at relay time and be **additive** (`message` raw, `message_for_user` rendered).
- Machine identifiers are never rewritten: URLs, `/` and `\` paths, hyphen-, dot- or `@`-joined
  IDs, `code spans` and `{placeholders}`.
- `@log_tool_execution` must preserve MCP error semantics: a raised `DCTClientError` still
  becomes a `CallToolResult` with `isError=True`.
- Code style: Python 3.11+; `get_logger(__name__)`; `DCTClientError`/`MCPError` only; DCT paths
  come from config, never inlined.
- Translation runs on every error and every `discovery` listing: no network calls, no per-call
  file I/O; rules load and compile once (`lru_cache`).
- The canonical column of `vocabulary.txt` is shown to end users via `message_for_user`, so it
  must never contain an instruction to the model.
- Ticket constraints that bind this server: no change to confirmation gating (facts.json
  constraints[1], [3]), no tool annotations (constraints[2]), no API path renames
  (constraints[4]), CC reconciliation limited to retired terms (constraints[0]).

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| GAP-6: Breaking persona-toolset renames (13 rows, e.g. `timeflow_tool` -> `timeline_tool`, `toolkit_tool` -> `connector_schema_tool`) with no aliases break saved scripts and prompts | High (persona-toolset users) | Medium | Old-to-new table in the in-repo `docs/PPM-1129/PPM-1129-agent-ready-api-surface-proposal.md`; default `dynamic` toolset unaffected; design to confirm the no-alias decision |
| GAP-1: A vocabulary-layer exception replaces the real DCT error. `to_canonical()` and its lazy import run with no try/except in `core/decorators.py:_with_message_for_user()` and `tools/core/dynamic.py:_error_response()`; rules load lazily on the first translation and `load_vocabulary_rules()` opens `vocabulary.txt` with no try/except and no `encoding=`, so an unreadable or non-UTF-8 file raises on the first DCT error | Medium | High (user loses the actual error) | Design: wrap import, rule loading and translation; fall back to the raw error with a WARNING log; read with `encoding="utf-8"`; add tests that force each to raise |
| GAP-7: `load_server_instructions()` catches only `OSError` and opens without `encoding=`, so a non-UTF-8 instructions file (or a non-UTF-8 locale) raises `UnicodeDecodeError` at `FastMCP(instructions=...)` construction and stops startup | Low | High (server does not start) | Design: read with `encoding="utf-8"` and also catch `UnicodeDecodeError`; add a test with invalid UTF-8 bytes |
| GAP-2: `discovery`/`execute` docstrings and elicitation `Field(description=...)` text in `tools/core/dynamic.py` are not scanned against `_BANNED` | Medium | Medium | Extend `test_vocabulary_regression.py` (FR-003 AC-4, FR-007 AC-5, FR-011 AC-3) |
| GAP-3: Bare "engine" in relayed DCT text has no `vocabulary.txt` rule and is not in `_BANNED`, so it passes through untranslated | High | Medium | Instruction rule 2 tells the model to qualify it; design to decide whether to add an evidence-gated rule (same signal sets as "Delphix engine") |
| GAP-4: `loader.clear_cache()` clears the vocabulary loaders but not `vocabulary._compiled_rules` or `vocabulary._translate`, so translation keeps stale rules after a reset | Medium | Low | Design: have `clear_cache()` also clear both vocabulary caches (or expose a vocabulary reset); add a test |
| GAP-5: The 5-hop bound on body-level `$ref` resolution in `tools/core/spec_model.py` has no test, and an exhausted bound silently yields zero body fields | Low | Low | Add a self-referential `$ref` test; consider a WARNING log when the bound is hit |
| Translator false positives on words with unrelated meaning (Kubernetes "container", Oracle CDB, "VDB inventory report") | Medium | High | Positive-evidence guards (`only_if_text_mentions=@signals`); corpus test over 7,249 strings; negative cases in `test_vocabulary.py`; never fix a false positive by widening a skip list |
| Ambiguous "Delphix engine" silently resolved to the wrong product | Medium | High | Whole-word evidence plus veto signals; explicit "either" fallback; instruction rule 2 |
| Translation corrupts an identifier needed for support (path, job ID, plugin ID) | Low | High | Protected spans; corpus test asserts byte-identical identifiers; raw message always kept |
| Pre-built tool errors stop reporting `isError` | Low (regressed at 132aae8, fixed at 9079a02; `origin/main` never affected) | High | `_with_message_for_user()` re-raises; `test_decorators_extended.py` fails 4 tests on the regressed revision |
| Model ignores `instructions` (client does not surface them) | Medium | Medium | Defence in depth: names, docstrings, templates and relayed text are canonical regardless |
| `_translate` memo (8192 entries) retains many distinct multi-KB error bodies | Low | Low | Bounded LRU; optionally skip memoizing very large strings |
| `_extract_resource_id` names the wrong resource for paths matching no template (positional fallback) | Medium | Low (confirmation still required) | Known follow-up; only the displayed name is affected |
| `DCT_SERVER_INSTRUCTIONS` points at a missing/unreadable file | Low | Low | `load_server_instructions()` warns and returns `""`; server starts without guidance |
| Everyday-word false positives remain in positive-evidence signal sets outside the corpus | Low | Low | Guideline requires a negative test per new signal word |

## Assumptions

- Spec is reverse-engineered from the branch diff against `origin/main` at `d5f89d6` and PR
  #134's description.
- `server_instructions.md` and `vocabulary.txt` are UTF-8; today the code relies on the system
  locale to decode them (GAP-1, GAP-7).
- Only `DCTClientError` gets a `message_for_user` rendering in pre-built tools; other
  exceptions are re-raised untranslated (scope limit, not a gap).
- Scope is limited to the dxi-mcp-server repository per the user's constraint. Only ticket
  outcomes that are about this server are traced (facts.json acceptance_criteria[0], [1], [2],
  [3], [5]); the others are not part of this spec.
- The `spec_model.py` body-level `$ref` fix (238 operations, including all `/search`
  endpoints, now expose request-body fields) is in scope as a server-side agent-readiness fix,
  though no ticket outcome names it.
- dSource stays the canonical term, as already encoded in `server_instructions.md`.
- This phase does not modify production code.

---
<!-- Cross-reference: Goals G1-G7 map to FR-001..FR-012 in PPM-1129-functional.md (see that file's footer).
     Success Criteria SC1-SC10 map to Acceptance Criteria in those FRs. -->
