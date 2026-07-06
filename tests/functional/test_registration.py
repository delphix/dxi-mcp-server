"""
Layer 3a — Toolset registration over the MCP wire.

Boots the dct-mcp-server as a subprocess (pointed at dct_stub) and asserts the
right tools are exposed for a persona. This catches "an edit to config or code
silently changed what a persona exposes".

Two registration paths are covered:
  * self_service over the real MCP stdio wire (fixed mode falls back to the pre-built
    dataset/job modules — exactly the self_service surface).
  * ALL personas via the in-memory tool generator (`tool_factory.generate_tools_for_toolset`)
    seeded from the bundled OpenAPI spec fixture. This is the production mechanism for the
    non-self_service personas (their pre-built fallback was removed by the kept refactor),
    and it runs offline with no disk writes — unlike the dev-mode file generator, which
    writes into src/.
"""

import pytest

from tests._support import config_cases


EXPECTED_SELF_SERVICE_TOOLS = {
    "data_tool",
    "snapshot_bookmark_tool",
    "data_connection_tool",
    "job_tool",
    "timeflow_tool",
}


@pytest.mark.asyncio
async def test_self_service_registers_exactly_its_configured_tools(
    mcp_client_self_service,
):
    """self_service must expose exactly the pre-built tools from dataset_endpoints_tool and job_endpoints_tool."""
    tools = await mcp_client_self_service.list_tools()
    names = {t.name for t in tools}
    assert names == EXPECTED_SELF_SERVICE_TOOLS, (
        f"self_service registered surface drifted.\n"
        f"  missing: {EXPECTED_SELF_SERVICE_TOOLS - names}\n  unexpected: {names - EXPECTED_SELF_SERVICE_TOOLS}"
    )


@pytest.mark.parametrize("toolset", config_cases.toolset_names())
def test_persona_generates_exactly_its_configured_tools(
    seed_tool_factory_spec, toolset
):
    """
    Every persona's tools generate correctly from the OpenAPI spec — the dynamic path
    that backs registration for personas without a pre-built module. Asserts the
    generated tool set exactly equals the toolset config (the oracle).
    """
    tf = seed_tool_factory_spec
    generated = {name for _, name in tf.generate_tools_for_toolset(toolset)}
    expected = set(config_cases.tools_for(toolset))
    assert generated == expected, (
        f"{toolset}: generated tool set drifted from config.\n"
        f"  missing: {expected - generated}\n  unexpected: {generated - expected}"
    )
