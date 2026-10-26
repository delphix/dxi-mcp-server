"""Unit tests for connector_secrets.py (DLPXECO-14781)."""

import json
import pytest
from pathlib import Path

from dct_mcp_server.tools.core.connector_secrets import (
    walk_secret_paths,
    expand_and_flag,
    parse_applied,
    drop_applied,
    clear_caches,
    SecretPath,
    FlaggedLocation,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "toolkits"


@pytest.fixture(autouse=True)
def reset():
    clear_caches()
    yield
    clear_caches()


# ── walk_secret_paths ─────────────────────────────────────────────────────────


def test_flat_password_field():
    schema = {
        "type": "object",
        "properties": {
            "username": {"type": "string"},
            "password": {"type": "string", "format": "password"},
        },
        "required": ["username", "password"],
    }
    paths = walk_secret_paths(schema)
    names = {p.path for p in paths}
    assert "password" in names
    assert "username" not in names


def test_required_flag_propagated():
    schema = {
        "type": "object",
        "properties": {
            "secret": {"type": "string", "format": "password"},
        },
        "required": ["secret"],
    }
    paths = walk_secret_paths(schema)
    p = next(x for x in paths if x.path == "secret")
    assert p.required is True


def test_optional_password_not_required():
    schema = {
        "type": "object",
        "properties": {
            "optSecret": {"type": "string", "format": "password"},
        },
    }
    paths = walk_secret_paths(schema)
    p = next(x for x in paths if x.path == "optSecret")
    assert p.required is False


def test_nested_object():
    schema = {
        "type": "object",
        "properties": {
            "credentials": {
                "type": "object",
                "properties": {
                    "user": {"type": "string"},
                    "pass": {"type": "string", "format": "password"},
                },
                "required": ["user", "pass"],
            }
        },
    }
    paths = walk_secret_paths(schema)
    names = {p.path for p in paths}
    assert "credentials.pass" in names
    assert "credentials.user" not in names


def test_array_items():
    schema = {
        "type": "object",
        "properties": {
            "nodes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "nodeId": {"type": "string"},
                        "nodePassword": {"type": "string", "format": "password"},
                    },
                    "required": ["nodeId", "nodePassword"],
                },
            }
        },
    }
    paths = walk_secret_paths(schema)
    names = {p.path for p in paths}
    assert "nodes[*].nodePassword" in names
    assert "nodes[*].nodeId" not in names


def test_ref_resolution():
    schema = {
        "type": "object",
        "properties": {"creds": {"$ref": "#/definitions/Creds"}},
        "definitions": {
            "Creds": {
                "type": "object",
                "properties": {
                    "pw": {"type": "string", "format": "password"},
                },
                "required": ["pw"],
            }
        },
    }
    paths = walk_secret_paths(schema, root=schema)
    names = {p.path for p in paths}
    assert "creds.pw" in names


def test_oneof_marks_conditional():
    schema = {
        "type": "object",
        "properties": {
            "authConfig": {
                "oneOf": [
                    {
                        "properties": {
                            "method": {"type": "string"},
                            "password": {"type": "string", "format": "password"},
                        }
                    },
                    {
                        "properties": {
                            "method": {"type": "string"},
                            "keyPath": {"type": "string"},
                        }
                    },
                ]
            }
        },
    }
    paths = walk_secret_paths(schema)
    pw = next((p for p in paths if "password" in p.path), None)
    assert pw is not None
    assert pw.conditional is True


def test_allof_not_conditional():
    schema = {
        "type": "object",
        "allOf": [
            {
                "properties": {
                    "sharedPass": {"type": "string", "format": "password"},
                }
            }
        ],
    }
    paths = walk_secret_paths(schema)
    pw = next((p for p in paths if "sharedPass" in p.path), None)
    assert pw is not None
    assert pw.conditional is False


def test_cycle_guard():
    """Self-referencing schema must not infinite-loop."""
    schema = {
        "type": "object",
        "properties": {
            "child": {"$ref": "#"},
            "pw": {"type": "string", "format": "password"},
        },
        "required": ["pw"],
    }
    paths = walk_secret_paths(schema, root=schema)
    # Should not hang; pw at root level must be found
    names = {p.path for p in paths}
    assert "pw" in names


def test_depth_bound_terminates():
    """Deeply nested schema terminates before depth 33."""
    schema: dict = {
        "type": "object",
        "properties": {"pw": {"type": "string", "format": "password"}},
    }
    current = schema
    for i in range(40):
        wrapper = {"type": "object", "properties": {"child": current}}
        current = wrapper
    paths = walk_secret_paths(current)
    assert isinstance(paths, frozenset)  # terminated without error


def test_non_dict_root_returns_empty():
    paths = walk_secret_paths("not a dict")
    assert paths == frozenset()


