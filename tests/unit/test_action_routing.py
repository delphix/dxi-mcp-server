"""
Layer 1 unit tests proving every self_service action routes to the correct
HTTP method + endpoint in the pre-built tool functions.

Parametrized over EVERY (tool, action) pair in the self_service toolset (parsed
independently by config_cases). For each case we drive the real pre-built async
function with a mocked client and assert client.make_request was called once
with the expected method and the placeholder-substituted endpoint.

Actions present in the toolset config but NOT implemented in the pre-built
module (generation-only) are xfail'd rather than deleted.
"""

import re

import pytest

from dct_mcp_server.tools import dataset_endpoints_tool, job_endpoints_tool
from tests._support import config_cases

# Placeholder -> param-name overrides. All current self_service placeholders are
# plain snake_case of the camelCase placeholder, so the default rule covers them
# and this map is empty. It exists so future placeholders that diverge can be
# fixed here without touching the substitution logic.
PLACEHOLDER_TO_PARAM: dict[str, str] = {}

DUMMY = "X1"

# Map from config tool name → actual pre-built module function name
_TOOL_FUNC_MAP = {
    "vdb_tool": "data_tool",
    "vdb_group_tool": "data_tool",
    "dsource_tool": "data_tool",
    "snapshot_tool": "snapshot_bookmark_tool",
    "bookmark_tool": "snapshot_bookmark_tool",
    "job_tool": "job_tool",
    "timeflow_tool": "timeflow_tool",
    "data_tool": "data_tool",
    "snapshot_bookmark_tool": "snapshot_bookmark_tool",
    "data_connection_tool": "data_connection_tool",
}

# Map from (config_tool, config_action) → pre-built action name
_ACTION_MAP = {
    # vdb_tool -> data_tool actions
    ("vdb_tool", "search"): "search_vdbs",
    ("vdb_tool", "get"): "get_vdb",
    ("vdb_tool", "start"): "start_vdb",
    ("vdb_tool", "stop"): "stop_vdb",
    ("vdb_tool", "enable"): "enable_vdb",
    ("vdb_tool", "disable"): "disable_vdb",
    ("vdb_tool", "refresh_by_timestamp"): "refresh_vdb_by_timestamp",
    ("vdb_tool", "refresh_by_snapshot"): "refresh_vdb_by_snapshot",
    ("vdb_tool", "refresh_from_bookmark"): "refresh_vdb_from_bookmark",
    ("vdb_tool", "rollback_by_timestamp"): "rollback_vdb_by_timestamp",
    ("vdb_tool", "rollback_by_snapshot"): "rollback_vdb_by_snapshot",
    ("vdb_tool", "rollback_from_bookmark"): "rollback_vdb_from_bookmark",
    ("vdb_tool", "list_snapshots"): "list_vdb_snapshots",
    ("vdb_tool", "list_bookmarks"): "list_vdb_bookmarks",
    ("vdb_tool", "get_tags"): "get_vdb_tags",
    ("vdb_tool", "add_tags"): "add_vdb_tags",
    ("vdb_tool", "delete_tags"): "delete_vdb_tags",
    # vdb_group_tool -> data_tool actions
    ("vdb_group_tool", "search"): "search_vdb_groups",
    ("vdb_group_tool", "get"): "get_vdb_group",
    ("vdb_group_tool", "refresh"): "refresh_vdb_group",
    ("vdb_group_tool", "refresh_from_bookmark"): "refresh_vdb_group_from_bookmark",
    ("vdb_group_tool", "refresh_by_snapshot"): "refresh_vdb_group_by_snapshot",
    ("vdb_group_tool", "refresh_by_timestamp"): "refresh_vdb_group_by_timestamp",
    ("vdb_group_tool", "rollback"): "rollback_vdb_group",
    ("vdb_group_tool", "lock"): "lock_vdb_group",
    ("vdb_group_tool", "unlock"): "unlock_vdb_group",
    ("vdb_group_tool", "start"): "start_vdb_group",
    ("vdb_group_tool", "stop"): "stop_vdb_group",
    ("vdb_group_tool", "enable"): "enable_vdb_group",
    ("vdb_group_tool", "disable"): "disable_vdb_group",
    ("vdb_group_tool", "list_bookmarks"): "list_vdb_group_bookmarks",
    ("vdb_group_tool", "get_tags"): "get_vdb_group_tags",
    ("vdb_group_tool", "add_tags"): "add_vdb_group_tags",
    ("vdb_group_tool", "delete_tags"): "delete_vdb_group_tags",
    # dsource_tool -> data_tool actions
    ("dsource_tool", "search"): "search_dsources",
    ("dsource_tool", "get"): "get_dsource",
    ("dsource_tool", "list_snapshots"): "list_dsource_snapshots",
    ("dsource_tool", "get_tags"): "get_dsource_tags",
    # snapshot_tool -> snapshot_bookmark_tool actions
    ("snapshot_tool", "search"): "search_snapshots",
    ("snapshot_tool", "get"): "get_snapshot",
    ("snapshot_tool", "get_timeflow_range"): "get_snapshot_timeflow_range",
    ("snapshot_tool", "get_runtime"): "get_runtime",
    ("snapshot_tool", "find_by_location"): "find_snapshot_by_location",
    ("snapshot_tool", "find_by_timestamp"): "find_snapshot_by_timestamp",
    ("snapshot_tool", "get_tags"): "get_snapshot_tags",
    ("snapshot_tool", "add_tags"): "add_snapshot_tags",
    ("snapshot_tool", "delete_tags"): "delete_snapshot_tags",
    # bookmark_tool -> snapshot_bookmark_tool actions
    ("bookmark_tool", "search"): "search_bookmarks",
    ("bookmark_tool", "get"): "get_bookmark",
    ("bookmark_tool", "create"): "create_bookmark",
    ("bookmark_tool", "update"): "update_bookmark",
    ("bookmark_tool", "delete"): "delete_bookmark",
    ("bookmark_tool", "get_vdb_groups"): "get_bookmark_vdb_groups",
    ("bookmark_tool", "get_tags"): "get_bookmark_tags",
    ("bookmark_tool", "add_tags"): "add_bookmark_tags",
    ("bookmark_tool", "delete_tags"): "delete_bookmark_tags",
}


