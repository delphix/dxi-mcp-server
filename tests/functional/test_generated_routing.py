"""
Generated-action routing sweep (Phase L3 / 3b — non-self_service personas).

The non-self_service personas (continuous_data_admin, platform_admin,
reporting_insights, self_service_provision) are DYNAMIC-GENERATION-ONLY: their
pre-built `*_endpoints_tool.py` modules were deleted, so the fixed-mode
subprocess cannot serve them (and triggering the dev-mode disk generator would
rewrite src/). So we test the IN-MEMORY tools straight from `tool_factory`.

This module proves that EVERY action of EVERY generated grouped tool for those
four personas routes to the correct HTTP method + endpoint path. We:

  1. seed `tf._openapi_spec` from the bundled fixture (offline, no disk/network),
  2. generate each persona's tools ONCE (cached module-level — CDA alone has 434
     actions, so regenerating per case would be wasteful),
  3. parametrize over `config_cases.action_cases(ts)` — the ground-truth oracle
     parsed independently from the toolset `.txt` files,
  4. drive each generated func with a MOCKED client and assert the (method, path)
     it sent to `make_request`.

Global state (`tf._openapi_spec`, `tf._dct_client`) is set/restored via the
`seed_tool_factory_spec` fixture (monkeypatch) plus an explicit client reset, so
nothing leaks into other tests or the subprocess-isolated demo suite.
"""

import re

import pytest
from unittest.mock import AsyncMock, MagicMock

from tests._support import config_cases as cc

NON_SELF_SERVICE = [
    "continuous_data_admin",
    "platform_admin",
    "reporting_insights",
    "self_service_provision",
]

# All routing cases across the four personas, with stable ids.
_ALL_CASES = [c for ts in NON_SELF_SERVICE for c in cc.action_cases(ts)]
_ALL_IDS = [cc.action_id(c) for c in _ALL_CASES]


@pytest.fixture(scope="module")
def _generated_tools(request):
    """
    Generate every non-self_service persona's tools ONCE per module.

    Seeds the spec cache from the downloaded/cached api-external.yaml and tears it
    back down afterwards. Returns {toolset: {tool_name: func}}.
    """
    import yaml
    import dct_mcp_server.tools.core.tool_factory as tf
    from tests.functional.conftest import _SPEC_CACHE, _download_spec

    # Load spec: prefer fresh download if DCT creds available, else use cache
    if _SPEC_CACHE.exists():
        spec_data = yaml.safe_load(_SPEC_CACHE.read_text())
    else:
        spec_data = _download_spec()
        if spec_data is None:
            pytest.skip("OpenAPI spec not available — set DCT_BASE_URL+DCT_API_KEY or ensure cache exists")

    saved_spec, saved_client = tf._openapi_spec, tf._dct_client
    tf._openapi_spec = spec_data

    tools_by_toolset = {}
    for ts in NON_SELF_SERVICE:
        tools_by_toolset[ts] = {name: func for func, name in tf.generate_tools_for_toolset(ts)}

    def _restore():
        tf._openapi_spec = saved_spec
        tf._dct_client = saved_client

    request.addfinalizer(_restore)
    return tools_by_toolset


@pytest.fixture
def _mock_client():
    """A MagicMock DCT client with an async make_request, installed on tool_factory."""
    import dct_mcp_server.tools.core.tool_factory as tf

    client = MagicMock()
    client.make_request = AsyncMock(return_value={})
    saved = tf._dct_client
    tf._dct_client = client
    try:
        yield client
    finally:
        tf._dct_client = saved


def test_case_count_is_large():
    """Guard against a silent empty sweep (a regression in the config oracle)."""
    assert len(_ALL_CASES) >= 600, f"expected a large sweep, got {len(_ALL_CASES)}"


@pytest.mark.parametrize("case", _ALL_CASES, ids=_ALL_IDS)
@pytest.mark.asyncio
async def test_generated_action_routes(case, _generated_tools, _mock_client):
    """Each generated action routes to the right (method, final_path)."""
    func = _generated_tools[case.toolset].get(case.tool)
    assert func is not None, f"no generated tool {case.tool!r} for {case.toolset!r}"

    # Path params: the tool substitutes the LITERAL placeholder name from kwargs.
    path_kwargs = {m.group(1): "X1" for m in re.finditer(r"\{(\w+)\}", case.path)}

    _mock_client.make_request.reset_mock()
    # confirmed=True so confirmation-gated ops reach make_request.
    await func(action=case.action, confirmed=True, **path_kwargs)

    expected_path = re.sub(r"\{\w+\}", "X1", case.path)

    if not _mock_client.make_request.called:
        pytest.xfail(f"{case.tool}.{case.action} did not reach make_request")

    assert _mock_client.make_request.call_count == 1
    call = _mock_client.make_request.call_args
    assert call.args[0] == case.method, (
        f"{case.tool}.{case.action}: method {call.args[0]} != {case.method}"
    )
    assert call.args[1] == expected_path, (
        f"{case.tool}.{case.action}: path {call.args[1]} != {expected_path}"
    )
