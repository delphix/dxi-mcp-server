"""
Layer 4 fixtures (full suite) — real DCT instance, no stub. Generalized over toolsets.

`real_mcp_client` connects to dct-mcp-server pointed at DCT_BASE_URL / DCT_API_KEY
(set by `dct-mcp-test --layer e2e` from flags, by CI secrets, or by the shell).
All tests here must be @pytest.mark.real_dct — the root conftest skips its placeholder
env override for that marker so real credentials flow through.
"""

import os
import sys
from typing import AsyncIterator

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport


def build_real_transport(toolset: str = "self_service") -> StdioTransport:
    """Transport for dct-mcp-server pointed at a real DCT, for any toolset. Skips if no creds."""
    base_url = os.environ.get("DCT_BASE_URL")
    api_key = os.environ.get("DCT_API_KEY")
    if not base_url or not api_key:
        pytest.skip(
            "DCT_BASE_URL and DCT_API_KEY env vars are required for real_dct tests — "
            "run via `dct-mcp-test --layer e2e --base-url ... --api-key ...`"
        )
    return StdioTransport(
        command=sys.executable,
        args=["-m", "dct_mcp_server.main"],
        env={
            **os.environ,
            "DCT_API_KEY": api_key,
            "DCT_BASE_URL": base_url,
            "DCT_TOOLSET": toolset,
            "DCT_VERIFY_SSL": "false",
            "DCT_LOG_LEVEL": "ERROR",
            "DCT_TIMEOUT": "30",
            "DCT_MAX_RETRIES": "3",
        },
    )


@pytest.fixture
async def real_mcp_client() -> AsyncIterator[Client]:
    """MCP client connected to dct-mcp-server pointed at a real DCT (self_service)."""
    async with Client(build_real_transport("self_service")) as client:
        yield client
