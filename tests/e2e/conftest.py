"""
Layer 4 fixtures — real DCT instance, no stub.

The real_mcp_client fixture spawns the dct-mcp-server subprocess pointed at
the DCT_BASE_URL / DCT_API_KEY env vars (set by `dct-mcp-test --layer e2e`
from --base-url / --api-key flags, or by the GitHub Actions secrets, or by
the developer's shell).

All tests here must be decorated with @pytest.mark.real_dct. The root
conftest's autouse env fixture (tests/conftest.py) skips for tests with this
marker so the real credentials are not overridden with placeholders.
"""

import os
import sys
from typing import AsyncIterator

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport


@pytest.fixture
async def real_mcp_client() -> AsyncIterator[Client]:
    """MCP client connected to dct-mcp-server pointed at a real DCT instance."""
    base_url = os.environ.get("DCT_BASE_URL")
    api_key = os.environ.get("DCT_API_KEY")
    if not base_url or not api_key:
        pytest.skip(
            "DCT_BASE_URL and DCT_API_KEY env vars are required for real_dct "
            "tests — set them, or run via `dct-mcp-test --layer e2e "
            "--base-url ... --api-key ...`"
        )

    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "dct_mcp_server.main"],
        env={
            **os.environ,
            "DCT_API_KEY": api_key,
            "DCT_BASE_URL": base_url,
            "DCT_TOOLSET": "self_service",
            "DCT_VERIFY_SSL": "false",       # local DCT typically self-signed
            "DCT_LOG_LEVEL": "ERROR",
            "DCT_TIMEOUT": "30",
            "DCT_MAX_RETRIES": "3",          # real DCT has real transient errors
        },
    )
    async with Client(transport) as client:
        yield client