def test_db2_fixture_passwords():
    tk = json.loads((FIXTURES / "db2_toolkit.json").read_text())
    schema = tk["linked_source_definition"]
    paths = walk_secret_paths(schema, root=schema)
    names = {p.path for p in paths}
    assert "instancePassword" in names
    assert "nodes[*].instancePassword" in names
    assert "instanceUser" not in names
    assert "port" not in names


def test_mysql_fixture_ref_password():
    tk = json.loads((FIXTURES / "mysql_toolkit.json").read_text())
    schema = tk["linked_source_definition"]
    paths = walk_secret_paths(schema, root=schema)
    names = {p.path for p in paths}
    assert "credentials.dbPassword" in names
    assert "replicationPassword" in names


# ── expand_and_flag ───────────────────────────────────────────────────────────


def test_expand_present_flat():
    records = frozenset([SecretPath("password", required=True, conditional=False)])
    body_val = {"username": "alice", "password": "s3cr3t"}
    result = expand_and_flag("parameters", body_val, records)
    locs = {f.location for f in result}
    assert "parameters.password" in locs


def test_expand_array_present():
    records = frozenset(
        [SecretPath("nodes[*].nodePassword", required=True, conditional=False)]
    )
    body_val = {
        "nodes": [
            {"nodeId": "n1", "nodePassword": "pw1"},
            {"nodeId": "n2", "nodePassword": "pw2"},
        ]
    }
    result = expand_and_flag("parameters", body_val, records)
    locs = {f.location for f in result}
    assert "parameters.nodes[0].nodePassword" in locs
    assert "parameters.nodes[1].nodePassword" in locs


def test_expand_missing_required_flagged():
    records = frozenset([SecretPath("password", required=True, conditional=False)])
    body_val = {"username": "alice"}  # password absent
    result = expand_and_flag("parameters", body_val, records)
    locs = {f.location for f in result}
    assert "parameters.password" in locs


def test_expand_missing_optional_not_flagged():
    records = frozenset([SecretPath("optPass", required=False, conditional=False)])
    body_val = {"username": "alice"}
    result = expand_and_flag("parameters", body_val, records)
    assert result == []


def test_expand_missing_conditional_not_flagged():
    records = frozenset([SecretPath("authPass", required=True, conditional=True)])
    body_val = {"method": "key"}
    result = expand_and_flag("parameters", body_val, records)
    assert result == []


def test_expand_present_overrides_conditional():
    """A conditional field that IS present must still be flagged."""
    records = frozenset([SecretPath("authPass", required=True, conditional=True)])
    body_val = {"authPass": "typed-in-chat"}
    result = expand_and_flag("parameters", body_val, records)
    assert len(result) == 1
    assert result[0].location == "parameters.authPass"


# ── parse_applied / drop_applied ──────────────────────────────────────────────


def test_parse_applied_no_nonce(monkeypatch):
    from dct_mcp_server.tools.core import host_trust

    monkeypatch.delenv(host_trust._SENSITIVE_NONCE_ENV, raising=False)
    names, locs = parse_applied({"nonce": "any", "fields": ["password"]})
    assert names == frozenset()
    assert locs == frozenset()


def test_parse_applied_good_nonce(monkeypatch):
    from dct_mcp_server.tools.core import host_trust

    monkeypatch.setenv(host_trust._SENSITIVE_NONCE_ENV, "testnonce")
    names, locs = parse_applied(
        {"nonce": "testnonce", "fields": ["password", "parameters.dbPass"]}
    )
    assert "password" in names
    assert "parameters.dbPass" in locs


def test_drop_applied_exact_location():
    flagged = [FlaggedLocation(name="dbPass", location="parameters.dbPass")]
    result = drop_applied(flagged, frozenset(), frozenset(["parameters.dbPass"]))
    assert result == []


def test_drop_applied_bare_name():
    flagged = [FlaggedLocation(name="password", location="parameters.password")]
    result = drop_applied(flagged, frozenset(["password"]), frozenset())
    assert result == []


def test_drop_applied_relative_location():
    """Sub-object-relative location match."""
    flagged = [FlaggedLocation(name="dbPass", location="parameters.dbPass")]
    result = drop_applied(flagged, frozenset(), frozenset(["dbPass"]))
    # bare name "dbPass" matches leaf name
    assert result == []


def test_drop_applied_different_index_no_match():
    flagged = [
        FlaggedLocation(
            name="nodePassword", location="parameters.nodes[0].nodePassword"
        ),
        FlaggedLocation(
            name="nodePassword", location="parameters.nodes[1].nodePassword"
        ),
    ]
    result = drop_applied(
        flagged, frozenset(), frozenset(["parameters.nodes[0].nodePassword"])
    )
    assert len(result) == 1
    assert result[0].location == "parameters.nodes[1].nodePassword"
