"""
Layer 1 unit tests for the pure helper functions shared by every pre-built tool
module: build_params (drops None and '') and _SafeDict (missing key -> literal).
"""

from dct_mcp_server.tools.dataset_endpoints_tool import build_params, _SafeDict


def test_build_params_drops_none_and_empty_string_but_keeps_zero_and_false():
    result = build_params(a=1, b=None, c="", d=0, e=False)
    assert result == {"a": 1, "d": 0, "e": False}


def test_build_params_empty():
    assert build_params() == {}


def test_build_params_keeps_falsy_zero_and_false_only():
    # 0 and False are falsy but must be kept; only None and '' are dropped.
    assert build_params(x=0) == {"x": 0}
    assert build_params(x=False) == {"x": False}
    assert build_params(x=None) == {}
    assert build_params(x="") == {}


def test_safedict_missing_key_stays_literal():
    assert "{x}-{y}".format_map(_SafeDict(x="A")) == "A-{y}"


def test_safedict_all_keys_present():
    assert "{x}-{y}".format_map(_SafeDict(x="A", y="B")) == "A-B"
