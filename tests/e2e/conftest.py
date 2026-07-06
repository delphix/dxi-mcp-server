"""
Layer 4 fixtures (full suite) — real DCT instance, no stub. Generalized over toolsets.

`real_mcp_client` connects to dct-mcp-server using the server definition in
`.mcp.json` (the same config Claude Code uses interactively), overriding
DCT_TOOLSET for the requested persona. Credentials come from DCT_BASE_URL /
DCT_API_KEY env vars — never hardcoded.

SAFE-RUN: the server command is read from .mcp.json (currently `python -m
dct_mcp_server.main`). In a dev/editable checkout the startup generator writes
into src/. Run these tests from the `.venv-live` non-editable install to avoid
that — generation then goes to $TEMP, src/ is untouched:
    set -a; source .env.local; set +a
    .venv-live/bin/python -m pytest tests/e2e -m real_dct -v

All tests here must be @pytest.mark.real_dct — the root conftest skips its
placeholder env override for that marker so real credentials flow through.
"""

import json
import os
from pathlib import Path
from typing import AsyncIterator

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MCP_JSON = _REPO_ROOT / ".mcp.json"
MCP_SERVER_NAME = "delphix-dct"


def build_real_transport(toolset: str = "self_service") -> StdioTransport:
    """
    Build a StdioTransport for the dct-mcp-server using the `.mcp.json` server
    definition, overriding DCT_TOOLSET with the requested toolset.
    Credentials (DCT_BASE_URL, DCT_API_KEY) are read from the environment.
    Skips the test if credentials are absent.
    """
    base_url = os.environ.get("DCT_BASE_URL")
    api_key = os.environ.get("DCT_API_KEY")
    if not base_url or not api_key:
        pytest.skip(
            "DCT_BASE_URL and DCT_API_KEY env vars are required for real_dct tests — "
            "run via `dct-mcp-test --layer e2e --base-url ... --api-key ...`"
        )

    # Read server definition from .mcp.json so there is one source of truth.
    mcp_config = json.loads(_MCP_JSON.read_text())
    server = mcp_config["mcpServers"][MCP_SERVER_NAME]

    server_env = {
        # Resolve any ${VAR} references in the config's env block
        k: os.path.expandvars(v) if isinstance(v, str) else v
        for k, v in server.get("env", {}).items()
    }
    # Override with explicit runtime values
    server_env.update(
        {
            "DCT_API_KEY": api_key,
            "DCT_BASE_URL": base_url,
            "DCT_TOOLSET": toolset,
            "DCT_VERIFY_SSL": "false",
            "DCT_LOG_LEVEL": "ERROR",
            "DCT_TIMEOUT": "30",
            "DCT_MAX_RETRIES": "3",
        }
    )
    # Propagate TMPDIR for generation isolation (safe-run venv writes to $TEMP)
    if os.environ.get("TMPDIR"):
        server_env["TMPDIR"] = os.environ["TMPDIR"]

    return StdioTransport(
        command=server["command"],
        args=server.get("args", []),
        env={**os.environ, **server_env},
    )


@pytest.fixture
async def real_mcp_client() -> AsyncIterator[Client]:
    """MCP client connected to dct-mcp-server pointed at a real DCT (self_service)."""
    async with Client(build_real_transport("self_service")) as client:
        yield client
