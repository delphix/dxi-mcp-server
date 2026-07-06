"""
Unit tests for tools/core/meta_tools.py.

Tests the two retained spec-reading helpers:
- find_endpoint: fuzzy-matches a query against the cached OpenAPI spec
- get_spec_chunk: resolves a JSON pointer / $ref against the cached spec
"""

from __future__ import annotations

# Warm up pydantic's generic-model registry before any mcp.server.fastmcp import.
# Without this, running this file in isolation triggers KeyError: 'pydantic.root_model'
# during collection (mcp triggers generic model creation before pydantic internals are
# registered in sys.modules).
from pydantic import RootModel  # noqa: F401 — must be first import

from unittest.mock import patch

from dct_mcp_server.tools.core.meta_tools import find_endpoint, get_spec_chunk


# ---------------------------------------------------------------------------
# Minimal fake spec shared across tests
# ---------------------------------------------------------------------------

_FAKE_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "DCT API", "version": "1.0"},
    "paths": {
        "/vdbs/search": {
            "post": {
                "operationId": "searchVdbs",
                "summary": "Search virtual databases",
                "tags": ["VDB"],
                "requestBody": {"$ref": "#/components/requestBodies/SearchBody"},
            }
        },
        "/dsources/search": {
            "post": {
                "operationId": "searchDsources",
                "summary": "Search data sources",
                "tags": ["dSource"],
            }
        },
    },
    "components": {
        "parameters": {
            "limit": {
                "name": "limit",
                "in": "query",
                "schema": {"type": "integer", "default": 100},
            }
        },
        "requestBodies": {
            "SearchBody": {
                "content": {"application/json": {"schema": {"type": "object"}}}
            }
        },
    },
}

_FAKE_INDEX = {
    "corpus": [
        {
            "method": "POST",
            "path": "/vdbs/search",
            "operation_id": "searchVdbs",
            "summary": "Search virtual databases",
            "tags": ["VDB"],
            "score": 0.0,
        },
        {
            "method": "POST",
            "path": "/dsources/search",
            "operation_id": "searchDsources",
            "summary": "Search data sources",
            "tags": ["dSource"],
            "score": 0.0,
        },
    ],
    "hot_keywords": {},
}


def _make_ranked(*items):
    """Return a list of pre-scored candidate dicts."""
    result = []
    for i, item in enumerate(items):
        result.append(
            {
                "method": item.get("method", "POST"),
                "path": item.get("path", f"/fake/{i}"),
                "operation_id": item.get("operation_id", f"op{i}"),
                "summary": item.get("summary", ""),
                "tags": item.get("tags", []),
                "score": item.get("score", 0.9),
            }
        )
    return result


# ---------------------------------------------------------------------------
# find_endpoint — error / edge cases
# ---------------------------------------------------------------------------


def test_find_endpoint_empty_query_returns_error():
    result = find_endpoint("")
    assert "error" in result
    assert result.get("candidates") == []


def test_find_endpoint_whitespace_query_returns_error():
    result = find_endpoint("   ")
    assert "error" in result


def test_find_endpoint_spec_unavailable_returns_error():
    with patch(
        "dct_mcp_server.tools.core.meta_tools.get_cached_spec", return_value=None
    ):
        result = find_endpoint("list all vdbs")
    assert "error" in result
    assert result.get("candidates") == []


def test_find_endpoint_invalid_limit_type_returns_error():
    with patch(
        "dct_mcp_server.tools.core.meta_tools.get_cached_spec",
        return_value=_FAKE_SPEC,
    ):
        result = find_endpoint("list vdbs", limit="not_a_number")
    assert "error" in result


# ---------------------------------------------------------------------------
# find_endpoint — successful path
# ---------------------------------------------------------------------------


