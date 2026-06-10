"""Unit tests for the spec-derived confirmation resolver (DLPXECO-13984, auto mode)."""

import dct_mcp_server.tools.core.dynamic_confirmation as dc
from dct_mcp_server.tools.core.dynamic_confirmation import (
    _confirm,
    _lookup_operation,
    _matched_keyword,
    _none,
    get_confirmation_for_operation_dynamic,
    resolve_confirmation,
)

# A minimal OpenAPI-shaped spec exercising the heuristic branches.
SAMPLE_SPEC = {
    "paths": {
        "/vdbs/{vdbId}/refresh": {
            "post": {"summary": "Refresh a VDB", "operationId": "refresh_vdb"},
        },
        "/vdbs/{vdbId}/tags": {
            "post": {"summary": "Create tags for a VDB", "operationId": "create_vdb_tags"},
        },
        "/vdbs/{vdbId}": {
            "delete": {"summary": "Delete a VDB", "operationId": "delete_vdb"},
            "get": {"summary": "Get a VDB", "operationId": "get_vdb"},
        },
        "/snapshots/search": {
            "post": {"summary": "Search for snapshots", "operationId": "search_snapshots"},
        },
    }
}


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #


def test_get_never_requires_confirmation():
    result = get_confirmation_for_operation_dynamic("GET", "/vdbs/{vdbId}", SAMPLE_SPEC)
    assert result["level"] == "none"
    assert result["conditional"] is False


def test_head_and_options_are_reads():
    for method in ("HEAD", "OPTIONS", "head"):
        assert get_confirmation_for_operation_dynamic(method, "/x", SAMPLE_SPEC)["level"] == "none"


# --------------------------------------------------------------------------- #
# Deletes
# --------------------------------------------------------------------------- #


def test_delete_always_manual_regardless_of_spec():
    # Even with no matching spec entry, DELETE is gated.
    result = get_confirmation_for_operation_dynamic("DELETE", "/unknown/path", {})
    assert result["level"] == "manual"
    assert "cannot be undone" in result["message"]


def test_delete_is_case_insensitive():
    assert (
        get_confirmation_for_operation_dynamic("delete", "/vdbs/{vdbId}", SAMPLE_SPEC)["level"]
        == "manual"
    )


# --------------------------------------------------------------------------- #
# Mutating non-delete methods — keyword gated
# --------------------------------------------------------------------------- #


def test_post_with_hot_keyword_is_elevated():
    result = get_confirmation_for_operation_dynamic("POST", "/vdbs/{vdbId}/refresh", SAMPLE_SPEC)
    assert result["level"] == "elevated"
    assert "refresh" in result["message"].lower()


def test_post_without_hot_keyword_passes():
    result = get_confirmation_for_operation_dynamic("POST", "/vdbs/{vdbId}/tags", SAMPLE_SPEC)
    assert result["level"] == "none"


def test_post_search_with_snapshot_keyword_is_gated():
    # "snapshot" is a hot keyword, so POST .../search still matches via summary.
    result = get_confirmation_for_operation_dynamic("POST", "/snapshots/search", SAMPLE_SPEC)
    assert result["level"] == "elevated"


def test_post_with_delete_keyword_in_summary_is_manual():
    spec = {"paths": {"/x/purge": {"post": {"summary": "Delete old data"}}}}
    result = get_confirmation_for_operation_dynamic("POST", "/x/purge", spec)
    assert result["level"] == "manual"


def test_unknown_operation_passes_when_no_keyword():
    result = get_confirmation_for_operation_dynamic("PUT", "/not/in/spec", SAMPLE_SPEC)
    assert result["level"] == "none"


def test_spec_none_falls_back_to_cached_spec(monkeypatch):
    monkeypatch.setattr(dc, "get_cached_spec", lambda: SAMPLE_SPEC, raising=False)
    # Patch the lazily-imported symbol used inside the function.
    import dct_mcp_server.tools.core.tool_factory as tf

    monkeypatch.setattr(tf, "get_cached_spec", lambda: SAMPLE_SPEC)
    result = get_confirmation_for_operation_dynamic("POST", "/vdbs/{vdbId}/refresh")
    assert result["level"] == "elevated"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def test_none_returns_independent_copies():
    a, b = _none(), _none()
    a["level"] = "mutated"
    assert b["level"] == "none"


def test_confirm_shape():
    c = _confirm("manual", "msg")
    assert c == {"level": "manual", "message": "msg", "conditional": False, "threshold_days": None}


def test_matched_keyword():
    assert _matched_keyword("Please Refresh now") == "refresh"
    assert _matched_keyword("update the source config field") == "source config"
    assert _matched_keyword("a harmless read") is None


def test_lookup_operation():
    assert _lookup_operation(SAMPLE_SPEC, "GET", "/vdbs/{vdbId}")["operationId"] == "get_vdb"
    assert _lookup_operation(SAMPLE_SPEC, "POST", "/vdbs/{vdbId}") is None  # no POST defined
    assert _lookup_operation({}, "GET", "/x") is None
    assert _lookup_operation(None, "GET", "/x") is None


# --------------------------------------------------------------------------- #
# Mode-aware routing
# --------------------------------------------------------------------------- #


def test_resolve_confirmation_auto_uses_spec(monkeypatch):
    monkeypatch.setattr(dc, "get_dct_config", lambda: {"toolset": "auto"})
    import dct_mcp_server.tools.core.tool_factory as tf

    monkeypatch.setattr(tf, "get_cached_spec", lambda: SAMPLE_SPEC)
    assert resolve_confirmation("DELETE", "/vdbs/{vdbId}")["level"] == "manual"


def test_resolve_confirmation_non_auto_uses_static(monkeypatch):
    monkeypatch.setattr(dc, "get_dct_config", lambda: {"toolset": "self_service"})
    sentinel = {
        "level": "static-rule",
        "message": None,
        "conditional": False,
        "threshold_days": None,
    }
    monkeypatch.setattr(dc, "get_confirmation_for_operation", lambda m, p: sentinel)
    assert resolve_confirmation("DELETE", "/vdbs/{vdbId}") is sentinel


def test_resolve_confirmation_config_error_falls_back_to_static(monkeypatch):
    def boom():
        raise RuntimeError("config unavailable")

    monkeypatch.setattr(dc, "get_dct_config", boom)
    sentinel = {
        "level": "static-rule",
        "message": None,
        "conditional": False,
        "threshold_days": None,
    }
    monkeypatch.setattr(dc, "get_confirmation_for_operation", lambda m, p: sentinel)
    assert resolve_confirmation("POST", "/x") is sentinel
