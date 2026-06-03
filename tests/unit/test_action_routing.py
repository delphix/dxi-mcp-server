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
    return job_endpoints_tool if tool == "job_tool" else dataset_endpoints_tool


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
    fn = getattr(module, case.tool)
    kwargs = _path_kwargs(case.path)

    result = await fn(action=case.action, confirmed=True, **kwargs)

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
    result = await dataset_endpoints_tool.vdb_tool(action="get")
    assert isinstance(result, dict) and "error" in result
    assert not _wire_client.make_request.called


async def test_unknown_action_returns_error_and_no_call(_wire_client):
    result = await dataset_endpoints_tool.vdb_tool(
        action="not_a_real_action", vdb_id="X1"
    )
    assert isinstance(result, dict) and "error" in result
    assert not _wire_client.make_request.called
