# DLPXECO-14257 — Design

> **Revised per scope clarification:** Keep `dynamic` mode AND the spec-reading helpers
> (`get_spec_chunk`, `find_endpoint`, spec-derived confirmation) as standalone utilities.
> Remove only the *auto wiring*: the `auto` toolset name, meta-tool registration, runtime
> tool-switching, and `is_auto_mode`. **No files are deleted.** The OpenAPI spec cache
> (`spec_cache.py`) and all spec-fetch functions are preserved.

## High-level approach

Auto mode = (1) a set of registered meta-tools, (2) runtime tool-list switching state, (3) the `auto` toolset name/branching, and (4) the `is_auto_mode` flag. Strip exactly those four, while leaving every spec-reading utility callable. `meta_tools.py` is slimmed to its reusable spec helpers; `dynamic_confirmation.py` keeps its spec-derived resolver but drops the `auto` dispatch; `dynamic` mode and persona toolsets are untouched.

## Design decisions

1. **Keep helpers, not deletions.** Per scope clarification, `get_spec_chunk`, `find_endpoint` (+ `endpoint_discovery.py`), and `get_confirmation_for_operation_dynamic` are retained as standalone (currently unused) utilities — available to wire into `dynamic` mode later. Only their *auto registration/dispatch* is removed.
2. **`spec_cache.py` is untouched.** The cache variable (`_cached_spec`) and `get_cached_spec`/`load_and_cache_spec` live there and are used by `dynamic.py` directly. Confirmed not auto-specific.
3. **Invalid value → explicit error; server falls back to `dynamic`.** `get_configured_toolset()` raises `ValueError` for `auto` (message lists valid toolsets, no `auto`). `register_all_tools()`'s `except ValueError` fallback is repointed `"auto"`→`"dynamic"` so a stale config still boots.
4. **Strip the `auto` dispatch in `resolve_confirmation`** (it checks `toolset == "auto"`). After removal it delegates to the static `get_confirmation_for_operation` for all toolsets. `get_confirmation_for_operation_dynamic` stays defined (available) but is no longer auto-dispatched. `dynamic` mode is unaffected (uses `confirmation_resolver.check_confirmation`).

## Architectural changes (no file deletions)

**`tools/core/meta_tools.py` — slim to spec helpers.**
- **Remove:** module state (`_app`, `_dct_client`, `_tool_inventory`, `_current_toolset`, `_registered_tool_names`); `initialize_tool_inventory`, `list_available_toolsets`, `get_toolset_tools`, `enable_toolset`, `disable_toolset`, `_register_toolset_tools`, `_disable_current_toolset_internal`, `check_operation_confirmation`, `_get_confirmation_guidance`, `execute_action`, `register_meta_tools`, `get_current_toolset`, `get_registered_tool_count`.
- **Keep:** `_endpoint_toolset_index`, `find_endpoint`, `get_spec_chunk` (+ needed imports: `get_available_toolsets`, `load_toolset_grouped_apis`, `get_cached_spec`, `get_discovery_index`, `rank_candidates`, `resolve_confirmation`, `log_tool_execution`, `HARD_LIMIT`).
- **Drop now-unused imports:** `load_toolset_metadata`, `load_all_toolsets_metadata`, `get_tools_for_toolset`, `initialize_openapi_cache`, `register_toolset_tools`, `Context`.
- Rewrite the module docstring; soften `find_endpoint`'s instruction strings that referenced `enable_toolset`/`execute_action` (now gone) — keep the `suggested_toolset` hint (points at a persona usable via `DCT_TOOLSET`).

**`tools/core/dynamic_confirmation.py` — keep resolver, drop auto dispatch.**
- `resolve_confirmation()` → delegate unconditionally to `get_confirmation_for_operation` (remove the `if toolset == "auto"` branch and the now-unused `get_dct_config` import). Keep `get_confirmation_for_operation_dynamic` + its helpers. Update docstring.

**`tools/__init__.py`**
- Remove `register_meta_tools_only()`; remove the `if toolset == "auto": … return` branch; repoint the invalid-config fallback `"auto"`→`"dynamic"`; remove the `is_auto_mode` import; remove the two now-redundant `meta_tools` skip-guards (the slimmed module exposes no `register_tools`, so it is never auto-loaded).

**`config/loader.py`**
- Remove `META_TOOLS` constant; remove `is_auto_mode()`; in `get_configured_toolset()` change `("auto", "dynamic")` → `("dynamic",)` and drop `auto` from the error message.

**`config/__init__.py`** — drop `is_auto_mode` and `META_TOOLS` from the re-export list.

**`main.py`** — remove `is_auto_mode` import, the auto-mode startup logging block, the `DCT_TOOLSET=auto` docstring line.

**`config/config.py`** — remove the `auto:` line in `print_config_help`.

**`evals/integration_test_dynamic.py`** — remove the `DCT_TOOLSET=auto` step (keep the dynamic test).

**Docs:** README.md (feature list, env-var table, "Auto Mode" section, VS Code note), CLAUDE.md, src/dct_mcp_server/CLAUDE.md, tools/CLAUDE.md, config/CLAUDE.md, .claude/architecture.md.

**Files NOT touched:** `spec_cache.py`, `endpoint_discovery.py`, `dynamic.py`, `confirmation_resolver.py`, persona toolset `.txt` configs, `tool_factory.py` (its `resolve_confirmation` import still resolves).

## Test plan

Pure-Python unit tests (no live DCT), mapped to ticket ACs:

- **AC-1:** `get_configured_toolset()` with `DCT_TOOLSET=auto` raises `ValueError`; message contains `dynamic` + persona names, not `auto`. Assert `is_auto_mode` / `META_TOOLS` no longer importable from `dct_mcp_server.config`.
- **AC-2:** default → `get_configured_toolset() == "dynamic"`; assert the former meta-tools (`enable_toolset`, `disable_toolset`, `execute_action`, `list_available_toolsets`, `get_toolset_tools`, `register_meta_tools`) are gone from `meta_tools`.
- **AC-3:** `DCT_TOOLSET=self_service` → `get_modules_for_toolset` still resolves the persona's modules unchanged.
- **AC-4:** confirmation intact — `confirmation_resolver.check_confirmation` for a `DELETE` returns `requires_confirmation=True`; `resolve_confirmation` still returns the static rule shape.
- **Helpers retained:** `from dct_mcp_server.tools.core.meta_tools import find_endpoint, get_spec_chunk` imports cleanly; `get_spec_chunk` resolves a `$ref` against a stub spec.
- **AC-5 (guard):** no `is_auto_mode`, `register_meta_tools`, `register_meta_tools_only`, or `== "auto"` under `src/`; `ruff check` / `ruff format --check` clean; `pytest` green at/above the coverage floor.

No integration coverage required — verifiable by unit tests + clean build/lint.
