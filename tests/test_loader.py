"""
Unit tests for dct_mcp_server.config.loader (DLPXECO-14014).

Coverage targets:
- load_toolset_apis: positive, unknown toolset, malformed lines, inheritance
- clear_cache: cache invalidation
- get_confirmation_for_operation: manual level, no-match
- requires_confirmation: destructive vs read
- validate_toolset_config: valid and empty toolset

All functions in this module were AI-generated.  Each test carries an
``# AI-generated`` comment on the first line of its body.
"""

import textwrap

import pytest

from dct_mcp_server.config import loader
from dct_mcp_server.config.loader import (
    TOOLSETS_DIR,
    clear_cache,
    get_confirmation_for_operation,
    load_toolset_apis,
    requires_confirmation,
    validate_toolset_config,
)


# ---------------------------------------------------------------------------
# load_toolset_apis — positive cases
# ---------------------------------------------------------------------------


def test_load_toolset_apis_self_service_returns_nonempty():
    # AI-generated
    result = load_toolset_apis("self_service")
    assert len(result) > 0, "Expected at least one API entry for self_service toolset"
    first = result[0]
    assert "method" in first
    assert "path" in first
    assert "action" in first


def test_load_toolset_apis_self_service_has_search_action():
    # AI-generated
    result = load_toolset_apis("self_service")
    actions = [entry["action"] for entry in result]
    assert "search" in actions, (
        "Expected 'search' action for POST /vdbs/search in self_service toolset"
    )


def test_load_toolset_apis_result_is_tuple_of_dicts():
    # AI-generated
    result = load_toolset_apis("self_service")
    assert isinstance(result, tuple), "load_toolset_apis should return a tuple"
    for entry in result:
        assert isinstance(entry, dict)


# ---------------------------------------------------------------------------
# load_toolset_apis — error cases
# ---------------------------------------------------------------------------


def test_load_toolset_apis_unknown_toolset_raises_value_error():
    # AI-generated
    with pytest.raises(ValueError, match="Unknown toolset"):
        load_toolset_apis("this_toolset_does_not_exist_12345")


def test_load_toolset_apis_empty_string_raises_value_error():
    # AI-generated  (EC-1: empty string toolset name)
    with pytest.raises(ValueError):
        load_toolset_apis("")


# ---------------------------------------------------------------------------
# load_toolset_apis — malformed and edge-case file content
# ---------------------------------------------------------------------------


def test_load_toolset_apis_skips_comment_and_blank_lines(tmp_path, monkeypatch):
    # AI-generated
    toolset_file = tmp_path / "comment_only.txt"
    toolset_file.write_text(
        textwrap.dedent(
            """\
            # This is a header comment
            # Another comment

            # Yet another comment
            """
        )
    )
    monkeypatch.setattr(loader, "TOOLSETS_DIR", tmp_path)
    clear_cache()
    result = load_toolset_apis("comment_only")
    assert result == (), "Expected empty tuple when file has only comments and blanks"


def test_load_toolset_apis_malformed_line_ignored(tmp_path, monkeypatch):
    # AI-generated  — a line with only one pipe-separator should be silently skipped
    toolset_file = tmp_path / "malformed.txt"
    toolset_file.write_text(
        textwrap.dedent(
            """\
            # valid
            POST|/vdbs/search|search
            BADLINE_NO_PIPES
            GET|/vdbs/{vdbId}|get
            """
        )
    )
    monkeypatch.setattr(loader, "TOOLSETS_DIR", tmp_path)
    clear_cache()
    result = load_toolset_apis("malformed")
    actions = [e["action"] for e in result]
    assert "search" in actions
    assert "get" in actions
    assert len(result) == 2, "Malformed line should be silently skipped"


# ---------------------------------------------------------------------------
# load_toolset_apis — inheritance
# ---------------------------------------------------------------------------


