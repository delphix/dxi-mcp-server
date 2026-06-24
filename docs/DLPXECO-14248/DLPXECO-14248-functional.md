# Functional Specification: DLPXECO-14248

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-14248
**Generated from**: Acceptance criteria in Jira ticket DLPXECO-14248

---

## FR-001: Centralized OpenAPI spec object model

### Description
Introduces a single `spec_model.py` module that owns all OpenAPI structural traversal logic — `$ref` resolution (single-level and recursive), `allOf` merging, path template matching, and schema property extraction — eliminating the need for any consumer to walk raw dicts directly.

### Input
- `raw` (dict, required): A parsed OpenAPI spec dict (as returned by `yaml.safe_load` on `api-external.yaml`).

### Processing
1. `OpenAPISpec.wrap(raw)` is called by each consumer (discovery, execute, generators) to obtain or retrieve a memoized wrapper.
2. The wrapper is keyed by `id(raw)` in a module-level `_WRAPPER_CACHE`; the cache stores exactly one entry so stale wrappers are not retained across spec reloads.
3. All downstream operations (path lookup, `$ref` resolution, schema wrapping) go through this wrapper instance.
4. No mutation of the original `raw` dict occurs.

### Output
- Success: An `OpenAPISpec` instance wrapping `raw`, returned from `_WRAPPER_CACHE` if already present.
- Side effect: `_WRAPPER_CACHE` updated to hold the latest wrapper.

### Acceptance Criteria
- [ ] AC-1: Given a valid spec dict, when `OpenAPISpec.wrap()` is called twice with the same object, then the same wrapper instance is returned both times (cache hit).
- [ ] AC-2: Given a spec dict `A` and then a new dict `B`, when `OpenAPISpec.wrap(B)` is called, then a new wrapper is returned and the cache no longer returns the `A` wrapper.
- [ ] AC-3: Given `None` or an empty dict, when `wrap()` is called, then `None` is returned.
- [ ] AC-4: Given a non-dict input, when `OpenAPISpec.__init__` is called directly, then `TypeError` is raised immediately.

---

## FR-002: Single `$ref` resolution replacing four duplicated implementations

### Description
Replaces the four independent `$ref` resolver copies in `dynamic.py`, `driver.py`, `tool_factory.py`, and `endpoint_discovery.py` with two canonical methods: `OpenAPISpec.resolve_pointer` (single-level, used by code generators) and `OpenAPISpec.resolve_refs` (recursive inlining with cycle detection, used by discovery).

### Input
- For `resolve_pointer`: `ref` (str, required) — a `#/components/...` JSON pointer string.
- For `resolve_refs`: `obj` (any, required), `max_depth` (int, optional, default 10), `depth` (int, optional, default 0), `visited` (frozenset, optional, default empty).

### Processing
**`resolve_pointer`**:
1. Validate that `ref` starts with `#/`; raise `ValueError` otherwise.
2. Split the remainder on `/` and traverse the raw spec dict key by key.
3. Raise `KeyError` if any intermediate key is absent.

**`resolve_refs`**:
1. If `depth > max_depth`, return `{"$ref_truncated": True, "reason": "max_depth_exceeded"}`, `True`.
2. If `obj` is not a dict, return it unchanged.
3. If `obj` has a `$ref` key: check `visited`; if present, return cycle-detected marker. Otherwise, call `resolve_pointer` (catching `KeyError`/`ValueError` → `SCHEMA_REF_NOT_FOUND` marker), then recurse into the resolved target.
4. Otherwise, recurse into each value (dict items and list elements), accumulating `truncated` flag.

### Output
- `resolve_pointer`: The target node (dict, str, list, etc.) at the referenced path.
- `resolve_refs`: `(resolved_obj, truncated_bool)` — `truncated` is `True` if any depth limit or cycle was hit.

