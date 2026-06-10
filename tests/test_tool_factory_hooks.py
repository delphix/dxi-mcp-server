"""Unit tests for hook-key normalization in tool_factory (DLPXECO-13799)."""

from dct_mcp_server.tools.core.tool_factory import (
    _VALID_HOOK_TYPES,
    _camel_to_snake,
    _normalize_hooks_in_body,
)


def test_normalize_hooks_camelcase_keys_rewritten():
    body = {"hooks": {"configureClone": [{"command": "echo hi"}]}}
    err = _normalize_hooks_in_body(body)
    assert err is None
    assert body["hooks"] == {"configure_clone": [{"command": "echo hi"}]}


def test_normalize_hooks_snake_case_passthrough():
    body = {"hooks": {"configure_clone": [{"command": "echo hi"}]}}
    original = {"configure_clone": [{"command": "echo hi"}]}
    err = _normalize_hooks_in_body(body)
    assert err is None
    assert body["hooks"] == original


def test_normalize_hooks_mixed_keys():
    body = {
        "hooks": {
            "configureClone": [{"name": "a"}],
            "pre_refresh": [{"name": "b"}],
            "postSnapshot": [{"name": "c"}],
        }
    }
    err = _normalize_hooks_in_body(body)
    assert err is None
    assert set(body["hooks"].keys()) == {"configure_clone", "pre_refresh", "post_snapshot"}
    assert body["hooks"]["configure_clone"] == [{"name": "a"}]
    assert body["hooks"]["pre_refresh"] == [{"name": "b"}]
    assert body["hooks"]["post_snapshot"] == [{"name": "c"}]


def test_normalize_hooks_unknown_key_returns_error():
    body = {"hooks": {"bogusHook": [{"name": "x"}]}}
    err = _normalize_hooks_in_body(body)
    assert err is not None
    assert "bogusHook" in err["error"]
    assert "valid_hook_types" in err
    # Body is left as-is on error (no partial mutation guarantee needed; just no crash).


def test_normalize_hooks_no_hooks_field():
    body = {"name": "test", "description": "no hooks here"}
    err = _normalize_hooks_in_body(body)
    assert err is None
    assert body == {"name": "test", "description": "no hooks here"}


def test_normalize_hooks_non_dict_value():
    for value in (None, [], "configure_clone"):
        body = {"hooks": value}
        err = _normalize_hooks_in_body(body)
        assert err is None
        assert body["hooks"] == value


def test_normalize_hooks_empty_dict():
    body = {"hooks": {}}
    err = _normalize_hooks_in_body(body)
    assert err is None
    assert body["hooks"] == {}


def test_normalize_hooks_none_body():
    assert _normalize_hooks_in_body(None) is None
    assert _normalize_hooks_in_body({}) is None


def test_all_known_camelcase_variants_normalize():
    camel_to_snake = {
        "preRefresh": "pre_refresh",
        "postRefresh": "post_refresh",
        "preSelfRefresh": "pre_self_refresh",
        "postSelfRefresh": "post_self_refresh",
        "preRollback": "pre_rollback",
        "postRollback": "post_rollback",
        "configureClone": "configure_clone",
        "preSnapshot": "pre_snapshot",
        "postSnapshot": "post_snapshot",
        "preStart": "pre_start",
        "postStart": "post_start",
        "preStop": "pre_stop",
        "postStop": "post_stop",
    }
    for camel, snake in camel_to_snake.items():
        body = {"hooks": {camel: [{"name": camel}]}}
        err = _normalize_hooks_in_body(body)
        assert err is None, f"unexpected error for {camel}"
        assert list(body["hooks"].keys()) == [snake]


def test_camel_to_snake_helper():
    assert _camel_to_snake("configureClone") == "configure_clone"
    assert _camel_to_snake("preSelfRefresh") == "pre_self_refresh"
    assert _camel_to_snake("already_snake") == "already_snake"
    assert _camel_to_snake("simple") == "simple"


def test_valid_hook_types_matches_spec():
    # Sanity: every entry in our enum is snake_case.
    for h in _VALID_HOOK_TYPES:
        assert h.islower()
        assert " " not in h


def test_normalize_hooks_duplicate_after_rewrite_returns_error():
    body = {"hooks": {"configureClone": [1], "configure_clone": [2]}}
    err = _normalize_hooks_in_body(body)
    assert err is not None
    assert "configure_clone" in err["error"]
