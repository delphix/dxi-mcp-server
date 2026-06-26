# DLPXECO-13799 — Design

## High-level approach

Add a small normalization step in `tool_factory.py:_create_grouped_tool_function`'s `grouped_tool` closure, immediately before the request is dispatched to `DCTAPIClient.make_request`. If the assembled `json_body` contains a top-level `hooks` key whose value is a `dict`, walk its keys and:

1. If a key is already a valid snake_case hook type — leave it alone.
2. If a key matches a known camelCase form (`configureClone`, `preRefresh`, etc.) — rewrite it to snake_case in place.
3. If a key is neither — return an error response listing the valid hook types, so the caller sees an explicit failure instead of a silently-discarded hook.

The valid hook types are a fixed enum (taken from the OpenAPI `VirtualizationHooks` schema): `pre_refresh, post_refresh, pre_self_refresh, post_self_refresh, pre_rollback, post_rollback, configure_clone, pre_snapshot, post_snapshot, pre_start, post_start, pre_stop, post_stop`.

The normalizer lives as a module-private helper in `tool_factory.py` (no new file) and runs once per request, so cost is negligible.

## Design decisions

**Where to normalize — dynamic factory only.**
The pre-built `vdb_tool` and `dsource_tool` modules in `dataset_endpoints_tool.py` do not implement `update_vdb` / `update_*_dsource` (only the dynamic factory does), so a single fix in `tool_factory.py` covers every affected action today. Putting the normalizer in the HTTP client (`dct_client/client.py`) was considered and rejected: the client is intentionally generic and shouldn't know about VDB/dsource semantics. Putting it in a request-body interceptor at the FastMCP layer was rejected for the same reason.

**Normalize, don't reject, for known camelCase.**
The ticket's failure mode is silent dropping. Auto-correcting `configureClone` → `configure_clone` (and friends) is safe because the mapping is unambiguous and it directly resolves the user-visible bug. Strict rejection of camelCase would also fix the bug but pushes the same correction burden onto every caller and every prompt template — worse UX for no functional gain.

**Reject unknown keys.**
If a key is neither valid snake_case nor a known camelCase variant, we return `{"error": ..., "valid_hook_types": [...]}`. This is the only way to make a typo (`configre_clone`) loud rather than silent.

**Static enum, not OpenAPI lookup.**
We could read `VirtualizationHooks` from the cached OpenAPI spec at request time. Rejected: it adds spec-resolution code paths to the hot path for a list that changes maybe once a year. The enum is a constant in `tool_factory.py` with a comment pointing at the spec section so future spec changes are easy to mirror.

## Architectural changes

None. One new private function and one ~10-line block inserted into the existing `grouped_tool` closure. No public API change, no config change, no new module. The pre-built tools in `tools/*_endpoints_tool.py` are untouched.

## Test plan

**Unit tests** (new file `tests/tools/test_tool_factory_hooks.py` — the repo has no existing test infra; see *Build & test* note below):

1. `test_normalize_hooks_camelcase_keys_rewritten` — body `{"hooks": {"configureClone": [...]}}` → keys become `{"configure_clone": [...]}`; value list is preserved verbatim.
2. `test_normalize_hooks_snake_case_passthrough` — body `{"hooks": {"configure_clone": [...]}}` → unchanged.
3. `test_normalize_hooks_mixed_keys` — body containing both `configureClone` and `pre_refresh` — both end up snake_case, no duplication.
4. `test_normalize_hooks_unknown_key_returns_error` — body `{"hooks": {"bogusHook": [...]}}` → returns an error dict mentioning the invalid key and the valid hook list; no HTTP call is made.
5. `test_normalize_hooks_no_hooks_field` — body without `hooks` → unchanged, no error.
6. `test_normalize_hooks_non_dict_value` — body with `hooks: None` or `hooks: []` → unchanged (defensive: not our schema, don't blow up).
7. `test_all_known_camelcase_variants` — every camelCase form in the mapping table normalizes to its snake_case counterpart.

Edge cases covered: empty hooks dict, hooks key present but value is `None`, repeated calls (idempotent), unknown key when other keys are valid (still rejects).

**Integration coverage** — out of scope for this fix; it is exercised by the existing `continuous_data_admin` test prompt suite (`.claude/rules/testing/continuous_data_admin.md` items around `update_vdb` and `update_*_dsource`). PR description will note this for the reviewer.

## Build & test note

The project's `CLAUDE.md` states: *"No automated test suite exists. Testing is done by connecting an MCP client to the running server."* This ticket is the first to add unit tests under this repo. The Phase-5 test plan therefore also covers (a) adding `pytest` as a dev dependency and (b) creating `tests/` with a single `__init__.py` so future bug fixes can build on the same harness. We will confirm this approach with the user at the design-approval gate before scaffolding test infra.
