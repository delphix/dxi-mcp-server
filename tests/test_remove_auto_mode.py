"""
Unit tests for the removal of auto mode (DLPXECO-14257).

Coverage targets (mapped to ticket acceptance criteria):
- AC-1: DCT_TOOLSET=auto raises ValueError; "auto" not in the valid-values list.
- AC-2: default toolset is "dynamic"; the auto meta-tools / registration are gone.
- AC-3: persona toolset module resolution is unchanged.
- AC-4: the confirmation system is intact (static resolver + dynamic check_confirmation).
- Helpers retained: find_endpoint / get_spec_chunk remain importable and callable.

All tests in this module were AI-generated. Each test carries an
``# AI-generated`` comment on the first line of its body.
"""

import pytest

from dct_mcp_server import config
from dct_mcp_server.config import loader
from dct_mcp_server.config.loader import get_configured_toolset, get_available_toolsets


# ---------------------------------------------------------------------------
# AC-1: DCT_TOOLSET=auto is now invalid
# ---------------------------------------------------------------------------


def test_auto_toolset_raises_value_error(monkeypatch):
    # AI-generated
    monkeypatch.setenv("DCT_TOOLSET", "auto")
    with pytest.raises(ValueError):
        get_configured_toolset()


def test_auto_not_in_valid_values_message(monkeypatch):
    # AI-generated
    monkeypatch.setenv("DCT_TOOLSET", "auto")
    try:
        get_configured_toolset()
        pytest.fail("expected ValueError for DCT_TOOLSET=auto")
    except ValueError as exc:
        msg = str(exc)
        # The valid-values list must advertise dynamic + personas, never "auto".
        valid_values_part = msg.split("Valid values:", 1)[1]
        assert "dynamic" in valid_values_part
        assert "self_service" in valid_values_part
        assert "auto" not in valid_values_part


# ---------------------------------------------------------------------------
# AC-2: default is dynamic; auto symbols/meta-tools are gone
# ---------------------------------------------------------------------------


def test_default_toolset_is_dynamic(monkeypatch):
    # AI-generated
    monkeypatch.delenv("DCT_TOOLSET", raising=False)
    assert get_configured_toolset() == "dynamic"


def test_is_auto_mode_and_meta_tools_constant_removed():
    # AI-generated
    assert not hasattr(config, "is_auto_mode")
    assert not hasattr(config, "META_TOOLS")
    assert not hasattr(loader, "is_auto_mode")
    assert not hasattr(loader, "META_TOOLS")


def test_auto_meta_tools_and_registration_removed():
    # AI-generated
    from dct_mcp_server.tools.core import meta_tools

    for gone in (
        "register_meta_tools",
        "initialize_tool_inventory",
        "enable_toolset",
        "disable_toolset",
        "execute_action",
        "list_available_toolsets",
        "get_toolset_tools",
        "check_operation_confirmation",
    ):
        assert not hasattr(meta_tools, gone), f"{gone} should have been removed"


def test_register_all_tools_has_no_auto_path():
    # AI-generated
    import dct_mcp_server.tools as tools_pkg

    assert not hasattr(tools_pkg, "register_meta_tools_only")


# ---------------------------------------------------------------------------
# AC-3: persona toolset resolution unchanged
# ---------------------------------------------------------------------------


def test_persona_toolset_modules_still_resolve():
    # AI-generated
    modules = config.get_modules_for_toolset("self_service")
    assert modules, "self_service should resolve to at least one tool module"


def test_personas_still_in_available_toolsets():
    # AI-generated
    available = get_available_toolsets()
    for persona in ("self_service", "continuous_data_admin", "platform_admin"):
        assert persona in available


# ---------------------------------------------------------------------------
# AC-4: confirmation system intact
# ---------------------------------------------------------------------------


def test_resolve_confirmation_returns_rule_shape():
    # AI-generated
    from dct_mcp_server.tools.core.dynamic_confirmation import resolve_confirmation

    result = resolve_confirmation("DELETE", "/bookmarks/{bookmarkId}")
    assert "level" in result


def test_dynamic_confirmation_delete_is_manual():
    # AI-generated
    from dct_mcp_server.tools.core.dynamic_confirmation import (
        get_confirmation_for_operation_dynamic,
    )

    result = get_confirmation_for_operation_dynamic("DELETE", "/vdbs/{vdbId}")
    assert result["level"] == "manual"


# ---------------------------------------------------------------------------
# Retained helpers: find_endpoint / get_spec_chunk
# ---------------------------------------------------------------------------


def test_spec_helpers_are_importable():
    # AI-generated
    from dct_mcp_server.tools.core import find_endpoint, get_spec_chunk

    assert callable(find_endpoint)
    assert callable(get_spec_chunk)


def test_get_spec_chunk_resolves_pointer(monkeypatch):
    # AI-generated
    stub_spec = {
        "components": {"parameters": {"limit": {"name": "limit", "in": "query"}}}
    }
    monkeypatch.setattr(
        "dct_mcp_server.tools.core.meta_tools.get_cached_spec", lambda: stub_spec
    )
    from dct_mcp_server.tools.core.meta_tools import get_spec_chunk

    result = get_spec_chunk("#/components/parameters/limit")
    assert result["value"] == {"name": "limit", "in": "query"}


def test_find_endpoint_handles_missing_spec(monkeypatch):
    # AI-generated
    monkeypatch.setattr(
        "dct_mcp_server.tools.core.meta_tools.get_cached_spec", lambda: None
    )
    from dct_mcp_server.tools.core.meta_tools import find_endpoint

    result = find_endpoint("list vdbs")
    assert result["candidates"] == []