### Acceptance Criteria
- [ ] AC-1: Given `#/components/schemas/DSource`, when `resolve_pointer` is called, then the raw `DSource` schema dict is returned.
- [ ] AC-2: Given a ref to a non-existent key `#/components/schemas/NoSuch`, when `resolve_pointer` is called, then `KeyError` is raised.
- [ ] AC-3: Given a schema with a circular `$ref` (`A` → `B` → `A`), when `resolve_refs` is called, then `{"$ref_truncated": True, "reason": "cycle_detected", "ref": ...}` is returned and `truncated=True`.
- [ ] AC-4: Given a deeply nested schema at depth 11 (with `max_depth=10`), when `resolve_refs` is called, then `{"$ref_truncated": True, "reason": "max_depth_exceeded"}` is returned.
- [ ] AC-5: Given a schema with a `$ref` to a missing key, when `resolve_refs` is called, then a `SCHEMA_REF_NOT_FOUND` marker is returned (not an exception propagated to the caller).
- [ ] AC-6: Given the same `$ref` resolution logic, when the output of `OpenAPISpec.resolve_refs` is compared with the former `dynamic.py._resolve_refs` for the same input, then the outputs are identical for all DCT spec schemas.
- [ ] AC-7: Given a top-level list input (e.g., `[{"$ref": "#/components/schemas/DSource"}, "plain"]`), when `resolve_refs` is called, then each dict element is resolved and non-dict elements are left unchanged; the return value is a list (not a dict) and `truncated` accurately reflects whether any element hit a depth or cycle limit.

---

## FR-003: `allOf` merging via `SchemaObject`

### Description
Consolidates the `allOf` merging logic previously found only in `driver.py:resolve_schema_properties` into `SchemaObject._resolve()`, making it available to all consumers (discovery, execute, generators) through a single typed API.

### Input
- `spec` (OpenAPISpec, required): the parent spec wrapper.
- `raw` (dict, required): the raw schema dict (may contain `allOf`, `$ref`, `properties`, `required`).
- `name` (str, optional): the `components/schemas` key for named domain objects.

### Processing
1. If `raw` has a top-level `$ref`, resolve it via `spec.resolve_pointer` to obtain the target schema before proceeding.
2. If the schema has `allOf`:
   a. Iterate over each sub-schema in the `allOf` list.
   b. For `$ref` sub-schemas: resolve via `resolve_pointer`; mark them as `is_ref=True`.
   c. For nested `allOf`: recurse via a child `SchemaObject` and merge its `properties` and `required`.
   d. For flat sub-schemas: accumulate `properties` and `required` directly.
   e. Key-property heuristic: inline sub-schemas and small `$ref` schemas (≤5 properties) contribute to `key_properties`; large base schemas do not.
3. If no `allOf`: `properties` comes from `schema["properties"]`, `required` from `schema["required"]`, `key_properties` = all property names.
4. Cache result in `_resolved` for subsequent accesses.

### Output
- `properties`: merged `dict[str, Any]` of all schema properties.
- `required`: merged `list[str]` of all required field names.
- `key_properties`: `set[str]` of action-specific (non-base-inherited) field names.

### Acceptance Criteria
- [ ] AC-1: Given `DSource` (which uses `allOf` over a large base schema), when `SchemaObject` is instantiated and `.properties` accessed, then all top-level properties from both the base schema and the action-specific sub-schema are present.
- [ ] AC-2: Given `CreateVDBBySnapshotParameters` (which has a large base `allOf` entry and a small inline entry), when `.key_properties` is accessed, then only the small inline entry's property names are returned.
- [ ] AC-3: Given a flat schema with `properties` and `required`, when `SchemaObject._resolve()` is called, then `key_properties` equals all property names.
- [ ] AC-4: Given the same `DSource` schema, when `SchemaObject` output is compared with the former `driver.py:resolve_schema_properties` output, then `properties` and `required` lists are identical.

---

## FR-004: `Operation`, `RequestBody`, and `Response` typed wrappers

### Description
Exposes each API operation's path parameters, request body (with field flattening), and response schema as typed objects — replacing the inline dict traversal in `dynamic.py._flatten_request_body`, `dynamic.py.get_operation_schema`, and related helpers.

### Input
- `Operation`: constructed from `(spec, path, method, raw_op_dict)`.
- `RequestBody`: constructed from `(spec, raw_requestBody_dict)`.
- `Response`: constructed from `(spec, status_code, raw_response_dict)`.

### Processing
**Operation**:
1. Expose `operation_id`, `summary`, `description`, `tags` from the raw op dict.
2. Wrap `parameters` list as `list[Parameter]`.
3. Wrap `requestBody` as `RequestBody | None`.
4. Wrap `responses` dict as `dict[str, Response]`.
5. Extract `path_param_names` via regex on the path template.

