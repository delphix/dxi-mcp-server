"""
Layer 3b — bookmark workflow.

Translates `.claude/test/testing/self_service.md` prompts 48-56:

    48. Search for all bookmarks
    49. Get the first bookmark's details
    50. Create a new bookmark on the first VDB
    51. Update that bookmark's name                  [retention_check conf]
    52. Get the VDB groups associated with that bookmark
    53. Get the tags for that bookmark
    54. Add the tag test=true
    55. Remove the test=true tag                     [standard conf]
    56. Delete that bookmark                          [manual conf]

Note: the created bookmark's id ("new-1" from the stub) is carried forward;
the existing-bookmark id from search is used for the read-only/tag steps.
"""

import pytest

from tests.functional.workflows._helpers import payload, first_id


@pytest.mark.asyncio
async def test_bookmark_workflow(mcp_client_self_service, dct_stub):
    client = mcp_client_self_service

    # Prompt 48 — Search for all bookmarks.
    res = await client.call_tool("bookmark_tool", {"action": "search", "limit": 10})
    assert not res.is_error, f"search failed: {res}"
    assert dct_stub.received_request("POST", "/dct/v3/bookmarks/search")
    bk_id = first_id(res)

    # Prompt 49 — Get the first bookmark's details.
    res = await client.call_tool("bookmark_tool", {"action": "get", "bookmark_id": bk_id})
    assert not res.is_error
    assert payload(res).get("id") == bk_id
    assert dct_stub.received_request("GET", f"/dct/v3/bookmarks/{bk_id}")

    # Prompt 50 — Create a new bookmark on the first VDB (v-1).
    res = await client.call_tool(
        "bookmark_tool",
        {"action": "create", "name": "test-bookmark", "vdb_ids": ["v-1"]},
    )
    assert not res.is_error
    assert dct_stub.received_request("POST", "/dct/v3/bookmarks")
    created_id = payload(res).get("id")
    assert created_id, "create should return a new bookmark id"

    # Prompt 51 — Update that bookmark's name (retention_check conf -> pre-confirm).
    res = await client.call_tool(
        "bookmark_tool",
        {"action": "update", "bookmark_id": created_id,
         "name": "test-bookmark-updated", "confirmed": True},
    )
    assert not res.is_error
    assert dct_stub.received_request("PATCH", f"/dct/v3/bookmarks/{created_id}")

    # Prompt 52 — Get the VDB groups associated with that bookmark.
    res = await client.call_tool(
        "bookmark_tool", {"action": "get_vdb_groups", "bookmark_id": bk_id}
    )
    assert not res.is_error
    assert dct_stub.received_request("GET", f"/dct/v3/bookmarks/{bk_id}/vdb-groups")

    # Prompt 53 — Get the tags for that bookmark.
    res = await client.call_tool("bookmark_tool", {"action": "get_tags", "bookmark_id": bk_id})
    assert not res.is_error
    assert dct_stub.received_request("GET", f"/dct/v3/bookmarks/{bk_id}/tags")

    # Prompt 54 — Add the tag test=true.
    res = await client.call_tool(
        "bookmark_tool",
        {"action": "add_tags", "bookmark_id": bk_id,
         "tags": [{"key": "test", "value": "true"}]},
    )
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/bookmarks/{bk_id}/tags")

    # Prompt 55 — Remove the test=true tag (standard conf -> pre-confirm).
    res = await client.call_tool(
        "bookmark_tool",
        {"action": "delete_tags", "bookmark_id": bk_id,
         "tags": [{"key": "test", "value": "true"}], "confirmed": True},
    )
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/bookmarks/{bk_id}/tags/delete")

    # Prompt 56 — Delete that bookmark (manual conf -> pre-confirm).
    res = await client.call_tool(
        "bookmark_tool",
        {"action": "delete", "bookmark_id": created_id, "confirmed": True},
    )
    assert not res.is_error
    assert dct_stub.received_request("DELETE", f"/dct/v3/bookmarks/{created_id}")
