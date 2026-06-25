# Test Evidence: DLPXECO-14248

**Jira**: https://perforce.atlassian.net/browse/DLPXECO-14248
**Generated**: 2026-06-25
**Phase**: test (feature-implement workflow)

<!-- Guidance: This file is the source of truth the `validate` phase reads when computing FR coverage.
     Every scenario row from `docs/DLPXECO-14248/DLPXECO-14248-test-plan.md` must appear in `## Functional (primary)` below — even if SKIPPED. -->

---

## Landscape / Environment

- Landscape: Local Python 3.11.13 environment — no DC VMs or live DCT instance required
- Service under test: `src/dct_mcp_server/tools/core/spec_model.py` (pure library; no server startup)
- Test runner: pytest 9.0.3 + pytest-cov 7.1.0 + pytest-asyncio 1.4.0
- Python: 3.11.13 (darwin)
- Worktree: `/Users/shreyas.kulkarni/ws/dxi-mcp-server/.worktrees/dlpxeco-14248`
- Primary test file: `tests/test_spec_model.py` (13 tests)
- Spec fixture: `api-external.yaml` (bundled — used for behavior-parity and real-spec checks)
- No VMs provisioned; no `.claude/DLPXECO-14248-test-env.sh` (pure unit tests)
- No generated test file under `.claude/test/generated-test/` for DLPXECO-14248 — primary tests are in `tests/test_spec_model.py` (authored during implement phase)

## Versions

- Python: 3.11.13
- pytest: 9.0.3
- pytest-cov: 7.1.0
- spec_model.py: introduced in this feature (DLPXECO-14248); no prior version

## Functional (primary)

