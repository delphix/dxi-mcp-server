"""
Layer 4 — Real-DCT smoke & read-only contract tests for the continuous_data_admin
(CDA, admin persona) toolset.

Mirrors tests/e2e/test_smoke.py but targets the CDA toolset: boots dct-mcp-server
against a REAL DCT with DCT_TOOLSET=continuous_data_admin and exercises read-only
operations. Proves real auth, the live tool surface, and response-shape contract for
the admin persona — things the stub can't (real API drift, real latency).

Read-only and safe to run against any DCT. All tests are @pytest.mark.real_dct and
SKIP cleanly when DCT_BASE_URL/DCT_API_KEY are absent. Run via:
    dct-mcp-test --layer e2e --base-url https://<dct> --api-key <key>
"""

from typing import AsyncIterator

import pytest
from fastmcp import Client

from tests._support import config_cases
from tests.e2e._helpers import call_tool_tolerant, payload as _payload
from tests.e2e.conftest import build_real_transport

pytestmark = [pytest.mark.real_dct, pytest.mark.asyncio]

_TOOLSET = "continuous_data_admin"


# Derived from the SAME config the server reads, so this stays in sync with the
# toolset definition. The CDA tools that expose a literal "search" action.
SEARCH_TOOLS = sorted(
    tool
    for tool, apis in config_cases.tools_for(_TOOLSET).items()
    if any(action == "search" for _method, _path, action in apis)
)


@pytest.fixture
async def cda_mcp_client() -> AsyncIterator[Client]:
    """MCP client connected to dct-mcp-server pointed at a real DCT (CDA toolset)."""
    async with Client(build_real_transport(_TOOLSET)) as client:
        yield client


async def test_cda_registers_all_configured_tools(cda_mcp_client):
    """The server starts against the real DCT and exposes the full CDA surface (all 22)."""
    names = {t.name for t in await cda_mcp_client.list_tools()}
    expected = set(config_cases.tools_for(_TOOLSET))
    missing = expected - names
    assert not missing, (
        f"missing CDA tools against real DCT: {missing}; registered: {sorted(names)}"
    )


@pytest.mark.parametrize("tool", SEARCH_TOOLS)
async def test_cda_read_only_search_well_shaped(cda_mcp_client, tool):
    """
    Each CDA resource's search returns a well-shaped paginated response from the real
    DCT. The list may be empty — we assert SHAPE, not contents.
    """
    result = await call_tool_tolerant(
        cda_mcp_client, tool, {"action": "search", "limit": 5}
    )
    body = _payload(result)
    assert isinstance(body, dict), f"{tool} search returned non-dict: {body!r}"
    assert "items" in body, f"{tool} search response missing 'items': {body}"
    assert isinstance(body["items"], list), (
        f"{tool} 'items' not a list: {type(body['items'])}"
    )
