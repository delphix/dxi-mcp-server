"""Tests for the shared OpenAPI object model (tools/core/spec_model.py).

These exercise the centralized $ref/allOf resolution, path-template matching,
request-body flattening, and curated domain objects that discovery/execute and
the code generators now all delegate to.
"""

from __future__ import annotations

import pytest

from dct_mcp_server.tools.core.spec_model import (
    DSource,
    OpenAPISpec,
    RequestBody,
    SchemaObject,
    VDB,
)


@pytest.fixture
def spec_dict() -> dict:
    """A small but representative spec: $ref, allOf, cycle, and path templates."""
    return {
        "openapi": "3.0.0",
        "paths": {
            "/vdbs/{vdbId}": {
                "get": {
                    "operationId": "get_vdb_by_id",
                    "summary": "Get a VDB",
                    "tags": ["VDBs"],
                    "parameters": [
                        {"name": "vdbId", "in": "path", "required": True,
                         "schema": {"type": "string"}},
                    ],
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/VDB"}}},
                        }
                    },
                },
            },
            "/dsources/link": {
                "post": {
                    "operationId": "link_dsource",
                    "summary": "Link a dSource",
                    "tags": ["dSources"],
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/LinkParams"}}},
                    },
                    "responses": {"200": {"description": "ok"}},
                },
            },
        },
        "components": {
            "schemas": {
                "VDB": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}, "name": {"type": "string"}},
                },
                "DSource": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                },
                # >5 properties so it counts as a large inherited base schema
                # (its props are excluded from key_properties).
                "Base": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "string"}, "b": {"type": "string"},
                        "c": {"type": "string"}, "d": {"type": "string"},
                        "e": {"type": "string"}, "f": {"type": "string"},
                    },
                    "required": ["a"],
                },
                "LinkParams": {
                    "required": ["source_id"],
                    "allOf": [
                        {"$ref": "#/components/schemas/Base"},
                        {"type": "object",
                         "properties": {"source_id": {"type": "string",
                                                      "description": "the source"}},
                         "required": ["source_id"]},
                    ],
                },
                # Self-referential schema to exercise cycle detection.
                "Node": {
                    "type": "object",
                    "properties": {"child": {"$ref": "#/components/schemas/Node"}},
                },
            }
        },
    }


# --------------------------------------------------------------------------- #
# OpenAPISpec
# --------------------------------------------------------------------------- #

def test_wrap_memoizes_by_identity(spec_dict):
    a = OpenAPISpec.wrap(spec_dict)
    b = OpenAPISpec.wrap(spec_dict)
    assert a is b
    assert OpenAPISpec.wrap(None) is None


def test_resolve_pointer(spec_dict):
    spec = OpenAPISpec(spec_dict)
    assert spec.resolve_pointer("#/components/schemas/VDB")["type"] == "object"
    with pytest.raises(ValueError):
        spec.resolve_pointer("components/schemas/VDB")  # missing leading #/
    with pytest.raises(KeyError):
        spec.resolve_pointer("#/components/schemas/Nope")


def test_resolve_refs_inlines_and_flags_cycle(spec_dict):
    spec = OpenAPISpec(spec_dict)
    resolved, truncated = spec.resolve_refs({"$ref": "#/components/schemas/VDB"})
    assert resolved["properties"]["id"]["type"] == "string"
    assert truncated is False

    # The self-referential Node schema must terminate and flag truncation.
    resolved, truncated = spec.resolve_refs({"$ref": "#/components/schemas/Node"})
    assert truncated is True


def test_resolve_refs_depth_limit(spec_dict):
    spec = OpenAPISpec(spec_dict)
    nested = {"a": {"b": {"c": {"d": {"e": "deep"}}}}}
    _, truncated = spec.resolve_refs(nested, max_depth=2)
    assert truncated is True


def test_resolve_refs_missing_ref_returns_error_marker(spec_dict):
    spec = OpenAPISpec(spec_dict)
    resolved, truncated = spec.resolve_refs({"$ref": "#/components/schemas/Ghost"})
    assert resolved["code"] == "SCHEMA_REF_NOT_FOUND"
    assert truncated is False


