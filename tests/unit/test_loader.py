"""
Layer 1 unit tests for config/loader.py, cross-checked against the independent
config_cases oracle (which parses the same .txt files without using the loader).
"""

from dct_mcp_server.config.loader import (
    get_modules_for_toolset,
    get_tools_for_toolset,
)
from tests._support import config_cases


def test_modules_for_self_service():
    assert set(get_modules_for_toolset("self_service")) == {
        "dataset_endpoints_tool",
        "job_endpoints_tool",
    }


def test_loader_tool_names_match_oracle():
    loader_names = {t["name"] for t in get_tools_for_toolset("self_service")}
    oracle_names = set(config_cases.tools_for("self_service"))
    assert loader_names == oracle_names


def test_loader_actions_match_oracle_per_tool():
    loader = {
        t["name"]: set(t["actions"]) for t in get_tools_for_toolset("self_service")
    }
    for tool, apis in config_cases.tools_for("self_service").items():
        oracle_actions = {action for (_m, _p, action) in apis}
        assert loader[tool] == oracle_actions, f"action mismatch for {tool}"


def test_provision_inherits_self_service():
    base = set(config_cases.tools_for("self_service"))
    provision = set(config_cases.tools_for("self_service_provision"))
    assert base.issubset(provision)


def test_provision_adds_provision_actions():
    provision_tools = config_cases.tools_for("self_service_provision")
    all_actions = {
        action for apis in provision_tools.values() for (_m, _p, action) in apis
    }
    provision_actions = {a for a in all_actions if a.startswith("provision_")}
    assert provision_actions, (
        "expected self_service_provision to add provision_* actions"
    )