def test_find_endpoint_returns_candidates_key():
    ranked = _make_ranked({"path": "/vdbs/search", "method": "POST"})
    with patch(
        "dct_mcp_server.tools.core.meta_tools.get_cached_spec",
        return_value=_FAKE_SPEC,
    ):
        with patch(
            "dct_mcp_server.tools.core.meta_tools.get_discovery_index",
            return_value=_FAKE_INDEX,
        ):
            with patch(
                "dct_mcp_server.tools.core.meta_tools.rank_candidates",
                return_value=ranked,
            ):
                result = find_endpoint("list all vdbs")
    assert "candidates" in result


def test_find_endpoint_returns_source_openapi_spec():
    ranked = _make_ranked({"path": "/vdbs/search", "method": "POST"})
    with patch(
        "dct_mcp_server.tools.core.meta_tools.get_cached_spec",
        return_value=_FAKE_SPEC,
    ):
        with patch(
            "dct_mcp_server.tools.core.meta_tools.get_discovery_index",
            return_value=_FAKE_INDEX,
        ):
            with patch(
                "dct_mcp_server.tools.core.meta_tools.rank_candidates",
                return_value=ranked,
            ):
                result = find_endpoint("list vdbs")
    assert result.get("source") == "openapi_spec"


def test_find_endpoint_respects_limit():
    many = _make_ranked(*[{"path": f"/things/{i}", "method": "GET"} for i in range(20)])
    with patch(
        "dct_mcp_server.tools.core.meta_tools.get_cached_spec",
        return_value=_FAKE_SPEC,
    ):
        with patch(
            "dct_mcp_server.tools.core.meta_tools.get_discovery_index",
            return_value=_FAKE_INDEX,
        ):
            with patch(
                "dct_mcp_server.tools.core.meta_tools.rank_candidates",
                return_value=many[:3],  # rank_candidates already applies limit
            ) as mock_rank:
                find_endpoint("things", limit=3)
    # rank_candidates was called with capped_limit=3
    call_args = mock_rank.call_args
    assert call_args.args[3] == 3 or call_args.args[4] == 3 or 3 in call_args.args


def test_find_endpoint_passes_method_types_to_rank():
    ranked = _make_ranked({"path": "/vdbs/search", "method": "POST"})
    with patch(
        "dct_mcp_server.tools.core.meta_tools.get_cached_spec",
        return_value=_FAKE_SPEC,
    ):
        with patch(
            "dct_mcp_server.tools.core.meta_tools.get_discovery_index",
            return_value=_FAKE_INDEX,
        ):
            with patch(
                "dct_mcp_server.tools.core.meta_tools.rank_candidates",
                return_value=ranked,
            ) as mock_rank:
                find_endpoint("search vdbs", method_types=["GET"])
    call_args = mock_rank.call_args
    assert ["GET"] in call_args.args or call_args.kwargs.get("method_types") == ["GET"]


def test_find_endpoint_empty_results_returns_hint():
    with patch(
        "dct_mcp_server.tools.core.meta_tools.get_cached_spec",
        return_value=_FAKE_SPEC,
    ):
        with patch(
            "dct_mcp_server.tools.core.meta_tools.get_discovery_index",
            return_value=_FAKE_INDEX,
        ):
            with patch(
                "dct_mcp_server.tools.core.meta_tools.rank_candidates",
                return_value=[],
            ):
                result = find_endpoint("zzz_no_match_zzz")
    assert result.get("candidates") == []
    assert "hint" in result


def test_find_endpoint_ranking_exception_returns_error():
    with patch(
        "dct_mcp_server.tools.core.meta_tools.get_cached_spec",
        return_value=_FAKE_SPEC,
    ):
        with patch(
            "dct_mcp_server.tools.core.meta_tools.get_discovery_index",
            side_effect=RuntimeError("index build failed"),
        ):
            result = find_endpoint("list vdbs")
    assert "error" in result
    assert result.get("candidates") == []


