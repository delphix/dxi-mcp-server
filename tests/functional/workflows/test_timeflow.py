"""
Layer 3b — timeflow workflow.

Translates `.claude/test/testing/self_service.md` prompts 61-70:

    61. List all timeflows
    62. Search for all timeflows
    63. Get the first timeflow's details
    64. Update that timeflow's name
    65. Get the snapshot day range for that timeflow
    66. Repair that timeflow
    67. Get the tags for that timeflow
    68. Add a tag to that timeflow
    69. Remove the tag from that timeflow   (delete_tags — standard confirmation)
    70. Delete that timeflow                (manual confirmation)

Gated steps (delete_tags, delete) are pre-confirmed with confirmed=True — the
handshake itself is covered in tests/functional/test_confirmation_handshake.py.
"""

import pytest

from tests.functional.workflows._helpers import payload, first_id


@pytest.mark.asyncio
async def test_timeflow_workflow(mcp_client_self_service, dct_stub):
    client = mcp_client_self_service

    # Prompt 61 — List all timeflows.
    res = await client.call_tool("timeflow_tool", {"action": "list"})
    assert not res.is_error, f"list failed: {res}"
    assert dct_stub.received_request("GET", "/dct/v3/timeflows")

    # Prompt 62 — Search for all timeflows.
    res = await client.call_tool("timeflow_tool", {"action": "search", "limit": 10})
    assert not res.is_error
    assert dct_stub.received_request("POST", "/dct/v3/timeflows/search")
    tf_id = first_id(res)

    # Prompt 63 — Get the first timeflow's details.
    res = await client.call_tool("timeflow_tool", {"action": "get", "timeflow_id": tf_id})
    assert not res.is_error
    assert payload(res).get("id") == tf_id
    assert dct_stub.received_request("GET", f"/dct/v3/timeflows/{tf_id}")

    # Prompt 64 — Update the timeflow name (PATCH; no confirmation rule).
    res = await client.call_tool(
        "timeflow_tool", {"action": "update", "timeflow_id": tf_id, "name": "test-timeflow"}
    )
    assert not res.is_error
    assert dct_stub.received_request("PATCH", f"/dct/v3/timeflows/{tf_id}")

    # Prompt 65 — Snapshot day range.
    res = await client.call_tool(
        "timeflow_tool", {"action": "get_snapshot_day_range", "timeflow_id": tf_id}
    )
    assert not res.is_error
    assert dct_stub.received_request(
        "GET", f"/dct/v3/timeflows/{tf_id}/timeflowSnapshotDayRange"
    )

    # Prompt 66 — Repair the timeflow.
    res = await client.call_tool("timeflow_tool", {"action": "repair", "timeflow_id": tf_id})
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/timeflows/{tf_id}/repair")

    # Prompt 67 — Get tags.
    res = await client.call_tool("timeflow_tool", {"action": "get_tags", "timeflow_id": tf_id})
    assert not res.is_error
    assert dct_stub.received_request("GET", f"/dct/v3/timeflows/{tf_id}/tags")

    # Prompt 68 — Add a tag.
    res = await client.call_tool("timeflow_tool", {"action": "add_tags", "timeflow_id": tf_id})
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/timeflows/{tf_id}/tags")

    # Prompt 69 — Remove the tag (delete_tags — standard confirmation, pre-confirmed).
    res = await client.call_tool(
        "timeflow_tool", {"action": "delete_tags", "timeflow_id": tf_id, "confirmed": True}
    )
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/timeflows/{tf_id}/tags/delete")

    # Prompt 70 — Delete the timeflow (manual confirmation, pre-confirmed).
    res = await client.call_tool(
        "timeflow_tool", {"action": "delete", "timeflow_id": tf_id, "confirmed": True}
    )
    assert not res.is_error
    assert dct_stub.received_request("DELETE", f"/dct/v3/timeflows/{tf_id}")