# --------------------------------------------------------------------------- #
# Operations & path matching
# --------------------------------------------------------------------------- #

def test_operations_iterates_all(spec_dict):
    spec = OpenAPISpec(spec_dict)
    ops = {(o.method, o.path) for o in spec.operations()}
    assert ("GET", "/vdbs/{vdbId}") in ops
    assert ("POST", "/dsources/link") in ops


def test_find_path_item_exact_and_wildcard(spec_dict):
    spec = OpenAPISpec(spec_dict)
    assert spec.find_path_item("/vdbs/{vdbId}") is not None
    # A fully-resolved path matches its template.
    assert spec.find_path_item("/vdbs/vdb-123") is not None
    assert spec.find_path_item("/vdbs/vdb-123/extra") is None


def test_operation_at(spec_dict):
    spec = OpenAPISpec(spec_dict)
    # A resolved path matches its template; the Operation carries the queried
    # path (matching the historical get_operation_schema behaviour).
    op = spec.operation_at("/vdbs/vdb-9", "get")
    assert op is not None
    assert op.operation_id == "get_vdb_by_id"
    assert op.tags == ["VDBs"]
    assert [p.name for p in op.parameters] == ["vdbId"]
    assert spec.operation_at("/vdbs/vdb-9", "delete") is None

    # Querying with the template path exposes the {placeholder} names.
    op_tmpl = spec.operation_at("/vdbs/{vdbId}", "get")
    assert op_tmpl.path_param_names == ["vdbId"]


# --------------------------------------------------------------------------- #
# RequestBody
# --------------------------------------------------------------------------- #

def test_request_body_fields_merge_allof(spec_dict):
    spec = OpenAPISpec(spec_dict)
    op = spec.operation_at("/dsources/link", "post")
    rb = op.request_body
    assert isinstance(rb, RequestBody)
    assert rb.required is True
    names = {f["name"] for f in rb.fields()}
    # allOf-merged: base props (a, b) plus the action-specific source_id.
    assert {"a", "b", "source_id"} <= names
    src = next(f for f in rb.fields() if f["name"] == "source_id")
    assert src["required"] is True
    assert src["description"] == "the source"


def test_request_body_required_field_names_top_level_only(spec_dict):
    spec = OpenAPISpec(spec_dict)
    op = spec.operation_at("/dsources/link", "post")
    # Execute validation reads only the resolved schema's top-level required
    # (lenient behaviour preserved): source_id, not the allOf-nested "a".
    assert op.request_body.required_field_names() == ["source_id"]


# --------------------------------------------------------------------------- #
# SchemaObject & curated domain objects
# --------------------------------------------------------------------------- #

def test_schema_object_allof_key_properties(spec_dict):
    spec = OpenAPISpec(spec_dict)
    obj = SchemaObject(spec, {"$ref": "#/components/schemas/LinkParams"})
    assert set(obj.properties) == {"a", "b", "c", "d", "e", "f", "source_id"}
    # Inline (non-$ref) sub-schema props are "key"; the large $ref'd Base
    # (>5 props) is an inherited base and its props are excluded.
    assert obj.key_properties == {"source_id"}
    assert "a" in obj.required and "source_id" in obj.required


def test_domain_object_returns_curated_subclasses(spec_dict):
    spec = OpenAPISpec(spec_dict)
    assert isinstance(spec.domain_object("DSource"), DSource)
    assert isinstance(spec.domain_object("VDB"), VDB)
    # Generic fallback for non-curated schemas, None when absent.
    generic = spec.domain_object("Base")
    assert isinstance(generic, SchemaObject) and not isinstance(generic, (DSource, VDB))
    assert spec.domain_object("DoesNotExist") is None


def test_domain_object_cached(spec_dict):
    spec = OpenAPISpec(spec_dict)
    assert spec.domain_object("VDB") is spec.domain_object("VDB")
