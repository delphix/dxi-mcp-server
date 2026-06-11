"""Validation tests for the schema-driven connector fixture layer."""

import os
from pathlib import Path

import pytest
import yaml

from tests.llm_local.connector_fixtures import (
    ConnectorSpec, load_connector_spec, schema_link_hints, _SCHEMA_FILE,
)

_SCHEMA = yaml.safe_load(_SCHEMA_FILE.read_text()) if _SCHEMA_FILE.exists() else {}
_KNOWN_TYPES = list(_SCHEMA.get("connectors", {}).keys())


# ── Offline unit tests ────────────────────────────────────────────────────────

def test_schema_file_exists_and_has_connectors():
    assert _SCHEMA_FILE.exists(), f"Schema file missing: {_SCHEMA_FILE}"
    assert _KNOWN_TYPES, "Schema has no connector definitions"


def test_all_schema_connectors_load():
    for ctype in _KNOWN_TYPES:
        spec = load_connector_spec(ctype)
        assert isinstance(spec, ConnectorSpec)
        assert spec.connector_type == ctype
        assert spec.dsource_link_action.startswith("dsource_link_")
        assert spec.display_name


def test_mysql_has_expected_link_fields():
    spec = load_connector_spec("mysql")
    required = {"mountPath", "stagingBasedir", "stagingPort",
                "sourceip", "sourceUser", "sourcePass", "serverId"}
    assert required.issubset(spec.link_fields), (
        f"Missing MySQL link fields: {required - set(spec.link_fields)}"
    )


def test_mysql_has_expected_provision_fields():
    spec = load_connector_spec("mysql")
    required = {"vdbUser", "vdbPass", "baseDir", "port", "serverId", "mPath"}
    assert required.issubset(spec.provision_fields), (
        f"Missing MySQL VDB provision fields: {required - set(spec.provision_fields)}"
    )


def test_link_prompt_detail_non_empty_for_mysql():
    spec = load_connector_spec("mysql")
    detail = spec.link_prompt_detail()
    assert "mountPath" in detail
    assert "connector-specific" in detail


def test_short_host_names():
    spec = load_connector_spec("mysql")
    assert "." not in spec.source_short
    assert "." not in spec.target_short


def test_unknown_connector_type_raises():
    with pytest.raises(ValueError, match="Unknown connector type"):
        load_connector_spec("cobol")


def test_schema_hints_non_empty_for_mysql():
    hints = schema_link_hints("mysql")
    assert "mountPath" in hints
    assert "stagingPort" in hints
    assert "default" in hints or "example" in hints


def test_ci_env_var_override(tmp_path):
    """CI path: env vars override the secrets file."""
    fake_secrets = tmp_path / "no.yaml"  # doesn't exist
    old = {
        k: os.environ.pop(k, None)
        for k in ["DCT_CONNECTOR_MYSQL_SOURCE_HOST",
                  "DCT_CONNECTOR_MYSQL_TARGET_HOST",
                  "DCT_CONNECTOR_MYSQL_LINK_PASSWORD"]
    }
    try:
        os.environ["DCT_CONNECTOR_MYSQL_SOURCE_HOST"] = "ci-src.example.com"
        os.environ["DCT_CONNECTOR_MYSQL_TARGET_HOST"] = "ci-tgt.example.com"
        os.environ["DCT_CONNECTOR_MYSQL_LINK_PASSWORD"] = "ci-secret"
        spec = load_connector_spec("mysql", secrets_file=fake_secrets)
        assert spec.source_host == "ci-src.example.com"
        assert spec.target_host == "ci-tgt.example.com"
        assert spec.link_password == "ci-secret"
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_session_fixture_loads(connector_spec):
    """Session fixture — loads from .secrets.yaml or env vars, no DCT call."""
    assert connector_spec.connector_type in _KNOWN_TYPES
    assert connector_spec.dsource_link_action
    assert connector_spec.display_name
    print(f"\n  {connector_spec.connector_type}: "
          f"source={connector_spec.source_host} target={connector_spec.target_host}")
