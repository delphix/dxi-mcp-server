"""
Layer 3b — VDB lifecycle workflow test.

Translates `.claude/test/testing/self_service.md` lines 12-15 into a
deterministic Python test:

    1. Search for all VDBs
    2. Get the details of the first VDB from the previous result
    3. Start that VDB
    4. Stop that VDB

The "that VDB" chaining becomes a Python variable. Each step is a real MCP
call over stdio against the spawned dct-mcp-server subprocess. Each step is
verified at the wire level via dct_stub.received_request.

This is the test that DIRECTLY replaces the manual Claude Desktop playbook
for this workflow.
"""

import pytest


def _payload(result):
    """Extract the tool's JSON response dict from a fastmcp CallToolResult.

    fastmcp 3.x wraps the tool's dict return value as {"result": <dict>}
    inside structured_content. Unwrap that one level so test code sees the
    raw DCT response shape.
    """
    sc = result.structured_content or {}
    return sc.get("result", sc)


@pytest.mark.asyncio
async def test_vdb_lifecycle_search_get_start_stop(mcp_client_self_service, dct_stub):
    # --- Step 1 — Search for all VDBs ---
    search_result = await mcp_client_self_service.call_tool(
        "vdb_tool", {"action": "search", "limit": 10}
    )
    assert not search_result.is_error, f"search failed: {search_result}"
    assert dct_stub.received_request("POST", "/dct/v3/vdbs/search")

    items = _payload(search_result).get("items", [])
    assert items, "search returned no VDBs from the stub"
    vdb_id = items[0]["id"]
    assert vdb_id == "v-1", "stub should always return v-1 first (deterministic fixture)"

    # --- Step 2 — Get the first VDB's details ---
    get_result = await mcp_client_self_service.call_tool(
        "vdb_tool", {"action": "get", "vdb_id": vdb_id}
    )
    assert not get_result.is_error
    assert _payload(get_result).get("id") == vdb_id
    assert dct_stub.received_request("GET", f"/dct/v3/vdbs/{vdb_id}")

    # --- Step 3 — Start that VDB ---
    start_result = await mcp_client_self_service.call_tool(
        "vdb_tool", {"action": "start", "vdb_id": vdb_id}
    )
    assert not start_result.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/vdbs/{vdb_id}/start")

    # --- Step 4 — Stop that VDB ---
    # stop requires `standard` confirmation per manual_confirmation.txt,
    # so we pre-confirm to bypass the handshake (which has its own test).
    stop_result = await mcp_client_self_service.call_tool(
        "vdb_tool", {"action": "stop", "vdb_id": vdb_id, "confirmed": True}
    )
    assert not stop_result.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/vdbs/{vdb_id}/stop")

    # Sanity check — every expected endpoint was hit at least once.
    # Membership rather than exact sequence keeps the assertion robust to any
    # client-side retries against the stub.
    seen = {(m, p) for m, p, _ in dct_stub.requests}
    expected = {
        ("POST", "/dct/v3/vdbs/search"),
        ("GET", f"/dct/v3/vdbs/{vdb_id}"),
        ("POST", f"/dct/v3/vdbs/{vdb_id}/start"),
        ("POST", f"/dct/v3/vdbs/{vdb_id}/stop"),
    }
    assert expected.issubset(seen), f"Missing DCT calls: {expected - seen}"
