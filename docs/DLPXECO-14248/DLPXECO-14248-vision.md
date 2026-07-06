# Vision: DLPXECO-14248

## Problem Statement

The DCT MCP Server reads the DCT OpenAPI spec (`api-external.yaml`, ~700 endpoints + `components/schemas`) as a raw nested dict and traverses it by hand in at least four independent modules — `toolsgenerator/driver.py`, `tools/core/tool_factory.py`, `tools/core/dynamic.py`, and `tools/core/endpoint_discovery.py`. Each module re-implements `$ref` resolution, `allOf` merging, request-body flattening, and response-schema extraction independently, with differing cycle detection logic, depth limits, and truncation handling. There is no shared abstraction layer, so any change to OpenAPI traversal rules must be replicated across all four consumers, and bugs in one copy do not benefit the others.

## Goals

- G1: Introduce a single `spec_model.py` module that centralizes all `$ref` resolution (both single-level pointer lookup and recursive inlining) and `allOf` merging so there is one source of truth for OpenAPI structural traversal.
- G2: Replace all four duplicated traversal implementations in `dynamic.py`, `driver.py`, `tool_factory.py`, and `endpoint_discovery.py` with calls to the shared model, eliminating the drift in cycle detection, depth limits, and truncation handling.
- G3: Expose request bodies, response schemas, and domain objects (dSource, VDB) as typed wrapper objects (`RequestBody`, `Response`, `SchemaObject`, and curated subclasses) so consumers query structure rather than dict-walking by hand.
- G4: Preserve identical runtime behavior of endpoint discovery and execution — no regression in endpoint selection, parameter extraction, or execution.

## Non-Goals

- NG1: Runtime data validation of live API payloads (Pydantic models, schema validation of actual HTTP request/response bodies) — the model describes spec structure only, never instance data.
- NG2: Build-time code generation of model class files from the spec — all wrapping is lazy at runtime over the already-cached spec dict.
- NG3: Full OpenAPI 3.0 compliance (e.g., `oneOf`, `anyOf`, discriminators, external `$ref` URLs) — only the patterns present in the DCT `api-external.yaml` are in scope.
- NG4: Changes to the MCP tool API surface, toolset definitions, or confirmation rules — this is a pure internal refactor.

## Success Criteria

- SC1: A single `spec_model.py` module exists containing `OpenAPISpec`, `Operation`, `Parameter`, `RequestBody`, `Response`, and `SchemaObject` classes; all `$ref` resolution logic is removed from `dynamic.py`, `driver.py`, `tool_factory.py`, and `endpoint_discovery.py`.
- SC2: The four previously duplicated `$ref` resolvers are deleted (not merely wrapped) and replaced by calls to `OpenAPISpec.resolve_pointer` / `OpenAPISpec.resolve_refs`.
- SC3: `SchemaObject` handles any `components/schemas` entry including `allOf`-composed schemas; named `DSource` and `VDB` subclasses exist and are returned by `OpenAPISpec.domain_object()`.
- SC4: All existing unit tests and integration tests pass without modification to test assertions (behavior is unchanged).
- SC5: The `spec_model.py` unit test suite covers `$ref` resolution, cycle detection, `allOf` merging, path matching, and request/response field extraction.

## Stakeholders

| Stakeholder | Interest |
|-------------|----------|
| Shreyas Kulkarni (assignee) | Maintainability — single place to fix OpenAPI traversal bugs or extend for new spec patterns |
| MCP server consumers (AI assistants) | Correctness — consistent endpoint discovery and parameter extraction across all toolset modes |
| Future contributors | Understandability — one module to read rather than four diverging implementations |
| Delphix platform team | Stability — no regressions in live DCT API interactions |

## Constraints

