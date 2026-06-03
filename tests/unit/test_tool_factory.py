"""
Layer 1 unit tests for the toolset -> grouped-tools mapping the OpenAPI tool
generator relies on.

We deliberately stay OFFLINE: rather than invoking tool_factory's live spec
download, we assert the offline `load_toolset_grouped_apis` mapping (the same
data the generator consumes to decide which grouped tools/actions to emit)
matches the independent config_cases oracle for self_service.
"""

from dct_mcp_server.config.loader import load_toolset_grouped_apis
from tests._support import config_cases


def test_grouped_apis_tool_names_match_oracle():
    grouped = load_toolset_grouped_apis("self_service")
    assert set(grouped) == set(config_cases.tools_for("self_service"))


def test_grouped_apis_actions_match_oracle_per_tool():
    grouped = load_toolset_grouped_apis("self_service")
    for tool, apis in config_cases.tools_for("self_service").items():
        oracle_actions = {action for (_m, _p, action) in apis}
        grouped_actions = {api["action"] for api in grouped[tool]["apis"]}
        assert grouped_actions == oracle_actions, f"action mismatch for {tool}"


def test_grouped_apis_method_path_match_oracle_per_tool():
    grouped = load_toolset_grouped_apis("self_service")
    for tool, apis in config_cases.tools_for("self_service").items():
        oracle_triples = {(m, p, a) for (m, p, a) in apis}
        grouped_triples = {
            (api["method"], api["path"], api["action"])
            for api in grouped[tool]["apis"]
        }
        assert grouped_triples == oracle_triples, f"triple mismatch for {tool}"
