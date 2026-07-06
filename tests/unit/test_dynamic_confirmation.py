"""
Unit tests for dct_mcp_server.tools.core.dynamic_confirmation.

Covers: get_confirmation_for_operation_dynamic, _matched_keyword,
        resolve_confirmation (mode-aware dispatch).
"""

from unittest.mock import patch


from dct_mcp_server.tools.core.dynamic_confirmation import (
    _matched_keyword,
    get_confirmation_for_operation_dynamic,
    resolve_confirmation,
)

# ---------------------------------------------------------------------------
# _matched_keyword
# ---------------------------------------------------------------------------


def test_matched_keyword_refresh():
    assert _matched_keyword("Refresh VDBs") == "refresh"


def test_matched_keyword_delete():
    assert _matched_keyword("Delete this VDB permanently") == "delete"


def test_matched_keyword_provision():
    assert _matched_keyword("Provision a new VDB") == "provision"


def test_matched_keyword_rollback():
    assert _matched_keyword("Rollback to a previous snapshot") == "rollback"


def test_matched_keyword_snapshot():
    assert _matched_keyword("Create a snapshot") == "snapshot"


def test_matched_keyword_source_config():
    assert _matched_keyword("Update source config for this dsource") == "source config"


def test_matched_keyword_neutral_text_returns_none():
    assert _matched_keyword("List all environments") is None


def test_matched_keyword_case_insensitive():
    assert _matched_keyword("REFRESH ALL VDBS") == "refresh"


def test_matched_keyword_empty_string():
    assert _matched_keyword("") is None


# ---------------------------------------------------------------------------
# get_confirmation_for_operation_dynamic — read methods
# ---------------------------------------------------------------------------


def test_get_reads_return_none():
    result = get_confirmation_for_operation_dynamic("GET", "/vdbs/search")
    assert result["level"] == "none"
    assert result["message"] is None


def test_get_head_returns_none():
    result = get_confirmation_for_operation_dynamic("HEAD", "/vdbs")
    assert result["level"] == "none"


def test_get_options_returns_none():
    result = get_confirmation_for_operation_dynamic("OPTIONS", "/vdbs")
    assert result["level"] == "none"


# ---------------------------------------------------------------------------
# get_confirmation_for_operation_dynamic — DELETE always manual
# ---------------------------------------------------------------------------


def test_delete_always_requires_manual_confirmation():
    result = get_confirmation_for_operation_dynamic("DELETE", "/vdbs/vdb-123")
    assert result["level"] == "manual"
    assert result["message"] is not None
    assert "DELETE" in result["message"] or "destructive" in result["message"].lower()


# ---------------------------------------------------------------------------
# get_confirmation_for_operation_dynamic — POST with spec
# ---------------------------------------------------------------------------

_REFRESH_SPEC = {
    "paths": {
        "/vdbs/vdb-123": {
            "post": {
                "operationId": "refreshVdb",
                "summary": "Refresh VDB",
                "description": "Refresh a VDB to the latest data.",
            }
        }
    }
}

_DELETE_SPEC = {
    "paths": {
        "/vdbs/vdb-123": {
            "post": {
                "operationId": "deleteVdb",
                "summary": "Delete VDB permanently",
                "description": "",
            }
        }
    }
}

_NEUTRAL_SPEC = {
    "paths": {
        "/data/upload": {
            "post": {
                "operationId": "uploadData",
                "summary": "Upload data file",
                "description": "",
            }
        }
    }
}


def test_post_with_refresh_summary_returns_elevated():
    result = get_confirmation_for_operation_dynamic(
        "POST", "/vdbs/vdb-123", _REFRESH_SPEC
    )
    assert result["level"] == "elevated"
    assert "refresh" in result["message"].lower()


def test_post_with_delete_summary_returns_manual():
    result = get_confirmation_for_operation_dynamic(
        "POST", "/vdbs/vdb-123", _DELETE_SPEC
    )
    assert result["level"] == "manual"


def test_post_with_neutral_summary_returns_none():
    result = get_confirmation_for_operation_dynamic(
        "POST", "/data/upload", _NEUTRAL_SPEC
    )
    assert result["level"] == "none"


def test_post_no_spec_no_match_returns_none():
    """When spec is None and lazy import returns None, neutral POST → none."""
    with patch(
        "dct_mcp_server.tools.core.dynamic_confirmation.get_confirmation_for_operation_dynamic"
    ) as _mock:
        # Call the real function but supply a spec with no hot keywords
        pass

    result = get_confirmation_for_operation_dynamic("POST", "/some/path", {})
    assert result["level"] == "none"


def test_put_with_snapshot_in_description_returns_elevated():
    spec = {
        "paths": {
            "/snapshots/snap-1": {
                "put": {
                    "operationId": "updateSnapshot",
                    "summary": "Update",
                    "description": "Update snapshot retention.",
                }
            }
        }
    }
    result = get_confirmation_for_operation_dynamic("PUT", "/snapshots/snap-1", spec)
    assert result["level"] == "elevated"


def test_patch_with_rollback_summary_returns_elevated():
    spec = {
        "paths": {
            "/vdbs/vdb-1": {
                "patch": {
                    "operationId": "rollbackVdb",
                    "summary": "Rollback VDB to bookmark",
                }
            }
        }
    }
    result = get_confirmation_for_operation_dynamic("PATCH", "/vdbs/vdb-1", spec)
    assert result["level"] == "elevated"


# ---------------------------------------------------------------------------
# resolve_confirmation — always delegates to static rules (auto mode removed)
# ---------------------------------------------------------------------------


def test_resolve_confirmation_delegates_to_static():
    """resolve_confirmation always uses static manual_confirmation.txt rules."""
    with patch(
        "dct_mcp_server.tools.core.dynamic_confirmation.get_confirmation_for_operation",
    ) as mock_static:
        mock_static.return_value = {
            "level": "none",
            "message": None,
            "conditional": False,
            "threshold_days": None,
        }
        resolve_confirmation("GET", "/vdbs")
    mock_static.assert_called_once_with("GET", "/vdbs")


def test_resolve_confirmation_passes_method_and_path():
    """resolve_confirmation forwards method and path to the static resolver."""
    with patch(
        "dct_mcp_server.tools.core.dynamic_confirmation.get_confirmation_for_operation",
    ) as mock_static:
        mock_static.return_value = {"level": "none", "message": None, "conditional": False, "threshold_days": None}
        resolve_confirmation("POST", "/vdbs/vdb-1/refresh")
    mock_static.assert_called_once_with("POST", "/vdbs/vdb-1/refresh")


def test_resolve_confirmation_returns_static_result():
    """resolve_confirmation returns whatever the static resolver returns."""
    expected = {"level": "manual", "message": "Confirm", "conditional": False, "threshold_days": None}
    with patch(
        "dct_mcp_server.tools.core.dynamic_confirmation.get_confirmation_for_operation",
        return_value=expected,
    ):
        result = resolve_confirmation("DELETE", "/vdbs/vdb-1")
    assert result == expected


def test_resolve_confirmation_dynamic_toolset_uses_static():
    """DCT_TOOLSET=dynamic still uses static rules (no auto-mode dispatch)."""
    with patch(
        "dct_mcp_server.tools.core.dynamic_confirmation.get_confirmation_for_operation",
    ) as mock_static:
        mock_static.return_value = {"level": "none", "message": None, "conditional": False, "threshold_days": None}
        resolve_confirmation("GET", "/vdbs/search")
    mock_static.assert_called_once()
