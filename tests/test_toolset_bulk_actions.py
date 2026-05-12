"""Tests for bulk action registration in toolset .txt config files."""
import pytest
from dct_mcp_server.config.loader import load_toolset_grouped_apis, load_toolset_apis


BULK_ACTIONS = {"bulk_start", "bulk_stop", "bulk_enable", "bulk_disable"}


def test_self_service_vdb_tool_has_all_bulk_actions():
    grouped = load_toolset_grouped_apis("self_service")
    vdb_actions = {api["action"] for api in grouped["vdb_tool"]["apis"]}
    assert BULK_ACTIONS.issubset(vdb_actions), (
        f"Missing bulk actions in self_service vdb_tool: {BULK_ACTIONS - vdb_actions}"
    )


def test_continuous_data_admin_data_tool_has_all_bulk_actions():
    grouped = load_toolset_grouped_apis("continuous_data_admin")
    data_actions = {api["action"] for api in grouped["data_tool"]["apis"]}
    assert BULK_ACTIONS.issubset(data_actions), (
        f"Missing bulk actions in continuous_data_admin data_tool: {BULK_ACTIONS - data_actions}"
    )


def test_reporting_insights_has_no_bulk_actions():
    apis = load_toolset_apis("reporting_insights")
    all_actions = {api["action"] for api in apis}
    overlap = BULK_ACTIONS & all_actions
    assert not overlap, f"Unexpected bulk actions in reporting_insights: {overlap}"
