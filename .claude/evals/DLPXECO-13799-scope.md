# DLPXECO-13799 — Scope

## Ticket summary

- **Title:** Failed to add a hook in an MSSQL VDB
- **Reporter / Assignee:** Shreyas Kulkarni
- **Status:** In Progress
- **URL:** https://perforce.atlassian.net/browse/DLPXECO-13799

When a user calls `vdb_tool(action="update_vdb", ...)` (or the analogous dsource update actions) and supplies a `hooks` payload with camelCase keys (e.g. `configureClone`), the request is forwarded as-is to the Delphix Engine. The engine silently accepts the unknown key and discards the hook. The user sees a 200 OK but the hook is never installed. The expected snake_case key (`configure_clone`) works correctly.

The ticket asks that this be fixed in the MCP server: normalize / validate hook keys before they hit the engine, so callers cannot silently drop hooks by passing the wrong casing.

## What I found

- `update_vdb` and `update_*_dsource` actions are **dynamically generated** by `src/dct_mcp_server/tools/core/tool_factory.py:_create_grouped_tool_function` (`grouped_tool` closure, lines ~351–415). The pre-built `vdb_tool` in `src/dct_mcp_server/tools/dataset_endpoints_tool.py` does not implement `update_vdb` — it falls through to the dynamic factory.
- In `grouped_tool`, after path-param extraction and `filter_expression`/`body` handling, all remaining kwargs are merged into `json_body` (line 401-405). For PATCH/POST/PUT this body is passed verbatim to `DCTAPIClient.make_request`. There is no per-field normalization.
- The OpenAPI spec (`api-external.yaml`) defines `VirtualizationHooks` with snake_case keys only:
  `pre_refresh, post_refresh, pre_self_refresh, post_self_refresh, pre_rollback, post_rollback, configure_clone, pre_snapshot, post_snapshot, pre_start, post_start, pre_stop, post_stop`.
- The dynamic tool's docstring exposes the hook field generically as `hooks: ...` (see `dataset_endpoints_tool.py:167` and `:1176` for the equivalent pre-built tool docstrings), so the LLM caller has no schema-level signal about the required casing.
- Toolset config (`config/toolsets/continuous_data_admin.txt:13, 111, 122, 129`) maps the affected operations:
  - `PATCH /vdbs/{vdbId}` → `update_vdb`
  - `PATCH /dsources/oracle/{dsourceId}` → `update_oracle_dsource`
  - `PATCH /dsources/appdata/{dsourceId}` → `update_appdata_dsource`
  - `PATCH /dsources/mssql/{dsourceId}` → `update_mssql_dsource`

## Root-cause hypothesis

**High confidence.** The MCP server passes the JSON body through unchanged. The Delphix Engine API accepts unknown JSON properties silently (no strict-schema rejection) for PATCH endpoints, so `configureClone` is treated as an irrelevant field and the hook is dropped. The MCP server is the right place to enforce the spec since it is the schema-aware boundary.

## What I need to proceed

None — the ticket is self-contained and the fix surface is localized. Proceeding to design.

## Implicit assumptions

- The fix should apply to **any** request where the JSON body contains a top-level `hooks` object — not just `update_vdb`. dSource hook updates use the same field name and the same enum of hook types.
- camelCase → snake_case mapping is a deterministic, lossless transform for the known hook keys; we will normalize in place rather than reject, so existing (correct) snake_case payloads remain unchanged.
- An unknown hook key (neither valid snake_case nor a known camelCase variant) should be surfaced as an error rather than silently passed through — that preserves the bug-fix intent.
- The companion DLPX-side bug (engine should reject unknown fields) is out of scope here; only the MCP-server-side normalization is being addressed.
