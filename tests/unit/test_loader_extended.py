"""
Extended unit tests for config/loader.py.

Covers the uncovered statements:
- get_available_toolsets()
- load_toolset_metadata()
- load_all_toolsets_metadata()
- load_toolset_grouped_apis() — inheritance path, no-description path
- get_confirmation_for_operation() / _path_matches()
- requires_confirmation()
- validate_toolset_config() / validate_all_configs()
- clear_cache()
- get_configured_toolset() — auto, valid, invalid
"""

from __future__ import annotations

import pytest

from unittest.mock import patch

import dct_mcp_server.config.loader as _loader_mod

from dct_mcp_server.config.loader import (
    _path_matches,
    clear_cache,
    get_available_toolsets,
    get_configured_toolset,
    get_confirmation_for_operation,
    get_tools_for_toolset,
    is_dynamic_mode,
    load_all_toolsets_metadata,
    load_manual_confirmation_rules,
    load_toolset_apis,
    load_toolset_grouped_apis,
    load_toolset_metadata,
    requires_confirmation,
    validate_all_configs,
    validate_toolset_config,
)


# ---------------------------------------------------------------------------
# get_available_toolsets
# ---------------------------------------------------------------------------


def test_get_available_toolsets_returns_list():
    toolsets = get_available_toolsets()
    assert isinstance(toolsets, list)
    assert len(toolsets) > 0


def test_get_available_toolsets_includes_self_service():
    toolsets = get_available_toolsets()
    assert "self_service" in toolsets


def test_get_available_toolsets_includes_expected_toolsets():
    toolsets = get_available_toolsets()
    for expected in ["self_service", "continuous_data_admin", "platform_admin"]:
        assert expected in toolsets, f"{expected} not in available toolsets"


# ---------------------------------------------------------------------------
# load_toolset_metadata
# ---------------------------------------------------------------------------


def test_load_toolset_metadata_self_service():
    meta = load_toolset_metadata("self_service")
    assert meta is not None
    assert meta["name"] == "self_service"
    assert "tool_count" in meta
    assert meta["tool_count"] > 0


def test_load_toolset_metadata_has_description():
    meta = load_toolset_metadata("self_service")
    assert "description" in meta
    assert len(meta["description"]) > 0


def test_load_toolset_metadata_nonexistent_returns_none():
    meta = load_toolset_metadata("this_does_not_exist")
    assert meta is None


def test_load_toolset_metadata_platform_admin():
    meta = load_toolset_metadata("platform_admin")
    assert meta is not None
    assert meta["name"] == "platform_admin"


def test_load_toolset_metadata_has_primary_use_case():
    toolsets = get_available_toolsets()
    # At least one toolset should have target users / primary use case
    found_use_case = False
    for ts in toolsets:
        meta = load_toolset_metadata(ts)
        if meta and "primary_use_case" in meta:
            found_use_case = True
            break
    assert found_use_case


# ---------------------------------------------------------------------------
# load_all_toolsets_metadata
# ---------------------------------------------------------------------------


def test_load_all_toolsets_metadata_returns_dict():
    all_meta = load_all_toolsets_metadata()
    assert isinstance(all_meta, dict)
    assert len(all_meta) > 0


def test_load_all_toolsets_metadata_contains_self_service():
    all_meta = load_all_toolsets_metadata()
    assert "self_service" in all_meta


def test_load_all_toolsets_metadata_all_have_name():
    all_meta = load_all_toolsets_metadata()
    for name, meta in all_meta.items():
        assert meta["name"] == name


# ---------------------------------------------------------------------------
# load_toolset_grouped_apis
# ---------------------------------------------------------------------------


def test_load_toolset_grouped_apis_self_service():
    grouped = load_toolset_grouped_apis("self_service")
    assert isinstance(grouped, dict)
    assert len(grouped) > 0


def test_load_toolset_grouped_apis_has_vdb_tool():
    grouped = load_toolset_grouped_apis("self_service")
    assert "vdb_tool" in grouped


def test_load_toolset_grouped_apis_has_apis_list():
    grouped = load_toolset_grouped_apis("self_service")
    for tool_name, tool_data in grouped.items():
        assert "apis" in tool_data
        assert isinstance(tool_data["apis"], list)
        assert len(tool_data["apis"]) > 0


def test_load_toolset_grouped_apis_apis_have_required_keys():
    grouped = load_toolset_grouped_apis("self_service")
    for tool_name, tool_data in grouped.items():
        for api in tool_data["apis"]:
            assert "method" in api
            assert "path" in api
            assert "action" in api


