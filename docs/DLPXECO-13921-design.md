# Design — DLPXECO-13921: `find_endpoint` + `get_spec_chunk` meta-tools

> Implements [`DLPXECO-13921-functional.md`](./DLPXECO-13921-functional.md). Read the vision and functional specs first.

## High-level approach

Add **two** new meta-tools to `dct_mcp_server.tools.core.meta_tools`. Both reuse the OpenAPI spec cached at startup by `tool_factory.initialize_openapi_cache`. The spec is the source of truth for auto mode.

1. **`find_endpoint(query, method_types=None, limit=10, min_score=0.15)`** — fuzzy-matches a free-text user intent against the spec and returns ranked `(method, path, operation_id, summary, tags, score, requires_confirmation, confirmation_level, suggested_toolset)`. Scoring uses spec data only. `suggested_toolset` is a non-authoritative hint — the first persona `.txt` file that exposes the same `(method, path)` — so the LLM can call `enable_toolset(name)` if it wants the domain-tool path; otherwise `execute_action` works directly with the path.

2. **`get_spec_chunk(ref)`** — resolves a JSON pointer / OpenAPI `$ref` (e.g. `#/components/parameters/limit`) against the cached spec and returns the resolved object. Lets the LLM lazily fetch parameter / schema / requestBody definitions referenced by `find_endpoint` results, instead of pre-inlining them.

Execution stays on the existing `execute_action` meta-tool — no new executor function is needed.

A new helper module `tools/core/endpoint_discovery.py` contains pure functions for corpus building, hot-keyword extraction, scoring, and ranking. This keeps `meta_tools.py` thin.

If the OpenAPI spec is not cached at startup, `find_endpoint` returns an error with a clear message. There is no fallback to toolset `.txt` files — this tool is spec-only.

## Design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Result shape | `(method, path, operation_id, summary, tags, score)` only | No toolset reverse-mapping; LLM uses the path directly or calls `get_toolset_tools` separately |
| Hot-keyword source | OpenAPI spec tags + operationId tokens | Derived entirely from the spec; tags weighted 3× as the canonical resource vocabulary |
| Ranker | stdlib `difflib.SequenceMatcher` | No new dependencies; sufficient for spec size |
| No-spec behaviour | Return error dict, no fallback | `find_endpoint` is auto-mode / spec-only; falling back to `.txt` files would return lower-quality results without the spec's summaries/tags |
| POST `/*/search` as GET-equivalent | Yes, when `method_types=["GET"]` | Search endpoints are semantically reads |

## Architecture changes

### Source files modified/created

| File | Change |
|---|---|
| `src/dct_mcp_server/tools/core/endpoint_discovery.py` | **New file.** Pure helpers: `build_corpus_from_spec`, `extract_hot_keywords_from_spec`, `score_candidate`, `rank_candidates`. |
| `src/dct_mcp_server/tools/core/meta_tools.py` | Add `find_endpoint` and `get_spec_chunk` functions + `HARD_LIMIT` constant; register both in `register_meta_tools`; update all tool counts 6→8; update `list_available_toolsets` instructions to recommend `find_endpoint` first. |
| `.claude/rules/testing/auto.md` | Fix stale "5 meta-tools" counts to 7; append prompts 58–66 for fuzzy discovery. |

No changes to `config/loader.py`, `config/toolsets/*.txt`, `tool_factory.py`, `tools/__init__.py`, or any `*_endpoints_tool.py`.

### Module: `endpoint_discovery.py`

**`extract_hot_keywords_from_spec(spec)`** — iterates all operations, collects `tags` (weighted 3×) and `operationId` tokens (weighted 1×), returns a `frozenset` of tokens appearing in ≥3 operations. No hardcoded keyword list.

**`build_corpus_from_spec(spec)`** — flattens `spec.paths` into a list of dicts with `method`, `path`, `operation_id`, `summary`, `description`, `tags`.

**`score_candidate(query_tokens, hot_keywords, candidate)`** — weighted formula:
```
score = 0.55 × overlap + 0.30 × path_similarity_ratio + hot_boost
```
- `overlap` = `|query_tokens ∩ cand_tokens| / |query_tokens|`
- `path_similarity_ratio` = `difflib.SequenceMatcher` ratio between sorted query tokens and the path
- `hot_boost` = `min(0.2, 0.05 × |hot_hits|)` where `hot_hits = (query ∩ cand) ∩ hot_keywords`
- `cand_tokens` draws from path tokens, summary, operationId, and tags

**`rank_candidates(...)`** — filters by method, scores all candidates, drops those below `min_score`, sorts by `(-score, len(path))`, returns up to `limit`.

### Public tool surface (`meta_tools.py`)

```python
@log_tool_execution
def find_endpoint(
    query: str,
    method_types: Optional[List[str]] = None,
    limit: int = 10,
    min_score: float = 0.15,
) -> Dict[str, Any]:
```

Return shape per candidate:
```json
{
  "score": 0.82,
  "method": "POST",
  "path": "/vdbs/search",
  "operation_id": "searchVdbs",
  "summary": "Search for VDBs",
  "tags": ["VDB"],
  "requires_confirmation": false,
  "confirmation_level": "none",
  "suggested_toolset": "self_service"
}
```

`suggested_toolset` is `null` when no persona toolset exposes the endpoint (e.g. compliance endpoints) — the LLM can still call `execute_action` directly with the path, or fall back to a richer query.

### `get_spec_chunk(ref)` surface

```python
@log_tool_execution
def get_spec_chunk(ref: str) -> Dict[str, Any]:
```

Accepts either `#/components/parameters/limit` (standard OpenAPI form) or `/components/parameters/limit` (plain JSON pointer). Returns `{"ref": "...", "value": <resolved>}` on success or `{"error": "...", "ref": "..."}` if the ref is malformed, the spec is uncached, or any segment is unresolvable.

### Data flow

1. **Startup (unchanged)** — `register_meta_tools_only` → `register_meta_tools(app)` (now 7 tools) → `initialize_openapi_cache`.
2. **LLM calls `find_endpoint("find vdb with most snapshots", method_types=["GET","POST"])`**
3. Pull spec from `get_cached_spec()`. If None → return error.
4. Build corpus + hot keywords from spec.
5. Rank, enrich with confirmation level from `get_confirmation_for_operation`, return.
6. LLM inspects `path` + `operation_id`, then calls `execute_action` or `enable_toolset` as appropriate.

### Error handling

| Source | Behaviour |
|---|---|
| `query` empty | Return `{"error": "query is required", ...}`. No exception. |
| `spec is None` | Return `{"error": "OpenAPI spec not available...", "candidates": []}`. No fallback. |
| Per-candidate scorer raises | Caught, logged at WARNING, candidate skipped. |
| `get_confirmation_for_operation` raises | Caught, default `confirmation_level="none"`, logged at WARNING. |
| Invalid `limit` | Clamped to `[1, 25]`. |
| Invalid `method_types` entries | Dropped silently. |

## Test plan

See `.claude/rules/testing/auto.md` prompts 58–66 (appended by this change).

Regression: all 57 existing prompts must still pass — the new tool is purely additive.

No-spec case: start with unreachable `DCT_BASE_URL`. Call `find_endpoint` — verify `error` field is present and `candidates` is `[]`.

## Rollout

- Pure additive change. No data migration, no env var changes.
- Existing 6 meta-tools are unchanged in shape and behaviour.
- Fixed-toolset users (non-auto mode) are unaffected — `find_endpoint` is only registered in auto mode.
