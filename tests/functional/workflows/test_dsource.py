"""
Layer 3b — dSource workflow.

Translates `.claude/test/testing/self_service.md` prompts 35-38:

    35. Search for all dSources
    36. Get the first dSource's details
    37. List all snapshots for that dSource
    38. Get the tags for that dSource
"""

import pytest

from tests.functional.workflows._helpers import payload, first_id


@pytest.mark.asyncio
async def test_dsource_workflow(mcp_client_self_service, dct_stub):
    client = mcp_client_self_service

    # Prompt 35 — Search for all dSources.
    res = await client.call_tool(
        "data_tool", {"action": "search_dsources", "limit": 10}
    )
    assert not res.is_error, f"search failed: {res}"
    assert dct_stub.received_request("POST", "/dct/v3/dsources/search")
    ds_id = first_id(res)

    # Prompt 36 — Get the first dSource's details.
    res = await client.call_tool(
        "data_tool", {"action": "get_dsource", "dsource_id": ds_id}
    )
    assert not res.is_error
    assert payload(res).get("id") == ds_id
    assert dct_stub.received_request("GET", f"/dct/v3/dsources/{ds_id}")

    # Prompt 37 — List all snapshots for that dSource.
    res = await client.call_tool(
        "data_tool", {"action": "list_dsource_snapshots", "dsource_id": ds_id}
    )
    assert not res.is_error
    assert dct_stub.received_request("GET", f"/dct/v3/dsources/{ds_id}/snapshots")

    # Prompt 38 — Get the tags for that dSource.
    res = await client.call_tool(
        "data_tool", {"action": "get_dsource_tags", "dsource_id": ds_id}
    )
    assert not res.is_error
    assert dct_stub.received_request("GET", f"/dct/v3/dsources/{ds_id}/tags")
