# Feature Design: DLPXECO-14248

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-14248
**Status**: Proposed
<!-- Guidance: H1 title must be exactly "Feature Design: $NAME" (not H2). check-structure.sh does not enforce this mechanically, but downstream review tooling relies on it. -->

---

## Summary

This feature introduces a single `spec_model.py` module that centralizes all OpenAPI structural traversal logic for the DCT MCP Server, replacing four independent implementations spread across `dynamic.py`, `driver.py`, `tool_factory.py`, and `endpoint_discovery.py`. Each of those modules previously re-implemented `$ref` resolution, `allOf` merging, request-body flattening, and path-template matching with differing cycle detection, depth limits, and truncation handling. The shared module wraps the raw spec dict in lazily-evaluated typed objects (`OpenAPISpec`, `Operation`, `Parameter`, `RequestBody`, `Response`, `SchemaObject`) so consumers query structure rather than walking dicts. Named domain subclasses (`DSource`, `VDB`) provide typed access to the two highest-value DCT domain objects. No MCP tool API surface, toolset configuration, or external behavior changes; this is a pure internal refactor.

## Affected Components
<!-- Guidance: Render the component checklist from .claude/architecture.md. Tick `[x]` for components this feature changes; leave `[ ]` for the rest. Do not invent components — only those listed in architecture.md may appear here. -->

- [ ] `main.py` — entry point (startup/shutdown only — no change)
- [ ] `config/config.py` — env var loading (no change)
- [ ] `config/loader.py` — toolset + confirmation rule parsing (no change)
- [ ] `config/toolsets/*.txt` — persona toolset definitions (no change)
- [ ] `config/mappings/manual_confirmation.txt` — confirmation rules (no change)
- [ ] `dct_client/client.py` — async HTTP client (no change)
- [ ] `core/logging.py` — logging infrastructure (no change)
- [ ] `core/session.py` — telemetry session management (no change)
- [ ] `core/decorators.py` — `@log_tool_execution` decorator (no change)
- [ ] `core/exceptions.py` — `DCTClientError`, `MCPError` (no change)
- [x] `tools/core/spec_model.py` — **new file**: centralized OpenAPI object model (`OpenAPISpec`, `Operation`, `Parameter`, `RequestBody`, `Response`, `SchemaObject`, `DSource`, `VDB`)
- [x] `tools/core/dynamic.py` — remove `_resolve_refs`, `_find_path_item`, `_flatten_request_body`; replace inline `allOf`/`$ref` traversal with `OpenAPISpec.wrap()` + model calls
- [x] `toolsgenerator/driver.py` — replace `resolve_ref`, `resolve_schema_properties` with thin wrappers over `OpenAPISpec.resolve_pointer` / `SchemaObject`; delete standalone deep-resolver logic
- [x] `tools/core/tool_factory.py` — replace `_resolve_ref` with thin wrapper over `OpenAPISpec.resolve_pointer`; remove inline schema traversal
- [x] `tools/core/endpoint_discovery.py` — replace inline `paths` traversal with `spec.operations()` iteration via `OpenAPISpec.wrap()`

## Architecture Changes

### Schema / Config Changes

None. This is a pure Python internal refactor. No schema files, config formats, or persisted state shapes are modified. The `_WRAPPER_CACHE` is a module-level Python dict, not persisted state.

### Source Files to Modify