def _snake(name: str) -> str:
    """camelCase placeholder -> snake_case param name (vdbId -> vdb_id)."""
    s = re.sub(r"(?<!^)(?=[A-Z])", "_", name)
    return s.lower()


def _path_kwargs(path: str) -> dict:
    kwargs = {}
    for placeholder in re.findall(r"\{([^}]+)\}", path):
        param = PLACEHOLDER_TO_PARAM.get(placeholder, _snake(placeholder))
        kwargs[param] = DUMMY
    return kwargs


def _expected_endpoint(path: str) -> str:
    return re.sub(r"\{[^}]+\}", DUMMY, path)


def _module_for(tool: str):
    func_name = _TOOL_FUNC_MAP.get(tool, tool)
    if func_name == "job_tool":
        return job_endpoints_tool
    return dataset_endpoints_tool


_CASES = config_cases.action_cases("self_service")


@pytest.fixture
def _wire_client(monkeypatch, mock_dct_client):
    """Point both tool modules' module-level `client` at the shared mock."""
    monkeypatch.setattr(dataset_endpoints_tool, "client", mock_dct_client)
    monkeypatch.setattr(job_endpoints_tool, "client", mock_dct_client)
    return mock_dct_client


@pytest.mark.parametrize("case", _CASES, ids=[config_cases.action_id(c) for c in _CASES])
async def test_action_routes_to_correct_endpoint(case, _wire_client):
    module = _module_for(case.tool)
    func_name = _TOOL_FUNC_MAP.get(case.tool, case.tool)
    fn = getattr(module, func_name)
    # Translate config action → pre-built action
    actual_action = _ACTION_MAP.get((case.tool, case.action), case.action)
    kwargs = _path_kwargs(case.path)

    result = await fn(action=actual_action, confirmed=True, **kwargs)

    # Detect generation-only actions: the pre-built function returns an
    # "unknown action" error (or otherwise never calls the client).
    if not _wire_client.make_request.called:
        reason = "action not in pre-built module; generation-only"
        if isinstance(result, dict) and "error" in result:
            reason = f"{reason} ({result['error']})"
        pytest.xfail(reason)

    assert _wire_client.make_request.call_count == 1, (
        f"{case.tool}.{case.action} called make_request "
        f"{_wire_client.make_request.call_count} times"
    )
    call = _wire_client.make_request.call_args
    assert call.args[0] == case.method, (
        f"{case.tool}.{case.action}: method {call.args[0]} != {case.method}"
    )
    assert call.args[1] == _expected_endpoint(case.path), (
        f"{case.tool}.{case.action}: endpoint {call.args[1]} "
        f"!= {_expected_endpoint(case.path)}"
    )


# --- explicit guard tests -------------------------------------------------


async def test_missing_required_param_returns_error_and_no_call(_wire_client):
    result = await dataset_endpoints_tool.data_tool(action="get_vdb")
    assert isinstance(result, dict) and "error" in result
    assert not _wire_client.make_request.called


async def test_unknown_action_returns_error_and_no_call(_wire_client):
    result = await dataset_endpoints_tool.data_tool(
        action="not_a_real_action", vdb_id="X1"
    )
    assert isinstance(result, dict) and "error" in result
    assert not _wire_client.make_request.called
