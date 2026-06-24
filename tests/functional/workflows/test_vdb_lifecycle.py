"""
Layer 3b — VDB lifecycle workflow.

Translates `.claude/test/testing/self_service.md` prompts 1-6 into a
deterministic, multi-step MCP test over the stdio wire:

    1. Search for all VDBs
    2. Get the details of the first VDB from the previous result
    3. Start that VDB
    4. Stop that VDB        (standard confirmation -> pre-confirmed)
    5. Enable that VDB
    6. Disable that VDB     (standard confirmation -> pre-confirmed)

"that VDB" -> a Python variable carried across steps. Each step asserts no
error AND the exact (method, wire-path) the server sent to DCT.
"""

import pytest

from tests.functional.workflows._helpers import payload, first_id


@pytest.mark.asyncio
async def test_vdb_lifecycle(mcp_client_self_service, dct_stub):
    client = mcp_client_self_service

    # Prompt 1 — Search for all VDBs.
    res = await client.call_tool("data_tool", {"action": "search_vdbs", "limit": 10})
    assert not res.is_error, f"search failed: {res}"
    assert dct_stub.received_request("POST", "/dct/v3/vdbs/search")
    vdb_id = first_id(res)
    assert vdb_id == "v-1", "stub must return v-1 first (deterministic fixture)"

    # Prompt 2 — Get the first VDB's details.
    res = await client.call_tool("data_tool", {"action": "get_vdb", "vdb_id": vdb_id})
    assert not res.is_error
    assert payload(res).get("id") == vdb_id
    assert dct_stub.received_request("GET", f"/dct/v3/vdbs/{vdb_id}")

    # Prompt 3 — Start that VDB.
    res = await client.call_tool("data_tool", {"action": "start_vdb", "vdb_id": vdb_id})
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/vdbs/{vdb_id}/start")

    # Prompt 4 — Stop that VDB (standard confirmation -> pre-confirm).
    res = await client.call_tool(
        "data_tool", {"action": "stop_vdb", "vdb_id": vdb_id, "confirmed": True}
    )
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/vdbs/{vdb_id}/stop")

    # Prompt 5 — Enable that VDB.
    res = await client.call_tool("data_tool", {"action": "enable_vdb", "vdb_id": vdb_id})
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/vdbs/{vdb_id}/enable")

    # Prompt 6 — Disable that VDB (standard confirmation -> pre-confirm).
    res = await client.call_tool(
        "data_tool", {"action": "disable_vdb", "vdb_id": vdb_id, "confirmed": True}
    )
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/vdbs/{vdb_id}/disable")
