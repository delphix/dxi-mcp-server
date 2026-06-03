"""
Layer 3c — Confirmation handshake over the MCP wire.

Verifies the two-step destructive-op contract for the VDB `stop` action
(standard confirmation level per config/mappings/manual_confirmation.txt):

    First call (no confirmed)      → confirmation_required, no DCT request
    Second call (confirmed=True)   → request actually issued to DCT

This proves the confirmation safety net survives end-to-end through the
MCP stdio transport — not just inside the tool function.
"""

import pytest


def _payload(result):
    """Unwrap fastmcp's {"result": <dict>} envelope to expose the raw tool return."""
    sc = result.structured_content or {}
    return sc.get("result", sc)


@pytest.mark.asyncio
async def test_stop_vdb_two_step_confirmation(mcp_client_self_service, dct_stub):
    vdb_id = "v-1"

    # --- Step 1 — first call must NOT execute, must return confirmation_required ---
    first = await mcp_client_self_service.call_tool(
        "vdb_tool", {"action": "stop", "vdb_id": vdb_id}
    )
    assert not first.is_error, f"First call should return confirmation, not error: {first}"

    body = _payload(first)
    assert body.get("status") == "confirmation_required", (
        f"Expected confirmation_required envelope, got: {body}"
    )
    assert body.get("confirmation_level") == "standard"
    assert not dct_stub.received_request("POST", f"/dct/v3/vdbs/{vdb_id}/stop"), (
        "MCP server must NOT have sent the stop request before confirmation"
    )

    # --- Step 2 — second call with confirmed=True actually issues the POST ---
    second = await mcp_client_self_service.call_tool(
        "vdb_tool",
        {"action": "stop", "vdb_id": vdb_id, "confirmed": True},
    )
    assert not second.is_error, f"Confirmed call should succeed: {second}"
    assert dct_stub.received_request("POST", f"/dct/v3/vdbs/{vdb_id}/stop"), (
        "MCP server must have sent the stop request after confirmation"
    )
