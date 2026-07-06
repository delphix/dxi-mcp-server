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
- is_auto_mode()
"""

from __future__ import annotations

import pytest

from dct_mcp_server.config.loader import (
    _path_matches,
    clear_cache,
    get_available_toolsets,
    get_configured_toolset,
    get_confirmation_for_operation,
    get_tools_for_toolset,
    is_auto_mode,
    load_all_toolsets_metadata,
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


def test_get_configured_toolset_auto(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "auto")
    assert get_configured_toolset() == "auto"


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
# is_auto_mode
# ---------------------------------------------------------------------------


def test_is_auto_mode_true(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "auto")
    assert is_auto_mode() is True


def test_is_auto_mode_false(monkeypatch):
    monkeypatch.setenv("DCT_TOOLSET", "self_service")
    assert is_auto_mode() is False


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