def test_load_toolset_inheritance_includes_parent_apis():
    # AI-generated — self_service_provision @inherit:self_service should include
    # self_service actions such as "search" (POST /vdbs/search)
    result = load_toolset_apis("self_service_provision")
    actions = [e["action"] for e in result]
    assert "search" in actions, (
        "self_service_provision should inherit 'search' action from self_service"
    )
    # Also verify it has its own provision_by_timestamp action
    assert "provision_by_timestamp" in actions, (
        "self_service_provision should have its own provision_by_timestamp action"
    )


def test_load_toolset_inheritance_missing_parent_raises(tmp_path, monkeypatch):
    # AI-generated
    child_file = tmp_path / "child_toolset.txt"
    child_file.write_text("@inherit:nonexistent_parent\nPOST|/foo|bar\n")
    monkeypatch.setattr(loader, "TOOLSETS_DIR", tmp_path)
    clear_cache()
    with pytest.raises(ValueError):
        load_toolset_apis("child_toolset")


# ---------------------------------------------------------------------------
# clear_cache — cache invalidation
# ---------------------------------------------------------------------------


def test_clear_cache_allows_fresh_reload(tmp_path, monkeypatch):
    # AI-generated — write a toolset, load it, modify it, clear cache, reload
    toolset_file = tmp_path / "cache_test.txt"
    toolset_file.write_text("POST|/initial/path|initial_action\n")
    monkeypatch.setattr(loader, "TOOLSETS_DIR", tmp_path)
    clear_cache()

    first_result = load_toolset_apis("cache_test")
    assert len(first_result) == 1
    assert first_result[0]["action"] == "initial_action"

    # Modify the file and clear the cache
    toolset_file.write_text("POST|/updated/path|updated_action\n")
    clear_cache()

    second_result = load_toolset_apis("cache_test")
    assert len(second_result) == 1
    assert second_result[0]["action"] == "updated_action", (
        "After clear_cache(), load_toolset_apis should re-read the file"
    )


# ---------------------------------------------------------------------------
# get_confirmation_for_operation
# ---------------------------------------------------------------------------


def test_get_confirmation_for_operation_manual_level():
    # AI-generated — POST to delete VDB endpoint should require manual confirmation
    result = get_confirmation_for_operation("POST", "/vdbs/vdb-abc-123/delete")
    assert result["level"] == "manual", (
        f"Expected level='manual' for POST /vdbs/{{id}}/delete, got {result['level']!r}"
    )
    assert result["message"] is not None


def test_get_confirmation_for_operation_no_match_returns_none():
    # AI-generated — GET on a VDB detail endpoint should have no confirmation
    result = get_confirmation_for_operation("GET", "/vdbs/vdb-123")
    assert result["level"] == "none"
    assert result["message"] is None
    assert result["conditional"] is False
    assert result["threshold_days"] is None


# ---------------------------------------------------------------------------
# requires_confirmation
# ---------------------------------------------------------------------------


def test_requires_confirmation_true_for_delete():
    # AI-generated — destructive POST /vdbs/{id}/delete should require confirmation
    assert requires_confirmation("POST", "/vdbs/any-vdb-id/delete") is True


def test_requires_confirmation_false_for_read():
    # AI-generated — GET requests for VDB details should not require confirmation
    assert requires_confirmation("GET", "/vdbs/vdb-123") is False


# ---------------------------------------------------------------------------
# validate_toolset_config
# ---------------------------------------------------------------------------


def test_validate_toolset_config_returns_empty_for_valid():
    # AI-generated — the self_service toolset is valid; no errors expected
    errors = validate_toolset_config("self_service")
    assert errors == [], f"Expected no validation errors for self_service, got: {errors}"


def test_validate_toolset_config_returns_error_for_empty_toolset(tmp_path, monkeypatch):
    # AI-generated  (EC-2: toolset file with no API entries should produce an error)
    empty_toolset_file = tmp_path / "empty_toolset.txt"
    empty_toolset_file.write_text("# Only comments, no API entries\n")
    monkeypatch.setattr(loader, "TOOLSETS_DIR", tmp_path)
    clear_cache()
    errors = validate_toolset_config("empty_toolset")
    assert len(errors) > 0, "Expected at least one validation error for a toolset with no APIs"
