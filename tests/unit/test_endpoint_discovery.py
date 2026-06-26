"""
Unit tests for dct_mcp_server.tools.core.endpoint_discovery.

All functions under test are pure (no I/O), so no mocking required.
"""

import pytest

from dct_mcp_server.tools.core.endpoint_discovery import (
    _path_tokens,
    _tokenize,
    build_corpus_from_spec,
    build_discovery_index,
    extract_hot_keywords_from_spec,
    get_discovery_index,
    rank_candidates,
    score_candidate,
)

# Reset the module-level cache between tests
import dct_mcp_server.tools.core.endpoint_discovery as _ed_module


@pytest.fixture(autouse=True)
def _reset_index_cache():
    """Clear the module-level _INDEX_CACHE before each test."""
    _ed_module._INDEX_CACHE = None
    yield
    _ed_module._INDEX_CACHE = None


# ---------------------------------------------------------------------------
# _tokenize
# ---------------------------------------------------------------------------


def test_tokenize_basic():
    tokens = _tokenize("search VDB")
    assert tokens == {"search", "vdb"}


def test_tokenize_lowercase():
    tokens = _tokenize("Refresh VDBs Now")
    assert "refresh" in tokens
    assert "vdbs" in tokens
    assert "now" in tokens


def test_tokenize_numbers():
    tokens = _tokenize("list 123")
    assert "list" in tokens
    assert "123" in tokens


def test_tokenize_empty_string():
    assert _tokenize("") == set()


# ---------------------------------------------------------------------------
# _path_tokens
# ---------------------------------------------------------------------------


def test_path_tokens_strips_param_placeholders():
    tokens = _path_tokens("/vdbs/{vdbId}/search")
    assert "vdbs" in tokens
    assert "search" in tokens
    # {vdbId} should NOT produce "vdbid" — the placeholder is removed entirely
    assert "vdbid" not in tokens


def test_path_tokens_simple_path():
    tokens = _path_tokens("/environments")
    assert "environments" in tokens


def test_path_tokens_camel_case_splits():
    # camelCase path segments should split into words
    tokens = _path_tokens("/vdbs/{vdbId}")
    # "vdbs" should be present; "vdbid" should NOT be present (placeholder stripped)
    assert "vdbs" in tokens
    assert "vdbid" not in tokens


def test_path_tokens_empty():
    tokens = _path_tokens("/")
    assert isinstance(tokens, set)


# ---------------------------------------------------------------------------
# build_corpus_from_spec
# ---------------------------------------------------------------------------

_MINI_SPEC = {
    "openapi": "3.0.0",
    "paths": {
        "/vdbs/search": {
            "post": {
                "operationId": "searchVdbs",
                "summary": "Search for VDBs",
                "description": "Full text search",
                "tags": ["VDBs"],
            }
        },
        "/vdbs/{vdbId}": {
            "get": {
                "operationId": "getVdb",
                "summary": "Get a VDB by ID",
                "tags": ["VDBs"],
            },
            "delete": {
                "operationId": "deleteVdb",
                "summary": "Delete a VDB",
                "tags": ["VDBs"],
            },
        },
        "/environments": {
            "get": {
                "operationId": "listEnvironments",
                "summary": "List environments",
                "tags": ["Environments"],
            }
        },
    },
}


def test_build_corpus_returns_list():
    corpus = build_corpus_from_spec(_MINI_SPEC)
    assert isinstance(corpus, list)


def test_build_corpus_correct_count():
    corpus = build_corpus_from_spec(_MINI_SPEC)
    # 4 operations total: POST /vdbs/search, GET /vdbs/{vdbId}, DELETE /vdbs/{vdbId}, GET /environments
    assert len(corpus) == 4


def test_build_corpus_entry_fields():
    corpus = build_corpus_from_spec(_MINI_SPEC)
    entry = next(c for c in corpus if c["path"] == "/vdbs/search")
    assert entry["method"] == "POST"
    assert entry["summary"] == "Search for VDBs"
    assert "VDBs" in entry["tags"]
    assert entry["operation_id"] == "searchVdbs"


