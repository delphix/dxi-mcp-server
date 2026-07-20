"""
Layer 3b — Representative continuous_data_admin (CDA) multi-step workflow chains.

CDA tools are dynamic-generation-only (pre-built modules removed), so these chains
drive the IN-MEMORY generated grouped tools (shared `persona_tools` fixture) against
the `dct_stub` catch-all over real HTTP — the fidelity counterpart to the mocked
routing sweep. Each chain asserts every step's request actually landed on the stub.

The stub catch-all serves `POST .../search` -> {items:[...]}, `GET .../{id}` -> the
object, and any other GET (incl. `/tags`) -> {items:[...]}. (method, path) per action
is resolved from the config oracle via `persona_path_for`, so nothing is hardcoded.
"""

import re

import pytest

from tests.functional.conftest import persona_path_for

TOOLSET = "continuous_data_admin"


async def _search_get(tools, dct_stub, tool):
    """search -> get(id); returns the discovered first id for further steps."""
    search_m, search_p = persona_path_for(TOOLSET, tool, "search")
    get_m, get_p = persona_path_for(TOOLSET, tool, "get")
    func = tools[tool]

    search_res = await func(action="search")
    items = search_res.get("items", [])
    assert items, f"{tool} search returned no items: {search_res}"
    first_id = items[0]["id"]

    placeholder = re.search(r"\{(\w+)\}", get_p).group(1)
    get_res = await func(action="get", **{placeholder: first_id})
    assert get_res.get("id") == first_id, f"{tool} get did not echo the id: {get_res}"

    assert dct_stub.received_request(search_m, "/dct/v3" + search_p)
    assert dct_stub.received_request(
        get_m, "/dct/v3" + re.sub(r"\{\w+\}", first_id, get_p)
    )
    return func, first_id


async def _get_tags_step(func, dct_stub, tool, first_id):
    """get_tags(id) -> assert the tags GET landed (stub returns {items:[...]})."""
    tags_m, tags_p = persona_path_for(TOOLSET, tool, "get_tags")
    placeholder = re.search(r"\{(\w+)\}", tags_p).group(1)
    tags_res = await func(action="get_tags", **{placeholder: first_id})
    assert "items" in tags_res, f"{tool} get_tags unexpected shape: {tags_res}"
    assert dct_stub.received_request(
        tags_m, "/dct/v3" + re.sub(r"\{\w+\}", first_id, tags_p)
    )


@pytest.mark.asyncio
async def test_cda_engine_search_get_tags(persona_tools, dct_stub):
    """engine_tool: search -> get(engineId) -> get_tags(engineId)."""
    tools = persona_tools(TOOLSET)
    func, first_id = await _search_get(tools, dct_stub, "engine_tool")
    await _get_tags_step(func, dct_stub, "engine_tool", first_id)


@pytest.mark.asyncio
async def test_cda_database_template_search_get_tags(persona_tools, dct_stub):
    """database_template_tool: search -> get -> get_tags."""
    tools = persona_tools(TOOLSET)
    func, first_id = await _search_get(tools, dct_stub, "database_template_tool")
    await _get_tags_step(func, dct_stub, "database_template_tool", first_id)


@pytest.mark.asyncio
async def test_cda_replication_search_get(persona_tools, dct_stub):
    """replication_tool: search -> get -> get_tags."""
    tools = persona_tools(TOOLSET)
    func, first_id = await _search_get(tools, dct_stub, "replication_tool")
    await _get_tags_step(func, dct_stub, "replication_tool", first_id)


@pytest.mark.asyncio
async def test_cda_virtualization_policy_search_get(persona_tools, dct_stub):
    """virtualization_policy_tool: search -> get -> get_tags."""
    tools = persona_tools(TOOLSET)
    func, first_id = await _search_get(tools, dct_stub, "virtualization_policy_tool")
    await _get_tags_step(func, dct_stub, "virtualization_policy_tool", first_id)


@pytest.mark.asyncio
async def test_cda_group_search_get(persona_tools, dct_stub):
    """group_tool: search -> get (no tags endpoint on groups)."""
    tools = persona_tools(TOOLSET)
    await _search_get(tools, dct_stub, "group_tool")