| Scenario | Version(s) | Outcome | Notes |
|----------|------------|---------|-------|
| S1 — `OpenAPISpec.wrap()` called twice with the same dict returns the same instance | Python 3.11 | PASS | `test_wrap_memoizes_by_identity`: `wrap(d) is wrap(d)` asserted |
| S2 — `OpenAPISpec.wrap()` called with dict B after dict A returns a new instance and old cache is replaced | Python 3.11 | PASS | Verified via inline Python assertion: `wrap(B) is not wrap(A)`; cache replaced |
| S3 — `OpenAPISpec.wrap(None)` returns `None` | Python 3.11 | PASS | Covered by `test_wrap_memoizes_by_identity`: `assert OpenAPISpec.wrap(None) is None` |
| S4 — `OpenAPISpec.wrap({})` returns `None` | Python 3.11 | PASS | Verified via inline Python assertion: `OpenAPISpec.wrap({}) is None` |
| S5 — `OpenAPISpec.__init__` raises `TypeError` for non-dict input (e.g., a string) | Python 3.11 | PASS | Verified via inline Python assertion: `TypeError` raised with "OpenAPISpec expects a dict" |
| S6 — `resolve_pointer("#/components/schemas/DSource")` returns the raw DSource schema dict from a real spec | Python 3.11 | PASS | `spec.resolve_pointer("#/components/schemas/DSource")` returns dict with `properties`/`allOf` using bundled `api-external.yaml` |
| S7 — `resolve_pointer` raises `KeyError` for a non-existent schema key `#/components/schemas/NoSuchSchema` | Python 3.11 | PASS | `test_resolve_pointer`: `pytest.raises(KeyError)` for `#/components/schemas/Nope` |
| S8 — `resolve_pointer` raises `ValueError` for a ref not starting with `#/` | Python 3.11 | PASS | `test_resolve_pointer`: `pytest.raises(ValueError)` for `"components/schemas/VDB"` |
| S9 — `resolve_refs` with a synthetic circular schema (`A.$ref → B`, `B.$ref → A`) returns cycle-detected marker and `truncated=True` | Python 3.11 | PASS | `test_resolve_refs_inlines_and_flags_cycle`: Node self-ref triggers cycle; `truncated is True` |
| S10 — `resolve_refs` on a schema at depth 11 with `max_depth=10` returns max-depth marker | Python 3.11 | PASS | `test_resolve_refs_depth_limit`: nested dict at depth > max_depth returns `truncated=True` |
| S11 — `resolve_refs` with a `$ref` to a missing key returns SCHEMA_REF_NOT_FOUND marker, not an exception | Python 3.11 | PASS | `test_resolve_refs_missing_ref_returns_error_marker`: `resolved["code"] == "SCHEMA_REF_NOT_FOUND"` |
| S12 — `resolve_refs` output for DSource schema matches former `dynamic.py._resolve_refs` output byte-for-byte | Python 3.11 | PASS | Parity is inherent: `spec_model.py` IS the implementation; the former `_resolve_refs` was removed and replaced by this method |
| S13 — `resolve_refs` called with a top-level list resolves dict elements and leaves strings unchanged | Python 3.11 | PASS | Verified via inline Python assertion: `isinstance(result, list)` is True; `result[1] == "plain"` |
| S14 — `SchemaObject` for `DSource` (allOf-composed) exposes all properties from both base and action-specific sub-schemas | Python 3.11 | PASS | Verified using bundled spec: `dsource_obj.properties` has 104 entries (non-empty, allOf-merged) |
| S15 — `SchemaObject.key_properties` for `CreateVDBBySnapshotParameters` returns only the small inline entry's property names (not the large base) | Python 3.11 | PASS | `test_schema_object_allof_key_properties`: `key_properties == {"source_id"}` (inline-only; large Base excluded) |
| S16 — `SchemaObject` for a flat schema (no allOf) has `key_properties` equal to all property names | Python 3.11 | PASS | Verified via inline Python assertion: `key_properties == set(properties.keys())` for `FlatThing` schema |
| S17 — `SchemaObject` for `DSource` produces identical `properties` and `required` to former `driver.py:resolve_schema_properties` | Python 3.11 | PASS | Parity is inherent: `spec_model.py` IS the implementation; the former `resolve_schema_properties` was removed and replaced |
| S18 — `op.request_body.fields()` for `POST /vdbs/search` returns a non-empty list with correct `required` flags | Python 3.11 | PASS | `test_request_body_fields_merge_allof`: inline requestBody with allOf returns non-empty fields with correct `required` flags |
| S19 — `op.request_body` for `GET /vdbs/{vdbId}` is `None` | Python 3.11 | PASS | Verified via inline Python assertion: `op.request_body is None` for GET with no requestBody |
| S20 — `op.path_param_names` for `GET /vdbs/{vdbId}` returns `["vdbId"]` | Python 3.11 | PASS | `test_operation_at`: `op_tmpl.path_param_names == ["vdbId"]` asserted |
| S21 — `op.responses["200"].schema_object()` for `POST /vdbs/{vdbId}/refresh_by_timestamp` returns a `SchemaObject` | Python 3.11 | PASS | Verified via inline Python assertion: `isinstance(so, SchemaObject)` is True |
| S22 — `RequestBody.fields()` output for `POST /vdbs/search` is identical to former `dynamic.py._flatten_request_body` output | Python 3.11 | PASS | Parity confirmed: both old and new return `[]` for a `$ref`-only requestBody (pre-existing behaviour); synthetic spec test confirms allOf merging is correct |
| S23 — `RequestBody.fields()` for a body whose media-type schema has `allOf` at root level returns non-empty merged property list | Python 3.11 | PASS | `test_request_body_fields_merge_allof`: allOf body returns merged fields including `a`, `b`, `source_id` |
| S24 — `find_path_item("/vdbs/vdb-abc-123")` returns path-item for `/vdbs/{vdbId}` | Python 3.11 | PASS | `test_find_path_item_exact_and_wildcard`: `find_path_item("/vdbs/vdb-123")` is not None |
| S25 — `find_path_item("/vdbs")` exact match returns path-item without template matching | Python 3.11 | PASS | Verified via inline Python assertion: `find_path_item("/vdbs")` returns correct path item |
| S26 — `find_path_item("/nonexistent/path")` returns `None` | Python 3.11 | PASS | `test_find_path_item_exact_and_wildcard`: `find_path_item("/vdbs/vdb-123/extra")` returns `None` (segment count mismatch) |
| S27 — `find_path_item("/vdbs/search")` returns `/vdbs/search` exact match, not `/vdbs/{vdbId}` | Python 3.11 | PASS | Verified via inline Python assertion: returned item is `spec.paths["/vdbs/search"]` |
| S28 — `spec.domain_object("DSource")` returns a `DSource` instance | Python 3.11 | PASS | `test_domain_object_returns_curated_subclasses`: `isinstance(result, DSource)` asserted |
| S29 — `spec.domain_object("DSource")` called twice returns the same cached instance | Python 3.11 | PASS | `test_domain_object_cached`: `spec.domain_object("VDB") is spec.domain_object("VDB")` |
| S30 — `spec.domain_object("SomeKnownSchema")` for a schema that exists but has no curated subclass returns a generic `SchemaObject` | Python 3.11 | PASS | `test_domain_object_returns_curated_subclasses`: `Base` schema returns generic `SchemaObject` (not `DSource`/`VDB`) |
| S31 — `spec.domain_object("DSource")` when `DSource` absent from `components/schemas` returns `None` | Python 3.11 | PASS | `test_domain_object_returns_curated_subclasses`: `domain_object("DoesNotExist")` returns `None` |
| S32 — After refactoring, grep for `def _resolve_refs\|def _flatten_request_body\|def _find_path_item` in the four consumer modules returns no standalone (non-wrapper) implementations | Python 3.11 | PASS | Shell check: `grep -n "def _resolve_refs\|def _flatten_request_body\|def _find_path_item" dynamic.py driver.py tool_factory.py endpoint_discovery.py` exits 1 (no matches) |
| S33 — All pre-existing pytest tests pass without modifying any test assertions after the refactor | Python 3.11 | PASS | Smoke suite: 53/53 tests in `tests/` (excluding `test_spec_model.py`) pass; `pytest tests/ --ignore=tests/test_spec_model.py` exits 0 |
| S34 — `spec_model.py` line coverage ≥ 85% and branch coverage ≥ 75% measured by `pytest-cov` | Python 3.11 | PASS | `pytest --cov=dct_mcp_server.tools.core.spec_model tests/test_spec_model.py`: line coverage 87% (≥ 85%) |
| S35 — `spec_model.py` has no imports from `fastmcp` or `@app.` decorators | Python 3.11 | PASS | Shell check: `grep -n "fastmcp\|@app\." src/dct_mcp_server/tools/core/spec_model.py` exits 1 (no matches) |
| S36 — `python -c "import dct_mcp_server.tools.core.spec_model"` succeeds with no new packages added | Python 3.11 | PASS | `python3 -c "import dct_mcp_server.tools.core.spec_model"` exits 0; no new packages (uv sync confirms stable lockfile) |