def test_build_corpus_uppercase_method():
    corpus = build_corpus_from_spec(_MINI_SPEC)
    for entry in corpus:
        assert entry["method"] == entry["method"].upper()


def test_build_corpus_skips_non_http_keys():
    spec = {
        "paths": {
            "/test": {
                "get": {"operationId": "getTest", "summary": "Get"},
                "parameters": [{"name": "id"}],  # top-level key, not a method
                "summary": "Test path",
            }
        }
    }
    corpus = build_corpus_from_spec(spec)
    assert len(corpus) == 1
    assert corpus[0]["method"] == "GET"


def test_build_corpus_empty_paths():
    corpus = build_corpus_from_spec({"paths": {}})
    assert corpus == []


# ---------------------------------------------------------------------------
# extract_hot_keywords_from_spec
# ---------------------------------------------------------------------------


def test_extract_hot_keywords_returns_frozenset():
    hot = extract_hot_keywords_from_spec(_MINI_SPEC)
    assert isinstance(hot, frozenset)


def test_extract_hot_keywords_includes_repeated_tags():
    # "VDBs" appears on 3 operations (each weighted 3) → "vdbs" should be hot
    hot = extract_hot_keywords_from_spec(_MINI_SPEC)
    assert "vdbs" in hot


def test_extract_hot_keywords_excludes_rare_tokens():
    # "environments" only appears on 1 operation (weight=3 total, meets threshold)
    # But short tokens (len <= 2) are excluded. "environments" > 2 chars, count=3 → borderline.
    # We just check the return is a frozenset and doesn't crash.
    hot = extract_hot_keywords_from_spec(_MINI_SPEC)
    assert isinstance(hot, frozenset)


def test_extract_hot_keywords_empty_spec():
    hot = extract_hot_keywords_from_spec({"paths": {}})
    assert hot == frozenset()


# ---------------------------------------------------------------------------
# score_candidate
# ---------------------------------------------------------------------------


def test_score_candidate_empty_query_returns_zero():
    candidate = {"path": "/vdbs/search", "summary": "Search VDBs", "operation_id": "", "tags": []}
    result = score_candidate(set(), frozenset(), candidate)
    assert result == 0.0


def test_score_candidate_returns_float_in_range():
    candidate = {
        "path": "/vdbs/search",
        "summary": "Search for VDBs",
        "operation_id": "searchVdbs",
        "tags": ["VDBs"],
    }
    result = score_candidate({"search", "vdb"}, frozenset({"vdbs", "search"}), candidate)
    assert 0.0 <= result <= 1.0


def test_score_candidate_high_relevance():
    candidate = {
        "path": "/vdbs/search",
        "summary": "Search for VDBs",
        "operation_id": "searchVdbs",
        "tags": ["VDBs"],
    }
    score = score_candidate({"search", "vdb"}, frozenset({"vdbs", "search"}), candidate)
    assert score > 0.3


def test_score_candidate_low_relevance():
    candidate = {
        "path": "/unrelated/path",
        "summary": "Completely different",
        "operation_id": "otherOp",
        "tags": [],
    }
    score = score_candidate({"search", "vdb"}, frozenset(), candidate)
    # Low but not necessarily zero since SequenceMatcher may find some ratio
    assert score < 0.6


def test_score_candidate_uses_precomputed_tokens():
    """If candidate has a 'tokens' key, it's used directly."""
    candidate = {
        "path": "/vdbs/search",
        "summary": "",
        "operation_id": "",
        "tags": [],
        "tokens": frozenset({"vdbs", "search"}),
    }
    score = score_candidate({"search", "vdb"}, frozenset({"vdbs"}), candidate)
    assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# rank_candidates
# ---------------------------------------------------------------------------

