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

from tests._support import config_cases as cc
from tests.fixtures.dct_stub import DctStub, StubServer

# OpenAPI spec: downloaded from the configured DCT instance (DCT_BASE_URL) or
# loaded from the local cache file. The cache (tests/fixtures/api-external.yaml)
# is gitignored — it is populated on the first run with DCT credentials present,
# and reused for subsequent offline runs. This ensures the spec always reflects
# the actual DCT version under test.
_SPEC_CACHE = Path(__file__).resolve().parents[1] / "fixtures" / "api-external.yaml"


def _download_spec() -> dict | None:
    """Download api-external.yaml from DCT_BASE_URL. Returns None on failure."""
    base_url = os.environ.get("DCT_BASE_URL", "")
    api_key = os.environ.get("DCT_API_KEY", "")
    if not base_url or not api_key:
        return None
    import requests

    try:
        url = f"{base_url.rstrip('/')}/dct/static/api-external.yaml"
        r = requests.get(
            url,
            headers={
                "Authorization": f"apk {api_key}",
                "Accept": "application/x-yaml, text/yaml",
            },
            verify=False,
            timeout=30,
        )
        r.raise_for_status()
        spec = yaml.safe_load(r.text)
        # Cache it locally so offline runs can reuse it
        _SPEC_CACHE.parent.mkdir(parents=True, exist_ok=True)
        _SPEC_CACHE.write_text(r.text)
        return spec
    except Exception as e:
        import warnings

        warnings.warn(f"Could not download api-external.yaml from DCT: {e}")
        return None


@pytest.fixture(scope="session")
def openapi_spec() -> dict:
    """
    The DCT OpenAPI spec, downloaded from DCT_BASE_URL on the first run and cached
    at tests/fixtures/api-external.yaml (gitignored) for subsequent offline runs.
    Falls back to the cache file if DCT is not reachable.
    """
    # Try to download fresh from the DCT instance
    spec = _download_spec()
    if spec:
        return spec
    # Fall back to cache
    if _SPEC_CACHE.exists():
        return yaml.safe_load(_SPEC_CACHE.read_text())
    pytest.skip(
        "OpenAPI spec not available: set DCT_BASE_URL + DCT_API_KEY to download it, "
        "or ensure tests/fixtures/api-external.yaml is present."
    )


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
    spec_data = (
        yaml.safe_load(_SPEC_CACHE.read_text())
        if _SPEC_CACHE.exists()
        else _download_spec()
    )
    if spec_data is None:
        pytest.skip("OpenAPI spec not available — ensure cache exists or set DCT creds")
    tf._openapi_spec = spec_data
    client = DCTAPIClient()
    tf._dct_client = client

    generated: dict = {}

    def make(toolset: str) -> dict:
        if toolset not in generated:
            generated[toolset] = {
                n: f for f, n in tf.generate_tools_for_toolset(toolset)
            }
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
