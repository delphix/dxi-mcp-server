"""
Layer 3b — VDB lists + tags workflow.

Translates `.claude/test/testing/self_service.md` prompts 13-17:

    13. List all snapshots for that VDB
    14. List all bookmarks for that VDB
    15. Get the tags for that VDB
    16. Add the tag environment=test to that VDB
    17. Remove the environment=test tag from that VDB   [standard conf]
"""

import pytest

from tests.functional.workflows._helpers import payload


@pytest.mark.asyncio
async def test_vdb_lists_and_tags(mcp_client_self_service, dct_stub):
    client = mcp_client_self_service
    vdb_id = "v-1"

    # Prompt 13 — List all snapshots.
    res = await client.call_tool("data_tool", {"action": "list_vdb_snapshots", "vdb_id": vdb_id})
    assert not res.is_error
    assert dct_stub.received_request("GET", f"/dct/v3/vdbs/{vdb_id}/snapshots")

    # Prompt 14 — List all bookmarks.
    res = await client.call_tool("data_tool", {"action": "list_vdb_bookmarks", "vdb_id": vdb_id})
    assert not res.is_error
    assert dct_stub.received_request("GET", f"/dct/v3/vdbs/{vdb_id}/bookmarks")

    # Prompt 15 — Get the tags.
    res = await client.call_tool("data_tool", {"action": "get_vdb_tags", "vdb_id": vdb_id})
    assert not res.is_error
    assert dct_stub.received_request("GET", f"/dct/v3/vdbs/{vdb_id}/tags")

    # Prompt 16 — Add the tag environment=test.
    res = await client.call_tool(
        "data_tool",
        {"action": "add_vdb_tags", "vdb_id": vdb_id,
         "tags": [{"key": "environment", "value": "test"}]},
    )
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/vdbs/{vdb_id}/tags")

    # Prompt 17 — Remove the environment=test tag (standard conf -> pre-confirm).
    res = await client.call_tool(
        "data_tool",
        {"action": "delete_vdb_tags", "vdb_id": vdb_id,
         "tags": [{"key": "environment", "value": "test"}], "confirmed": True},
    )
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/vdbs/{vdb_id}/tags/delete")