**RequestBody.fields()**:
1. Call `schema_object()` to get a `SchemaObject` for the primary media type schema (resolving `$ref`).
2. Iterate over `SchemaObject.properties`; for each property, emit `{name, required, type, description}`.
3. Replace the former `dynamic.py._flatten_request_body`.

**Response.schema_object()**:
1. Iterate over `content` values; return the first `SchemaObject` for a non-empty schema.

### Output
- `Operation.parameters`: `list[Parameter]` with `.name`, `.location`, `.required`, `.schema`.
- `RequestBody.fields()`: `list[dict]` — `{name, required, type, description}` for each body field.
- `RequestBody.required_field_names()`: `list[str]` — top-level required field names (from resolved schema).
- `Response.schema_object()`: `SchemaObject | None`.

### Acceptance Criteria
- [ ] AC-1: Given `POST /vdbs/search` (which has a `requestBody` with a `$ref`), when `op.request_body.fields()` is called, then a non-empty list of field dicts is returned with correct `required` flags.
- [ ] AC-2: Given `GET /vdbs/{vdbId}` (no request body), when `op.request_body` is accessed, then `None` is returned.
- [ ] AC-3: Given `GET /vdbs/{vdbId}`, when `op.path_param_names` is accessed, then `["vdbId"]` is returned.
- [ ] AC-4: Given `POST /vdbs/{vdbId}/refresh_by_timestamp` with a response, when `op.responses["200"].schema_object()` is called, then a `SchemaObject` wrapping the response schema is returned.
- [ ] AC-5: Given the same `POST /vdbs/search` body, when `RequestBody.fields()` output is compared with the former `dynamic.py._flatten_request_body` output, then the field lists are identical.
- [ ] AC-6: Given a request body whose media-type schema has `allOf` at the root level (e.g., `schema: {allOf: [{$ref: "#/components/schemas/BaseParams"}, {properties: {extra: ...}}]}`), when `RequestBody.fields()` is called, then the merged property list from all `allOf` entries is returned (not an empty list). This verifies that `allOf` at the body schema root — not only within `properties` values — is resolved before field extraction.

---

## FR-005: Path template matching centralized in `OpenAPISpec.find_path_item`

### Description
Centralizes the path-template-to-concrete-path matching logic (previously duplicated as `dynamic.py._find_path_item`) in `OpenAPISpec.find_path_item`, so that `operation_at()` and all consumers use a single lookup function.

### Input
- `path` (str, required): a concrete path like `/vdbs/vdb-123` or a template like `/vdbs/{vdbId}`.

### Processing
1. Try exact lookup in `self.paths`.
2. If not found: split both the input path and each spec path on `/`; compare segment by segment.
3. A spec segment that starts with `{` and ends with `}` matches any concrete segment.
4. Return the first match's path-item dict; return `None` if no match.

### Output
- The path-item dict from the spec, or `None` if no template match is found.

### Acceptance Criteria
- [ ] AC-1: Given path `/vdbs/vdb-abc-123`, when `find_path_item` is called, then the path-item for `/vdbs/{vdbId}` is returned.
- [ ] AC-2: Given path `/vdbs` (exact match), when `find_path_item` is called, then the path-item for `/vdbs` is returned without template matching.
- [ ] AC-3: Given path `/nonexistent/path`, when `find_path_item` is called, then `None` is returned.
- [ ] AC-4: Given two spec paths `/vdbs/{vdbId}` and `/vdbs/search`, when `find_path_item("/vdbs/search")` is called, then the exact match `/vdbs/search` is returned (not the parameterized one).

---

## FR-006: Curated domain object subclasses (`DSource`, `VDB`)

### Description
Provides named `DSource` and `VDB` subclasses of `SchemaObject` so that consumers can obtain a semantically typed wrapper for the two highest-value DCT domain objects via `OpenAPISpec.domain_object("DSource")` / `OpenAPISpec.domain_object("VDB")`.

### Input
- `name` (str, required): the `components/schemas` key to look up.