| File | Purpose | Maps to FR |
|------|---------|------------|
| `src/dct_mcp_server/tools/core/spec_model.py` | **New file**: Provides `OpenAPISpec`, `Operation`, `Parameter`, `RequestBody`, `Response`, `SchemaObject`, `DSource`, `VDB`. Owns all `$ref` resolution (`resolve_pointer`, `resolve_refs`), `allOf` merging, path-template matching (`find_path_item`), and the `_WRAPPER_CACHE` memoization. | FR-001, FR-002, FR-003, FR-004, FR-005, FR-006 |
| `src/dct_mcp_server/tools/core/dynamic.py` | Remove `_resolve_refs`, `_find_path_item`, `_flatten_request_body`, and all inline `$ref`/`allOf` traversal. Replace with `OpenAPISpec.wrap()` calls and typed model access (`op.request_body.fields()`, `op.parameters`, `model.find_path_item()`, `model.resolve_refs()`). | FR-002, FR-004, FR-005, FR-007 |
| `src/dct_mcp_server/toolsgenerator/driver.py` | Replace standalone `resolve_ref(ref, root)` and `resolve_schema_properties(schema, api_spec)` functions with thin wrappers that delegate to `OpenAPISpec(root).resolve_pointer(ref)` and `SchemaObject(OpenAPISpec(api_spec), schema)`. Remove any residual deep-resolver logic. | FR-002, FR-003, FR-007 |
| `src/dct_mcp_server/tools/core/tool_factory.py` | Replace `_resolve_ref(ref, spec)` with a thin wrapper over `OpenAPISpec(spec).resolve_pointer(ref)`. Remove inline schema iteration that duplicates spec_model logic. | FR-002, FR-007 |
| `src/dct_mcp_server/tools/core/endpoint_discovery.py` | Replace inline `paths` dict iteration with `OpenAPISpec.wrap(spec).operations()` generator. All per-operation field access goes through `Operation` typed properties (`op.method`, `op.path`, `op.operation_id`, `op.summary`, `op.tags`). | FR-005, FR-007 |
| `tests/test_spec_model.py` | **New file**: Unit test suite for `spec_model.py`. Covers `$ref` resolution, cycle detection, `allOf` merging, path matching, request/response field extraction, cache invalidation, and behavior parity with pre-refactor consumer functions. | FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007 |

### New Files (if any)

- `src/dct_mcp_server/tools/core/spec_model.py` — centralized OpenAPI structural object model (new in this PR; already present in the feature branch)
- `tests/test_spec_model.py` — unit test suite for `spec_model.py` covering all FR ACs

## Version Compatibility
<!-- Guidance: Pull the version table from .claude/architecture.md and mark whether this feature requires branching per version. "Branch?" = Yes if code path differs by version, No if behavior is identical. -->

This is a pure internal refactor of Python modules within the MCP server itself. The DCT API version is irrelevant to the refactor; the server reads whichever `api-external.yaml` is available (live download or bundled fallback) and the model classes operate identically regardless of spec version.

| Version | Supported? | Branch? | Notes |
|---------|-----------|---------|-------|
| Python 3.11 | Yes | No | Minimum runtime; `spec_model.py` uses `match`/`case`-compatible patterns but currently only relies on 3.11+ via `typing.Self` / `frozenset` literals |
| Python 3.12+ | Yes | No | No behavioral difference; no version guards needed |
| DCT API spec (any bundled or live) | Yes | No | `OpenAPISpec.wrap()` is spec-version-agnostic; the module handles whatever `api-external.yaml` version is loaded |
| FastMCP 2.13.2+ | Yes | No | `spec_model.py` is a pure library module — no FastMCP imports; version changes to FastMCP are irrelevant |

## Platform Behavior Notes
<!-- Guidance: Flag each "Non-Obvious Platform Behavior" from CLAUDE.md / architecture.md that this feature interacts with. -->

- **Spec loaded from `$TEMP/dct_mcp_tools/` or bundled fallback** — Affects: `OpenAPISpec.wrap()` receives whatever dict `spec_cache.get_cached_spec()` returns; the module does not care which source the spec came from, so the fallback path is exercised identically.
- **`_WRAPPER_CACHE` keyed by `id(raw)`** — Affects: CPython object identity semantics; the cache holds exactly one entry so stale wrappers are not retained across spec reloads. GIL-protected dict assignment makes this thread-safe under CPython's single-threaded async model (see Risk R-3 in vision doc; Risk column Assumption A4).
- **FastMCP lifespan** — N/A: `spec_model.py` never imports from `fastmcp` and triggers no lifespan events. It is importable before FastMCP is initialized.
- **API key prefix** — N/A: `spec_model.py` reads the spec structure only; it never makes HTTP calls and has no awareness of the `apk ` prefix behavior in `DCTAPIClient`.
- **`@lru_cache` in `config/loader.py`** — N/A: the toolset config cache is independent of the spec object model.
- **`@log_tool_execution` decorator** — N/A: `spec_model.py` provides pure library classes; it registers no tools and uses no decorators.
- **Confirmation system** — N/A: confirmation rules are looked up in `manual_confirmation.txt` via `confirmation_resolver.py`; `spec_model.py` plays no role in that path.

