"""
Layer 3b — VDB refresh + rollback workflow.

Translates `.claude/test/testing/self_service.md` prompts 7-12:

    7.  Refresh that VDB by timestamp (one hour ago)       [elevated conf]
    8.  List snapshots, then refresh by the most recent snapshot [elevated conf]
    9.  List bookmarks, then refresh from the first bookmark [elevated conf]
    10. Roll back that VDB by timestamp (two hours ago)   [standard conf]
    11. Roll back that VDB by the most recent snapshot     [standard conf]
    12. Roll back that VDB from the first bookmark         [standard conf]

Snapshot/bookmark ids are discovered from the list steps and carried into the
refresh/rollback steps. Refreshes (elevated) and rollbacks (standard) are both
pre-confirmed.
"""

import pytest

from tests.functional.workflows._helpers import first_id


@pytest.mark.asyncio
async def test_vdb_refresh_rollback(mcp_client_self_service, dct_stub):
    client = mcp_client_self_service
    vdb_id = "v-1"

    # Prompt 7 — Refresh by timestamp (elevated conf -> pre-confirm).
    res = await client.call_tool(
        "data_tool",
        {
            "action": "refresh_vdb_by_timestamp",
            "vdb_id": vdb_id,
            "timestamp": "2024-01-01T00:00:00.000Z",
            "confirmed": True,
        },
    )
    assert not res.is_error
    assert dct_stub.received_request(
        "POST", f"/dct/v3/vdbs/{vdb_id}/refresh_by_timestamp"
    )

    # Prompt 8 — List snapshots, then refresh by the most recent snapshot.
    res = await client.call_tool(
        "data_tool", {"action": "list_vdb_snapshots", "vdb_id": vdb_id}
    )
    assert not res.is_error
    assert dct_stub.received_request("GET", f"/dct/v3/vdbs/{vdb_id}/snapshots")
    snapshot_id = first_id(res)

    res = await client.call_tool(
        "data_tool",
        {
            "action": "refresh_vdb_by_snapshot",
            "vdb_id": vdb_id,
            "snapshot_id": snapshot_id,
            "confirmed": True,
        },
    )
    assert not res.is_error
    assert dct_stub.received_request(
        "POST", f"/dct/v3/vdbs/{vdb_id}/refresh_by_snapshot"
    )

    # Prompt 9 — List bookmarks, then refresh from the first bookmark.
    res = await client.call_tool(
        "data_tool", {"action": "list_vdb_bookmarks", "vdb_id": vdb_id}
    )
    assert not res.is_error
    assert dct_stub.received_request("GET", f"/dct/v3/vdbs/{vdb_id}/bookmarks")
    bookmark_id = first_id(res)

    res = await client.call_tool(
        "data_tool",
        {
            "action": "refresh_vdb_from_bookmark",
            "vdb_id": vdb_id,
            "bookmark_id": bookmark_id,
            "confirmed": True,
        },
    )
    assert not res.is_error
    assert dct_stub.received_request(
        "POST", f"/dct/v3/vdbs/{vdb_id}/refresh_from_bookmark"
    )

    # Prompt 10 — Roll back by timestamp (standard confirmation -> pre-confirm).
    res = await client.call_tool(
        "data_tool",
        {
            "action": "rollback_vdb_by_timestamp",
            "vdb_id": vdb_id,
            "timestamp": "2024-01-01T00:00:00.000Z",
            "confirmed": True,
        },
    )
    assert not res.is_error
    assert dct_stub.received_request(
        "POST", f"/dct/v3/vdbs/{vdb_id}/rollback_by_timestamp"
    )

    # Prompt 11 — Roll back by the most recent snapshot (standard conf).
    res = await client.call_tool(
        "data_tool",
        {
            "action": "rollback_vdb_by_snapshot",
            "vdb_id": vdb_id,
            "snapshot_id": snapshot_id,
            "confirmed": True,
        },
    )
    assert not res.is_error
    assert dct_stub.received_request(
        "POST", f"/dct/v3/vdbs/{vdb_id}/rollback_by_snapshot"
    )

    # Prompt 12 — Roll back from the first bookmark (standard conf).
    res = await client.call_tool(
        "data_tool",
        {
            "action": "rollback_vdb_from_bookmark",
            "vdb_id": vdb_id,
            "bookmark_id": bookmark_id,
            "confirmed": True,
        },
    )
    assert not res.is_error
    assert dct_stub.received_request(
        "POST", f"/dct/v3/vdbs/{vdb_id}/rollback_from_bookmark"
    )