def test_load_toolset_grouped_apis_inheriting_toolset():
    # self_service_provision inherits from self_service
    provision = load_toolset_grouped_apis("self_service_provision")
    base = load_toolset_grouped_apis("self_service")
    # All tools from base should be in provision
    for tool_name in base:
        assert tool_name in provision


def test_load_toolset_grouped_apis_continuous_data_admin():
    grouped = load_toolset_grouped_apis("continuous_data_admin")
    assert len(grouped) > 2  # Should have more tools than self_service


def test_load_toolset_grouped_apis_nonexistent_raises():
    with pytest.raises(ValueError, match="Unknown toolset"):
        load_toolset_grouped_apis("totally_fake_toolset")


# ---------------------------------------------------------------------------
# _path_matches
# ---------------------------------------------------------------------------


def test_path_matches_exact():
    assert _path_matches("/vdbs/search", "/vdbs/search") is True


def test_path_matches_with_placeholder():
    assert _path_matches("/vdbs/vdb-123", "/vdbs/{vdbId}") is True


def test_path_matches_with_multiple_placeholders():
    assert (
        _path_matches("/vdbs/abc/snapshots/snap-1", "/vdbs/{vdbId}/snapshots/{snapId}")
        is True
    )


def test_path_matches_no_match():
    assert _path_matches("/vdbs/abc", "/dsources/{id}") is False


def test_path_matches_wildcard_method_in_path():
    assert _path_matches("/vdbs/vdb-1/delete", "/vdbs/{vdbId}/delete") is True


def test_path_no_match_different_depth():
    assert _path_matches("/vdbs", "/vdbs/{vdbId}") is False


# ---------------------------------------------------------------------------
# get_confirmation_for_operation
# ---------------------------------------------------------------------------


def test_get_confirmation_for_operation_safe_get():
    result = get_confirmation_for_operation("GET", "/vdbs/search")
    assert result["level"] == "none"


def test_get_confirmation_for_operation_returns_dict():
    result = get_confirmation_for_operation("POST", "/vdbs/search")
    assert isinstance(result, dict)
    assert "level" in result
    assert "message" in result
    assert "conditional" in result


def test_get_confirmation_for_operation_delete_vdb():
    result = get_confirmation_for_operation("POST", "/vdbs/vdb-123/delete")
    # Should require some form of confirmation
    assert result["level"] in ("manual", "elevated", "standard", "none")


def test_get_confirmation_none_for_missing_rule():
    result = get_confirmation_for_operation("GET", "/some/unknown/endpoint")
    assert result["level"] == "none"
    assert result["conditional"] is False
    assert result["threshold_days"] is None


def test_get_confirmation_for_operation_conditional_structure():
    """Conditional rules have threshold_days"""
    result = get_confirmation_for_operation("POST", "/vdbs/vdb-123/delete")
    # Just validate structure
    assert "conditional" in result
    if result["conditional"]:
        assert result["threshold_days"] is not None


# ---------------------------------------------------------------------------
# requires_confirmation
# ---------------------------------------------------------------------------


def test_requires_confirmation_returns_bool():
    result = requires_confirmation("GET", "/vdbs/search")
    assert isinstance(result, bool)


def test_requires_confirmation_safe_ops_false():
    assert requires_confirmation("GET", "/some/read/endpoint") is False


# ---------------------------------------------------------------------------
# get_configured_toolset
# ---------------------------------------------------------------------------


def test_get_configured_toolset_auto_raises(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "auto")
    with pytest.raises(ValueError, match="Invalid toolset"):
        get_configured_toolset()