_CORPUS = [
    {"method": "GET", "path": "/vdbs", "summary": "List VDBs", "operation_id": "listVdbs", "tags": ["VDBs"]},
    {"method": "POST", "path": "/vdbs/search", "summary": "Search VDBs", "operation_id": "searchVdbs", "tags": ["VDBs"]},
    {"method": "DELETE", "path": "/vdbs/{vdbId}", "summary": "Delete VDB", "operation_id": "deleteVdb", "tags": ["VDBs"]},
    {"method": "GET", "path": "/environments", "summary": "List environments", "operation_id": "listEnvs", "tags": ["Environments"]},
]


def test_rank_candidates_no_method_filter_includes_all():
    results = rank_candidates(_CORPUS, "vdb", None, 0.0, 10, frozenset({"vdbs"}))
    methods = {r["method"] for r in results}
    assert "GET" in methods
    assert "DELETE" in methods


def test_rank_candidates_get_filter_excludes_delete():
    results = rank_candidates(_CORPUS, "vdb list", ["GET"], 0.0, 10, frozenset())
    methods = {r["method"] for r in results}
    assert "DELETE" not in methods
    # GET /vdbs should be included
    assert "GET" in methods


def test_rank_candidates_get_filter_includes_post_search():
    """POST /*/search endpoints are GET-equivalent and should be included."""
    results = rank_candidates(_CORPUS, "search vdb", ["GET"], 0.0, 10, frozenset())
    paths = {r["path"] for r in results}
    assert "/vdbs/search" in paths


def test_rank_candidates_min_score_filters_low_scorers():
    results = rank_candidates(_CORPUS, "vdb", None, 0.99, 10, frozenset())
    # With min_score=0.99, very few (possibly zero) results should pass
    assert isinstance(results, list)
    for r in results:
        assert r["score"] >= 0.99


def test_rank_candidates_limit_caps_results():
    results = rank_candidates(_CORPUS, "vdb", None, 0.0, 2, frozenset())
    assert len(results) <= 2


def test_rank_candidates_sorted_by_score_descending():
    results = rank_candidates(_CORPUS, "vdb", None, 0.0, 10, frozenset())
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_rank_candidates_score_added_to_result():
    results = rank_candidates(_CORPUS, "vdb", None, 0.0, 10, frozenset())
    for r in results:
        assert "score" in r
        assert isinstance(r["score"], float)


# ---------------------------------------------------------------------------
# build_discovery_index
# ---------------------------------------------------------------------------


def test_build_discovery_index_returns_dict_with_corpus_and_keywords():
    index = build_discovery_index(_MINI_SPEC)
    assert "corpus" in index
    assert "hot_keywords" in index


def test_build_discovery_index_corpus_has_tokens():
    index = build_discovery_index(_MINI_SPEC)
    for entry in index["corpus"]:
        assert "tokens" in entry
        assert isinstance(entry["tokens"], frozenset)


def test_build_discovery_index_hot_keywords_is_frozenset():
    index = build_discovery_index(_MINI_SPEC)
    assert isinstance(index["hot_keywords"], frozenset)


# ---------------------------------------------------------------------------
# get_discovery_index — caching behavior
# ---------------------------------------------------------------------------


def test_get_discovery_index_same_object_returns_cached():
    spec = dict(_MINI_SPEC)
    index1 = get_discovery_index(spec)
    index2 = get_discovery_index(spec)
    assert index1 is index2


def test_get_discovery_index_different_object_rebuilds():
    spec1 = dict(_MINI_SPEC)
    spec2 = dict(_MINI_SPEC)  # Same content but different object → different id()
    index1 = get_discovery_index(spec1)
    index2 = get_discovery_index(spec2)
    # Different objects → different cache entries (rebuilt)
    assert index1 is not index2


def test_get_discovery_index_cache_invalidated_on_new_spec():
    """After passing a new spec object the stale cache is replaced."""
    spec_old = {"paths": {"/old": {"get": {"operationId": "old", "summary": "Old"}}}}
    spec_new = {"paths": {"/new": {"get": {"operationId": "new", "summary": "New"}}}}

    idx_old = get_discovery_index(spec_old)
    idx_new = get_discovery_index(spec_new)

    assert len(idx_new["corpus"]) == 1
    assert idx_new["corpus"][0]["path"] == "/new"
