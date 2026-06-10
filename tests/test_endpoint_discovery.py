"""Unit tests for fuzzy endpoint discovery helpers (DLPXECO-13921)."""

import dct_mcp_server.tools.core.endpoint_discovery as ed
from dct_mcp_server.tools.core.endpoint_discovery import (
    _candidate_tokens,
    _path_tokens,
    _tokenize,
    build_corpus_from_spec,
    build_discovery_index,
    extract_hot_keywords_from_spec,
    get_discovery_index,
    rank_candidates,
    score_candidate,
)

SAMPLE_SPEC = {
    "paths": {
        "/vdbs/search": {
            "post": {
                "operationId": "search_vdbs",
                "summary": "Search for VDBs",
                "tags": ["VDBs"],
            }
        },
        "/vdbs/{vdbId}/refresh": {
            "post": {
                "operationId": "refresh_vdb",
                "summary": "Refresh a VDB by timestamp",
                "tags": ["VDBs"],
            }
        },
        "/vdbs/{vdbId}": {
            "get": {"operationId": "get_vdb", "summary": "Get a VDB", "tags": ["VDBs"]},
            "delete": {"operationId": "delete_vdb", "summary": "Delete a VDB", "tags": ["VDBs"]},
        },
        "/environments/search": {
            "post": {
                "operationId": "search_environments",
                "summary": "Search environments",
                "tags": ["Environments"],
            }
        },
        # Non-operation keys / malformed entries should be skipped gracefully.
        "/ignored": {"parameters": [], "x-extra": "noise"},
    }
}


# --------------------------------------------------------------------------- #
# Tokenizers
# --------------------------------------------------------------------------- #


def test_tokenize_lowercases_and_splits():
    assert _tokenize("Refresh VDB-123") == {"refresh", "vdb", "123"}


def test_path_tokens_strips_braces_and_splits_camel():
    tokens = _path_tokens("/vdbs/{vdbId}/refresh")
    assert "vdbs" in tokens
    assert "refresh" in tokens
    # the {vdbId} placeholder is removed, not tokenized
    assert "vdbid" not in tokens


def test_path_tokens_camelcase_segment():
    assert "source" in _path_tokens("/sourceConfigs")
    assert "configs" in _path_tokens("/sourceConfigs")


# --------------------------------------------------------------------------- #
# Corpus + hot keywords
# --------------------------------------------------------------------------- #


def test_build_corpus_flattens_operations():
    corpus = build_corpus_from_spec(SAMPLE_SPEC)
    methods_paths = {(c["method"], c["path"]) for c in corpus}
    assert ("POST", "/vdbs/search") in methods_paths
    assert ("DELETE", "/vdbs/{vdbId}") in methods_paths
    assert ("GET", "/vdbs/{vdbId}") in methods_paths
    # malformed/non-operation entries excluded
    assert all(c["path"] != "/ignored" for c in corpus)


def test_build_corpus_handles_empty_spec():
    assert build_corpus_from_spec({}) == []
    assert build_corpus_from_spec({"paths": None}) == []


def test_extract_hot_keywords_weights_tags():
    # "vdbs" appears as a tag on 4 ops (weighted 3x) -> well above threshold.
    hot = extract_hot_keywords_from_spec(SAMPLE_SPEC)
    assert "vdbs" in hot
    # short tokens (<=2 chars) are excluded
    assert all(len(k) > 2 for k in hot)


# --------------------------------------------------------------------------- #
# Index build + cache
# --------------------------------------------------------------------------- #


def test_build_discovery_index_precomputes_tokens():
    index = build_discovery_index(SAMPLE_SPEC)
    assert "corpus" in index and "hot_keywords" in index
    assert all("tokens" in c for c in index["corpus"])


def test_get_discovery_index_caches_by_identity():
    ed._INDEX_CACHE = None
    spec = dict(SAMPLE_SPEC)
    first = get_discovery_index(spec)
    second = get_discovery_index(spec)
    assert first is second  # same object identity -> cached


def test_get_discovery_index_rebuilds_on_new_spec():
    ed._INDEX_CACHE = None
    first = get_discovery_index(dict(SAMPLE_SPEC))
    second = get_discovery_index(dict(SAMPLE_SPEC))  # different object
    assert first is not second


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #


def test_score_empty_query_is_zero():
    cand = {"path": "/vdbs/search", "tokens": frozenset({"vdbs", "search"})}
    assert score_candidate(set(), frozenset(), cand) == 0.0


def test_score_rewards_token_overlap():
    cand = {"path": "/vdbs/search", "tokens": frozenset({"vdbs", "search"})}
    strong = score_candidate({"vdbs", "search"}, frozenset(), cand)
    weak = score_candidate({"environments"}, frozenset(), cand)
    assert strong > weak
    assert 0.0 <= strong <= 1.0


def test_score_hot_keyword_boost():
    cand = {"path": "/vdbs/x", "tokens": frozenset({"vdbs"})}
    without = score_candidate({"vdbs"}, frozenset(), cand)
    with_hot = score_candidate({"vdbs"}, frozenset({"vdbs"}), cand)
    assert with_hot > without


def test_score_computes_tokens_when_absent():
    # Candidate without a precomputed "tokens" key (back-compat path).
    cand = {"path": "/vdbs/search", "summary": "Search VDBs", "operation_id": "", "tags": []}
    assert score_candidate({"vdbs"}, frozenset(), cand) > 0


def test_candidate_tokens_merges_sources():
    cand = {
        "path": "/vdbs/{vdbId}",
        "summary": "Refresh data",
        "operation_id": "refresh_vdb",
        "tags": ["VDBs"],
    }
    tokens = _candidate_tokens(cand)
    assert {"vdbs", "refresh", "data"} <= tokens


# --------------------------------------------------------------------------- #
# Ranking
# --------------------------------------------------------------------------- #


def _index():
    return build_discovery_index(SAMPLE_SPEC)


def test_rank_returns_best_match_first():
    idx = _index()
    results = rank_candidates(idx["corpus"], "refresh vdb", None, 0.0, 5, idx["hot_keywords"])
    assert results
    assert results[0]["path"] == "/vdbs/{vdbId}/refresh"
    assert "score" in results[0]


def test_rank_respects_limit():
    idx = _index()
    results = rank_candidates(idx["corpus"], "vdb", None, 0.0, 2, idx["hot_keywords"])
    assert len(results) <= 2


def test_rank_method_filter():
    idx = _index()
    results = rank_candidates(idx["corpus"], "vdb", ["DELETE"], 0.0, 10, idx["hot_keywords"])
    assert results
    assert all(c["method"] == "DELETE" for c in results)


def test_rank_post_search_treated_as_get():
    idx = _index()
    results = rank_candidates(idx["corpus"], "search vdbs", ["GET"], 0.0, 10, idx["hot_keywords"])
    paths = {c["path"] for c in results}
    # POST /vdbs/search is surfaced when GET is requested
    assert "/vdbs/search" in paths


def test_rank_min_score_filters_weak_matches():
    idx = _index()
    results = rank_candidates(idx["corpus"], "vdb", None, 0.99, 10, idx["hot_keywords"])
    assert results == []


def test_rank_invalid_method_ignored():
    idx = _index()
    # bogus method types are dropped, leaving no filter -> all candidates eligible
    results = rank_candidates(idx["corpus"], "vdb", ["BOGUS"], 0.0, 10, idx["hot_keywords"])
    assert results
