"""Unit tests for AppData operation loader (DLPXECO-14781)."""
import pytest
from dct_mcp_server.config.loader import (
    AppDataOperation,
    load_appdata_operations,
    match_appdata_operation,
    clear_cache,
)


@pytest.fixture(autouse=True)
def reset_cache():
    clear_cache()
    yield
    clear_cache()


def test_load_returns_ops_and_toolkit_path():
    ops, toolkit_path = load_appdata_operations()
    assert toolkit_path == "/toolkits/{id}"
    assert len(ops) == 19


def test_all_ops_have_sub_objects():
    ops, _ = load_appdata_operations()
    for op in ops:
        assert op.sub_objects, f"{op.method} {op.path_template} has no sub_objects"


def test_dsources_appdata_post():
    op = match_appdata_operation("POST", "/dsources/appdata")
    assert op is not None
    assert "parameters" in op.sub_objects
    assert op.sub_objects["parameters"] == "linked_source_definition"
    assert "sync_parameters" in op.sub_objects
    assert op.sub_objects["sync_parameters"] == "snapshot_parameters_definition"


def test_dsources_appdata_patch():
    op = match_appdata_operation("PATCH", "/dsources/appdata/ds-123")
    assert op is not None
    assert op.path_template == "/dsources/appdata/{dsourceId}"
    assert "parameters" in op.sub_objects
    assert op.sub_objects["parameters"] == "linked_source_definition"


def test_vdbs_provision_by_snapshot():
    op = match_appdata_operation("POST", "/vdbs/provision_by_snapshot")
    assert op is not None
    assert "appdata_source_params" in op.sub_objects
    assert "appdata_config_params" in op.sub_objects


def test_no_match_for_native_operation():
    op = match_appdata_operation("POST", "/environments")
    assert op is None


def test_no_match_for_get():
    op = match_appdata_operation("GET", "/dsources/appdata")
    assert op is None


def test_path_with_dct_prefix_stripped():
    # Paths may come in with /dct/v3 prefix from the resolved path
    op = match_appdata_operation("POST", "/dct/v3/dsources/appdata")
    assert op is not None


def test_match_export_by_snapshot_dsource():
    op = match_appdata_operation("POST", "/dsources/ds-abc/export-by-snapshot")
    assert op is not None
    assert "appdata_config_params" in op.sub_objects
    assert "appdata_v2p_params" in op.sub_objects


def test_match_export_by_snapshot_vdb():
    op = match_appdata_operation("POST", "/vdbs/vdb-abc/export-by-snapshot")
    assert op is not None
    assert "appdata_config_params" in op.sub_objects


def test_chains_nonempty():
    op = match_appdata_operation("POST", "/dsources/appdata")
    assert op is not None
    assert len(op.chains) > 0


def test_load_is_cached(monkeypatch):
    calls = []
    original = load_appdata_operations.__wrapped__
    ops1, _ = load_appdata_operations()
    ops2, _ = load_appdata_operations()
    assert ops1 is ops2  # same object (cached)