### Processing
1. Check `_schema_object_cache` for the name; return cached instance if present.
2. Look up `schemas[name]`; return `None` if absent.
3. Look up `name` in `_CURATED_DOMAIN_OBJECTS` registry; use the registered class if found, otherwise use `SchemaObject`.
4. Instantiate the class with `(spec, raw_schema, name=name)`.
5. Cache the result in `_schema_object_cache`.

### Output
- `DSource` instance (subclass of `SchemaObject`) when `name="DSource"`.
- `VDB` instance (subclass of `SchemaObject`) when `name="VDB"`.
- Generic `SchemaObject` for any other named schema.
- `None` when the schema key does not exist in the spec.

### Acceptance Criteria
- [ ] AC-1: Given a spec containing `DSource` schema, when `spec.domain_object("DSource")` is called, then a `DSource` instance is returned.
- [ ] AC-2: Given `spec.domain_object("DSource")` called twice, when the second call is made, then the same instance is returned (cache hit, no re-resolution).
- [ ] AC-3: Given `spec.domain_object("SomeUnknownSchema")` where the key exists in `components/schemas`, then a generic `SchemaObject` is returned (not `None`).
- [ ] AC-4: Given a spec where `DSource` is absent from `components/schemas`, when `domain_object("DSource")` is called, then `None` is returned.

---

## FR-007: Consumer refactoring — duplicated traversal removed from four modules

### Description
Removes all standalone `$ref` resolution, `allOf` merging, request-body flattening, and path-template matching code from `dynamic.py`, `driver.py`, `tool_factory.py`, and `endpoint_discovery.py`, replacing each call site with the equivalent `spec_model` API.

### Input
- Existing call sites in the four modules that currently operate on raw spec dicts.

### Processing
1. `dynamic.py`: replace `_resolve_refs`, `_find_path_item`, `_flatten_request_body`, and inline `allOf`/`$ref` traversal with `OpenAPISpec.wrap()` + model calls.
2. `driver.py`: replace `resolve_ref`, `resolve_schema_properties`, and related helpers with `OpenAPISpec.resolve_pointer` / `SchemaObject`.
3. `tool_factory.py`: replace `_resolve_ref` and inline schema traversal with `OpenAPISpec.resolve_pointer`.
4. `endpoint_discovery.py`: replace inline `paths` traversal with `spec.operations()` iteration.

### Output
- The four modules no longer contain standalone `$ref` resolution functions.
- All behaviors exposed to the MCP layer (endpoint selection, parameter extraction, body validation, tool generation) remain identical.

### Acceptance Criteria
- [ ] AC-1: After refactoring, `grep -r "def resolve_ref\|def _resolve_ref\|def _resolve_refs\|def _flatten_request_body\|def _find_path_item" src/` returns no matches.
- [ ] AC-2: All existing pytest tests pass without modifying any test assertions.
- [ ] AC-3: Given a live DCT instance, when `dynamic.py` discovery is invoked, then the same endpoints are returned as before the refactor.
- [ ] AC-4: Given a live DCT instance, when `dynamic.py` execute is invoked for a parameterized endpoint, then the request is dispatched correctly (no 404 from path mismatch).

---

## Quality Rules

