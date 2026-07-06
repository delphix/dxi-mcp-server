"""
Unit tests for the destructive-delete confirmation safety net.

Bug: a DELETE with no explicit rule in manual_confirmation.txt (e.g.
DELETE /synthetic/applications/{syntheticApplicationId}) executed with no
confirmation, because the rule file is an allowlist. The resolver now defaults
any unmatched destructive delete to manual confirmation, while explicit rules
still take precedence.

All tests in this module were AI-generated. Each test carries an
``# AI-generated`` comment on the first line of its body.
"""

from dct_mcp_server.config.loader import get_confirmation_for_operation
from dct_mcp_server.tools.core.confirmation_resolver import check_confirmation


# ---------------------------------------------------------------------------
# Reported bug: synthetic data application delete is now gated
# ---------------------------------------------------------------------------


def test_synthetic_application_delete_requires_manual_confirmation():
    # AI-generated
    result = get_confirmation_for_operation("DELETE", "/synthetic/applications/app-123")
    assert result["level"] == "manual"
    assert result["conditional"] is False


def test_synthetic_application_delete_gated_via_dynamic_resolver():
    # AI-generated
    conf = check_confirmation("DELETE", "/synthetic/applications/app-123")
    assert conf["requires_confirmation"] is True
    assert conf["confirmation_level"] == "manual"


# ---------------------------------------------------------------------------
# The whole class of unlisted deletes is covered
# ---------------------------------------------------------------------------


def test_unlisted_delete_paths_default_to_manual():
    # AI-generated
    for path in (
        "/synthetic/connectors/c-1",
        "/synthetic/datasets/d-1",
        "/synthetic/generators/g-1",
        "/synthetic/jobs/j-1",
    ):
        assert get_confirmation_for_operation("DELETE", path)["level"] == "manual"


def test_post_delete_action_path_defaults_to_manual():
    # AI-generated
    result = get_confirmation_for_operation(
        "POST", "/synthetic/datasets/d-1/structures/delete"
    )
    assert result["level"] == "manual"


# ---------------------------------------------------------------------------
# Explicit rules still take precedence
# ---------------------------------------------------------------------------


def test_explicit_rule_overrides_safety_net_message():
    # AI-generated
    result = get_confirmation_for_operation("DELETE", "/bookmarks/bk-1")
    assert result["level"] == "manual"
    # Tailored message from manual_confirmation.txt, not the generic safety-net one.
    assert "bookmark" in result["message"].lower()


# ---------------------------------------------------------------------------
# Non-destructive operations are unaffected (no over-gating of reads)
# ---------------------------------------------------------------------------


def test_get_is_not_gated():
    # AI-generated
    assert (
        get_confirmation_for_operation("GET", "/synthetic/applications/app-123")[
            "level"
        ]
        == "none"
    )


def test_non_delete_post_is_not_gated():
    # AI-generated
    # A POST that is not a ".../delete" action must not be gated by the safety net.
    assert (
        get_confirmation_for_operation("POST", "/synthetic/applications/app-1/sync")[
            "level"
        ]
        == "none"
    )
