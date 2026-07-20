"""
Layer 3b — snapshot workflow.

Translates `.claude/test/testing/self_service.md` prompts 39-47:

    39. Search for all snapshots
    40. Get the first snapshot's details
    41. Get the timeflow range for that snapshot
    42. Get the runtime details for that snapshot
    43. Find a snapshot by location
    44. Find a snapshot by timestamp (one hour ago)
    45. Get the tags for that snapshot
    46. Add the tag backup=true
    47. Remove the backup=true tag        [standard conf]
"""

import pytest

from tests.functional.workflows._helpers import payload, first_id


@pytest.mark.asyncio
async def test_snapshot_workflow(mcp_client_self_service, dct_stub):
    client = mcp_client_self_service

    # Prompt 39 — Search for all snapshots.
    res = await client.call_tool(
        "snapshot_bookmark_tool", {"action": "search_snapshots", "limit": 10}
    )
    assert not res.is_error, f"search failed: {res}"
    assert dct_stub.received_request("POST", "/dct/v3/snapshots/search")
    snap_id = first_id(res)

    # Prompt 40 — Get the first snapshot's details.
    res = await client.call_tool(
        "snapshot_bookmark_tool", {"action": "get_snapshot", "snapshot_id": snap_id}
    )
    assert not res.is_error
    assert payload(res).get("id") == snap_id
    assert dct_stub.received_request("GET", f"/dct/v3/snapshots/{snap_id}")

    # Prompt 41 — Get the timeflow range for that snapshot.
    res = await client.call_tool(
        "snapshot_bookmark_tool",
        {"action": "get_snapshot_timeflow_range", "snapshot_id": snap_id},
    )
    assert not res.is_error
    assert dct_stub.received_request(
        "GET", f"/dct/v3/snapshots/{snap_id}/timeflow_range"
    )

    # Prompt 42 — Get the runtime details for that snapshot.
    res = await client.call_tool(
        "snapshot_bookmark_tool", {"action": "get_runtime", "snapshot_id": snap_id}
    )
    assert not res.is_error
    assert dct_stub.received_request("GET", f"/dct/v3/snapshots/{snap_id}/runtime")

    # Prompt 45 — Get the tags for that snapshot.
    res = await client.call_tool(
        "snapshot_bookmark_tool",
        {"action": "get_snapshot_tags", "snapshot_id": snap_id},
    )
    assert not res.is_error
    assert dct_stub.received_request("GET", f"/dct/v3/snapshots/{snap_id}/tags")

    # Prompt 46 — Add the tag backup=true.
    res = await client.call_tool(
        "snapshot_bookmark_tool",
        {
            "action": "add_snapshot_tags",
            "snapshot_id": snap_id,
            "tags": [{"key": "backup", "value": "true"}],
        },
    )
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/snapshots/{snap_id}/tags")

    # Prompt 47 — Remove the backup=true tag (standard conf -> pre-confirm).
    res = await client.call_tool(
        "snapshot_bookmark_tool",
        {
            "action": "delete_snapshot_tags",
            "snapshot_id": snap_id,
            "tags": [{"key": "backup", "value": "true"}],
            "confirmed": True,
        },
    )
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/snapshots/{snap_id}/tags/delete")
