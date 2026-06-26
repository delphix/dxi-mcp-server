"""
Unit tests for dct_mcp_server.tools.core.confirmation_resolver.

Tests the check_confirmation() public function and its internal helpers
_parse_threshold and _reconstruct_level_string.
"""

from unittest.mock import patch

import pytest

from dct_mcp_server.tools.core.confirmation_resolver import (
    _parse_threshold,
    _reconstruct_level_string,
    check_confirmation,
)

# ---------------------------------------------------------------------------
# Helpers: _parse_threshold
# ---------------------------------------------------------------------------


def test_parse_threshold_valid():
    assert _parse_threshold("retention_check:7", "retention_check:") == 7


def test_parse_threshold_larger_number():
    assert _parse_threshold("policy_impact_check:100", "policy_impact_check:") == 100


def test_parse_threshold_invalid_string_returns_zero():
    assert _parse_threshold("retention_check:abc", "retention_check:") == 0


def test_parse_threshold_empty_suffix_returns_zero():
    assert _parse_threshold("retention_check:", "retention_check:") == 0


# ---------------------------------------------------------------------------
# Helpers: _reconstruct_level_string
# ---------------------------------------------------------------------------


def test_reconstruct_level_string_with_threshold():
    result = _reconstruct_level_string("retention_check", 7, {})
    assert result == "retention_check:7"


def test_reconstruct_level_string_without_threshold():
    result = _reconstruct_level_string("manual", None, {})
    assert result == "manual"


def test_reconstruct_level_string_full_string_already():
    result = _reconstruct_level_string("retention_check:7", None, {})
    assert result == "retention_check:7"


# ---------------------------------------------------------------------------
# check_confirmation — level="none" cases
# ---------------------------------------------------------------------------

_NONE_RESULT = {"level": "none", "message": None, "conditional": False, "threshold_days": None}


def test_level_none_returns_no_confirmation():
    with patch(
        "dct_mcp_server.tools.core.confirmation_resolver.get_confirmation_for_operation",
        return_value=_NONE_RESULT,
    ):
        result = check_confirmation("GET", "/vdbs/search")

    assert result["requires_confirmation"] is False
    assert result["confirmation_level"] is None
    assert result["message_template"] is None


# ---------------------------------------------------------------------------
# check_confirmation — standard (non-conditional) levels
# ---------------------------------------------------------------------------


def test_manual_level_non_conditional_requires_confirmation():
    mock_raw = {
        "level": "manual",
        "message": "Please confirm deletion",
        "conditional": False,
        "threshold_days": None,
    }
    with patch(
        "dct_mcp_server.tools.core.confirmation_resolver.get_confirmation_for_operation",
        return_value=mock_raw,
    ):
        result = check_confirmation("POST", "/vdbs/vdb-123/delete")

    assert result["requires_confirmation"] is True
    assert result["confirmation_level"] == "manual"
    assert result["message_template"] == "Please confirm deletion"


def test_elevated_level_non_conditional_requires_confirmation():
    mock_raw = {
        "level": "elevated",
        "message": "Warning: this is impactful",
        "conditional": False,
        "threshold_days": None,
    }
    with patch(
        "dct_mcp_server.tools.core.confirmation_resolver.get_confirmation_for_operation",
        return_value=mock_raw,
    ):
        result = check_confirmation("POST", "/vdbs/vdb-123/refresh")

    assert result["requires_confirmation"] is True
    assert result["confirmation_level"] == "elevated"


def test_standard_level_requires_confirmation():
    mock_raw = {
        "level": "standard",
        "message": "Confirm operation",
        "conditional": False,
        "threshold_days": None,
    }
    with patch(
        "dct_mcp_server.tools.core.confirmation_resolver.get_confirmation_for_operation",
        return_value=mock_raw,
    ):
        result = check_confirmation("DELETE", "/some/path")

    assert result["requires_confirmation"] is True
    assert result["confirmation_level"] == "standard"


# ---------------------------------------------------------------------------
# check_confirmation — retention_check conditional
# ---------------------------------------------------------------------------


def test_retention_check_retention_below_threshold_requires_confirmation():
    """retention_days < N → confirmation required."""
    mock_raw = {
        "level": "retention_check",
        "message": "Low retention warning",
        "conditional": True,
        "threshold_days": 7,
    }
    with patch(
        "dct_mcp_server.tools.core.confirmation_resolver.get_confirmation_for_operation",
        return_value=mock_raw,
    ):
        result = check_confirmation(
            "POST", "/snapshots/snap-1/delete", context={"retention_days": 3}
        )

    assert result["requires_confirmation"] is True
    assert result["confirmation_level"] == "retention_check"


def test_retention_check_retention_equal_threshold_no_confirmation():
    """retention_days >= N → no confirmation (threshold NOT exceeded)."""
    mock_raw = {
        "level": "retention_check",
        "message": "Low retention warning",
        "conditional": True,
        "threshold_days": 7,
    }
    with patch(
        "dct_mcp_server.tools.core.confirmation_resolver.get_confirmation_for_operation",
        return_value=mock_raw,
    ):
        result = check_confirmation(
            "POST", "/snapshots/snap-1/delete", context={"retention_days": 7}
        )

    assert result["requires_confirmation"] is False
    assert result["confirmation_level"] is None


