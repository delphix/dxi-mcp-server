# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Config Directory

This directory is the primary place to make changes without touching Python code.

### Toolset Files (`toolsets/*.txt`)

Define which DCT API endpoints belong to each persona toolset.

**Format:**
```
# Toolset Name - N Tools
# Description: <human-readable toolset description>
# Target users: <intended persona>

# TOOL N: tool_name - Tool Description
METHOD|/endpoint/path/{pathParam}|action_name
```

**Rules:**
- The `# TOOL N: tool_name - Description` header defines a grouped tool. All lines below it (until the next `# TOOL` header) belong to that tool.
- `action_name` must match what the tool implementation in `tools/*_endpoints_tool.py` handles.
- Use `@inherit:parent_toolset_name` to include all APIs from another toolset.
- The toolset file name (without `.txt`) is the value used in `DCT_TOOLSET`.

**Adding a new endpoint to an existing toolset:**
1. Find the relevant `# TOOL` section in the `.txt` file.
2. Add a line: `METHOD|/path/{param}|action_name`
3. Implement `action_name` handling in the corresponding `tools/*_endpoints_tool.py`.
4. Check `action_name` and its docstring against
   [`../../../.claude/rules/vocabulary-editorial-guidelines.md`](../../../.claude/rules/vocabulary-editorial-guidelines.md)
   before merging — this is where internal-terminology regressions have slipped in before.

**Creating a new toolset:**
1. Create `toolsets/my_toolset.txt` with the format above.
2. Add tool-to-module mappings in `loader.py:get_modules_for_toolset()` for any new tool names.

### Confirmation Rules (`mappings/manual_confirmation.txt`)

Controls which operations require user confirmation before execution.

**Format:**
```
METHOD|path_pattern|confirmation_level|message_template
```

**Confirmation levels:**
| Level | Meaning |
|---|---|
| `standard` | Simple yes/no confirmation |
| `elevated` | Stronger warning |
| `manual` | Must type specific text to confirm |
| `retention_check:N` | Conditional — triggers only if snapshot retention < N days |
| `policy_impact_check:N` | Conditional — triggers if policy affects > N objects |

- Use `*` as the method wildcard to match any HTTP method.
- Path patterns support `{paramName}` placeholders (matched as `[^/]+` regex).
- Message templates support `{name}`, `{days}` and `{count}`, rendered by
  `tools/core/confirmation_resolver.py:render_message_template()`. A placeholder that cannot
  be resolved is dropped together with the words that only frame it (quotes; "in {days} day(s)"),
  so write each one as a removable clause.
- Rules are evaluated in order; first match wins.

### Vocabulary Map (`mappings/vocabulary.txt`)

Internal-to-canonical term map (PPM-1129) applied by `tools/core/vocabulary.py:to_canonical()`
to upstream text a user may see: raw DCT error bodies (as an additive `message_for_user`) and
OpenAPI summaries. Parsed by `loader.py:load_vocabulary_rules()`.

**Format:**
```
@signals name=word,word,...
internal_term|canonical_term[|directive=word,word...]...
```

- Matching is case-insensitive and whole-word; longer internal terms are applied first.
  Several lines may share an internal term: the first whose text conditions hold wins.
- Directives (all optional, comma-separated, whole-word; a space in a phrase also matches a
  hyphen; `@name` expands to a declared `@signals` set):

| Directive | Effect |
|---|---|
| `only_if_text_mentions=` | Positive evidence: apply this line only if the text contains one of these words |
| `skip_if_text_mentions=` | Do not apply this line if the text contains one of these words |
| `skip_if_preceded_by=` | Leave a match alone directly after one of these words |
| `skip_if_followed_by=` | Leave a match alone directly before one of these words |

- Never translated: URLs, `/` and `\` paths, hyphen/dot/@-joined identifiers, `code spans`,
  `{placeholders}`. A substitution never doubles a term ("VDB containers" -> "VDB Groups").
- Words with an everyday meaning (`container`, `inventory`) or an ambiguous referent
  (`Delphix engine`) are translated only on positive evidence -- tighten the `@signals` set
  rather than adding skip words for the latest false positive.
- The canonical column is customer-facing text: never put a model instruction in it.
- Tests: `tests/unit/test_vocabulary.py` (cases), `tests/unit/test_vocabulary_spec_corpus.py`
  (every summary/description in a real DCT spec). Editorial rules:
  `.claude/rules/vocabulary-editorial-guidelines.md`.

### `config.py` and `loader.py`

- `config.py` — Reads and validates all environment variables. Add new env vars here.
- `loader.py` — Parses `.txt` files; results are `@lru_cache`d. Call `clear_cache()` if config files change at runtime.
