"""
Layer 3b — Dynamic mode (DCT_TOOLSET=dynamic) over the MCP wire.

Verifies that the 2-tool architecture (discovery + execute) is correctly wired
and accessible over the MCP stdio transport.  Uses a pre-populated spec cache
file (DCT_SPEC_CACHE_PATH + DCT_SPEC_MAX_AGE_HOURS=9999) so the server does
not need a live DCT connection to load the OpenAPI spec.
"""

from __future__ import annotations

import os
import sys

import pytest
import yaml
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from tests.fixtures.dct_stub import DctStub

# ---------------------------------------------------------------------------
# Minimal spec shared by all tests in this module
# ---------------------------------------------------------------------------

_MINIMAL_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "DCT Test", "version": "1"},
    "paths": {
        "/vdbs": {
            "get": {
                "operationId": "listVdbs",
                "summary": "List VDBs",
                "tags": ["VDBs"],
            }
        },
        "/vdbs/search": {
            "post": {
                "operationId": "searchVdbs",
                "summary": "Search VDBs",
                "tags": ["VDBs"],
            }
        },
        "/environments": {
            "get": {
                "operationId": "listEnvironments",
                "summary": "List environments",
                "tags": ["Environments"],
            }
        },
    },
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def dynamic_spec_cache(tmp_path_factory):
    """Write _MINIMAL_SPEC to a temp YAML file; return its path."""
    cache_file = tmp_path_factory.mktemp("spec") / "api-external-dynamic.yaml"
    cache_file.write_text(yaml.dump(_MINIMAL_SPEC))
    return str(cache_file)


def _build_dynamic_transport(stub: DctStub, spec_cache_path: str) -> StdioTransport:
    """Spawn the MCP server in dynamic mode with a pre-seeded spec cache."""
    return StdioTransport(
        command=sys.executable,
        args=["-m", "dct_mcp_server.main"],
        env={
            **os.environ,
            "DCT_API_KEY": "test-api-key",
            "DCT_BASE_URL": stub.url,
            "DCT_TOOLSET": "dynamic",
            "DCT_VERIFY_SSL": "false",
            "DCT_LOG_LEVEL": "ERROR",
            "DCT_TIMEOUT": "10",
            "DCT_MAX_RETRIES": "2",
            # Point the server at our pre-seeded spec file; disable re-download.
            "DCT_SPEC_CACHE_PATH": spec_cache_path,
            "DCT_SPEC_MAX_AGE_HOURS": "9999",
        },
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dynamic_mode_registers_exactly_two_tools(dct_stub, dynamic_spec_cache):
    """Dynamic mode must expose exactly `discovery` and `execute` — no more, no less."""
    async with Client(_build_dynamic_transport(dct_stub, dynamic_spec_cache)) as client:
        tools = await client.list_tools()
    names = {t.name for t in tools}
    expected = {"discovery", "execute"}
    assert names == expected, (
        f"Dynamic mode tool surface drifted.\n"
        f"  missing: {expected - names}\n"
        f"  unexpected: {names - expected}"
    )


@pytest.mark.asyncio
async def test_dynamic_mode_discovery_list_tags(dct_stub, dynamic_spec_cache):
    """discovery(action='list_tags') returns a non-empty list of API tags."""
    async with Client(_build_dynamic_transport(dct_stub, dynamic_spec_cache)) as client:
        result = await client.call_tool("discovery", {"action": "list_tags"})

    assert not result.is_error, f"discovery list_tags errored: {result}"
    sc = result.structured_content or {}
    data = sc.get("result", sc)
    assert "tags" in data, f"expected 'tags' key, got: {data}"
    assert len(data["tags"]) > 0
    tag_names = {t["name"] for t in data["tags"]}
    assert "VDBs" in tag_names


@pytest.mark.asyncio
async def test_dynamic_mode_discovery_list_operations(dct_stub, dynamic_spec_cache):
    """discovery(action='list_operations') returns operations from the spec."""
    async with Client(_build_dynamic_transport(dct_stub, dynamic_spec_cache)) as client:
        result = await client.call_tool("discovery", {"action": "list_operations"})

    assert not result.is_error, f"discovery list_operations errored: {result}"
    sc = result.structured_content or {}
    data = sc.get("result", sc)
    assert "operations" in data
    assert data["total_count"] >= 3  # 3 paths in _MINIMAL_SPEC


@pytest.mark.asyncio
async def test_dynamic_mode_execute_dispatches_to_stub(dct_stub, dynamic_spec_cache):
    """`execute` dispatches a GET to the stub and returns status: success."""
    async with Client(_build_dynamic_transport(dct_stub, dynamic_spec_cache)) as client:
        result = await client.call_tool(
            "execute",
            {"path": "/vdbs", "method": "GET"},
        )

    assert not result.is_error, f"execute errored: {result}"
    sc = result.structured_content or {}
    data = sc.get("result", sc)
    assert data.get("status") == "success", f"expected success, got: {data}"
    assert dct_stub.received_request("GET", "/dct/v3/vdbs")
