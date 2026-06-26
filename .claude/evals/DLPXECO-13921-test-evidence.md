# Test Evidence — DLPXECO-13921

> Fuzzy endpoint discovery + spec-chunk fetcher meta-tools for auto mode.

## Environment

| Item | Value |
|---|---|
| Branch | `dlpx/pr/shreyaskulkarni/DLPXECO-13921-improve-auto-mode-fuzzy-endpoint-discovery` |
| Toolset | `auto` (only mode where the new meta-tools are registered) |
| OpenAPI spec | Bundled `api-external.yaml` from the repo root, injected directly into `tool_factory._openapi_spec` |
| DCT instance | Not exercised in this evidence run — tests are spec-only and do not call DCT |
| MCP client | None — invoked the tool functions directly via Python to exercise the discovery/resolver logic |

End-to-end MCP-client testing against a live DCT instance is still pending and is the next gate before merge.

## What was tested

### 1. Imports and registration shape

```text
from dct_mcp_server.tools.core.meta_tools import find_endpoint, get_spec_chunk, register_meta_tools
from dct_mcp_server.tools.core.endpoint_discovery import (
    build_corpus_from_spec, extract_hot_keywords_from_spec, rank_candidates,
)
# imports OK
```

Meta-tool count updated 6 → 8 in `register_meta_tools`, `enable_toolset.total_available_tools`, `disable_toolset.remaining_tools`, and the module docstring.

### 2. `find_endpoint` — fuzzy ranking

| Query | `method_types` | Top result | Score | `suggested_toolset` |
|---|---|---|---|---|
| `list all dsources` | `["GET","POST"]` | `GET /dsources` | 0.885 | `continuous_data_admin` |
| `list all dsources` | `["GET","POST"]` | `GET /cdb-dsources` | 0.860 | `continuous_data_admin` |
| `find vdb with most snapshots` | `["GET","POST"]` | `GET /snapshots/find_by_timestamp` | 0.459 | `continuous_data_admin` |
| `list all compliance connectors` | (none) | `GET /compliance-job-collections` | 0.554 | `null` (not exposed by any persona) |
| `list all compliance connectors` | (none) | `GET /compliance-jobs/{complianceJobId}/connectors` | 0.535 | `null` |
| `delete a bookmark` | `["DELETE"]` | `DELETE /bookmarks/{bookmarkId}` | 0.785 | `continuous_data_admin`, `confirmation_level=manual` |

Observations:
- The user's worked example (`list all compliance connectors`) returns the right endpoints with `suggested_toolset=null`, demonstrating the spec-only + auto-enable-hint path: no persona exposes compliance, so the LLM must call `execute_action` directly with the spec path.
- Confirmation levels are correctly enriched per candidate (`manual` for `DELETE /bookmarks/{bookmarkId}`).
- POST `/*/search` endpoints are folded into the GET-equivalent set when `method_types=["GET"]`.

### 3. `get_spec_chunk` — `$ref` resolution

| Input ref | Outcome |
|---|---|
| `#/components/parameters/limit` | resolved → `value.name == "limit"` |
| `#/components/parameters/cursor` | resolved → `value.name == "cursor"` |
| `/components/parameters/limit` (no leading `#`) | resolved (plain JSON pointer form accepted) |
| `#/components/parameters/nonexistent_xyz` | `error: ref segment 'nonexistent_xyz' not found in spec` |

This covers the explicit user example: `/dsources/search` references `#/components/parameters/limit`, and the LLM can fetch that fragment with one round-trip via `get_spec_chunk`.

### 4. Error / edge cases

| Case | Behaviour |
|---|---|
| `find_endpoint("")` | `error: query is required`, `candidates: []`, no exception |
| `find_endpoint(...)` with no cached spec | `error: OpenAPI spec not available; cannot perform fuzzy discovery.`, `candidates: []` |
| `get_spec_chunk("")` / non-string | `error: ref is required (string)` |
| `get_spec_chunk("not-a-pointer")` | `error: ref must be a JSON pointer like '#/components/parameters/limit' …` |
| `get_spec_chunk(...)` with no cached spec | `error: OpenAPI spec not available` |

All clean dicts — no bare exceptions raised, no global state mutated.

## Pending / out of scope for this evidence run

- **Live MCP-client exercise** with `DCT_TOOLSET=auto` against a real DCT instance (`/list_available_toolsets` instructions text now mentions `find_endpoint` first; `tools/list_changed` is unaffected).
- The `.claude/rules/testing/auto.md` prompts were not extended in this commit — see follow-up task to append fuzzy-discovery prompts (steps 58+).
- Regression check that all 57 existing auto-mode prompts still pass — also pending live-client run.
