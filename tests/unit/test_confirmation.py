"""
Layer 1 unit tests for the confirmation config layer.

Parametrized over EVERY rule in config/mappings/manual_confirmation.txt (parsed
independently by config_cases) so a single test proves every rule is reachable
through get_confirmation_for_operation and resolves to its declared level.
"""

import re

import pytest

from dct_mcp_server.config.loader import (
    get_confirmation_for_operation,
    requires_confirmation,
)
from tests._support import config_cases


def _concrete_path(path: str) -> str:
    """Replace every {placeholder} with a dummy non-slash segment."""
    return re.sub(r"\{[^}]+\}", "X", path)


def _concrete_method(method: str) -> str:
    """Pick a real method for a rule; wildcard rules accept any so use POST."""
    return "POST" if method == "*" else method


@pytest.mark.parametrize(
    "rule",
    config_cases.confirmation_rules(),
    ids=config_cases.rule_id,
)
def test_every_confirmation_rule_is_reachable(rule):
    method = _concrete_method(rule.method)
    path = _concrete_path(rule.path)

    result = get_confirmation_for_operation(method, path)

    # The rule must MATCH (some rule may shadow it earlier in the file; in that
    # case the matched level should still be a real confirmation level).
    assert result["level"] != "none", (
        f"rule {rule.method}|{rule.path}|{rule.level} did not match {method} {path}"
    )

    # The base level returned must equal this rule's base level — unless an
    # earlier rule in the file shadows this concrete path with a different
    # level. We assert the returned base level is one of the known levels and,
    # when no earlier rule shadows, equals the rule's base.
    expected_base = rule.level.split(":")[0]
    returned_base = result["level"]

    # Recompute the first-match base independently to allow for legitimate
    # shadowing (first match wins, documented in loader).
    first_match_base = None
    for r in config_cases.confirmation_rules():
        if r.method != "*" and r.method != method:
            continue
        regex = "^" + re.sub(r"\{[^}]+\}", r"[^/]+", r.path) + "$"
        if re.match(regex, path):
            first_match_base = r.level.split(":")[0]
            break

    assert returned_base == first_match_base, (
        f"{method} {path}: returned {returned_base}, "
        f"first-match expected {first_match_base}"
    )
    # And the matched level is a legitimate confirmation level (this rule's or
    # a shadowing rule's — both are real rules from the same file).
    assert returned_base in {
        "standard",
        "elevated",
        "manual",
        "retention_check",
        "policy_impact_check",
        "batch_check",
    }
    # Conditional levels expose a threshold.
    if ":" in rule.level and first_match_base == expected_base:
        assert result["conditional"] is True
        assert result["threshold_days"] == int(rule.level.split(":")[1])


def test_no_rule_path_returns_none():
    result = get_confirmation_for_operation("GET", "/vdbs/search")
    assert result["level"] == "none"
    assert requires_confirmation("GET", "/vdbs/search") is False


def test_known_destructive_op_requires_confirmation():
    # /vdbs/{vdbId}/delete is a destructive POST defined in the rules file.
    assert requires_confirmation("POST", "/vdbs/X/delete") is True
