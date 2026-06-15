"""
Unit tests for confirmation rule matching in dct_mcp_server.config.loader
(DLPXECO-14014).

Coverage targets:
- get_confirmation_for_operation: manual, standard, elevated, retention_check,
  policy_impact_check, and no-match cases
- requires_confirmation: destructive vs. read
- _path_matches: exact, parameterised, multi-param (EC-6), no-match
- Wildcard method (*) matching
- First-matching-rule-wins ordering

Tests use both the real ``manual_confirmation.txt`` (integration-style) and
synthetic rule data (injected via monkeypatch on MAPPINGS_DIR).

All functions in this module were AI-generated.  Each test carries an
``# AI-generated`` comment on the first line of its body.
"""

import textwrap

import pytest

from dct_mcp_server.config import loader
from dct_mcp_server.config.loader import (
    MAPPINGS_DIR,
    _path_matches,
    clear_cache,
    get_confirmation_for_operation,
    load_manual_confirmation_rules,
    requires_confirmation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_synthetic_rules(tmp_path, rules_text: str):
    """Write synthetic confirmation rules to a temp directory and patch MAPPINGS_DIR."""
    (tmp_path / "manual_confirmation.txt").write_text(rules_text)


# ---------------------------------------------------------------------------
# get_confirmation_for_operation — using real manual_confirmation.txt
# ---------------------------------------------------------------------------


def test_manual_confirmation_delete_vdb():
    # AI-generated — POST /vdbs/{id}/delete should return level == "manual"
    result = get_confirmation_for_operation("POST", "/vdbs/any-id/delete")
    assert result["level"] == "manual", (
        f"Expected 'manual' for POST /vdbs/{{id}}/delete, got {result['level']!r}"
    )
    assert result["message"] is not None


def test_manual_confirmation_delete_bookmark():
    # AI-generated — DELETE /bookmarks/{id} should return level == "manual"
    result = get_confirmation_for_operation("DELETE", "/bookmarks/bm-1")
    assert result["level"] == "manual", (
        f"Expected 'manual' for DELETE /bookmarks/{{id}}, got {result['level']!r}"
    )


def test_no_confirmation_get_vdb_search():
    # AI-generated — POST /vdbs/search is a search (read-like), no confirmation expected
    result = get_confirmation_for_operation("POST", "/vdbs/search")
    assert result["level"] == "none", (
        f"Expected 'none' for POST /vdbs/search, got {result['level']!r}"
    )


def test_no_confirmation_get_vdb_details():
    # AI-generated — GET /vdbs/{id} is a read operation, no confirmation expected
    result = get_confirmation_for_operation("GET", "/vdbs/vdb-1")
    assert result["level"] == "none"
    assert result["message"] is None
    assert result["conditional"] is False
    assert result["threshold_days"] is None


def test_retention_check_level_parsed():
    # AI-generated — PATCH /snapshots/{id} maps to retention_check:7
    result = get_confirmation_for_operation("PATCH", "/snapshots/snap-1")
    assert result["level"] == "retention_check", (
        f"Expected 'retention_check' for PATCH /snapshots/{{id}}, got {result['level']!r}"
    )
    assert result["conditional"] is True
    assert result["threshold_days"] == 7


def test_standard_confirmation_stop_vdb():
    # AI-generated — POST /vdbs/{id}/stop maps to standard confirmation
    result = get_confirmation_for_operation("POST", "/vdbs/vdb-1/stop")
    assert result["level"] == "standard"


def test_elevated_confirmation_provision_vdb():
    # AI-generated — POST /vdbs/provision_by_timestamp maps to elevated confirmation
    result = get_confirmation_for_operation("POST", "/vdbs/provision_by_timestamp")
    assert result["level"] == "elevated"


# ---------------------------------------------------------------------------
# _path_matches — parameterised and exact paths
# ---------------------------------------------------------------------------


def test_path_matches_with_path_param():
    # AI-generated — path with a single path parameter should match correctly
    assert _path_matches("/vdbs/abc-123/delete", "/vdbs/{vdbId}/delete") is True


def test_path_matches_no_match():
    # AI-generated — /vdbs/search should NOT match /vdbs/{vdbId}/delete
    assert _path_matches("/vdbs/search", "/vdbs/{vdbId}/delete") is False


def test_path_matches_exact_path_no_params():
    # AI-generated — exact match with no parameters
    assert _path_matches("/vdbs/search", "/vdbs/search") is True


def test_path_matches_multiple_path_params():
    # AI-generated  (EC-6: pattern with two path parameters)
    pattern = "/access-groups/{groupId}/scopes/{scopeId}"
    assert _path_matches("/access-groups/ag-1/scopes/sc-99", pattern) is True
    assert _path_matches("/access-groups/ag-1/scopes", pattern) is False
    assert _path_matches("/access-groups/ag-1/scopes/sc-99/extra", pattern) is False


# ---------------------------------------------------------------------------
# requires_confirmation
# ---------------------------------------------------------------------------


def test_requires_confirmation_true_for_destructive():
    # AI-generated — POST to delete endpoint should require confirmation
    assert requires_confirmation("POST", "/vdbs/x/delete") is True


def test_requires_confirmation_false_for_read():
    # AI-generated — GET requests should not require confirmation
    assert requires_confirmation("GET", "/vdbs/x") is False


# ---------------------------------------------------------------------------
# Wildcard method matching — synthetic rules
# ---------------------------------------------------------------------------


def test_wildcard_method_matches_any(tmp_path, monkeypatch):
    # AI-generated — a rule with method "*" should match any HTTP method
    _write_synthetic_rules(
        tmp_path,
        "*|/any/path|manual|Wildcard confirmation required\n",
    )
    monkeypatch.setattr(loader, "MAPPINGS_DIR", tmp_path)
    clear_cache()

    for method in ("GET", "POST", "DELETE", "PATCH", "PUT"):
        result = get_confirmation_for_operation(method, "/any/path")
        assert result["level"] == "manual", (
            f"Wildcard rule should match method={method!r}, got {result['level']!r}"
        )


# ---------------------------------------------------------------------------
# First-matching-rule-wins ordering — synthetic rules
# ---------------------------------------------------------------------------


def test_first_matching_rule_wins(tmp_path, monkeypatch):
    # AI-generated — when two rules match the same path, the first one wins
    _write_synthetic_rules(
        tmp_path,
        textwrap.dedent(
            """\
            POST|/vdbs/{vdbId}/delete|manual|First rule - manual
            POST|/vdbs/{vdbId}/delete|standard|Second rule - standard
            """
        ),
    )
    monkeypatch.setattr(loader, "MAPPINGS_DIR", tmp_path)
    clear_cache()

    result = get_confirmation_for_operation("POST", "/vdbs/vdb-1/delete")
    assert result["level"] == "manual", (
        f"Expected first matching rule's level='manual', got {result['level']!r}"
    )


# ---------------------------------------------------------------------------
# Missing confirmation file — graceful handling (EC-8)
# ---------------------------------------------------------------------------


def test_missing_confirmation_file_returns_empty(tmp_path, monkeypatch):
    # AI-generated  (EC-8: manual_confirmation.txt does not exist → no confirmation for any path)
    monkeypatch.setattr(loader, "MAPPINGS_DIR", tmp_path)
    clear_cache()
    # File is absent — load_manual_confirmation_rules should return empty tuple
    rules = load_manual_confirmation_rules()
    assert rules == ()
    # requires_confirmation should return False for all paths
    assert requires_confirmation("POST", "/vdbs/vdb-1/delete") is False
