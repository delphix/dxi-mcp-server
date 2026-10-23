# Vocabulary Editorial Guidelines

PPM-1129 outcome #6: editorial guidelines in place for future action additions, preventing
regression. This file is the guideline. Read it before adding or renaming any tool, action,
docstring, or user-facing message.

## Why this exists

The MCP Server is a product voice channel. Every tool name, action name, docstring, and
message a user sees shapes how an AI agent talks about Delphix. Internal terminology that
leaks into one of these surfaces gets repeated verbatim to customers. This has already
happened twice in practice (`container` was silently untranslated; bare `engine` was
silently defaulting to the wrong product) — both were only caught by reconciling against
the real glossary, not by code review alone. This guideline exists so the next regression
is caught by a checklist and a test, not by another reconciliation pass.

## Before adding or renaming a tool, action, or docstring

1. **Check the term against the canonical glossary.** The authoritative source is
   `DCT_MCP_Server_Vocabulary_Glossary_v1.2.xlsx`, attached to the PPM-1129 Jira ticket
   (32 Canonical Terms rows -- #1-#28 plus 3a, 7a, 7b, 19a -- and 169 Synonym Map rows).
   If the term you're adding already has a
   canonical form in that glossary, use it — don't introduce a new synonym.
2. **If the glossary doesn't cover the term**, prefer the term a customer would use, not
   the term the DCT API or an engine uses internally. When unsure, ask in the PR rather
   than guessing — a wrong default is worse than an open question (see "bare engine"
   below for why).
3. **Never put a retired or forbidden term in a tool name, action name, or docstring.**
   Check `config/server_instructions.md`'s terminology table and the "Never use in
   output" column of the glossary. Retired terms (`timeflow`, `container`, `inventory`,
   `rewind`, `Cloud Engine`, `AppData`, `plugin`, `toolkit`, `Virtualization Engine`,
   `Masking Engine`, `Delphix Masking`, and `Delphix engine` / bare `engine` -- always
   say which engine) must never appear in anything the model reads or can echo back,
   in any inflection ("timeflows", "rewinding", "timeflow-specific").
   A retired word that has an unrelated everyday meaning is not retired in that meaning:
   Oracle's "container database" (CDB) and DCT's "VDB inventory report" are legitimate.
   Kubernetes/Docker "container" is what the word *now* means. Never "translate" those.
4. **If a term is genuinely ambiguous and context-dependent** (the way "Delphix engine" is
   ambiguous between Continuous Data and Continuous Compliance), do not add a flat
   replacement to `config/mappings/vocabulary.txt` that silently picks one meaning.
   Resolve it from whole-word evidence in the text (`only_if_text_mentions=@signals`,
   vetoed by `skip_if_text_mentions=` for contrary evidence), and make the final
   fallback line say plainly what is known (see the `delphix engine` entries). A silent
   wrong default is a correctness bug, not a convenience.
5. **Translated text is customer-facing.** `message_for_user` is shown to end users, so
   the canonical column of `vocabulary.txt` must never contain an instruction to the
   model ("clarify which"). Conversational behaviour belongs in `server_instructions.md`.
6. **Words with a second meaning are translated on positive evidence only.** If a term
   you add to `vocabulary.txt` also has an unrelated meaning, gate it with
   `only_if_text_mentions=` on words that only occur when the text is about the retired
   Delphix meaning (see `@signals selfservice` for `container`) and add a negative test
   case. Do **not** fix a false positive by adding the example's neighbouring word to a
   skip list -- that is how this went wrong twice: the list only ever covers the examples
   someone already saw. Paths (`/` and `\`), URLs, hyphen/dot/@ IDs, `code spans` and
   `{placeholders}` are already never translated. `tests/unit/test_vocabulary_spec_corpus.py`
   runs the real DCT API text through the translator; it must stay green.

## Where a vocabulary rule belongs

| Situation | Where it goes |
|---|---|
| A raw string from an upstream API/error body needs translating | `config/mappings/vocabulary.txt` (`internal_term\|canonical_term[\|guard=words]`) |
| A cross-cutting rule the model needs to apply in conversation (e.g. "never say X", "retrain gently", "ask instead of guessing") | `config/server_instructions.md` — add to the terminology table and/or the numbered "Additional rules" |
| A confirmation/error message template | `config/mappings/manual_confirmation.txt` — use canonical terms only |
| A tool or action name | Rename in the relevant `config/toolsets/*.txt` file and the corresponding `tools/*_endpoints_tool.py` handler |

## After making the change

1. **Add a regression test.** `tests/unit/test_vocabulary_regression.py` keeps a `_BANNED`
   list of retired terms and checks it against confirmation messages, every tool/action
   name in `config/toolsets/*.txt` and the pre-built modules, and every pre-built tool
   docstring, matching inflected forms too. If you retired a new term, add it to that
   list (irregular forms such as "rewound" go in `_IRREGULAR`). A legitimate exception (a
   different meaning of the same word) goes in `_NAME_EXCEPTIONS` / `_PROSE_EXCEPTIONS`
   with a comment saying why. If you added a new raw-text translation, add a before/after
   case to `tests/unit/test_vocabulary.py` -- and, if the word has another meaning, a case
   proving that meaning is left alone.
2. **Run the full suite**, not just the vocabulary tests — tool/action renames touch
   dynamic-mode registration and toolset loading, which have their own tests.
3. **Update `docs/PPM-1129/PPM-1129-agent-ready-api-surface-proposal.md` and the
   Confluence Vocabulary Detail page** if the change adds or retires a term-level mapping,
   so the term-by-term reference stays in sync with the code. These are reference
   documents, not just historical records — let them drift and the next engineer
   reconciles against a stale page instead of the real glossary.

## What "done" looks like for a vocabulary change

- The new/renamed identifier contains no retired or forbidden term.
- Every ambiguous term is flagged, not silently defaulted.
- A test exists that would fail if the regression were reintroduced.
- The Vocabulary Detail Confluence page and `vocabulary.txt`/`server_instructions.md`
  agree with each other.

If any of these isn't true, the change isn't ready to ship, regardless of whether the
immediate feature works.