| Rule | Description | Enforcement | Status | Evidence |
|------|-------------|-------------|--------|----------|
| API backward compatibility | No change to MCP tool signatures, toolset action names, or HTTP client behavior | Automated: `git diff main -- src/dct_mcp_server/tools/*_endpoints_tool.py src/dct_mcp_server/dct_client/client.py` must produce no output in the PR diff; verified in code review checklist | Pending | — |
| Behavior parity | Refactored consumers produce identical output to pre-refactor for all DCT spec inputs | Automated: `tests/test_spec_model.py` parametrizes over known DCT spec shapes (`DSource`, `VDB`, `CreateVDBBySnapshotParameters`) and asserts `.properties` and `.required` are identical between old and new code paths; must pass in CI | Pending | — |
| No new dependencies | `spec_model.py` imports only stdlib and existing `core/` modules | Automated CI check: `python -c "import dct_mcp_server.tools.core.spec_model"` followed by `pip list --format=freeze > before.txt && pip install -e . && pip list --format=freeze > after.txt && diff before.txt after.txt` must show no new packages | Pending | — |
| Python 3.11+ only | `spec_model.py` must not use compatibility shims for Python < 3.11 and may freely use 3.11+ features | Automated: `pyupgrade --py311-plus src/dct_mcp_server/tools/core/spec_model.py` must produce no changes; `python --version` in CI must be 3.11.x or higher | Pending | — |
| FastMCP isolation | `spec_model.py` must not import from `fastmcp`, register tools, or access FastMCP application state | Automated: `grep -n "fastmcp\|@app\." src/dct_mcp_server/tools/core/spec_model.py` must return no matches | Pending | — |
| Dead code removed | Former `$ref` resolver functions deleted, not just shadowed | Automated CI grep step: `grep -rn "def resolve_ref\b\|def _resolve_ref\b\|def _resolve_refs\b\|def _flatten_request_body\b\|def _find_path_item\b" src/dct_mcp_server/tools/core/dynamic.py src/dct_mcp_server/toolsgenerator/driver.py src/dct_mcp_server/tools/core/tool_factory.py src/dct_mcp_server/tools/core/endpoint_discovery.py` must return exit code 1 (no matches) | Pending | — |
| Test coverage | `spec_model.py` line coverage ≥ 85% measured by `pytest-cov`; branch coverage ≥ 75% | Automated: `pytest --cov=dct_mcp_server.tools.core.spec_model --cov-report=term-missing --cov-fail-under=85 tests/test_spec_model.py`; CI fails if threshold is not met | Pending | — |

---

## Edge Cases

- EC-1: Spec loaded as `None` or empty dict → `OpenAPISpec.wrap()` returns `None`; all callers guard against `None` before calling methods.
- EC-2: Schema with circular `$ref` (e.g., `A.$ref → B`, `B.properties.x.$ref → A`) → `resolve_refs` detects the cycle via `visited` frozenset; emits `{"$ref_truncated": True, "reason": "cycle_detected"}` and returns `truncated=True` without infinite recursion.
- EC-3: Two callers call `resolve_refs` concurrently with different `visited` sets for the same starting object → no shared mutable state between calls; each call uses its own `frozenset` accumulation (immutable, functional style).
- EC-4: `allOf` sub-schema is itself an `allOf` (multi-level composition) → `SchemaObject._resolve()` instantiates a child `SchemaObject` for the nested `allOf` and merges its `properties`/`required` up.
- EC-5: `$ref` in `allOf` entry points to a non-existent schema → `resolve_pointer` raises `KeyError`; `_resolve` propagates this upward; caller must handle absent schema gracefully.
- EC-6: Spec with zero `paths` entries → `operations()` yields nothing; `find_path_item` returns `None` for any input.
- EC-7: Path segment comparison where spec has `/vdbs/{vdbId}` and input is `/vdbs/` (trailing slash mismatch) → segment count differs; no match returned.
- EC-8: `domain_object()` called on a schema whose `$ref` points to another schema that itself uses `allOf` → `SchemaObject._resolve` handles the nested resolution via recursive `resolve_pointer` + `allOf` iteration.
- EC-9: Spec reload mid-operation (new dict object replaces old one in the cache) → `_WRAPPER_CACHE` is replaced atomically (dict assignment); the old wrapper and its `_schema_object_cache` are GC'd; consumers that hold a reference to the old `OpenAPISpec` instance continue using stale data until they call `wrap()` again.
- EC-10: `RequestBody.fields()` called on a body where the primary schema has no `properties` (e.g., free-form JSON `{}`) → `SchemaObject.properties` returns `{}`; `fields()` returns `[]`.
- EC-11: Concurrent spec reload during cache invalidation — two coroutines call `OpenAPISpec.wrap()` at the same instant: coroutine A passes old dict `D1`, coroutine B passes new dict `D2`. CPython's GIL ensures each dict assignment to `_WRAPPER_CACHE` is atomic. The last writer wins; the earlier caller's `OpenAPISpec` instance remains valid for the lifetime of that call but will not be returned by subsequent `wrap()` calls. No corruption occurs because `_WRAPPER_CACHE` is replaced as a whole unit, not mutated in place.
- EC-12: `RequestBody.fields()` called on a request body whose media-type schema has `allOf` at the body level (not inside `properties`) — e.g., `requestBody.content["application/json"].schema = {"allOf": [...]}` rather than `{"properties": {...}}`. `RequestBody.schema_object()` must pass the raw schema dict (including the top-level `allOf`) to `SchemaObject`; `SchemaObject._resolve()` then merges the `allOf` entries before `fields()` iterates `.properties`. A body where `allOf` is the root key (not nested under `properties`) must not return `[]` from `fields()`.
- EC-13: `resolve_refs` called with a list at the top level (not a dict) — e.g., `resolve_refs([{"$ref": "#/components/schemas/Foo"}, "plain_string"])`. The method must iterate list elements, resolving any element that is a dict containing `$ref`, and leave non-dict elements (strings, ints) unchanged. The return value is a new list (not a dict) and `truncated` reflects whether any element triggered depth-limit or cycle-detection. This matches the behavior of the former `dynamic.py._resolve_refs` which handled list traversal in the same pass.

