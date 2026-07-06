"""
Layer 4 — Real-DCT smoke & read-only contract tests.

Boots the dct-mcp-server against a REAL DCT (self_service) and exercises read-only
operations. Proves real auth, the live OpenAPI/tool surface, and response-shape
contract — the things the stub can't (real API drift, real latency).

Read-only and safe to run against any DCT (including production-shaped clones).
All tests are @pytest.mark.real_dct and SKIP cleanly when DCT_BASE_URL/DCT_API_KEY
are absent. Run via:
    dct-mcp-test --layer e2e --base-url https://<dct> --api-key <key>
"""

import pytest

from tests._support import config_cases
from tests.e2e._helpers import call_tool_tolerant, payload as _payload

pytestmark = [pytest.mark.real_dct, pytest.mark.asyncio]


# Read-only "search" actions for each self_service tool (POST /<resource>/search).
SEARCH_TOOLS = [
    "vdb_tool",
    "vdb_group_tool",
    "dsource_tool",
    "snapshot_tool",
    "bookmark_tool",
    "job_tool",
    "timeflow_tool",
]


async def test_server_boots_and_registers_self_service(real_mcp_client):
    """The server starts against the real DCT and exposes the self_service surface."""
    names = {t.name for t in await real_mcp_client.list_tools()}
    expected = set(config_cases.tools_for("self_service"))
    missing = expected - names
    assert not missing, (
        f"missing tools against real DCT: {missing}; registered: {sorted(names)}"
    )


@pytest.mark.parametrize("tool", SEARCH_TOOLS)
async def test_read_only_search_returns_well_shaped_response(real_mcp_client, tool):
    """
    Each resource's search returns a well-shaped paginated response from the real
    DCT. The list may be empty (fresh DCT) — we assert SHAPE, not contents.
    """
    result = await call_tool_tolerant(
        real_mcp_client, tool, {"action": "search", "limit": 5}
    )
    body = _payload(result)
    assert isinstance(body, dict), f"{tool} search returned non-dict: {body!r}"
    assert "items" in body, f"{tool} search response missing 'items': {body}"
    assert isinstance(body["items"], list), (
        f"{tool} 'items' not a list: {type(body['items'])}"
    )


async def test_vdb_get_roundtrip_if_any_exist(real_mcp_client):
    """If the DCT has any VDBs, GET the first one and confirm its id echoes back."""
    search = await call_tool_tolerant(
        real_mcp_client, "vdb_tool", {"action": "search", "limit": 1}
    )
    items = _payload(search).get("items", [])
    if not items:
        pytest.skip("no VDBs on this DCT — nothing to round-trip (not a failure)")
    vdb_id = items[0]["id"]
    got = await call_tool_tolerant(
        real_mcp_client, "vdb_tool", {"action": "get", "vdb_id": vdb_id}
    )
    assert _payload(got).get("id") == vdb_id
