"""
Layer 3b — VDB group workflow.

Translates `.claude/test/testing/self_service.md` prompts 18-34:

    18. Search for all VDB groups
    19. Get the first VDB group's details
    20. Refresh that VDB group
    21. List bookmarks, then refresh from the first bookmark
    22. Refresh by snapshot
    23. Refresh by timestamp (one hour ago)
    24. Roll back that VDB group           [standard conf]
    25. Lock that VDB group
    26. Unlock that VDB group
    27. Start that VDB group
    28. Stop that VDB group
    29. Enable that VDB group
    30. Disable that VDB group
    31. List the bookmarks for that VDB group
    32. Get the tags for that VDB group
    33. Add the tag team=qa
    34. Remove the team=qa tag              [standard conf]

Group id is discovered from search; the bookmark id from the list step.
"""

import pytest

from tests.functional.workflows._helpers import payload, first_id


@pytest.mark.asyncio
async def test_vdb_group_workflow(mcp_client_self_service, dct_stub):
    client = mcp_client_self_service

    # Prompt 18 — Search for all VDB groups.
    res = await client.call_tool("vdb_group_tool", {"action": "search", "limit": 10})
    assert not res.is_error, f"search failed: {res}"
    assert dct_stub.received_request("POST", "/dct/v3/vdb-groups/search")
    vg_id = first_id(res)

    # Prompt 19 — Get the first VDB group's details.
    res = await client.call_tool("vdb_group_tool", {"action": "get", "vdb_group_id": vg_id})
    assert not res.is_error
    assert payload(res).get("id") == vg_id
    assert dct_stub.received_request("GET", f"/dct/v3/vdb-groups/{vg_id}")

    # Prompt 20 — Refresh that VDB group.
    res = await client.call_tool("vdb_group_tool", {"action": "refresh", "vdb_group_id": vg_id})
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/vdb-groups/{vg_id}/refresh")

    # Prompt 21 — List bookmarks, then refresh from the first bookmark.
    res = await client.call_tool(
        "vdb_group_tool", {"action": "list_bookmarks", "vdb_group_id": vg_id}
    )
    assert not res.is_error
    assert dct_stub.received_request("GET", f"/dct/v3/vdb-groups/{vg_id}/bookmarks")
    bookmark_id = first_id(res)

    res = await client.call_tool(
        "vdb_group_tool",
        {"action": "refresh_from_bookmark", "vdb_group_id": vg_id, "bookmark_id": bookmark_id},
    )
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/vdb-groups/{vg_id}/refresh_from_bookmark")

    # Prompt 22 — Refresh by snapshot.
    res = await client.call_tool(
        "vdb_group_tool", {"action": "refresh_by_snapshot", "vdb_group_id": vg_id}
    )
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/vdb-groups/{vg_id}/refresh_by_snapshot")

    # Prompt 23 — Refresh by timestamp (one hour ago).
    res = await client.call_tool(
        "vdb_group_tool", {"action": "refresh_by_timestamp", "vdb_group_id": vg_id}
    )
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/vdb-groups/{vg_id}/refresh_by_timestamp")

    # Prompt 24 — Roll back (standard conf -> pre-confirm).
    res = await client.call_tool(
        "vdb_group_tool", {"action": "rollback", "vdb_group_id": vg_id, "confirmed": True}
    )
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/vdb-groups/{vg_id}/rollback")

    # Prompt 25 — Lock.
    res = await client.call_tool("vdb_group_tool", {"action": "lock", "vdb_group_id": vg_id})
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/vdb-groups/{vg_id}/lock")

    # Prompt 26 — Unlock.
    res = await client.call_tool("vdb_group_tool", {"action": "unlock", "vdb_group_id": vg_id})
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/vdb-groups/{vg_id}/unlock")

    # Prompt 27 — Start.
    res = await client.call_tool("vdb_group_tool", {"action": "start", "vdb_group_id": vg_id})
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/vdb-groups/{vg_id}/start")

    # Prompt 28 — Stop.
    res = await client.call_tool("vdb_group_tool", {"action": "stop", "vdb_group_id": vg_id})
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/vdb-groups/{vg_id}/stop")

    # Prompt 29 — Enable.
    res = await client.call_tool("vdb_group_tool", {"action": "enable", "vdb_group_id": vg_id})
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/vdb-groups/{vg_id}/enable")

    # Prompt 30 — Disable.
    res = await client.call_tool("vdb_group_tool", {"action": "disable", "vdb_group_id": vg_id})
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/vdb-groups/{vg_id}/disable")

    # Prompt 31 — List the bookmarks again.
    res = await client.call_tool(
        "vdb_group_tool", {"action": "list_bookmarks", "vdb_group_id": vg_id}
    )
    assert not res.is_error
    assert dct_stub.received_request("GET", f"/dct/v3/vdb-groups/{vg_id}/bookmarks")

    # Prompt 32 — Get the tags.
    res = await client.call_tool("vdb_group_tool", {"action": "get_tags", "vdb_group_id": vg_id})
    assert not res.is_error
    assert dct_stub.received_request("GET", f"/dct/v3/vdb-groups/{vg_id}/tags")

    # Prompt 33 — Add the tag team=qa.
    res = await client.call_tool(
        "vdb_group_tool",
        {"action": "add_tags", "vdb_group_id": vg_id,
         "tags": [{"key": "team", "value": "qa"}]},
    )
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/vdb-groups/{vg_id}/tags")

    # Prompt 34 — Remove the team=qa tag (standard conf -> pre-confirm).
    res = await client.call_tool(
        "vdb_group_tool",
        {"action": "delete_tags", "vdb_group_id": vg_id,
         "tags": [{"key": "team", "value": "qa"}], "confirmed": True},
    )
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/vdb-groups/{vg_id}/tags/delete")
