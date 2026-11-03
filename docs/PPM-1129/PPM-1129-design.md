# Feature Design: PPM-1129

**Jira**: PPM-1129 (Delphix AI Assistant (GA) - Vocabulary & Domain Model Guidance) -- PR https://github.com/delphix/dxi-mcp-server/pull/134
**Status**: Proposed
<!-- Guidance: H1 title must be exactly "Feature Design: $NAME" (not H2). check-structure.sh does not enforce this mechanically, but downstream review tooling relies on it. -->

**Scope**: dxi-mcp-server only -- `src/dct_mcp_server`, its config files, its tests and in-repo
docs. Nothing outside this repository is designed here.

**Two kinds of content in this document**:

- **As-built (FR-001..FR-012)** -- the vocabulary layer already implemented by hand on branch
  `dlpx/pr/vinay.byrappa/ppm-1129-vocabulary-agent-ready-api` (head `d5f89d6`). Documented so
  validate can check the code against it. No change is designed for these parts.
- **Gap fixes (GAP-1..GAP-7)** -- the server-side gaps from
  `docs/PPM-1129/PPM-1129-functional.md` "Open Server-Side Gaps". These are the only code changes
  the implement phase makes. Each is small and local.

---

## Summary
<!-- Guidance: One paragraph (3–5 sentences). What this feature does, who it is for, why it is being built now. Avoid implementation detail — that belongs in Architecture Changes below.
     Example: Adds a distributed-lock acquisition step to the sync coordinator so concurrent syncs cannot write to the same target schema. The change unblocks scheduled multi-tenant syncs that have been racing on shared schemas. It does not alter the public sync API. -->

The DCT MCP Server is a product voice channel: the words a model reads in tool names, docstrings,
server instructions, confirmation prompts and relayed DCT text are the words it repeats to
customers. PPM-1129 makes every one of those surfaces use canonical Delphix vocabulary (timeline,
VDB Group, connector, Continuous Data / Continuous Compliance engine) through four config-driven
levers: MCP `instructions`, renamed persona-toolset names and docstrings, canonical confirmation
templates, and an additive translator for relayed upstream text, all guarded by regression tests
and an in-repo editorial checklist. Most of this already exists on the branch. This design
documents it and adds hardening so the vocabulary layer can never hide a real DCT error, never
stops startup because of a badly encoded config file, honours `clear_cache()`, and has its
remaining untested surfaces (dynamic-mode docstrings, elicitation text, the `$ref` bound) under
test. It does not change which operations are gated, any DCT API path, or the `dynamic` tool set.

## Affected Components
<!-- Guidance: Render the component checklist from .claude/architecture.md. Tick `[x]` for components this feature changes; leave `[ ]` for the rest. Do not invent components — only those listed in architecture.md may appear here.
     Example:
     - [x] Sync coordinator (src/coordinator/)
     - [x] Lock registry (src/locks/)
     - [ ] Public API (src/api/)
     - [ ] CLI (src/cli/) -->

From the `.claude/architecture.md` layer map. "As-built" = changed on the branch already;
"Gap fix" = changed by the implement phase.

- [x] `main.py` -- entry point; passes `instructions=load_server_instructions()` to `FastMCP(...)` (as-built, FR-001)
- [x] `toolsgenerator/driver.py` -- generated tools render confirmation placeholders (as-built, FR-007)
- [ ] `tools/__init__.py` -- dynamic tool registration (unchanged; loads the renamed modules through `TOOL_TO_MODULE`)
- [ ] `tools/core/meta_tools.py` -- retained spec helpers (not touched)
- [ ] `tools/core/tool_factory.py` -- runtime tool generation (unchanged)
- [x] `tools/core/dynamic.py` -- `discovery`/`execute` translation, elicitation schemas (as-built FR-003/FR-007; gap fix GAP-1)
- [ ] `tools/core/confirmation_token.py` -- not touched
- [ ] `tools/core/confirmation_store.py` -- not touched
- [x] `tools/core/confirmation_levels.py` -- canonical prompt wording (as-built, FR-007)
- [x] `tools/core/confirmation_resolver.py` -- `render_message_template()`, `_resolve_resource_name()` (as-built, FR-007)
- [ ] `tools/core/audit.py` -- not touched
- [ ] `tools/core/floor_operations.py` -- not touched
- [ ] `tools/core/velocity_counter.py` -- not touched
- [x] `tools/*_endpoints_tool.py` -- renamed tools/actions and canonical docstrings (as-built, FR-005/FR-006/FR-009)
- [x] `config/config.py` -- `DCT_SERVER_INSTRUCTIONS` (as-built, FR-001)
- [x] `config/loader.py` -- `load_server_instructions()`, `load_vocabulary_rules()`, `clear_cache()` (as-built FR-001/FR-002; gap fixes GAP-1, GAP-4, GAP-7)
- [x] `config/toolsets/*.txt` -- canonical tool/action names (as-built, FR-005)
- [x] `config/mappings/manual_confirmation.txt` -- canonical templates (as-built, FR-007)
- [ ] `config/mappings/floor_operations.txt` -- not touched
- [ ] `config/mappings/read_exclusions.txt` -- not touched
- [ ] `dct_client/client.py` -- not touched
- [ ] `testing/cli.py` -- not touched
- [ ] `core/logging.py` -- not touched
- [ ] `core/session.py` -- not touched
- [x] `core/decorators.py` -- `_with_message_for_user()` (as-built FR-004; gap fix GAP-1)
- [ ] `core/exceptions.py` -- not touched

Components added by the branch that `.claude/architecture.md` does not list yet (it predates
them; see Open Questions): `config/server_instructions.md`, `config/mappings/vocabulary.txt`,
`tools/core/vocabulary.py`, `tools/core/dynamic_confirmation.py` (keyword-fallback prompt),
`tools/core/spec_model.py` (request-body `$ref` resolution).

## Architecture Changes

Two parts: the as-built vocabulary layer that FR-001..FR-012 describe (no change designed),
then the seven gap fixes that the implement phase makes. All gap fixes are local to
`config/loader.py`, `tools/core/vocabulary.py`, `core/decorators.py`, `tools/core/dynamic.py`,
`tools/core/spec_model.py` and the unit tests; no config format, API path, tool name or
confirmation level changes.

### As-built design (FR-001..FR-012)

The vocabulary layer is four independent levers. Each is config-driven and each fails open (no
lever can stop a tool call or startup once the gap fixes below land).