- Must be backward-compatible at the Python API level: `dynamic.py`, `driver.py`, `tool_factory.py`, and `endpoint_discovery.py` are callers; their public interfaces (function signatures, return types) cannot change.
- **Python 3.11+ only** — `spec_model.py` may use `match`/`case` statements, `tomllib`, and `typing.Self` without compatibility shims; no Python 3.10 or earlier support is required.
- **FastMCP compatibility** — `spec_model.py` is a pure library module; it must not import from `fastmcp`, register any tools, or trigger FastMCP lifespan events. The module must be importable before the FastMCP application is initialized.
- No new third-party dependencies — the model must be pure Python (stdlib + `get_logger` from existing `core/`). `pip show <package>` on the installed environment must show no new packages after `spec_model.py` is added.
- Must not introduce a build step — all model classes are lazy runtime wrappers over the existing cached spec dict.
- `resolve_refs` truncation markers (`$ref_truncated`, `reason`) must remain byte-identical to the former `dynamic.py._resolve_refs` output for backward compatibility with any consumer that pattern-matches on those keys.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| `allOf` merge behavior differs subtly between old and new code, breaking field extraction in generated tools | Medium | High | Add unit tests that reproduce exact `allOf` cases from `api-external.yaml` (e.g., `DSource`, `VDB`, `CreateVDBBySnapshotParameters`) and assert property/required lists match pre-refactor output |
| Path template matching logic in `find_path_item` diverges from the prior `dynamic.py._find_path_item`, causing execute to 404 on parameterized paths | Medium | High | Port the existing regex/segment logic exactly and add parametric-path round-trip tests; run full integration suite against a live DCT instance |
| `_WRAPPER_CACHE` keyed by `id(raw)` retains stale wrappers if the spec dict is replaced by reference but `id` is reused by the Python allocator | Low | Medium | Cache stores only one entry at a time (replacing the dict on every new `wrap()` call); add a unit test `test_wrap_cache_invalidates_on_new_dict` that creates dict A, wraps it, creates dict B, calls `wrap(B)`, then asserts `wrap(A)` returns a new instance (not the B wrapper); document the single-entry invariant in a module-level docstring |
| Consumers that currently ignore missing `$ref` targets (caught by `KeyError` silently) may surface new `ValueError` from `resolve_pointer` | Low | Medium | `resolve_refs` already converts `KeyError` / `ValueError` to a `SCHEMA_REF_NOT_FOUND` marker dict; verify this path in unit tests |
| `SchemaObject._resolve` caches results on the instance but the instance is short-lived (created per-call in some paths), yielding no cache benefit | Low | Low | `OpenAPISpec.domain_object()` caches named `SchemaObject` instances; inline schemas used within a single request are short-lived by design — acceptable |

## Assumptions

The following assumptions were made during spec generation. Each should be validated before implementation begins.

- **A1**: The four consumer modules (`dynamic.py`, `driver.py`, `tool_factory.py`, `endpoint_discovery.py`) are the complete set of callers that contain standalone `$ref` resolution logic. No other modules in `src/` directly traverse `components/schemas` or dereference `$ref` keys.
- **A2**: `api-external.yaml` uses only local JSON pointer `$ref` values (starting with `#/`). No external URL `$ref` values (e.g., `https://...` or relative file paths) appear in the bundled spec. If external refs are introduced in a future DCT version, `resolve_pointer` will raise `ValueError` and the feature scope must be revisited.
- **A3**: The spec dict passed to `OpenAPISpec.wrap()` is already the fully-parsed Python dict from `yaml.safe_load`. No partial loading, streaming parsing, or lazy-loading pattern is in use.
- **A4**: There is at most one goroutine/thread performing a spec reload at any given time. The `_WRAPPER_CACHE` dict assignment is a single CPython bytecode operation (GIL-protected); no additional locking is needed. If the server is ever moved to a multi-threaded model, this assumption must be re-evaluated.
- **A5**: `DSource` and `VDB` are the only two domain objects in `components/schemas` that warrant curated subclasses at this time. All other named schemas are accessed via the generic `SchemaObject` path. Additional curated subclasses can be added to `_CURATED_DOMAIN_OBJECTS` without changing the `domain_object()` API.
- **A6**: FastMCP is imported and initialized in `main.py` before any tool module is imported. `spec_model.py` will always be imported after FastMCP initialization completes, so it is safe to assume the FastMCP lifespan is already running when the module is first used.

---
<!-- Cross-reference: Goals (G1-G4) map to FR descriptions in the functional spec.
     Success Criteria (SC1-SC5) map to Acceptance Criteria in FR-* entries.
     Constraints and Risks inform the Quality Rules and Edge Cases sections.
     Assumptions (A1-A6) are implicit invariants that implementation must verify. -->