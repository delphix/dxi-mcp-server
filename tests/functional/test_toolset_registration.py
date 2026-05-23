"""
Layer 3a — Toolset registration.

Verifies that when the MCP server boots with DCT_TOOLSET=self_service, the
expected set of tools is registered and visible to the MCP client over stdio.

This is the test that catches "I broke a persona by editing config or code" —
every PR runs this and a missing tool fails CI.

NOTE on naming: the dct_stub does not serve /dct/static/api-external.yaml, so
the OpenAPI tool generator fails on startup and the server falls back to the
pre-built tool modules. The pre-built `dataset_endpoints_tool.py` consolidates
VDB / dSource / snapshot / bookmark domains into broader grouped tools
(`data_tool`, `snapshot_bookmark_tool`, `timeflow_tool`) rather than the
per-resource names in the toolset .txt file. We assert against the actual
registered surface — a fuller test against the dynamically-generated names
would need the stub to serve a real OpenAPI yaml (future work).
"""

import pytest


# Tools the pre-built fallback registers for self_service. Includes the dataset
# module's consolidated tools plus job_tool from the job module.
EXPECTED_SELF_SERVICE_TOOLS = {
    "data_tool",
    "snapshot_bookmark_tool",
    "timeflow_tool",
    "data_connection_tool",
    "job_tool",
}


@pytest.mark.asyncio
async def test_self_service_registers_expected_tools(mcp_client_self_service):
    """self_service must expose the expected consolidated tool surface."""
    tools = await mcp_client_self_service.list_tools()
    names = {t.name for t in tools}

    missing = EXPECTED_SELF_SERVICE_TOOLS - names
    assert not missing, (
        f"self_service is missing expected tools: {missing}\n"
        f"Actually registered: {sorted(names)}"
    )
