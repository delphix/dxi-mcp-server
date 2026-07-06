# Test Plan: DLPXECO-14248

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-14248
**Derived from**: `docs/DLPXECO-14248/DLPXECO-14248-design.md` `## Affected Components` and `## Version Compatibility`

<!-- Guidance: This file is the authoritative list of scenarios for the test-generation phase.
     Every row in `## Scenarios` becomes one test() / it() / def test_* block in `.claude/test/generated-test/`.
     If a scenario row cannot be expressed as a real assertion, refine the row — do not weaken the generated test. -->

---

## Test Approach

Unit tests using `pytest` + `pytest-asyncio` in the `tests/` directory, exercising `spec_model.py` in isolation by constructing synthetic spec dicts — no live DCT instance is required. Behavior-parity tests load a real `api-external.yaml` (from `docs/api-external.yaml`) to assert that `spec_model.py` output is byte-identical to pre-refactor output from the former consumer functions.

## Environment / Landscape

- **Landscape**: Local Python 3.11+ environment with `uv sync` / `pip install -e .`
- **Service under test**: `src/dct_mcp_server/tools/core/spec_model.py` (pure library; no server startup needed)
- **VMs to provision**: None — all tests are pure-Python unit tests; no DCT host required
- **Spec fixture**: `docs/api-external.yaml` (bundled spec) used for behavior-parity scenarios; synthetic dicts used for unit scenarios

## Versions to Cover

| Version | Why | Required? |
|---------|-----|-----------|
| Python 3.11 | Minimum declared runtime; spec_model.py targets 3.11+ | Yes |
| Python 3.12 | Next supported runtime in CI | Yes (smoke-only) |

## Scenarios

| # | Scenario | Maps to FR | Versions | Expected outcome |
|---|----------|-----------|----------|------------------|
| S1 | `OpenAPISpec.wrap()` called twice with the same dict returns the same instance | FR-001 | Python 3.11 | `wrap(d) is wrap(d)` — both calls return identical object |
| S2 | `OpenAPISpec.wrap()` called with dict B after dict A returns a new instance and old cache is replaced | FR-001 | Python 3.11 | `wrap(B) is not wrap(A)` after B call; `wrap(A)` returns new instance not equal to prior A wrapper |
| S3 | `OpenAPISpec.wrap(None)` returns `None` | FR-001 | Python 3.11 | Return value is `None` |
| S4 | `OpenAPISpec.wrap({})` returns `None` | FR-001 | Python 3.11 | Return value is `None` (falsy empty dict) |
| S5 | `OpenAPISpec.__init__` raises `TypeError` for non-dict input (e.g., a string) | FR-001 | Python 3.11 | `TypeError` raised with message containing "OpenAPISpec expects a dict" |
| S6 | `resolve_pointer("#/components/schemas/DSource")` returns the raw DSource schema dict from a real spec | FR-002 | Python 3.11 | Returned dict has `"properties"` key; no exception raised |
| S7 | `resolve_pointer` raises `KeyError` for a non-existent schema key `#/components/schemas/NoSuchSchema` | FR-002 | Python 3.11 | `KeyError` raised |
| S8 | `resolve_pointer` raises `ValueError` for a ref not starting with `#/` | FR-002 | Python 3.11 | `ValueError` raised with message containing "Unsupported ref format" |
| S9 | `resolve_refs` with a synthetic circular schema (`A.$ref → B`, `B.$ref → A`) returns cycle-detected marker and `truncated=True` | FR-002 | Python 3.11 | Return value is `({"$ref_truncated": True, "reason": "cycle_detected", "ref": ...}, True)` |
| S10 | `resolve_refs` on a schema at depth 11 with `max_depth=10` returns max-depth marker | FR-002 | Python 3.11 | Return value is `({"$ref_truncated": True, "reason": "max_depth_exceeded"}, True)` |
| S11 | `resolve_refs` with a `$ref` to a missing key returns SCHEMA_REF_NOT_FOUND marker, not an exception | FR-002 | Python 3.11 | Return value is `({"status": "error", "code": "SCHEMA_REF_NOT_FOUND", ...}, False)`; no exception propagated |
| S12 | `resolve_refs` output for DSource schema matches former `dynamic.py._resolve_refs` output byte-for-byte | FR-002 | Python 3.11 | `assert resolved_new == resolved_old` on DSource raw schema from bundled spec |
| S13 | `resolve_refs` called with a top-level list resolves dict elements and leaves strings unchanged | FR-002 | Python 3.11 | Return value is a list; dict element with `$ref` is resolved; string element unchanged; `truncated` reflects any depth/cycle hits |
| S14 | `SchemaObject` for `DSource` (allOf-composed) exposes all properties from both base and action-specific sub-schemas | FR-003 | Python 3.11 | `.properties` dict is non-empty and contains fields from both base and inline sub-schema entries |
| S15 | `SchemaObject.key_properties` for `CreateVDBBySnapshotParameters` returns only the small inline entry's property names (not the large base) | FR-003 | Python 3.11 | `key_properties` is a subset of all properties; large base schema properties are absent from `key_properties` |
| S16 | `SchemaObject` for a flat schema (no allOf) has `key_properties` equal to all property names | FR-003 | Python 3.11 | `key_properties == set(properties.keys())` |
| S17 | `SchemaObject` for `DSource` produces identical `properties` and `required` to former `driver.py:resolve_schema_properties` | FR-003 | Python 3.11 | `obj.properties == old_props` and `obj.required == old_required` using bundled spec |
| S18 | `op.request_body.fields()` for `POST /vdbs/search` returns a non-empty list with correct `required` flags | FR-004 | Python 3.11 | List is non-empty; each element has `name`, `required`, `type`, `description` keys; `required` values match spec |
| S19 | `op.request_body` for `GET /vdbs/{vdbId}` is `None` | FR-004 | Python 3.11 | `op.request_body is None` |
| S20 | `op.path_param_names` for `GET /vdbs/{vdbId}` returns `["vdbId"]` | FR-004 | Python 3.11 | `op.path_param_names == ["vdbId"]` |
| S21 | `op.responses["200"].schema_object()` for `POST /vdbs/{vdbId}/refresh_by_timestamp` returns a `SchemaObject` | FR-004 | Python 3.11 | Return value is a `SchemaObject` instance (not `None`) |
| S22 | `RequestBody.fields()` output for `POST /vdbs/search` is identical to former `dynamic.py._flatten_request_body` output | FR-004 | Python 3.11 | `new_fields == old_fields` (same list contents, same order) |
| S23 | `RequestBody.fields()` for a body whose media-type schema has `allOf` at root level returns non-empty merged property list | FR-004 | Python 3.11 | `len(fields) > 0`; fields contain properties from all `allOf` entries |
| S24 | `find_path_item("/vdbs/vdb-abc-123")` returns path-item for `/vdbs/{vdbId}` | FR-005 | Python 3.11 | Returned dict is the same object as `spec.paths["/vdbs/{vdbId}"]` |
| S25 | `find_path_item("/vdbs")` exact match returns path-item without template matching | FR-005 | Python 3.11 | Returned dict is `spec.paths["/vdbs"]` |
| S26 | `find_path_item("/nonexistent/path")` returns `None` | FR-005 | Python 3.11 | Return value is `None` |
| S27 | `find_path_item("/vdbs/search")` returns `/vdbs/search` exact match, not `/vdbs/{vdbId}` | FR-005 | Python 3.11 | Returned dict is `spec.paths["/vdbs/search"]` (not the parameterized path item) |
| S28 | `spec.domain_object("DSource")` returns a `DSource` instance | FR-006 | Python 3.11 | `isinstance(result, DSource)` is `True` |
| S29 | `spec.domain_object("DSource")` called twice returns the same cached instance | FR-006 | Python 3.11 | `spec.domain_object("DSource") is spec.domain_object("DSource")` |
| S30 | `spec.domain_object("SomeKnownSchema")` for a schema that exists but has no curated subclass returns a generic `SchemaObject` | FR-006 | Python 3.11 | `type(result) is SchemaObject` (not `DSource` or `VDB`) and result is not `None` |
| S31 | `spec.domain_object("DSource")` when `DSource` absent from `components/schemas` returns `None` | FR-006 | Python 3.11 | Return value is `None` |
| S32 | After refactoring, grep for `def _resolve_refs\|def _flatten_request_body\|def _find_path_item` in the four consumer modules returns no standalone (non-wrapper) implementations | FR-007 | Python 3.11 | Shell command exits with code 1 (no matches) |
| S33 | All pre-existing pytest tests pass without modifying any test assertions after the refactor | FR-007 | Python 3.11 | `pytest tests/ -v` exit code 0; no assertion failures |
| S34 | `spec_model.py` line coverage ≥ 85% and branch coverage ≥ 75% measured by `pytest-cov` | FR-007 | Python 3.11 | `pytest --cov=dct_mcp_server.tools.core.spec_model --cov-fail-under=85 tests/test_spec_model.py` exits 0 |
| S35 | `spec_model.py` has no imports from `fastmcp` or `@app.` decorators | FR-001 | Python 3.11 | `grep -n "fastmcp\|@app\." src/dct_mcp_server/tools/core/spec_model.py` returns no matches |
| S36 | `python -c "import dct_mcp_server.tools.core.spec_model"` succeeds with no new packages added | FR-001 | Python 3.11 | Import exits 0; `pip list` diff shows no new packages relative to pre-feature baseline |