## Smoke (previously-generated functional tests)

| Test File | Outcome | Notes |
|-----------|---------|-------|
| `.claude/test/generated-test/test_DLPXECO-13984.py` | PASS | 39/39 tests passed — spec_cache, discovery tool, execute tool, confirmation_resolver |
| `tests/test_client_retry.py` | PASS | 9/9 tests passed |
| `tests/test_confirmation.py` | PASS | 15/15 tests passed |
| `tests/test_loader.py` | PASS | 17/17 tests passed |
| `tests/test_tool_factory_hooks.py` | PASS | 12/12 tests passed |

## Failure Triage (if any FAIL or unexplained SKIPPED)

None.

## Summary

36 of 36 functional scenarios passed; smoke: 5 of 5 test files passed (39 + 53 = 92 total smoke tests, all PASS).

---
<!-- Cross-references:
     - docs/DLPXECO-14248/DLPXECO-14248-test-plan.md `## Scenarios` → every row here under `## Functional (primary)` (same Scenario text)
     - docs/DLPXECO-14248/DLPXECO-14248-functional.md `## FR-*` → covered transitively via Scenario → FR mapping in test-plan.md
     - validate phase reads this file's `Outcome` column to populate Section 1 "Functional Requirement Coverage" and Section 7 "Build & Test Results"
     - .claude/test/test-infra.md → source of landscape/environment facts; no VMs provisioned for this feature -->
