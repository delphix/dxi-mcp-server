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
import re
import sys
from pathlib import Path
from typing import AsyncIterator, Iterator

import pytest
import yaml
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from tests._support import config_cases as cc
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


# ---------------------------------------------------------------------------
# In-process generated-tools fixture (shared by persona-chain / CDA functional
# tests). CDA tools are dynamic-generation-only (pre-built modules removed), so
# the subprocess+stub path cannot register them. These tests instead build the
# generated grouped tools IN-MEMORY, wired to a real DCTAPIClient pointed at the
# `dct_stub`, and call them directly (`await func(action=..., **kwargs)`).
# ---------------------------------------------------------------------------


@pytest.fixture
async def persona_tools(dct_stub: DctStub, monkeypatch):
    """
    Build generated tools wired to a real DCTAPIClient pointed at the stub.

    Returns a factory: `make(toolset) -> {tool_name: func}`. Restores tool_factory
    globals and closes the client on teardown. Available to all tests under
    tests/functional/ (incl. workflows/) via this conftest.
    """
    import dct_mcp_server.tools.core.tool_factory as tf
    from dct_mcp_server.dct_client.client import DCTAPIClient

    monkeypatch.setenv("DCT_BASE_URL", dct_stub.url)
    monkeypatch.setenv("DCT_API_KEY", "test")
    monkeypatch.setenv("DCT_VERIFY_SSL", "false")

    saved_spec, saved_client = tf._openapi_spec, tf._dct_client
    tf._openapi_spec = yaml.safe_load(SPEC_PATH.read_text())
    client = DCTAPIClient()
    tf._dct_client = client

    generated: dict = {}

    def make(toolset: str) -> dict:
        if toolset not in generated:
            generated[toolset] = {n: f for f, n in tf.generate_tools_for_toolset(toolset)}
        return generated[toolset]

    yield make

    await client.close()
    tf._openapi_spec = saved_spec
    tf._dct_client = saved_client


def persona_path_for(toolset: str, tool: str, action: str):
    """Look up (method, path) for an action from the config oracle (verifies it's real)."""
    for m, p, a in cc.tools_for(toolset)[tool]:
        if a == action:
            return m, p
    raise AssertionError(f"{toolset}/{tool} has no action {action!r}")
