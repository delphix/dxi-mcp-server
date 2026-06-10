"""P1 validation — tests for the ConnectorSpec fixture layer."""

import pytest
from tests.llm_local.connector_fixtures import load_connector_spec, ConnectorSpec, _LOADERS


# ── Offline unit tests ────────────────────────────────────────────────────────

def test_all_connector_types_load():
    for ctype in _LOADERS:
        spec = load_connector_spec(ctype)
        assert isinstance(spec, ConnectorSpec)
        assert spec.connector_type == ctype
        assert spec.dsource_link_action.startswith("dsource_link_")


def test_appdata_spec_has_mysql_link_fields():
    spec = load_connector_spec("appdata")
    required = {"mountPath", "stagingBasedir", "stagingPort", "sourceUser",
                "sourcePass", "sourceip", "serverId"}
    assert required.issubset(spec.link_fields), (
        f"Missing MySQL link fields: {required - set(spec.link_fields)}"
    )


def test_appdata_spec_has_vdb_provision_fields():
    spec = load_connector_spec("appdata")
    required = {"vdbUser", "vdbPass", "baseDir", "port", "serverId", "mPath"}
    assert required.issubset(spec.provision_fields), (
        f"Missing MySQL VDB provision fields: {required - set(spec.provision_fields)}"
    )


def test_appdata_link_prompt_detail_non_empty():
    spec = load_connector_spec("appdata")
    detail = spec.link_prompt_detail()
    assert "mountPath" in detail
    assert "connector-specific" in detail


def test_short_host_names():
    spec = load_connector_spec("appdata")
    assert "." not in spec.source_short
    assert "." not in spec.target_short


def test_unknown_connector_type_raises():
    with pytest.raises(ValueError, match="Unknown connector type"):
        load_connector_spec("postgres")


def test_session_fixture_loads(connector_spec):
    """Live or offline — fixture just reads env vars, no DCT call needed."""
    assert connector_spec.connector_type in _LOADERS
    assert connector_spec.dsource_link_action
    assert connector_spec.source_host
    assert connector_spec.target_host
    print(f"\n  type={connector_spec.connector_type} "
          f"source={connector_spec.source_host} "
          f"target={connector_spec.target_host}")