def test_find_endpoint_candidate_has_required_fields():
    ranked = _make_ranked({"path": "/vdbs/search", "method": "POST", "score": 0.8})
    with patch(
        "dct_mcp_server.tools.core.meta_tools.get_cached_spec",
        return_value=_FAKE_SPEC,
    ):
        with patch(
            "dct_mcp_server.tools.core.meta_tools.get_discovery_index",
            return_value=_FAKE_INDEX,
        ):
            with patch(
                "dct_mcp_server.tools.core.meta_tools.rank_candidates",
                return_value=ranked,
            ):
                result = find_endpoint("search vdbs")
    assert len(result["candidates"]) == 1
    cand = result["candidates"][0]
    for field in (
        "score",
        "method",
        "path",
        "operation_id",
        "requires_confirmation",
        "confirmation_level",
    ):
        assert field in cand, f"missing field: {field}"


def test_find_endpoint_count_matches_candidates():
    ranked = _make_ranked(
        {"path": "/vdbs/search", "method": "POST"},
        {"path": "/dsources/search", "method": "POST"},
    )
    with patch(
        "dct_mcp_server.tools.core.meta_tools.get_cached_spec",
        return_value=_FAKE_SPEC,
    ):
        with patch(
            "dct_mcp_server.tools.core.meta_tools.get_discovery_index",
            return_value=_FAKE_INDEX,
        ):
            with patch(
                "dct_mcp_server.tools.core.meta_tools.rank_candidates",
                return_value=ranked,
            ):
                result = find_endpoint("search")
    assert result["count"] == len(result["candidates"])


# ---------------------------------------------------------------------------
# get_spec_chunk — error cases
# ---------------------------------------------------------------------------


def test_get_spec_chunk_spec_unavailable_returns_error():
    with patch(
        "dct_mcp_server.tools.core.meta_tools.get_cached_spec", return_value=None
    ):
        result = get_spec_chunk("#/components/parameters/limit")
    assert "error" in result


def test_get_spec_chunk_empty_ref_returns_error():
    result = get_spec_chunk("")
    assert "error" in result


def test_get_spec_chunk_non_string_ref_returns_error():
    result = get_spec_chunk(None)
    assert "error" in result


def test_get_spec_chunk_unknown_ref_returns_error():
    with patch(
        "dct_mcp_server.tools.core.meta_tools.get_cached_spec",
        return_value=_FAKE_SPEC,
    ):
        result = get_spec_chunk("#/components/parameters/does_not_exist")
    assert "error" in result


def test_get_spec_chunk_bad_pointer_format_returns_error():
    with patch(
        "dct_mcp_server.tools.core.meta_tools.get_cached_spec",
        return_value=_FAKE_SPEC,
    ):
        result = get_spec_chunk("components/parameters/limit")  # missing leading #/
    assert "error" in result


# ---------------------------------------------------------------------------
# get_spec_chunk — success cases
# ---------------------------------------------------------------------------


def test_get_spec_chunk_resolves_with_hash_prefix():
    with patch(
        "dct_mcp_server.tools.core.meta_tools.get_cached_spec",
        return_value=_FAKE_SPEC,
    ):
        result = get_spec_chunk("#/components/parameters/limit")
    assert "error" not in result
    assert "value" in result
    assert isinstance(result["value"], dict)
    assert result["value"]["name"] == "limit"


def test_get_spec_chunk_resolves_without_hash_prefix():
    with patch(
        "dct_mcp_server.tools.core.meta_tools.get_cached_spec",
        return_value=_FAKE_SPEC,
    ):
        result = get_spec_chunk("/components/parameters/limit")
    assert "error" not in result
    assert result["value"]["name"] == "limit"


def test_get_spec_chunk_returns_ref_echo():
    ref = "#/components/parameters/limit"
    with patch(
        "dct_mcp_server.tools.core.meta_tools.get_cached_spec",
        return_value=_FAKE_SPEC,
    ):
        result = get_spec_chunk(ref)
    assert result["ref"] == ref


def test_get_spec_chunk_resolves_nested_path():
    with patch(
        "dct_mcp_server.tools.core.meta_tools.get_cached_spec",
        return_value=_FAKE_SPEC,
    ):
        result = get_spec_chunk("#/components/parameters/limit/schema")
    assert "error" not in result
    assert result["value"]["type"] == "integer"