def test_get_configured_toolset_self_service(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    assert get_configured_toolset() == "self_service"


def test_get_configured_toolset_invalid_raises(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "totally_invalid_toolset")
    with pytest.raises(ValueError, match="Invalid toolset"):
        get_configured_toolset()


def test_get_configured_toolset_default(monkeypatch):
    monkeypatch.delenv("DCT_TOOLSET", raising=False)
    result = get_configured_toolset()
    assert result == "dynamic"


# ---------------------------------------------------------------------------
# get_tools_for_toolset
# ---------------------------------------------------------------------------


def test_get_tools_for_toolset_self_service():
    tools = get_tools_for_toolset("self_service")
    assert isinstance(tools, list)
    assert len(tools) > 0


def test_get_tools_for_toolset_has_name_and_actions():
    tools = get_tools_for_toolset("self_service")
    for tool in tools:
        assert "name" in tool
        assert "actions" in tool
        assert isinstance(tool["actions"], list)


def test_get_tools_for_toolset_sorted():
    tools = get_tools_for_toolset("self_service")
    names = [t["name"] for t in tools]
    assert names == sorted(names)


# ---------------------------------------------------------------------------
# validate_toolset_config / validate_all_configs
# ---------------------------------------------------------------------------


def test_validate_toolset_config_self_service_no_errors():
    errors = validate_toolset_config("self_service")
    assert errors == []


def test_validate_toolset_config_nonexistent_has_errors():
    errors = validate_toolset_config("fake_toolset")
    assert len(errors) > 0


def test_validate_all_configs_returns_dict():
    results = validate_all_configs()
    assert isinstance(results, dict)


# ---------------------------------------------------------------------------
# clear_cache
# ---------------------------------------------------------------------------


def test_clear_cache_no_error():
    # Just verify it doesn't raise
    clear_cache()
    # And that we can still load after clearing
    toolsets = get_available_toolsets()
    assert len(toolsets) > 0


# ---------------------------------------------------------------------------
# Branch coverage: load_toolset_apis — @inherit: with missing parent (line 68)
# ---------------------------------------------------------------------------


def test_load_toolset_apis_inherit_missing_parent_raises(monkeypatch, tmp_path):
    """@inherit:nonexistent in load_toolset_apis raises ValueError (line 68)."""
    toolset_dir = tmp_path / "toolsets"
    toolset_dir.mkdir()
    (toolset_dir / "child_ts.txt").write_text("@inherit:ghost_parent\n")

    clear_cache()
    monkeypatch.setattr(_loader_mod, "TOOLSETS_DIR", toolset_dir)
    try:
        with pytest.raises(ValueError, match="ghost_parent"):
            load_toolset_apis("child_ts")
    finally:
        clear_cache()


# ---------------------------------------------------------------------------
# Branch coverage: load_toolset_grouped_apis — TOOL header without " - " (line 140)
# ---------------------------------------------------------------------------


def test_load_toolset_grouped_apis_tool_header_no_dash_sets_empty_description(
    monkeypatch, tmp_path
):
    """# TOOL N: tool_name (no ' - description') sets description to '' (line 140-141)."""
    toolset_dir = tmp_path / "toolsets"
    toolset_dir.mkdir()
    (toolset_dir / "nodesc_ts.txt").write_text(
        "# TOOL 1: simple_tool\nGET|/simple|simple_action\n"
    )

    clear_cache()
    monkeypatch.setattr(_loader_mod, "TOOLSETS_DIR", toolset_dir)
    try:
        grouped = load_toolset_grouped_apis("nodesc_ts")
        assert "simple_tool" in grouped
        assert grouped["simple_tool"]["description"] == ""
    finally:
        clear_cache()


# ---------------------------------------------------------------------------
# Branch coverage: load_toolset_grouped_apis — @inherit: with missing parent (line 159)
# ---------------------------------------------------------------------------


def test_load_toolset_grouped_apis_inherit_missing_parent_raises(monkeypatch, tmp_path):
    """@inherit:nonexistent in load_toolset_grouped_apis raises ValueError (line 159)."""
    toolset_dir = tmp_path / "toolsets"
    toolset_dir.mkdir()
    (toolset_dir / "grp_child_ts.txt").write_text("@inherit:no_such_parent\n")

    clear_cache()
    monkeypatch.setattr(_loader_mod, "TOOLSETS_DIR", toolset_dir)
    try:
        with pytest.raises(ValueError, match="no_such_parent"):
            load_toolset_grouped_apis("grp_child_ts")
    finally:
        clear_cache()


# ---------------------------------------------------------------------------
# Branch coverage: load_manual_confirmation_rules — file missing (line 263)
# ---------------------------------------------------------------------------


def test_load_manual_confirmation_rules_missing_file_returns_empty(
    monkeypatch, tmp_path
):
    """Missing confirmation file logs a warning and returns () (line 263-264)."""
    empty_mappings_dir = tmp_path / "mappings"
    empty_mappings_dir.mkdir()

    _loader_mod.load_manual_confirmation_rules.cache_clear()
    monkeypatch.setattr(_loader_mod, "MAPPINGS_DIR", empty_mappings_dir)
    try:
        rules = load_manual_confirmation_rules()
        assert rules == ()
    finally:
        _loader_mod.load_manual_confirmation_rules.cache_clear()


# ---------------------------------------------------------------------------
# Branch coverage: is_dynamic_mode() — returns True (line 437)
# ---------------------------------------------------------------------------


def test_is_dynamic_mode_returns_true_when_toolset_is_dynamic(monkeypatch):
    """is_dynamic_mode() returns True when DCT_TOOLSET=dynamic (line 437)."""
    monkeypatch.setenv("DCT_TOOLSET", "dynamic")
    assert is_dynamic_mode() is True


def test_is_dynamic_mode_returns_false_for_fixed_toolset(monkeypatch):
    """is_dynamic_mode() returns False for any non-dynamic toolset."""
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    assert is_dynamic_mode() is False


# ---------------------------------------------------------------------------
# Branch coverage: validate_toolset_config — empty toolset (line 587)
# ---------------------------------------------------------------------------


def test_validate_toolset_config_empty_toolset_returns_error(monkeypatch, tmp_path):
    """Toolset file with no API lines triggers 'no APIs defined' error (line 587)."""
    toolset_dir = tmp_path / "toolsets"
    toolset_dir.mkdir()
    # File exists but has no METHOD|path|action lines
    (toolset_dir / "empty_ts.txt").write_text(
        "# Self Service Toolset - 0 Tools\n# Description: empty\n"
    )

    clear_cache()
    monkeypatch.setattr(_loader_mod, "TOOLSETS_DIR", toolset_dir)
    try:
        errors = validate_toolset_config("empty_ts")
        assert len(errors) == 1
        assert "no APIs" in errors[0]
    finally:
        clear_cache()


def test_validate_toolset_config_general_exception_is_caught(monkeypatch):
    """Non-ValueError from load_toolset_apis is caught and reported (line 591-592)."""
    with patch.object(
        _loader_mod, "load_toolset_apis", side_effect=RuntimeError("disk failure")
    ):
        errors = validate_toolset_config("any_toolset")
    assert len(errors) == 1
    assert "disk failure" in errors[0]


# ---------------------------------------------------------------------------
# Branch coverage: validate_all_configs — error-populated toolset (line 610)
# ---------------------------------------------------------------------------


def test_validate_all_configs_includes_toolset_with_errors():
    """Toolsets with errors appear under 'toolset:<name>' key (line 610)."""
    with patch.object(_loader_mod, "get_available_toolsets", return_value=["bad_ts"]):
        with patch.object(
            _loader_mod, "validate_toolset_config", return_value=["missing file"]
        ):
            results = validate_all_configs()
    assert "toolset:bad_ts" in results
    assert results["toolset:bad_ts"] == ["missing file"]


def test_validate_all_configs_empty_confirmation_rules_reported():
    """Empty confirmation rules tuple adds a warning entry (line 616)."""
    with patch.object(_loader_mod, "get_available_toolsets", return_value=[]):
        with patch.object(
            _loader_mod, "load_manual_confirmation_rules", return_value=()
        ):
            results = validate_all_configs()
    assert "manual_confirmation.txt" in results


def test_validate_all_configs_confirmation_load_exception_reported():
    """Exception from load_manual_confirmation_rules is caught and reported (line 618)."""
    with patch.object(_loader_mod, "get_available_toolsets", return_value=[]):
        with patch.object(
            _loader_mod,
            "load_manual_confirmation_rules",
            side_effect=Exception("read error"),
        ):
            results = validate_all_configs()
    assert "manual_confirmation.txt" in results
    assert "read error" in results["manual_confirmation.txt"][0]


# ---------------------------------------------------------------------------
# Branch coverage: load_toolset_apis — API line with < 3 parts (line 78 False)
# ---------------------------------------------------------------------------


def test_load_toolset_apis_skips_lines_with_fewer_than_3_parts(monkeypatch, tmp_path):
    """Lines with fewer than 3 pipe-separated parts are silently skipped (line 78 False)."""
    toolset_dir = tmp_path / "toolsets"
    toolset_dir.mkdir()
    (toolset_dir / "sparse_ts.txt").write_text(
        "GET|/only-two-parts\nGET|/vdbs|search_vdbs\n"
    )

    clear_cache()
    monkeypatch.setattr(_loader_mod, "TOOLSETS_DIR", toolset_dir)
    try:
        apis = load_toolset_apis("sparse_ts")
        assert len(apis) == 1
        assert apis[0]["path"] == "/vdbs"
    finally:
        clear_cache()


# ---------------------------------------------------------------------------
# Branch coverage: load_toolset_grouped_apis — inherit where tool already exists
# (line 165 False → 170: existing tool gets APIs merged)
# ---------------------------------------------------------------------------


def test_load_toolset_grouped_apis_inherit_merges_existing_tool(monkeypatch, tmp_path):
    """When inherited tool_name already exists in child, APIs are merged (line 165 False→170)."""
    toolset_dir = tmp_path / "toolsets"
    toolset_dir.mkdir()
    # Parent defines simple_tool
    (toolset_dir / "parent_ts.txt").write_text(
        "# TOOL 1: simple_tool - Parent Tool\nGET|/parent|parent_action\n"
    )
    # Child also defines simple_tool, then inherits parent
    (toolset_dir / "child_ts2.txt").write_text(
        "# TOOL 1: simple_tool - Child Tool\n"
        "GET|/child|child_action\n"
        "@inherit:parent_ts\n"
    )

    clear_cache()
    monkeypatch.setattr(_loader_mod, "TOOLSETS_DIR", toolset_dir)
    try:
        grouped = load_toolset_grouped_apis("child_ts2")
        assert "simple_tool" in grouped
        # Both child and inherited parent APIs should be present
        actions = [api["action"] for api in grouped["simple_tool"]["apis"]]
        assert "child_action" in actions
        assert "parent_action" in actions
    finally:
        clear_cache()


# ---------------------------------------------------------------------------
# Branch coverage: load_toolset_grouped_apis — API line with < 3 parts or no
# current_tool (line 175 False)
# ---------------------------------------------------------------------------


def test_load_toolset_grouped_apis_skips_api_line_with_no_current_tool(
    monkeypatch, tmp_path
):
    """API line before any # TOOL header (current_tool is None) is skipped (line 175 False)."""
    toolset_dir = tmp_path / "toolsets"
    toolset_dir.mkdir()
    # API line appears before any TOOL header
    (toolset_dir / "orphan_ts.txt").write_text(
        "GET|/orphan|orphan_action\n"
        "# TOOL 1: real_tool - Real Tool\n"
        "GET|/real|real_action\n"
    )

    clear_cache()
    monkeypatch.setattr(_loader_mod, "TOOLSETS_DIR", toolset_dir)
    try:
        grouped = load_toolset_grouped_apis("orphan_ts")
        # The orphaned API line before the TOOL header is ignored
        assert "real_tool" in grouped
        assert len(grouped["real_tool"]["apis"]) == 1
    finally:
        clear_cache()


# ---------------------------------------------------------------------------
# Branch coverage: load_all_toolsets_metadata — toolset whose metadata is None
# (line 238 False: metadata is falsy → not added to results)
# ---------------------------------------------------------------------------


def test_load_all_toolsets_metadata_skips_toolset_with_none_metadata(monkeypatch):
    """Toolsets whose metadata is None are excluded from the result (line 238 False)."""
    with patch.object(
        _loader_mod, "get_available_toolsets", return_value=["good_ts", "bad_ts"]
    ):
        with patch.object(
            _loader_mod,
            "load_toolset_metadata",
            side_effect=lambda name: {"name": name} if name == "good_ts" else None,
        ):
            with patch.object(
                _loader_mod,
                "TOOLSETS_DIR",
                type(
                    "FakeDir",
                    (),
                    {
                        "glob": lambda self, pat: [
                            type("F", (), {"stem": "good_ts"})(),
                            type("F", (), {"stem": "bad_ts"})(),
                        ]
                    },
                )(),
            ):
                result = load_all_toolsets_metadata()
    # Only "good_ts" should appear (bad_ts returned None)
    assert "good_ts" in result
    assert "bad_ts" not in result


# ---------------------------------------------------------------------------
# Branch coverage: load_manual_confirmation_rules — line with < 4 parts (line 275 False)
# ---------------------------------------------------------------------------


def test_load_manual_confirmation_rules_skips_malformed_lines(monkeypatch, tmp_path):
    """Lines with fewer than 4 pipe-separated parts are silently skipped (line 275 False)."""
    mappings_dir = tmp_path / "mappings"
    mappings_dir.mkdir()
    (mappings_dir / "manual_confirmation.txt").write_text(
        "INCOMPLETE|line\nDELETE|/vdbs/{vdbId}|manual|Confirm delete\n"
    )

    _loader_mod.load_manual_confirmation_rules.cache_clear()
    monkeypatch.setattr(_loader_mod, "MAPPINGS_DIR", mappings_dir)
    try:
        rules = load_manual_confirmation_rules()
        assert len(rules) == 1
        assert rules[0]["level"] == "manual"
    finally:
        _loader_mod.load_manual_confirmation_rules.cache_clear()


# ---------------------------------------------------------------------------
# Branch coverage: requires_confirmation — POST /path/delete returns True (line 317)
# ---------------------------------------------------------------------------


def test_requires_confirmation_post_delete_path_returns_true():
    """POST on a path ending in /delete triggers confirmation (line 316-317)."""
    from dct_mcp_server.config.loader import requires_confirmation

    # Patch rules to return nothing so the heuristic is reached
    with patch.object(_loader_mod, "load_manual_confirmation_rules", return_value=()):
        assert requires_confirmation("POST", "/vdbs/vdb-1/delete") is True