## Open Questions / Risks

- R-1: `allOf` merge behavior differs subtly between old and new code, breaking field extraction in generated tools — **Mitigation**: Add unit tests that reproduce exact `allOf` cases from `api-external.yaml` (`DSource`, `VDB`, `CreateVDBBySnapshotParameters`) and assert `properties`/`required` lists match pre-refactor output. `driver.py`'s `resolve_schema_properties` is already a thin wrapper; parity is verifiable by comparing its output before and after.
- R-2: Path template matching in `find_path_item` diverges from the prior `dynamic.py._find_path_item`, causing execute to 404 on parameterized paths — **Mitigation**: Port the existing regex/segment logic exactly (already done); add parametric-path round-trip tests covering `/vdbs/vdb-abc-123` → `/vdbs/{vdbId}` and priority-over-exact-match edge case.
- R-3: `_WRAPPER_CACHE` keyed by `id(raw)` retains stale wrappers if the spec dict is replaced by reference but `id` is reused by the Python allocator — **Mitigation**: Cache stores only one entry at a time (replacing the dict on every new `wrap()` call); document the single-entry invariant; add a unit test asserting cache invalidates on new dict.
- R-4: Consumers that currently ignore missing `$ref` targets (caught by `KeyError` silently) may surface new `ValueError` from `resolve_pointer` — **Mitigation**: `resolve_refs` already converts `KeyError`/`ValueError` to a `SCHEMA_REF_NOT_FOUND` marker dict; verify this path is tested.
- Q-1: Should `driver.py`'s thin `resolve_ref` and `resolve_schema_properties` wrapper functions be kept for external callers or fully deleted? — Currently kept as thin wrappers (not deleted), preserving backward compatibility for any callers outside the four known consumers. The FR-007 AC-1 grep check tests only the direct bodies of `dynamic.py`, `driver.py`, `tool_factory.py`, `endpoint_discovery.py` — not whether the wrapper names remain. Owner: Shreyas Kulkarni.
- Q-2: `tool_factory.py` and `driver.py` both maintain their own separate `_openapi_spec` module-level caches in addition to `spec_model.py`'s `_WRAPPER_CACHE`. After this refactor, should these caches be consolidated so only one spec dict is held in memory? This is out of scope for DLPXECO-14248 (NG4 covers non-structural changes) but should be tracked as a follow-up. Owner: TBD.

## Acceptance Criteria

