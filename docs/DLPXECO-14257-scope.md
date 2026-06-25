# DLPXECO-14257 — Scope

## Ticket summary

- **Title:** Ecosystem-MCP: Remove auto mode (meta-tool dynamic toolset switching) from the MCP server; retain persona toolsets
- **Type / Points:** Story · 3 points · Epic DLPXECO-13984
- **Reporter / Assignee:** Shreyas Kulkarni · Status: Open
- **Problem statement:** The server supports a `DCT_TOOLSET=auto` mode where it boots with ~8 meta-tools and lets the AI enable/disable persona toolsets at runtime via `tools/list_changed` notifications. This mode is no longer wanted. The task is to remove auto mode entirely while leaving the persona toolsets and the default `dynamic` 2-tool mode fully intact.

> Note: this is a **planned removal / refactor**, not a defect. The "root-cause" framing below is adapted to "current state & removal rationale".

## What I found

Auto mode is implemented across the following (baseline = `main` @ `ff7af92`):

- **`src/dct_mcp_server/tools/core/meta_tools.py`** — the entire auto-mode surface: 8 meta-tools (`list_available_toolsets`, `get_toolset_tools`, `enable_toolset`, `disable_toolset`, `check_operation_confirmation`, `execute_action`, `find_endpoint`, `get_spec_chunk`), `register_meta_tools()`, `initialize_tool_inventory()`, and runtime-switching module state (`_tool_inventory`, `_current_toolset`, `_registered_tool_names`).
- **`src/dct_mcp_server/tools/core/endpoint_discovery.py`** — fuzzy-search helpers existing solely for the auto-mode `find_endpoint` meta-tool (file docstring line 1 says exactly this).
- **`src/dct_mcp_server/tools/__init__.py`** — `register_meta_tools_only()`, the `if toolset == "auto": ... return` branch in `register_all_tools()`, and the `if module_name == "meta_tools": continue` skip-guards in fixed-toolset registration.
- **`src/dct_mcp_server/config/loader.py`** — `is_auto_mode()`; `get_configured_toolset()` special-cases `"auto"` in its valid set; `META_TOOLS` constant.
- **`src/dct_mcp_server/config/__init__.py`** — re-exports `is_auto_mode` and `META_TOOLS`.
- **`src/dct_mcp_server/tools/core/dynamic_confirmation.py`** — `if toolset == "auto":` branch (docstring scopes the module to auto mode).
- **`src/dct_mcp_server/main.py`** — auto-mode startup logging block + a docstring line.
- **`src/dct_mcp_server/config/config.py`** — `auto:` line in the printed help.
- **Docs** — README.md ("Auto Mode" section, feature list, env-var table, VS Code note), CLAUDE.md, src/CLAUDE.md, tools/CLAUDE.md, config/CLAUDE.md ("shown in auto-mode discovery"), .claude/architecture.md.
- **`evals/integration_test_dynamic.py`** — sets `DCT_TOOLSET=auto` as a step.

**Verified independence (so removal is safe):**
- The default `dynamic` mode (`register_dynamic_tools` → `discovery` + `execute` in `tools/core/dynamic.py`) does **not** import or call `meta_tools`. `discovery`/`execute` are self-contained.
- `get_spec_chunk` and `find_endpoint` are referenced only within `meta_tools.py` / `endpoint_discovery.py` — no non-auto consumers.
- The default `DCT_TOOLSET` is `dynamic` (`config/config.py`), so removing `auto` does not change the default.

## Root-cause hypothesis / removal rationale

Auto mode adds an ~8-tool surface, runtime tool-list mutation, a separate spec-derived confirmation resolver, and a fuzzy-discovery index — all of which carry maintenance cost and a known client-compatibility caveat (VS Code Copilot needs a chat restart after `enable_toolset`). Persona toolsets and the `dynamic` explorer already cover the use cases, so auto mode is redundant. **Confidence: high** — the inventory shows auto-mode code is cleanly separable from dynamic/persona paths.

## What I need to proceed

No blocking unknowns. Two decisions I've defaulted (flag if you disagree):
1. **Invalid-value behavior:** after removal, `DCT_TOOLSET=auto` will be treated as an invalid value and raise the existing `ValueError` from `get_configured_toolset()` (message lists valid toolsets, minus `auto`). Alternative would be a silent fallback to `dynamic` — I chose the explicit error to match current handling of unknown values.
2. **Delete vs. deprecate:** full deletion of `meta_tools.py` and `endpoint_discovery.py` (not a deprecation shim), per the ticket's "remove" wording.

## Implicit assumptions

- `endpoint_discovery.py` may be deleted outright (its only consumer is the `find_endpoint` meta-tool). *(Caveat: PR #104 / DLPXECO-14248 refactored this file; if #104 merges first, this deletion will need a trivial rebase.)*
- No external automation or client config depends on `DCT_TOOLSET=auto` in a way that requires a graceful fallback rather than an error.
- The `META_TOOLS` constant in `loader.py` is used only for auto-mode bookkeeping and can be removed (to confirm during implementation).
- Removing the auto branch in `dynamic_confirmation.py` leaves dynamic-mode confirmation intact (to verify in Phase 4/5).