## Out of Scope

- Live DCT API calls — this feature is a pure internal refactor; behavior parity is validated against the bundled spec, not a live DCT instance (Non-Goal NG4 — no MCP tool surface changes)
- Runtime payload validation (Pydantic models) — Non-Goal NG1
- Build-time code generation — Non-Goal NG2
- Full OpenAPI 3.0 compliance (`oneOf`, `anyOf`, discriminators, external `$ref` URLs) — Non-Goal NG3
- Load/performance testing of `spec_model.py` — out of scope; the performance section of the functional spec documents the memoization properties but does not require benchmark assertions

## Test Data Requirements

- `docs/api-external.yaml` (bundled spec) — used as a real-world fixture for behavior-parity scenarios (S12, S17, S22); must exist in the repo at the path `docs/api-external.yaml` relative to the worktree root
- Synthetic spec dicts — constructed inline in test functions for unit isolation (all other scenarios); no external fixtures required
- Pre-refactor output snapshots — for S12, S17, S22: the "former" function behavior is captured by calling the thin wrapper functions (`resolve_ref`, `resolve_schema_properties`, `_flatten_request_body`) that still delegate to `spec_model.py`; parity is tested by comparing output of two calling conventions on the same input

## Exit Criteria

- All Required scenarios (S1–S36) PASS on Python 3.11
- Smoke suite (existing tests in `tests/` excluding DLPXECO-14248 test file) PASSes
- No scenario marked SKIPPED without a documented reason
- `pytest-cov` reports line coverage ≥ 85% for `spec_model.py`

---
<!-- Cross-references:
     - Each Scenario row → drives one test block in .claude/test/generated-test/$NAME.spec.* (test-generation phase)
     - Each FR in docs/$NAME/$NAME-functional.md → at least one scenario here (otherwise the FR is untested)
     - Versions column → must be a subset of docs/$NAME/$NAME-design.md ## Version Compatibility "Supported = Yes"
     Validation: feature-executor.md Phase: test-generation Step 2 treats this file as authoritative. -->
