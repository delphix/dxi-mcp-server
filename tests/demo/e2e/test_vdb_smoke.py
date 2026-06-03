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


# Tools generated dynamically from self_service.txt at runtime against real DCT.
# Names come straight from `# TOOL N: <name>` headers in config/toolsets/self_service.txt.
EXPECTED_SELF_SERVICE_TOOLS_REAL = {
    "vdb_tool",
    "vdb_group_tool",
    "dsource_tool",
    "snapshot_tool",
    "bookmark_tool",
    "job_tool",
    "timeflow_tool",
}


@pytest.mark.real_dct
@pytest.mark.asyncio
async def test_server_boots_and_registers_tools_against_real_dct(real_mcp_client):
    """
    The most basic smoke test: the MCP server starts, downloads the OpenAPI
    spec from the real DCT, generates tools dynamically, and exposes the full
    self_service surface. If THIS fails, nothing else in Layer 4 can pass.
    """
    tools = await real_mcp_client.list_tools()
    names = {t.name for t in tools}
    missing = EXPECTED_SELF_SERVICE_TOOLS_REAL - names
    assert not missing, (
        f"self_service is missing tools against real DCT: {missing}\n"
        f"Registered tools were: {sorted(names)}"
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
        "vdb_tool", {"action": "search", "limit": 10}
    )
    assert not result.is_error, f"vdb_tool search failed against real DCT: {result}"

    body = _payload(result)
    assert "items" in body, (
        f"Expected DCT vdbs/search response to contain 'items' key. "
        f"Actual response: {body}"
    )
    assert isinstance(body["items"], list), (
        f"'items' should be a list, got {type(body['items']).__name__}"
    )