- [ ] AC-1 (FR-001): `OpenAPISpec.wrap()` called twice with the same dict returns the same instance (cache hit).
- [ ] AC-2 (FR-001): `OpenAPISpec.wrap()` with a new dict replaces the cache; old dict's wrapper is no longer returned.
- [ ] AC-3 (FR-001): `OpenAPISpec.wrap(None)` and `wrap({})` return `None`.
- [ ] AC-4 (FR-001): `OpenAPISpec.__init__` raises `TypeError` for non-dict input.
- [ ] AC-5 (FR-002): `resolve_pointer("#/components/schemas/DSource")` returns the raw `DSource` schema dict.
- [ ] AC-6 (FR-002): `resolve_pointer` raises `KeyError` for a non-existent schema key.
- [ ] AC-7 (FR-002): `resolve_refs` with a circular schema returns `{"$ref_truncated": True, "reason": "cycle_detected"}` and `truncated=True`.
- [ ] AC-8 (FR-002): `resolve_refs` at depth 11 (max_depth=10) returns `{"$ref_truncated": True, "reason": "max_depth_exceeded"}`.
- [ ] AC-9 (FR-002): `resolve_refs` with a missing `$ref` target returns a `SCHEMA_REF_NOT_FOUND` marker (no exception propagated).
- [ ] AC-10 (FR-002): `resolve_refs` output is byte-identical to the former `dynamic.py._resolve_refs` for all DCT spec schemas.
- [ ] AC-11 (FR-002): `resolve_refs` called with a top-level list resolves dict elements and leaves non-dict elements unchanged; returns a list.
- [ ] AC-12 (FR-003): `SchemaObject` for `DSource` (allOf-composed) exposes all properties from both base and action-specific sub-schemas.
- [ ] AC-13 (FR-003): `SchemaObject.key_properties` for `CreateVDBBySnapshotParameters` returns only the small inline entry's property names.
- [ ] AC-14 (FR-003): `SchemaObject` for a flat schema exposes `key_properties` equal to all property names.
- [ ] AC-15 (FR-003): `SchemaObject` output for `DSource` matches `driver.py:resolve_schema_properties` output (`properties` and `required` identical).
- [ ] AC-16 (FR-004): `op.request_body.fields()` for `POST /vdbs/search` returns a non-empty list with correct `required` flags.
- [ ] AC-17 (FR-004): `op.request_body` for `GET /vdbs/{vdbId}` is `None`.
- [ ] AC-18 (FR-004): `op.path_param_names` for `GET /vdbs/{vdbId}` returns `["vdbId"]`.
- [ ] AC-19 (FR-004): `op.responses["200"].schema_object()` returns a `SchemaObject` for `POST /vdbs/{vdbId}/refresh_by_timestamp`.
- [ ] AC-20 (FR-004): `RequestBody.fields()` for `POST /vdbs/search` is identical to former `dynamic.py._flatten_request_body` output.
- [ ] AC-21 (FR-004): `RequestBody.fields()` for a body whose media-type schema has `allOf` at the root level returns a non-empty merged property list.
- [ ] AC-22 (FR-005): `find_path_item("/vdbs/vdb-abc-123")` returns the path-item for `/vdbs/{vdbId}`.
- [ ] AC-23 (FR-005): `find_path_item("/vdbs")` returns the exact `/vdbs` path-item without template matching.
- [ ] AC-24 (FR-005): `find_path_item("/nonexistent/path")` returns `None`.
- [ ] AC-25 (FR-005): `find_path_item("/vdbs/search")` returns the exact `/vdbs/search` entry, not the parameterized `/vdbs/{vdbId}`.
- [ ] AC-26 (FR-006): `spec.domain_object("DSource")` returns a `DSource` instance.
- [ ] AC-27 (FR-006): `spec.domain_object("DSource")` called twice returns the same cached instance.
- [ ] AC-28 (FR-006): `spec.domain_object("SomeUnknownSchema")` (schema exists) returns a generic `SchemaObject`.
- [ ] AC-29 (FR-006): `spec.domain_object("DSource")` when `DSource` absent from spec returns `None`.
- [ ] AC-30 (FR-007): `grep -r "def resolve_ref\|def _resolve_ref\|def _resolve_refs\|def _flatten_request_body\|def _find_path_item" src/` returns no standalone (non-wrapper) implementations in the four consumer modules.
- [ ] AC-31 (FR-007): All existing pytest tests pass without modifying any test assertions.
- [ ] AC-32 (FR-007): Line coverage ≥ 85% and branch coverage ≥ 75% for `spec_model.py` via `pytest-cov`.

---
<!-- Cross-references checked by check-structure.sh during the design phase:
     - Every FR-* in docs/$NAME/$NAME-functional.md → at least one row in ### Source Files to Modify
     - Non-Goals in docs/$NAME/$NAME-vision.md → MUST NOT appear in Architecture Changes (hard constraint)
     - Every AC → at least one FR-* in functional.md (transitive via FR mapping)
     Run: .claude/evals/check-structure.sh $NAME --step design -->
