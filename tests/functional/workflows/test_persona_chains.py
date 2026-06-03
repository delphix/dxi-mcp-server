"""
Representative in-process persona chains (Phase L3 / 3b — non-self_service).

One small chain per non-self_service persona, exercising the IN-MEMORY generated
tools against the `dct_stub` catch-all over REAL HTTP. This is the fidelity
counterpart to the mocked routing sweep in `test_generated_routing.py`: it proves
the generated tools actually talk to a DCT-shaped server and that search -> get
chaining (and confirmation gating) works end-to-end for dynamically-built tools.

Mechanism:
  * `dct_stub` gives a fresh stub server; we point a real `DCTAPIClient` at it
    via monkeypatched env, then install it as `tf._dct_client`.
  * `tf._openapi_spec` is seeded from the fixture so generation is offline.
  * All tool_factory globals + the client are restored / closed in fixture
    teardown so nothing leaks into other tests or the demo.

Chains use REAL actions verified against `config_cases`. The stub catch-all
(declared last in dct_stub.build_app) serves `POST .../search` -> items and
`GET .../{id}` -> object, which is all these chains need. No stub changes were
required.
"""

import re

import pytest

# `persona_tools` fixture + `persona_path_for` helper now live in the shared
# tests/functional/conftest.py so the CDA functional files can reuse them.
from tests.functional.conftest import persona_path_for as _path_for


async def _search_get_chain(tools, dct_stub, toolset, tool):
    """search -> get against the stub catch-all; assert both requests landed."""
    search_m, search_p = _path_for(toolset, tool, "search")
    get_m, get_p = _path_for(toolset, tool, "get")

    func = tools[tool]
    search_res = await func(action="search")
    items = search_res.get("items", [])
    assert items, f"{toolset}/{tool} search returned no items: {search_res}"
    first_id = items[0]["id"]

    # The single path placeholder takes the id we just discovered.
    placeholder = re.search(r"\{(\w+)\}", get_p).group(1)
    get_res = await func(action="get", **{placeholder: first_id})
    assert get_res.get("id") == first_id, f"get did not echo the id: {get_res}"

    expected_get_path = "/dct/v3" + re.sub(r"\{\w+\}", first_id, get_p)
    assert dct_stub.received_request(search_m, "/dct/v3" + search_p)
    assert dct_stub.received_request(get_m, expected_get_path)


@pytest.mark.asyncio
async def test_cda_group_search_get(persona_tools, dct_stub):
    """continuous_data_admin: group_tool search -> get."""
    tools = persona_tools("continuous_data_admin")
    await _search_get_chain(tools, dct_stub, "continuous_data_admin", "group_tool")


@pytest.mark.asyncio
async def test_platform_admin_engine_search_get(persona_tools, dct_stub):
    """platform_admin: engine_tool search -> get (under /management/engines)."""
    tools = persona_tools("platform_admin")
    await _search_get_chain(tools, dct_stub, "platform_admin", "engine_tool")


@pytest.mark.asyncio
async def test_reporting_insights_report_search(persona_tools, dct_stub):
    """reporting_insights: reporting_tool search of the VDB inventory report."""
    tools = persona_tools("reporting_insights")
    method, path = _path_for("reporting_insights", "reporting_tool", "search_vdb_inventory_report")
    res = await tools["reporting_tool"](action="search_vdb_inventory_report")
    assert "items" in res, f"expected a search result list, got: {res}"
    assert dct_stub.received_request(method, "/dct/v3" + path)


@pytest.mark.asyncio
async def test_self_service_provision_gated(persona_tools, dct_stub):
    """
    self_service_provision: vdb_tool provision_by_snapshot is 'elevated'-gated.

    First call (no confirmed) -> confirmation_required, NO HTTP request.
    Second call (confirmed=True) -> the request is issued. Doubles as a
    confirmation-over-generated-tool check.
    """
    tools = persona_tools("self_service_provision")
    method, path = _path_for("self_service_provision", "vdb_tool", "provision_by_snapshot")
    wire_path = "/dct/v3" + path

    gated = await tools["vdb_tool"](action="provision_by_snapshot")
    assert gated.get("status") == "confirmation_required"
    assert gated.get("confirmation_level") == "elevated"
    assert not dct_stub.received_request(method, wire_path), "gated call must not hit DCT"

    await tools["vdb_tool"](action="provision_by_snapshot", confirmed=True)
    assert dct_stub.received_request(method, wire_path)