def test_retention_check_retention_above_threshold_no_confirmation():
    """retention_days > N → no confirmation."""
    mock_raw = {
        "level": "retention_check",
        "message": "Low retention warning",
        "conditional": True,
        "threshold_days": 7,
    }
    with patch(
        "dct_mcp_server.tools.core.confirmation_resolver.get_confirmation_for_operation",
        return_value=mock_raw,
    ):
        result = check_confirmation(
            "POST", "/snapshots/snap-1/delete", context={"retention_days": 30}
        )

    assert result["requires_confirmation"] is False


def test_retention_check_no_context_no_confirmation():
    """retention_days=None (no context) → threshold not exceeded → no confirmation."""
    mock_raw = {
        "level": "retention_check",
        "message": "Low retention warning",
        "conditional": True,
        "threshold_days": 7,
    }
    with patch(
        "dct_mcp_server.tools.core.confirmation_resolver.get_confirmation_for_operation",
        return_value=mock_raw,
    ):
        result = check_confirmation("POST", "/snapshots/snap-1/delete")

    assert result["requires_confirmation"] is False


def test_retention_check_empty_context_no_confirmation():
    """Empty context dict (retention_days absent) → no confirmation."""
    mock_raw = {
        "level": "retention_check",
        "message": "Low retention warning",
        "conditional": True,
        "threshold_days": 7,
    }
    with patch(
        "dct_mcp_server.tools.core.confirmation_resolver.get_confirmation_for_operation",
        return_value=mock_raw,
    ):
        result = check_confirmation("POST", "/snapshots/snap-1/delete", context={})

    assert result["requires_confirmation"] is False


# ---------------------------------------------------------------------------
# check_confirmation — policy_impact_check conditional
# ---------------------------------------------------------------------------


def test_policy_impact_check_above_threshold_requires_confirmation():
    """affected_object_count > N → confirmation required."""
    mock_raw = {
        "level": "policy_impact_check",
        "message": "High impact warning",
        "conditional": True,
        "threshold_days": 10,
    }
    with patch(
        "dct_mcp_server.tools.core.confirmation_resolver.get_confirmation_for_operation",
        return_value=mock_raw,
    ):
        result = check_confirmation(
            "POST", "/policies/policy-1/apply", context={"affected_object_count": 50}
        )

    assert result["requires_confirmation"] is True
    assert result["confirmation_level"] == "policy_impact_check"


def test_policy_impact_check_equal_threshold_no_confirmation():
    """affected_object_count == N → NOT exceeded → no confirmation."""
    mock_raw = {
        "level": "policy_impact_check",
        "message": "High impact warning",
        "conditional": True,
        "threshold_days": 10,
    }
    with patch(
        "dct_mcp_server.tools.core.confirmation_resolver.get_confirmation_for_operation",
        return_value=mock_raw,
    ):
        result = check_confirmation(
            "POST", "/policies/policy-1/apply", context={"affected_object_count": 10}
        )

    assert result["requires_confirmation"] is False


def test_policy_impact_check_below_threshold_no_confirmation():
    """affected_object_count < N → no confirmation."""
    mock_raw = {
        "level": "policy_impact_check",
        "message": "High impact warning",
        "conditional": True,
        "threshold_days": 10,
    }
    with patch(
        "dct_mcp_server.tools.core.confirmation_resolver.get_confirmation_for_operation",
        return_value=mock_raw,
    ):
        result = check_confirmation(
            "POST", "/policies/policy-1/apply", context={"affected_object_count": 5}
        )

    assert result["requires_confirmation"] is False


def test_policy_impact_check_no_context_no_confirmation():
    """No context (affected_object_count=None) → no confirmation."""
    mock_raw = {
        "level": "policy_impact_check",
        "message": "High impact warning",
        "conditional": True,
        "threshold_days": 10,
    }
    with patch(
        "dct_mcp_server.tools.core.confirmation_resolver.get_confirmation_for_operation",
        return_value=mock_raw,
    ):
        result = check_confirmation("POST", "/policies/policy-1/apply")

    assert result["requires_confirmation"] is False


# ---------------------------------------------------------------------------
# check_confirmation — unknown conditional type (safety net)
# ---------------------------------------------------------------------------


def test_unknown_conditional_type_requires_confirmation():
    """Unknown conditional type is treated conservatively — requires confirmation."""
    mock_raw = {
        "level": "some_future_check",
        "message": "Unknown conditional",
        "conditional": True,
        "threshold_days": None,
    }
    with patch(
        "dct_mcp_server.tools.core.confirmation_resolver.get_confirmation_for_operation",
        return_value=mock_raw,
    ):
        result = check_confirmation("DELETE", "/something")

    assert result["requires_confirmation"] is True
    assert result["confirmation_level"] == "some_future_check"


# ---------------------------------------------------------------------------
# check_confirmation — context=None is handled gracefully
# ---------------------------------------------------------------------------


def test_context_none_defaults_to_empty_dict():
    """Passing context=None should not raise; treated same as empty dict."""
    mock_raw = {
        "level": "none",
        "message": None,
        "conditional": False,
        "threshold_days": None,
    }
    with patch(
        "dct_mcp_server.tools.core.confirmation_resolver.get_confirmation_for_operation",
        return_value=mock_raw,
    ):
        result = check_confirmation("GET", "/vdbs", context=None)

    assert result["requires_confirmation"] is False