```
                 +-----------------------------+
 startup ------> | loader.load_server_         |--> FastMCP(instructions=...)      Lever 1 (FR-001, FR-008)
                 | instructions()              |    -> MCP initialize response
                 +-----------------------------+

 persona toolsets: config/toolsets/*.txt + tools/*_endpoints_tool.py           Lever 2 (FR-005, FR-006, FR-009)
   canonical tool/action names, canonical docstrings, one "Customer aliases" line per tool

 confirmation: manual_confirmation.txt -> confirmation_resolver.render_message_template()   Lever 3 (FR-007)
   + elicitation schemas in dynamic.py, keyword-fallback prompt in dynamic_confirmation.py

 relayed text:                                                                Lever 4 (FR-002/003/004/010)
   DCT error body ----> dynamic._error_response()      --+
   DCT error body ----> decorators._with_message_for_user() --+--> vocabulary.to_canonical()
   OpenAPI summary --> dynamic discovery listing/schema --+        |  (rules: loader.load_vocabulary_rules()
   OpenAPI summary --> dynamic_confirmation keyword prompt -+       |   <- config/mappings/vocabulary.txt)
                                                                    v
                                     raw text kept; `message_for_user` added only when differs()
```

| FR | As-built mechanism | Key code |
|----|--------------------|----------|
| FR-001 | `load_server_instructions()` resolves `DCT_SERVER_INSTRUCTIONS` or the packaged `config/server_instructions.md`, returns stripped text (`lru_cache(maxsize=1)`), `""` + WARNING on missing/`OSError`. `main.py` passes it at `FastMCP(...)` construction because `FastMCP.instructions` is read-only afterwards. `config.py` documents the env var. | `config/loader.py:347`, `main.py:69-77` |
| FR-002 | `vocabulary.txt` holds `@signals` sets and `internal|canonical[|guard=...]` rules. `load_vocabulary_rules()` parses, expands `@signal` refs, warns on unknown guards/sets, sorts longest-first (stable). `to_canonical()` -> `_translate()` (`lru_cache(8192)`) applies `_compiled_rules()` (`lru_cache(1)`): whole-word case-insensitive match, protected spans (URLs, `/`/`\` paths, `-`/`.`/`@` IDs, code spans, `{placeholders}`), text-level `only_if`/`skip_if` evidence judged on the original text, word-level guards, casing, overlap merge, a/an fix. | `config/loader.py:404-482`, `tools/core/vocabulary.py` |
| FR-003 | `discovery` shows `to_canonical(summary)` and filters on operationId + raw summary + translated summary; operation schema translates summary/description. `execute` failures go through `_error_response()`, which adds `message_for_user` only when `differs()`. | `tools/core/dynamic.py:1196-1217, 1282-1290, 1414-1415` |
| FR-004 | `@log_tool_execution` catches `DCTClientError`, logs + telemetry, then `_with_message_for_user()` re-raises the same exception (no change) or `type(exc)(raw + "\nmessage_for_user: ...")` from the original. FastMCP turns the raise into `isError: true`. Other exceptions are re-raised untouched. | `core/decorators.py:27-111` |
| FR-005 | Rename table applied to all 5 `config/toolsets/*.txt`, `TOOL_TO_MODULE` in `loader.get_modules_for_toolset()`, and pre-built modules; no aliases (NG5). DCT paths unchanged (NG3). | `config/toolsets/*.txt`, `config/loader.py:710`, `tools/*_endpoints_tool.py` |
| FR-006 | Pre-built docstrings use canonical terms; legacy words appear only on the `Customer aliases (accept as input, never use in answers):` line. | `tools/{dataset,environment,engine,iam,job,misc,policy,reports,template}_endpoints_tool.py` |
| FR-007 | `render_message_template()` substitutes `{name}`/`{days}`/`{count}` and drops the clause of an unresolvable placeholder; `_resolve_resource_name()` falls back to `_extract_resource_id()`. 79 canonical templates. Keyword-fallback prompt translates the OpenAPI summary. Generated tools use the same renderer. Elicitation `Field(description=...)` text is canonical. | `tools/core/confirmation_resolver.py`, `tools/core/confirmation_levels.py`, `tools/core/dynamic_confirmation.py:149`, `toolsgenerator/driver.py`, `tools/core/dynamic.py:81-116` |
| FR-008 | `server_instructions.md` "Additional rules" 1-12 + terminology table (canonical / accept-as-input / never-use-in-output). Instruction-level only; no server-side rewriting of user input (NG6). | `config/server_instructions.md` |
| FR-009 | Rule 1 of the instructions; `toolkit_tool`->`connector_schema_tool`, `*_appdata_*`->`*_connector_*`; AppData/plugin/toolkit rules in `vocabulary.txt`; plugin IDs protected as joined identifiers. | `config/server_instructions.md`, `config/mappings/vocabulary.txt`, toolsets |
| FR-010 | Retired engine names map flatly; "Delphix engine(s)" picks one product only on `@data`/`@compliance` whole-word evidence (contrary evidence vetoes), else the "Continuous Data or Continuous Compliance engine" fallback. Bare "engine": see GAP-3 decision. | `config/mappings/vocabulary.txt:103-129` |
| FR-011 | `.claude/rules/vocabulary-editorial-guidelines.md` (linked from `CLAUDE.md`), `config/CLAUDE.md` vocabulary.txt syntax; `test_vocabulary_regression.py` (`_BANNED`, `_NAME_BANNED`, `_IRREGULAR`, `_NAME_EXCEPTIONS`, `_PROSE_EXCEPTIONS`, inflection-aware `_term_re`, scanner self-tests); `test_vocabulary_spec_corpus.py` over the 7,249-string corpus. | `tests/unit/test_vocabulary_regression.py`, `tests/unit/test_vocabulary_spec_corpus.py` |
| FR-012 | `RequestBody._resolved()` follows a body-level `$ref` so `required`/`content` are read from the target; exposes `filter_expression` for `/search` endpoints. **Correction to the functional spec's "5-hop bound"**: the `for _ in range(5)` loop calls `spec.resolve_ref()`, but `OpenAPISpec` has no `resolve_ref` (only `resolve_pointer`, `:120`, and `resolve_refs`, `:135`), so in production the first pass always falls through to `spec.resolve_refs(raw)`. The real bound is `resolve_refs()`'s cycle detection (`visited`) plus `DEFAULT_MAX_REF_DEPTH = 10` (a nesting-depth limit, not a hop count); a cycle returns a `{"$ref_truncated": True, "reason": "cycle_detected"}` marker, which has no `content`, so zero fields and no exception -- silently, because `_resolved()` discards the `truncated` flag. See GAP-5. | `tools/core/spec_model.py:395-420` |

### Gap-fix design (GAP-1..GAP-7)

**GAP-1 -- the translator must never replace a DCT error (FR-002 AC-8, FR-003 AC-5, FR-004 AC-4; QR-7).**
Defence in depth at three layers, so each layer is independently testable:

1. *Loader* (`config/loader.py:load_vocabulary_rules()`): open with `encoding="utf-8"`, with the
   `try` covering the **whole parse loop** (`with open(...)` through the last `rules.append`),
   because a text-mode `UnicodeDecodeError` is raised while iterating lines, not at `open()`. On
   `(OSError, UnicodeDecodeError)` log
   `WARNING Could not read vocabulary rules <path>: <e>` and return `()` -- the same degradation
   as a missing file. Partially parsed rules are discarded (all-or-nothing), so a file that fails
   halfway never yields a half rule set (`TextIOWrapper` decodes in ~8 KB chunks, so the test
   for this puts more than 8 KB of valid lines before the invalid bytes). `lru_cache` does not cache exceptions, so it is returning
   `()` (rather than raising) that makes the result cached until `clear_cache()`: a broken file
   costs one warning, not one per call.
2. *Translator* (`tools/core/vocabulary.py:to_canonical()`): wrap `_translate(text)` in
   `try/except Exception`; on failure return `text` unchanged. Log the first failure per process
   at WARNING with `exc_info=True`, later ones at DEBUG (module flag `_failure_logged`, reset by
   the GAP-4 cache hook), so a broken rule set cannot flood the log from a 1,000-summary
   `discovery` listing. The flag is a plain module bool; two threads racing on the first failure
   may both log at WARNING, which is harmless (EC-11), so no lock. This makes every caller safe, including the ones the functional spec does
   not list: `discovery` summaries (`dynamic.py:1284, 1414-1415`) and the keyword-fallback prompt
   (`dynamic_confirmation.py:149`).
3. *Error call sites* -- guard the call anyway, because the ACs patch `to_canonical` itself to
   raise and because the decorator's lazy import is outside layer 2:
   - `core/decorators.py:_with_message_for_user()`: add a module-level
     `logger = get_logger(__name__)` (the file today only creates loggers inside the wrappers);
     put the lazy import, `to_canonical()` and
     `differs()` in one `try/except Exception`; on failure log
     `WARNING Vocabulary translation failed; re-raising the original error` and set
     `message_for_user = None` so the function returns the original `exc` (attributes
     `raw_message`, `message_for_user=None`, `http_status` still attached). The caller's existing
     `if error is e: raise` keeps the original traceback and MCP `isError: true`.
   - `tools/core/dynamic.py:_error_response()`: wrap the translate/`differs` pair the same way;
     on failure log a WARNING and return the payload without `message_for_user`.
   - **Patch targets for the tests**: `dynamic.py:46` binds `to_canonical` by name at import, so the
     FR-003 AC-5 test patches `dct_mcp_server.tools.core.dynamic.to_canonical`. The decorator
     imports lazily (`decorators.py:52`), so the FR-004 AC-4 test patches
     `dct_mcp_server.tools.core.vocabulary.to_canonical`. The layer-2 test patches
     `vocabulary._compiled_rules` (inside the guard), not `to_canonical`.
   - Raising from inside the decorator's `except DCTClientError` block would *replace* the error
     (the sibling `except Exception` does not catch it), which is why the guard must live inside
     `_with_message_for_user()` and return `exc`, not raise.
   Catching `Exception` here is deliberate and local (a fallback, not a raise); the project rule
   only forbids *raising* bare `Exception`. `dynamic.py`'s module-level import of `vocabulary`
   stays: a failure there is an import-time bug caught by the test suite, not a runtime path.
4. *Keep CI strict*: layer 2 would otherwise let a translator bug pass the corpus test silently
   (a raising translator returns its input, so "identifiers byte-identical" still holds).
   `tests/unit/test_vocabulary_spec_corpus.py` today calls `to_canonical` (`:31`, `:86`); switch
   those corpus-wide helpers to `vocabulary._translate`, which stays unguarded, so any translator
   exception fails the corpus run. The hand-picked expectation test at `:276` can keep
   `to_canonical` (it asserts exact outputs, so a swallowed exception would still fail it).

Note: `discovery` and `execute` are themselves wrapped in `@log_tool_execution`
(`dynamic.py:216`, `:325`), contrary to `.claude/rules/code-style.md`. This is pre-existing and not
changed here; it means a `DCTClientError` escaping either dynamic tool also passes through
`_with_message_for_user()`, which the GAP-1 guard covers.

**GAP-2 -- scan dynamic-mode docstrings and elicitation text (FR-003 AC-4, FR-007 AC-5, FR-011 AC-3; QR-3).**
Test-only change in `tests/unit/test_vocabulary_regression.py`. Add a prose source that reads
what the model actually receives, not the source text:

- `_dynamic_tool_prose()`: call `register_dynamic_tools()` with a `MagicMock` app (the pattern in
  `tests/unit/test_dynamic.py::test_register_dynamic_tools_registers_two_tools`). `app.add_tool`
  receives plain functions (`dynamic.py:180`, `:183`), not tool objects, so build
  `mcp.server.fastmcp.tools.Tool.from_function(fn, name=<name>)` for each recorded call and yield
  each line of `.description` plus any `description` in `.parameters` (today the parameters carry
  none, so the docstring is the whole surface; the parameter walk guards future
  `Field(description=...)` additions).
- `_elicitation_prose()`: for `_StandardConfirmationSchema`, `_ElevatedConfirmationSchema` and
  `_ManualConfirmationSchema`, walk `model_json_schema()` and yield every `description` (pydantic
  puts the class docstring and each `Field(description=...)` there).
- Both pass through the existing `_IDENTIFIER_RE` strip, `_PROSE_EXCEPTIONS`, and `_ALIAS_LINE`
  exemption, then are checked against every `_BANNED` term with `_term_re`, and against an
  unqualified "engine" (same check as `test_engine_is_always_qualified_in_confirmation_messages`).
- Self-tests that prove each scanner can fail. Mutating `_RESOURCE_NAME_FIELD.description` after
  import does **not** work (pydantic copies the field into `model_fields`, so
  `model_json_schema()` keeps the original text). Instead: (a) define a throwaway `BaseModel`
  subclass in the test with `Field(description="Type the timeflows name")` and feed it to the same
  schema-walking helper; (b) feed the tool-prose helper a throwaway function whose docstring
  contains "timeflows". Both must be reported. The helpers therefore take the schema classes /
  functions as parameters rather than hard-coding them.

No production change is expected: a grep of `dynamic.py` finds banned words only in comments and
in the identifier `x-dct-toolkit-credential-field`. If the new test finds a hit, fix the wording
in `dynamic.py`, not the scanner.

**GAP-3 -- bare relayed "engine" (FR-010 AC-4). Decision: no `vocabulary.txt` rule; instruction rule 2 is the accepted mitigation, pinned by tests.**
Reasons: (a) in DCT text "engine" is a real, legitimate DCT object (registered engines,
`engine_tool`, `/management/engines`) and usually already qualified or named nearby ("engine
'cd-01'"), so the editorial guideline's "translate on positive evidence only" bar is rarely met
by the word itself; (b) an evidence-gated rule would rewrite "the engine" to "the Continuous Data
engine" inside text that already says "Continuous Data engine" elsewhere, adding no information
while risking a wrong product on mixed text; (c) the server never *authors* a bare "engine" --
confirmation templates are already checked by
`test_engine_is_always_qualified_in_confirmation_messages`, and GAP-2 extends that to dynamic
text. Tests pin the decision: bare "engine" in relayed text is returned unchanged, "Continuous
Data engine" is never doubled, and "Delphix engine" next to a bare "engine" still resolves per
FR-010. If reviewers reverse this, the fallback design is two lines reusing `@data`/`@compliance`
with **no** unconditional fallback line, plus the same tests flipped.

**GAP-4 -- `clear_cache()` must reset the translator (FR-002 AC-6; QR-9).**
`config/loader.py` gains a small hook registry: `_CACHE_CLEAR_HOOKS: list[Callable[[], None]]`
and `register_cache_clear_hook(fn)`. `clear_cache()` clears its own caches, then calls each hook.
`tools/core/vocabulary.py` registers one hook at import, after `_compiled_rules` and `_translate`
are defined, that calls both `cache_clear()`s and resets `_failure_logged`. The hook captures the
real cached function objects at definition time (not module-attribute lookups), so a test that
monkeypatches `_compiled_rules` with a plain function cannot make `clear_cache()` raise
`AttributeError`. `clear_cache()` also wraps each hook call in `try/except Exception` with a
WARNING, so one bad hook never stops the others. Order matters and is
guaranteed: loader caches are cleared first, so the next `_compiled_rules()` reloads the file.
Rejected alternatives are in the table below (lazy import of `vocabulary` from `loader` breaks the
config -> tools layering and risks a circular import through `tools/core/__init__`).

**GAP-5 -- make the real `$ref` bound visible and tested (FR-012 AC-2).**
Design review found the as-built 5-hop loop is unreachable: `OpenAPISpec` has no `resolve_ref`, so
production always takes the `spec.resolve_refs(raw)` path (see the FR-012 row above). A
`for ... else` WARNING on that loop would never fire in production, and a test built on a stub
spec that defines `resolve_ref` would prove nothing. The fix therefore targets the path that runs:

1. In `RequestBody._resolved()` (`tools/core/spec_model.py:397-420`), remove the dead
   `resolve_ref` loop and resolve a body-level `$ref` with
   `resolved, truncated = self.spec.resolve_refs(raw)` only. Behaviour for real specs is unchanged
   (this is the branch that already runs).
2. Inspect only the **top level** of the result: if `resolved.get("$ref_truncated")` or
   `resolved.get("code") == "SCHEMA_REF_NOT_FOUND"` (the body-level ref itself was a cycle,
   too deep, or dangling), return `{}` and log
   `WARNING Request body $ref <ref> could not be resolved (<reason>); exposing no body fields`.
3. `_resolved()` runs on every `required`/`content` access, i.e. several times per operation per
   `discovery` call, so the WARNING is emitted once per distinct ref per process: a module-level
   `_WARNED_BODY_REFS: set[str]` guards it (a race may log twice; harmless). The set is not tied to
   `clear_cache()` because the spec, not config, determines it.
4. Do **not** use the `truncated` flag. `resolve_refs()` inlines the whole body, and its `depth`
   increases per dict/list nesting level (`spec_model.py:174-197`), not per `$ref` hop, so
   `truncated=True` also means "some deeply nested schema was cut off". Second design review ran
   it on the live DCT spec: 84 of 239 `$ref` request bodies come back `truncated=True` (all
   `max_depth_exceeded`, none cycles) and 82 of them expose real fields today (e.g.
   `POST /access-groups/{accessGroupId}/tags/delete` -> `key`, `tags`, `value`). Rejecting on
   the flag would wipe those fields and log 84 false warnings.
5. The bound itself is `resolve_refs()`'s existing cycle detection (`visited`) plus
   `DEFAULT_MAX_REF_DEPTH = 10`, a **nesting-depth** limit -- no new constant.

Tests (all on a real `OpenAPISpec`, never a stub with `resolve_ref`): a self-referential
`components/requestBodies/A -> A` yields zero fields, no exception, exactly one WARNING across
repeated `required`/`content`/`fields()` access; a two-hop `A -> B -> body` chain resolves with
no WARNING; a dangling ref yields zero fields and one WARNING; a `$ref` body whose schema nests
more than 10 levels deep still exposes its top-level fields and logs no WARNING (regression
guard for step 4). The functional spec's "5 hops"
wording (FR-012 Processing step 1, AC-2, EC-10) should read "cycle detection / nesting depth
10"; the
validate phase checks the code against this design.

**GAP-6 -- breaking persona-toolset renames (FR-005 AC-4; QR-2). Decision: keep no aliases (NG5).**
An alias would keep the retired word in the tool list the model reads, which is exactly the
surface PPM-1129 cleans up; the default `dynamic` toolset is unaffected. The migration path is the
old-to-new table in `docs/PPM-1129/PPM-1129-agent-ready-api-surface-proposal.md`. Add a unit test
that diffs the names: a hard-coded `_RENAMES` list (the FR-005 table) where every new name must
be registered in some toolset, no old name may be, and every old->new pair must appear in the
proposal doc. The PR description (pr phase) must carry a "Breaking changes" section with the
same table.

**GAP-7 -- non-UTF-8 instructions must not stop startup (FR-001 AC-5; QR-9).**
In `load_server_instructions()`: `open(instructions_file, "r", encoding="utf-8")` and catch
`(OSError, UnicodeDecodeError)` with the existing WARNING + `""`. Explicit `encoding` also removes
the dependency on the host locale (a UTF-8 file on a `C`/`latin-1` locale is read correctly).
`main.py` needs no change: it already passes whatever the loader returns.

### Schema / Config Changes
<!-- Guidance: Every change to schema files, config formats, or persisted state shapes. Include the field path, type, sensitivity flag (if a credential), and which object it lives under. If your project has no schema layer, write "None."
     Example:
     | Field | Type | Object | Notes |
     |-------|------|--------|-------|
     | `lock.timeoutMs` | integer | SyncJob | New optional field, default 30000 |
     | `lock.caller`    | string  | SyncJob | Required when lock.timeoutMs is set | -->

| Field | Type | Object | Notes |
|-------|------|--------|-------|
| `DCT_SERVER_INSTRUCTIONS` | env var, string path | process env (`config/config.py`) | As-built. Optional; whitespace-only = unset. Not sensitive. GAP-7 makes the file explicitly UTF-8. |
| `config/server_instructions.md` | Markdown text, UTF-8 | packaged config | As-built. Sent as MCP `instructions`. |
| `config/mappings/vocabulary.txt` | line format `@signals name=w,...` / `internal|canonical[|guard=w,...]` | packaged config | As-built (38 rules, 3 signal sets). GAP-1 makes it explicitly UTF-8. No format change. |
| `config/mappings/manual_confirmation.txt` | `METHOD|path|level|message` | packaged config | As-built: wording and `{name}`/`{days}`/`{count}` placeholders only; methods, paths and levels unchanged (NG1). |
| `config/toolsets/*.txt` | `METHOD|/path|action` | packaged config | As-built: tool/action renames per FR-005; paths unchanged (NG3). |
| `message_for_user` | string, optional | `execute` error payload; `DCTClientError.message_for_user` attribute and appended text line | As-built. Present only when translation changed the raw message. GAP-1 guarantees it is omitted (never an exception) when translation fails. |

No persisted state, no migration.

### Source Files to Modify
<!-- Guidance: One row per file. The path must exist in the repo (check-structure.sh cross-references these rows against git status during the implement phase). Group by component. The "Purpose" column says what changes in that file.
     Example:
     | File | Purpose | Maps to FR |
     |------|---------|------------|
     | src/coordinator/sync.py | Call lock.acquire() before sync begins; release on success/failure | FR-001, FR-003 |
     | src/locks/registry.py | New file — lock registry with TTL-based expiry | FR-001, FR-002 |
     | src/api/schemas.py | Add lock.timeoutMs and lock.caller to SyncJob schema | FR-002 | -->

"As-built" rows are already changed on the branch (in `git diff origin/main`) and are listed so
validate's scope check accepts them; the implement phase does not touch them unless a gap row on
the same file says so.

| File | Purpose | Maps to FR |
|------|---------|------------|
| `src/dct_mcp_server/config/loader.py` | As-built: `load_server_instructions()`, `load_vocabulary_rules()`, `load_vocabulary_map()`, `TOOL_TO_MODULE` renames. **Gap fix**: UTF-8 + `(OSError, UnicodeDecodeError)` fallback in both loaders (GAP-1, GAP-7); `register_cache_clear_hook()` + hook loop in `clear_cache()` (GAP-4) | FR-001, FR-002, FR-005 |
| `src/dct_mcp_server/tools/core/vocabulary.py` | As-built translator. **Gap fix**: `to_canonical()` returns input on any translation exception, rate-limited WARNING (GAP-1); register cache-clear hook for `_compiled_rules`/`_translate` (GAP-4) | FR-002, FR-003, FR-007, FR-009, FR-010 |
| `src/dct_mcp_server/core/decorators.py` | As-built `_with_message_for_user()`. **Gap fix**: guard lazy import + translation; on failure re-raise the original `DCTClientError` with a WARNING (GAP-1) | FR-004 |
| `src/dct_mcp_server/tools/core/dynamic.py` | As-built: discovery/execute translation, canonical docstrings and elicitation schemas. **Gap fix**: guard translation in `_error_response()` (GAP-1). Wording fix only if the GAP-2 scan finds a hit | FR-003, FR-007, FR-011 |
| `src/dct_mcp_server/tools/core/spec_model.py` | As-built body-level `$ref` handling. **Gap fix**: drop the unreachable `resolve_ref` loop; return `{}` with a once-per-ref WARNING only when the top level of `resolve_refs()`'s result is a truncation/not-found marker (never on the nested `truncated` flag) (GAP-5) | FR-012 |
| `src/dct_mcp_server/main.py` | As-built: `FastMCP(instructions=load_server_instructions())`. No gap change | FR-001 |
| `src/dct_mcp_server/config/config.py` | As-built: `DCT_SERVER_INSTRUCTIONS` in config + `print_config_help()`. No gap change | FR-001 |
| `src/dct_mcp_server/config/server_instructions.md` | As-built domain model, terminology table, rules 1-12. No gap change (GAP-3 decision relies on rule 2 as written) | FR-001, FR-008, FR-009, FR-010 |
| `src/dct_mcp_server/config/mappings/vocabulary.txt` | As-built rule set. No gap change (GAP-3 decision: no bare-"engine" rule) | FR-002, FR-009, FR-010 |
| `src/dct_mcp_server/config/mappings/manual_confirmation.txt` | As-built canonical templates and placeholders. No gap change | FR-007 |
| `src/dct_mcp_server/config/toolsets/continuous_data_admin.txt` | As-built renames. No gap change | FR-005, FR-009 |
| `src/dct_mcp_server/config/toolsets/platform_admin.txt` | As-built renames. No gap change | FR-005, FR-009 |
| `src/dct_mcp_server/config/toolsets/self_service.txt` | As-built renames. No gap change | FR-005 |
| `src/dct_mcp_server/config/toolsets/self_service_provision.txt` | As-built renames. No gap change | FR-005 |
| `src/dct_mcp_server/config/toolsets/reporting_insights.txt` | As-built renames. No gap change | FR-005 |
| `src/dct_mcp_server/tools/dataset_endpoints_tool.py` | As-built renames + canonical docstrings + alias lines. No gap change | FR-005, FR-006, FR-009 |
| `src/dct_mcp_server/tools/environment_endpoints_tool.py` | As-built canonical docstrings. No gap change | FR-006 |
| `src/dct_mcp_server/tools/engine_endpoints_tool.py` | As-built canonical docstrings (engine always qualified). No gap change | FR-006, FR-010 |
| `src/dct_mcp_server/tools/template_endpoints_tool.py` | As-built `vdb_template_tool` rename + docstrings. No gap change | FR-005, FR-006 |
| `src/dct_mcp_server/tools/iam_endpoints_tool.py` | As-built canonical docstrings. No gap change | FR-006 |
| `src/dct_mcp_server/tools/job_endpoints_tool.py` | As-built canonical docstrings. No gap change | FR-006 |
| `src/dct_mcp_server/tools/misc_endpoints_tool.py` | As-built renames + canonical docstrings. No gap change | FR-005, FR-006, FR-009 |
| `src/dct_mcp_server/tools/policy_endpoints_tool.py` | As-built canonical docstrings. No gap change | FR-006 |
| `src/dct_mcp_server/tools/reports_endpoints_tool.py` | As-built canonical docstrings. No gap change | FR-006 |
| `src/dct_mcp_server/config/__init__.py` | As-built export of the vocabulary/instructions loaders. No gap change | FR-001, FR-002 |
| `src/dct_mcp_server/tools/core/confirmation_resolver.py` | As-built `render_message_template()` / `_resolve_resource_name()`. No gap change | FR-007 |
| `src/dct_mcp_server/tools/core/confirmation_levels.py` | As-built canonical prompt wording. No gap change | FR-007 |
| `src/dct_mcp_server/tools/core/dynamic_confirmation.py` | As-built keyword-fallback prompt via `to_canonical()`; protected by GAP-1 layer 2 without a local change | FR-007 |
| `src/dct_mcp_server/toolsgenerator/driver.py` | As-built placeholder rendering for generated tools. No gap change | FR-007 |
| `.claude/rules/vocabulary-editorial-guidelines.md` | As-built checklist. **Gap fix**: name the new GAP-2 dynamic/elicitation scan in "After making the change" step 1 | FR-011 |
| `src/dct_mcp_server/config/CLAUDE.md` | As-built vocabulary.txt syntax. **Gap fix**: one line stating the file is read as UTF-8 and an unreadable file degrades to no translation | FR-002, FR-011 |
| `CLAUDE.md` | As-built link to the editorial guideline. No gap change | FR-011 |
| `docs/PPM-1129/PPM-1129-agent-ready-api-surface-proposal.md` | As-built old-to-new rename table. **Gap fix**: verify every FR-005 pair is present (GAP-6 test enforces) | FR-005 |
| `tests/unit/test_vocabulary.py` | As-built FR-001/002/003/012 tests. **Gap fix**: add GAP-1 loader/translator, GAP-3 bare-engine, GAP-4 cache, GAP-5 `$ref` bound, GAP-7 encoding tests | FR-001, FR-002, FR-003, FR-010, FR-012 |
| `tests/unit/test_vocabulary_regression.py` | As-built scanners. **Gap fix**: dynamic tool + elicitation prose scan and self-test (GAP-2); rename-table test (GAP-6) | FR-003, FR-005, FR-006, FR-007, FR-009, FR-011 |
| `tests/unit/test_vocabulary_spec_corpus.py` | As-built corpus test. **Gap fix**: translate through the unguarded `vocabulary._translate` so a translator exception still fails CI after GAP-1 layer 2 | FR-002, FR-010 |
| `tests/unit/test_decorators_extended.py` | As-built `isError` + translation tests. **Gap fix**: sync and async "translation raises" tests (GAP-1) | FR-004 |
| `tests/unit/test_dynamic.py` | As-built error-payload tests. **Gap fix**: `_error_response()` "translation raises" test (GAP-1) | FR-003 |
| `tests/unit/test_loader_extended.py` | Unchanged on the branch (existing `clear_cache()` smoke test). **Gap fix**: hook-registry tests (GAP-4) | FR-002 |
| `tests/unit/test_dynamic_confirmation.py` | Unchanged on the branch. **Gap fix**: keyword-fallback prompt uses the canonical summary, and survives a raising translator (FR-007 AC-6, GAP-1) | FR-007 |
| `tests/unit/test_driver.py` | Unchanged on the branch. **Gap fix**: generated-tool confirmation renders placeholders (FR-007 AC-4) | FR-007 |
| `tests/functional/workflows/test_timeline.py` | As-built (renamed from `test_timeflow.py`). No gap change | FR-005 |
| `tests/functional/workflows/test_cda_workflows.py` | As-built: renamed tool/action names. No gap change | FR-005 |
| `tests/functional/workflows/test_snapshot.py` | As-built: renamed action names. No gap change | FR-005 |
| `tests/functional/test_registration.py` | As-built: renamed tools registered; dynamic still `discovery` + `execute`. No gap change | FR-005 |
| `tests/functional/test_confirmation_handshake.py` | As-built: canonical confirmation messages. No gap change | FR-007 |
| `tests/integration/test_host_approval_levels.py` | As-built: canonical confirmation/elicitation wording. No gap change | FR-007 |
| `tests/e2e/test_smoke.py` | As-built: renamed tool names (real-DCT marker; not in CI layer). No gap change | FR-005 |
| `tests/unit/test_main.py` | As-built: `FastMCP` receives `instructions`. No gap change | FR-001 |
| `tests/unit/test_config.py` | As-built: `DCT_SERVER_INSTRUCTIONS` config. No gap change | FR-001 |
| `tests/unit/test_config_extended.py` | As-built: `print_config_help()` lists `DCT_SERVER_INSTRUCTIONS`. No gap change | FR-001 |
| `tests/fixtures/dct_api_text_corpus.json.gz` | As-built 7,249-string DCT API text corpus. No gap change | FR-002, FR-010 |
| `tests/test_spec_model.py` | Pre-existing test file extended with GAP-5 tests: `test_request_body_resolved_uses_resolve_refs_not_resolve_ref`, `test_request_body_resolved_warns_once_for_missing_ref`, `test_request_body_resolved_warns_once_for_same_ref`, `test_request_body_resolved_inline_body_returns_content`. Scope expansion recorded at validate phase. | FR-012 |
| `.claude/rules/build-and-execution.md` | As-built: documents `DCT_SERVER_INSTRUCTIONS`. No gap change | FR-001 |

### New Files (if any)
<!-- Guidance: Path + one-line purpose. check-structure.sh does not cross-reference this list mechanically — it is purely for review readability. If no new files, write "None."
     Example:
     - `src/locks/registry.py` — TTL-backed distributed lock registry -->

None. (All gap-fix tests go into the existing test modules listed above, matching the
`tests/unit/` CI layout rather than a new `tests/PPM-1129-test.py`; see Open Questions on
`.claude/test/testing.md`.)

### Alternatives Considered
<!-- Guidance: One row per rejected approach: the option, its trade-off, and why it was rejected in favor of the chosen design above. This is not a place to re-argue the chosen design — just record what else was on the table and why it lost. If nothing substantive was considered and rejected, write "None."
     Example:
     | Option | Trade-off | Why rejected |
     |--------|-----------|---------------|
     | In-process mutex (no shared lock registry) | Simpler, no new storage; but only works within a single process | Scheduled syncs run as separate processes/pods, so an in-process mutex can't prevent cross-process races |
     | Advisory DB lock (e.g. `pg_advisory_lock`) | No new component; piggybacks on existing DB connection | Ties lock lifetime to a DB session that can silently drop, leaving the schema un-lockable until the session times out |
     | Distributed lock registry (chosen) | Requires a new small service + TTL expiry logic | Survives process crashes via TTL, and works across both pods and ad-hoc CLI runs | -->

| Option | Trade-off | Why rejected |
|--------|-----------|---------------|
| GAP-1: guard only the two error call sites (decorator, `_error_response`) | Smallest diff | Leaves `discovery` listings and the keyword-fallback confirmation prompt able to raise on a broken rule set; a confirmation prompt that raises blocks a gated operation |
| GAP-1: guard only inside `to_canonical()` | One place to maintain | The decorator's lazy import is outside it, and the FR ACs patch `to_canonical` itself to raise; call-site guards are what make those ACs testable |
| GAP-1: new `safe_to_canonical()` wrapper beside `to_canonical()` | Keeps `to_canonical()` strict for tests | Two functions that differ only in safety invite the unsafe one being used at the next call site |
| GAP-3: evidence-gated bare-"engine" rules reusing `@data`/`@compliance` | Qualifies more relayed text | "engine" is a legitimate DCT object name; rewrites mostly add a product name the text already states, and mixed text risks naming the wrong product. Kept as the documented fallback if reviewers reverse the decision |
| GAP-3: add "engine" to `_BANNED` | Strongest guard | Would ban `engine_tool` and the DCT "Engines" concept; the existing qualified-engine check covers server-authored text |
| GAP-4: `clear_cache()` lazily imports `tools.core.vocabulary` | No registry | Config layer reaching into tools layer; importing `tools.core` runs its `__init__` and risks circular imports during startup |
| GAP-4: drop `lru_cache` on `_compiled_rules`/`_translate` | No staleness at all | Re-compiles 38 regexes and re-translates up to ~1,044 summaries per `discovery` call; violates the no-per-call-cost constraint (QR-13) |
| GAP-6: keep deprecated aliases for one release | Saved scripts keep working | Alias names keep the retired word in the tool list the model reads (NG5); the default `dynamic` toolset is unaffected anyway |
| GAP-7: read with `errors="replace"` instead of catching | Startup always gets some text | Sends mojibake to the model as authoritative guidance; empty instructions plus a WARNING is the documented safe state |

## Version Compatibility
<!-- Guidance: Pull the version table from .claude/architecture.md and mark whether this feature requires branching per version. "Branch?" = Yes if code path differs by version, No if behavior is identical.
     Example:
     | Version | Supported? | Branch? | Notes |
     |---------|-----------|---------|-------|
     | v1.x | Yes | Yes | No lock API — falls back to mutex-per-process behavior |
     | v2.0+ | Yes | No  | Native lock API available | -->

| Version | Supported? | Branch? | Notes |
|---------|-----------|---------|-------|
| Python 3.11 | Yes | No | `requires-python = ">=3.11"`; CI matrix. `str | None`, `re` features used are 3.11-safe |
| Python 3.12 | Yes | No | CI matrix (`.github/workflows/ci.yml`) |
| mcp >=1.28.1,<2 (`mcp.server.fastmcp.FastMCP`, used by `main.py:32`, `dynamic.py:23`) | Yes | No | `FastMCP(instructions=...)` and `Tool.from_function()` (GAP-2 test) available across the range; no version bump |
| fastmcp >=2.13.2,<4 | Yes | No | Declared dependency; not the `FastMCP` class this server constructs. No change |
| pydantic 2.x (locked 2.12.4) | Yes | No | `model_json_schema()` includes the class docstring and `Field(description=...)` (GAP-2 test) |
| DCT 2026.x (7,249-string corpus fixture `tests/fixtures/dct_api_text_corpus.json.gz`; the source spec is not in the repo) | Yes | No | Translation is text-driven, not version-driven: any DCT spec/error text passes through the same rules. Corpus fixture regenerates per spec |
| Older/newer DCT specs (dynamic mode, downloaded at startup) | Yes | No | Unknown terms pass through unchanged; `$ref` resolution unchanged apart from the GAP-5 log line |
| Persona toolsets from before PPM-1129 (client scripts using old names) | No | No | Breaking by design (GAP-6/NG5); migration via the rename table |
| Host locale non-UTF-8 (e.g. a latin-1 locale with `PYTHONUTF8=0`; note `C`/POSIX is coerced to UTF-8 by Python 3.7+) | Yes | No | After GAP-1/GAP-7 both config files are read as UTF-8 regardless of locale |

## Platform Behavior Notes
<!-- Guidance: Flag each "Non-Obvious Platform Behavior" from CLAUDE.md / architecture.md that this feature interacts with. Mark each as "Affects" (this feature must respect the behavior) or "N/A" (unrelated). Do not delete behaviors that are N/A — leave them in the list so reviewers know they were considered.
     Example:
     - Stale-lock cleanup runs every 60s — Affects: TTL must be > 60s to avoid premature reclaim
     - Coordinator restart drops in-memory state — N/A (lock registry is persistent) -->

- `FastMCP.instructions` is read-only after construction -- Affects: instructions must be loaded
  at module import in `main.py`; a loader exception there stops startup, hence GAP-7.
- Toolset config cache: `loader.py` uses `@lru_cache`, `clear_cache()` resets it -- Affects:
  vocabulary caches live in another module and must be reset too (GAP-4).
- FastMCP turns a raised tool exception into `CallToolResult(isError=True)` -- Affects: the
  decorator must always raise, including when translation fails (FR-004, GAP-1).
- `tools.core` imports `log_tool_execution` at package init -- Affects: `decorators.py` must keep
  the lazy `vocabulary` import (circular otherwise); GAP-1 guards it rather than moving it.
- Generated tools in `$TEMP/dct_mcp_tools/` take priority over pre-built modules -- Affects:
  generated tools must render confirmation placeholders like pre-built ones (FR-007 AC-4,
  as-built in `driver.py`). Generated tool docstrings come from the DCT spec and are not covered
  by the GAP-2 scan (see Open Questions).
- `DCT_TOOLSET` defaults to `dynamic` -- Affects: most user-visible text is relayed, so the
  translator (FR-002/003) and the instructions (FR-001) are the main levers; renames (FR-005)
  only reach persona-toolset users.
- API key `apk ` prefix, SSL default `verify=false`, retry/backoff -- N/A.
- Confirmation hardening (single-use tokens, floor operations, grants, velocity, audit) -- N/A:
  only message wording and placeholder rendering change (NG1).
- Telemetry opt-in / session logs -- N/A: `@log_tool_execution` telemetry is recorded before
  translation and is unchanged.

## Open Questions / Risks
<!-- Guidance: One bullet per item. Format: "Q: <question> — Owner: <name or TBD>" or "R: <risk> — Mitigation: <action>". Keep blocking items at the top.
     Example:
     - Q: Should lock holders be allowed to extend TTL mid-sync? — Owner: TBD
     - R: Lock registry becomes a single point of failure — Mitigation: replicate registry across 3 nodes, document failover -->

None of the items below blocks implementation; each has a decided default.

- Q (non-blocking, decided): GAP-3 -- confirm "no bare-engine rule; instruction rule 2 is the
  mitigation" with the vocabulary design reviewers. Default if unanswered: ship the decision with
  the pinning tests. -- Owner: Jake Smith / Brian Deverter
- Q (non-blocking, decided): GAP-6 -- confirm no aliases for persona renames. Default: no aliases
  (NG5), rename table + PR "Breaking changes" section. -- Owner: Vinay Byrappa
- Q (non-blocking): Generated tools in `$TEMP/dct_mcp_tools/` take their docstrings from the DCT
  spec; they are not scanned by GAP-2 and their summaries are not passed through `to_canonical()`.
  Out of scope for this PR (relayed spec text, not server-authored); candidate follow-up. --
  Owner: TBD
- Q (non-blocking): `.claude/test/testing.md` and `.claude/architecture.md` predate the vocabulary
  layer. testing.md describes live-DCT tests named `tests/<ticket>-test.py` and does not describe
  the `tests/unit` CI layer (`dct-mcp-test --layer ci`) this plan uses; architecture.md does not
  list `vocabulary.py`, `dynamic_confirmation.py`, `spec_model.py`, `server_instructions.md` or
  `vocabulary.txt`. testing.md may be stale -- review before test phase. -- Owner: Vinay Byrappa
- R: The GAP-1 `except Exception` hides a real translator bug in production. -- Mitigation: first
  failure logged at WARNING with traceback; the corpus test is switched to the unguarded
  `vocabulary._translate` (GAP-1 layer 4) so a translator bug still fails CI.
- R: The functional spec describes FR-012's bound as "5 hops", which the code never executes. --
  Mitigation: GAP-5 redesign above; validate checks against this design, and the functional
  wording is corrected when the specs are next touched.
- R: GAP-2 scan finds a wording hit in `dynamic.py` docstrings. -- Mitigation: fix the wording;
  never widen `_PROSE_EXCEPTIONS` for a retired meaning (editorial guideline step 6).
- R: GAP-4 hook registered twice if `vocabulary` is re-imported (e.g. `importlib.reload` in a
  test). -- Mitigation: `register_cache_clear_hook()` **replaces** a hook with the same qualified
  name (so a reload never leaves a stale hook pointing at the old caches), and clearing is
  idempotent anyway.
- R: `_translate` memo retains up to 8192 distinct multi-KB error bodies. -- Mitigation: bounded
  LRU (as-built); optional follow-up to skip memoizing strings over a size cap.
- R: `_extract_resource_id` names the wrong resource for paths matching no template (ERR-5). --
  Mitigation: confirmation still required; follow-up outside this PR.
- R: Model ignores `instructions` when a client does not surface them. -- Mitigation: names,
  docstrings, templates and relayed text are canonical independently (defence in depth).
- R: Persona-toolset users hit "unknown tool/action" after upgrade (ERR-6). -- Mitigation: rename
  table, PR breaking-changes section; pin the previous server version to roll back.
## Acceptance Criteria
<!-- Guidance: Pull directly from the Jira ticket "Acceptance Criteria" section if present, else derive from vision-doc Goals. Each AC must be testable and map to at least one FR-* in functional.md.
     Example:
     - [ ] AC-1: A second sync attempt on a locked schema is rejected within 100ms
     - [ ] AC-2: A lock held by a crashed coordinator is reclaimed within (TTL + 60s) -->

Server-affecting ticket outcomes (facts.json `acceptance_criteria` ac-1, ac-2, ac-3, ac-4, ac-6)
plus the derived robustness goals G6/G7. Ticket ac-5 (BYO AI notice) and ac-7 (post-GA docs page)
are outside this repository's scope per the user's constraint.

- [ ] AC-1 (ticket ac-1): MCP Server responses consistently use canonical Delphix terminology --
      instructions, persona names, pre-built and dynamic docstrings, confirmation and elicitation
      text, and relayed DCT text carry no `_BANNED` term outside alias lines and protected
      identifiers. FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007.
- [ ] AC-2 (ticket ac-2): Legacy terms are understood and answered canonically with retraining
      notes for retired/confusable terms; `discovery` keyword search still matches legacy terms.
      FR-003, FR-008.
- [ ] AC-3 (ticket ac-3): The native vs. AppData connector split is not exposed: no
      AppData/plugin/toolkit in names, docstrings or translated prose; plugin IDs untouched.
      FR-009.
- [ ] AC-4 (ticket ac-4): Engine/DCT/product conflation is addressed: "Delphix engine" names one
      product only on evidence, else the explicit "either" phrase; retired engine names map;
      server-authored text never uses an unqualified "engine"; bare relayed "engine" behaviour is
      the GAP-3 decision, pinned by tests. FR-010.
- [ ] AC-5 (ticket ac-6): Editorial guideline in repo, linked from `CLAUDE.md`, and regression
      tests fail when a retired term returns in any controlled surface, including dynamic-mode
      docstrings and elicitation text (GAP-2). FR-011.
- [ ] AC-6 (derived G6): A failure in vocabulary import, rule loading or translation never
      replaces the DCT error (execute payload keeps `message`/`http_status`; pre-built tools
      re-raise the original `DCTClientError` with `isError: true`); a non-UTF-8 or unreadable
      `server_instructions.md`/`vocabulary.txt` never stops startup or a tool call;
      `clear_cache()` resets the translator. FR-001, FR-002, FR-003, FR-004 (GAP-1, GAP-4, GAP-7).
- [ ] AC-7 (derived G7): `$ref`-defined request bodies expose their fields (`filter_expression` on
      `/vdbs/search`), and a self-referential or dangling `$ref` yields zero fields, no exception
      and one WARNING per ref, while bodies with deeply nested schemas keep their top-level
      fields (bound = `resolve_refs()` cycle detection / nesting depth 10). FR-012 (GAP-5).
- [ ] AC-8 (derived, migration): Every FR-005 rename appears old-to-new in the proposal doc and
      the PR description; no old name is registered. FR-005 (GAP-6).
- [ ] AC-9 (QR-10): Full suite green -- `pytest tests/ -m "not real_dct and not llm_driven and not
      scenario"` with 0 failures, plus `pre-commit run --all-files` clean.

---
<!-- Cross-references checked by check-structure.sh during the design phase:
     - Every FR-* in docs/$NAME/$NAME-functional.md → at least one row in ### Source Files to Modify
     - Non-Goals in docs/$NAME/$NAME-vision.md → MUST NOT appear in Architecture Changes (hard constraint)
     - Every AC → at least one FR-* in functional.md (transitive via FR mapping)
     Run: .claude/evals/check-structure.sh $NAME --step design -->
