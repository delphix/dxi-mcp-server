# Vision — DLPXECO-13921: Improve `auto` mode endpoint discovery

> Source ticket: [DLPXECO-13921 — Make the auto mode in the dxi-mcp-server better](https://perforce.atlassian.net/browse/DLPXECO-13921)
> Issue type: Task | Domain: feature | Branch: `dlpx/pr/shreyaskulkarni/DLPXECO-13921-improve-auto-mode-fuzzy-endpoint-discovery`

## Problem

In `auto` mode (`DCT_TOOLSET=auto`), the DCT MCP server starts with only 6 meta-tools. To take any concrete DCT action, the LLM must:

1. Call `list_available_toolsets` — picks one of 5 personas.
2. Call `get_toolset_tools(<toolset>)` — receives the full grouped-tool catalogue (often **dozens of tools and hundreds of actions**, especially for `continuous_data_admin` with 431 prompt-level actions).
3. Either `enable_toolset` (rebuild the client tool list) or `execute_action(toolset, tool, action, ...)`.

This routes **every** user request through a persona filter that was designed for human users, not for an LLM that already knows the user's intent. The blast radius is two-fold:

- **Context bloat** — `get_toolset_tools("continuous_data_admin")` returns the metadata for hundreds of actions even when the user's request can be served by a single endpoint. Most of that text is never used.
- **Wrong-toolset traps** — actions the user wants are sometimes split across personas (e.g. a "find dataset with most snapshots" intent could be served by either `reporting_insights` or `continuous_data_admin`). The LLM has to guess which persona to enable, and a wrong guess wastes another round-trip.

The ticket proposes flipping the discovery model: use the OpenAPI spec the server already caches at startup, and let the LLM narrow endpoints by HTTP method + a fuzzy keyword search over endpoint paths/summaries/descriptions. The persona toolsets remain available for the multi-action workflows they were designed for, but the auto-mode "first move" stops being _"pick a persona blind"_.

## Goals

1. **G1 — Add a fuzzy endpoint-discovery meta-tool** that the LLM can call once with `(method_type, query)` and receive a small ranked list of candidate endpoints (path, method, summary, suggested toolset/tool/action) drawn from the cached OpenAPI spec.
2. **G2 — Reduce auto-mode discovery cost** for single-call intents to one meta-tool round-trip plus the actual `execute_action` call. Today's worst case is `list_available_toolsets` + `get_toolset_tools` + `execute_action` (3 calls) and frequently the wrong toolset on the first try (5+ calls).
3. **G3 — Keep the persona-discovery path working** unchanged, so existing auto-mode workflows (and the 57 prompts in `.claude/rules/testing/auto.md`) continue to pass.
4. **G4 — Work without a live DCT** — the discovery tool must function from the bundled spec fallback when the live download fails, mirroring `tool_factory.initialize_openapi_cache`.

## Non-Goals

- **NG1** Replacing or removing `list_available_toolsets` / `get_toolset_tools` / `enable_toolset` / `disable_toolset`. They keep their current behaviour.
- **NG2** Changing the persona toolset `.txt` files or the confirmation rules.
- **NG3** Building a server-side LLM-based ranker. The fuzzy match is deterministic, in-process, and runs on string features only.
- **NG4** Auto-executing the best match. The discovery tool returns candidates; the LLM still chooses and calls `execute_action`.
- **NG5** Indexing DCT API responses or response schemas. Discovery operates on path + summary + description only.

## Constraints

- **C1** Python 3.11+, no new heavy dependencies. Prefer the standard library (`difflib.SequenceMatcher`, `re`) plus what is already vendored. If a small focused dependency (e.g. `rapidfuzz`) is added, it must be optional.
- **C2** Must reuse `tool_factory.get_cached_spec()` — no second download of `api-external.yaml`.
- **C3** Must respect the existing confirmation system. Every candidate must include the confirmation level resolved through `get_confirmation_for_operation`.
- **C4** Must map every candidate to a `(toolset, tool, action)` triple so the LLM's follow-up call can reuse `execute_action` — i.e. the discovery output is _directly actionable_, not just informational.
- **C5** No code changes outside `tools/core/` and `config/` should be needed for the new meta-tool to land. Toolset `.txt` files and pre-built tools are not edited.
- **C6** The new meta-tool must register only when `DCT_TOOLSET=auto`, alongside the existing meta-tools.

## Risks

- **R1** **Spec absent at runtime.** If both the live download and bundled spec fail, discovery has no corpus. Mitigation: fall back to a degraded mode that searches over the union of toolset `.txt` entries (path + action name only).
- **R2** **Endpoint not in any toolset.** The OpenAPI spec lists every DCT endpoint, but the toolset files curate a subset. A fuzzy hit on an "orphan" endpoint cannot map to `(toolset, tool, action)`. Mitigation: in the candidate output, mark such results as `executable_via: "execute_action"` only after confirming there is a path in the toolsets, and otherwise return them with `executable_via: "none"` and a clear hint.
- **R3** **Ranking quality.** Naive substring match ranks `"snapshot"` higher than `"highest snapshot count"`. Mitigation: weighted scoring combining (a) keyword overlap, (b) `difflib` ratio on path, (c) hot-keyword boost (`snapshot`, `vdb`, `dsource`, `bookmark`, `engine`, `environment`, `report`, `tag`, `policy`, `job`).
- **R4** **Method-type filter too aggressive.** The LLM might pass `GET` for an intent that legitimately needs `POST /search`. Mitigation: accept a list of methods (`["GET","POST"]` default), and treat `/search` POST endpoints as read-equivalent (always included when `GET` is requested).
- **R5** **Result list too long.** Returning >20 candidates defeats the goal. Mitigation: hard cap (default 10), tunable via parameter, and drop candidates below a min score threshold.
- **R6** **Drift between spec and toolset files.** Spec advertises an endpoint that no toolset references. Caller resolves to `(None, None, None)` triple. Mitigation: explicit field in the result and a hint to use `execute_action` with raw `{method, path}` once that path is supported, or to use `enable_toolset` for the closest persona.

## Success Criteria

- **SC1** Auto mode can answer "find me the dataset with the highest number of snapshots" in two LLM tool calls (discovery → execute) without any `enable_toolset` / `get_toolset_tools` round-trip.
- **SC2** All 57 prompts in `.claude/rules/testing/auto.md` still pass — discovery is additive.
- **SC3** With both live and bundled spec unavailable, the new tool returns a structured error referencing the toolset-only fallback, not a stack trace.
- **SC4** A user request with no fuzzy match (`"foo bar baz"`) returns `candidates: []` and a `hint` pointing back to `list_available_toolsets`.
- **SC5** Each returned candidate carries enough information for the LLM to call `execute_action` directly: `toolset`, `tool`, `action`, `method`, `path`, `confirmation_level`, `summary`, `score`.
