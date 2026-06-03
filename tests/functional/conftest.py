"""
Functional-layer fixtures (full suite) — subprocess MCP server over stdio + dct_stub.

Generalized over toolsets so registration/workflow tests can target ANY persona:

    transport = build_stub_transport(stub, toolset="continuous_data_admin")
    async with Client(transport) as client:
        ...

A convenience `mcp_client_self_service` fixture covers the common case. Reuses the
shared stub in tests/fixtures/dct_stub.py.
"""

import os
import sys
from pathlib import Path
from typing import AsyncIterator, Iterator

import pytest
import yaml
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from tests.fixtures.dct_stub import DctStub, StubServer

# Bundled OpenAPI spec fixture (captured from a real DCT). Lets the in-memory tool
# generator produce ALL personas' tools offline — the safe way to test the dynamic
# path without the dev-mode generator writing into src/ (which it does on disk).
SPEC_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "api-external.yaml"


@pytest.fixture(scope="session")
def openapi_spec() -> dict:
    """The DCT OpenAPI spec fixture, parsed once per session."""
    return yaml.safe_load(SPEC_PATH.read_text())


@pytest.fixture
def seed_tool_factory_spec(openapi_spec, monkeypatch):
    """
    Seed tool_factory's in-memory spec cache from the fixture so
    `generate_tools_for_toolset(...)` runs offline with no disk writes and no
    network. Returns the tool_factory module. monkeypatch restores the cache after.
    """
    import dct_mcp_server.tools.core.tool_factory as tf

    monkeypatch.setattr(tf, "_openapi_spec", openapi_spec)
    return tf


@pytest.fixture
def dct_stub() -> Iterator[DctStub]:
    """A fresh stub DCT server per test (random port, isolated request log)."""
    server = StubServer()
    stub = server.start()
    try:
        yield stub
    finally:
        server.stop()


def build_stub_transport(stub: DctStub, toolset: str) -> StdioTransport:
    """Spawn dct-mcp-server as a stdio subprocess pointed at the stub, for any toolset."""
    return StdioTransport(
        command=sys.executable,
        args=["-m", "dct_mcp_server.main"],
        env={
            **os.environ,
            "DCT_API_KEY": "test-api-key",
            "DCT_BASE_URL": stub.url,
            "DCT_TOOLSET": toolset,
            "DCT_VERIFY_SSL": "false",
            "DCT_LOG_LEVEL": "ERROR",
            "DCT_TIMEOUT": "10",
            "DCT_MAX_RETRIES": "2",
        },
    )


@pytest.fixture
async def mcp_client_self_service(dct_stub: DctStub) -> AsyncIterator[Client]:
    """An MCP client connected to a server running the self_service toolset."""
    async with Client(build_stub_transport(dct_stub, "self_service")) as client:
        yield client
