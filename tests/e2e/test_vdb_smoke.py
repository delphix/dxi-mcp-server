"""
Layer 4 — Real DCT smoke tests.

Read-only tests that prove the MCP server can boot pointed at a real DCT
instance and execute basic API calls against it. No mutation — these are
safe to run against any DCT including production-shaped clones.

Run via:
    dct-mcp-test --layer e2e --base-url https://localhost --api-key <key>
or:
    /dct-mcp-test localhost --api-key <key> --layer e2e
"""

import pytest


def _payload(result):
    """Unwrap fastmcp's {"result": <dict>} envelope to expose the raw tool return."""
    sc = result.structured_content or {}
    return sc.get("result", sc)


@pytest.mark.real_dct
@pytest.mark.asyncio
async def test_server_boots_and_registers_tools_against_real_dct(real_mcp_client):
    """
    The most basic smoke test: the MCP server starts, completes its OpenAPI
    download/generation against the real DCT, and exposes the data_tool.
    If THIS fails, nothing else in Layer 4 can pass.
    """
    tools = await real_mcp_client.list_tools()
    names = {t.name for t in tools}
    assert names, "MCP server registered zero tools against real DCT"
    # data_tool is the VDB-domain entry point under self_service
    assert "data_tool" in names, (
        f"data_tool missing — registered tools were: {sorted(names)}"
    )


@pytest.mark.real_dct
@pytest.mark.asyncio
async def test_vdb_search_against_real_dct(real_mcp_client):
    """
    Read-only smoke: VDB search returns a well-shaped response from the real
    DCT. The list can be empty (fresh DCT) — we only assert response shape,
    not specific contents.
    """
    result = await real_mcp_client.call_tool(
        "data_tool", {"action": "search_vdbs", "limit": 10}
    )
    assert not result.is_error, f"search_vdbs failed against real DCT: {result}"

    body = _payload(result)
    assert "items" in body, (
        f"Expected DCT vdbs/search response to contain 'items' key. "
        f"Actual response: {body}"
    )
    assert isinstance(body["items"], list), (
        f"'items' should be a list, got {type(body['items']).__name__}"
    )