## Error Scenarios

- ERR-1: `resolve_pointer` called with an external `$ref` (not starting with `#/`) → `ValueError` raised immediately; caller must not pass external URLs; document restriction in docstring.
- ERR-2: Spec YAML is malformed and `yaml.safe_load` produces a non-dict root → `OpenAPISpec.__init__` raises `TypeError("OpenAPISpec expects a dict, ...")`; `wrap()` propagates this to the caller.
- ERR-3: `SchemaObject._resolve()` encounters `resolve_pointer` raising `KeyError` for a missing `$ref` target mid-`allOf` → the exception propagates out of `_resolve()` uncaught. Recovery responsibility lies with the caller: `endpoint_discovery.py` wraps each `operation_at()` call in a `try/except KeyError` block; on exception it calls `logger.warning("Skipping operation %s %s: unresolvable $ref — %s", method, path, e)` and continues iteration to the next operation (the broken operation is omitted from the discovered endpoint list). `driver.py` and `tool_factory.py` similarly wrap their per-schema resolution calls; on `KeyError` they log at `WARNING` and emit an empty properties dict (`{}`) so tool generation produces a valid (but parameter-less) tool entry rather than crashing the entire generation run.
- ERR-4: `OpenAPISpec.wrap()` called after Python GC has reused the `id` of a previously freed spec dict → new dict produces a new cache key because `id(raw)` refers to the new dict and the new `OpenAPISpec` is built; there is no false cache hit because the old dict no longer exists at that address.
- ERR-5: `RequestBody.required_field_names()` called on a body whose resolved schema is not a dict (e.g., a raw `string` type schema, or `true`/`false` boolean schemas used by some OpenAPI 3.0 permissive bodies) → `isinstance(resolved, dict)` check returns `False`; method returns `[]` safely. The caller (`dynamic.py` execute path) interprets `[]` as "no required fields"; it proceeds to dispatch the HTTP request without body-field validation, relying on the DCT API to return a `422` if required fields are missing. No exception is raised and no warning is logged for this case — it is a normal code path for endpoints that accept free-form bodies.

## Performance Considerations

- `OpenAPISpec.wrap()` uses an identity-keyed class-level cache (`_WRAPPER_CACHE`) so the wrapper construction cost (O(1) — no traversal at wrap time) is paid at most once per unique spec dict object. Discovery and execute calls (which may run dozens of times per session) get a free cache hit.
- `SchemaObject._resolve()` memoizes its result on the instance in `_resolved`. For named domain objects, instances are cached in `OpenAPISpec._schema_object_cache`. For inline schemas (created per-call inside `RequestBody.fields()`), resolution runs once per `RequestBody` instantiation — this is bounded by the number of operations traversed in a single discovery or execute call.
- `OpenAPISpec.operations()` is a generator — it does not materialize all ~700 operations at once. Consumers (`endpoint_discovery.py`) that iterate it once and build an index pay the traversal cost once at startup.
- `resolve_refs` is bounded by `max_depth=10` and the cycle-detection `frozenset`; worst-case cost is O(spec_size) but is practically bounded by the depth limit. No LRU cache is applied because the `visited` parameter makes the function context-dependent.

---
<!-- Cross-reference: FR descriptions map to Goals (G1-G4) in the vision doc.
     FR Acceptance Criteria satisfy Success Criteria (SC1-SC5).
     Quality Rules and Edge Cases address Constraints and Risks from the vision doc.
     FR-IDs defined here are referenced in tasks-template (Spec References) and validation-template (FR Coverage). -->
