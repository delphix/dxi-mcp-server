"""
Functional-layer fixtures.

dct_stub      → spins up a fake DCT API on 127.0.0.1 in a background thread
mcp_client    → spawns the dct-mcp-server as a subprocess via stdio,
                pointed at the stub, yields a connected fastmcp.Client
"""

import os
import sys
import asyncio
from typing import AsyncIterator, Iterator

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from tests.fixtures.dct_stub import DctStub, StubServer


@pytest.fixture
def dct_stub() -> Iterator[DctStub]:
    """A fresh stub DCT server per test (random port, isolated request log)."""
    server = StubServer()
    stub = server.start()
    try:
        yield stub
    finally:
        server.stop()


def _build_mcp_transport(stub: DctStub, toolset: str) -> StdioTransport:
    """Spawn dct-mcp-server as a stdio subprocess pointed at the stub."""
    return StdioTransport(
        command=sys.executable,
        args=["-m", "dct_mcp_server.main"],
        env={
            **os.environ,                    # PATH, HOME, PYENV stuff
            "DCT_API_KEY": "test-api-key",
            "DCT_BASE_URL": stub.url,
            "DCT_TOOLSET": toolset,
            "DCT_VERIFY_SSL": "false",
            "DCT_LOG_LEVEL": "ERROR",        # quiet the subprocess
            "DCT_TIMEOUT": "10",
            # >=2 so the client can recover after asyncio.run() inside the tool's
            # async_to_sync wrapper closes the event loop between calls (the
            # cached httpx client gets reset on first retry and the second
            # attempt succeeds against the stub).
            "DCT_MAX_RETRIES": "2",
        },
    )


@pytest.fixture
async def mcp_client_self_service(dct_stub: DctStub) -> AsyncIterator[Client]:
    """An MCP client connected to a server running the self_service toolset."""
    transport = _build_mcp_transport(dct_stub, toolset="self_service")
    async with Client(transport) as client:
        yield client
