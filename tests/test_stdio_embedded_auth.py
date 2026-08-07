"""Embedded auth over stdio (DLPXECO-14324).

A stdio pipe is 1:1 and carries no request headers, so a host that embeds this
server runs one process per caller and supplies the caller's DCT account id in
the child process environment as ``DCT_CLIENT_ID``. These tests cover that path
and prove it does not disturb the HTTP path, where identity still arrives per
request in the ``X-CLIENT-ID`` header.

The final test spawns the server as a real subprocess over stdio and drives it
with an MCP client. It is the only test in the suite that exercises the
transport the DCT assistant actually ships on.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from dct_mcp_server.core.auth import _CALLER_ID_VAR, resolve_auth
from dct_mcp_server.core.exceptions import AuthError

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

EMBEDDED_STDIO = {
    "DCT_AUTH_MODE": "embedded",
    "DCT_TRANSPORT": "stdio",
    "DCT_TOOLSET": "dynamic",
}


@pytest.fixture
def env(monkeypatch):
    """Apply an embedded+stdio environment, with DCT_API_KEY removed."""

    def _apply(**overrides):
        for key, value in {**EMBEDDED_STDIO, **overrides}.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, value)
        # Embedded mode never uses an API key; make sure a stray one from the
        # session fixture cannot mask a missing-identity failure.
        monkeypatch.delenv("DCT_API_KEY", raising=False)

    return _apply


# --------------------------------------------------------------------------- #
# resolve_auth()
# --------------------------------------------------------------------------- #


def test_identity_resolves_from_environment(env):
    """With no HTTP request in play, DCT_CLIENT_ID supplies the caller."""
    env(DCT_CLIENT_ID="acct-4711")
    ctx = resolve_auth()
    assert ctx.account_id == "acct-4711"
    assert ctx.auth_mode == "embedded"
    assert ctx.api_key is None


def test_missing_identity_raises(env):
    """Embedded mode must never fall back to a default identity."""
    env(DCT_CLIENT_ID=None)
    with pytest.raises(AuthError) as exc:
        resolve_auth()
    # The message must name both mechanisms so the failure is self-diagnosing.
    assert "X-CLIENT-ID" in str(exc.value)
    assert "DCT_CLIENT_ID" in str(exc.value)


def test_blank_identity_is_treated_as_missing(env):
    """An empty or whitespace-only value must not be accepted as an identity."""
    env(DCT_CLIENT_ID="   ")
    with pytest.raises(AuthError):
        resolve_auth()


def test_request_header_wins_over_environment(env):
    """An HTTP deployment is unaffected by a stray DCT_CLIENT_ID in the env."""
    env(DCT_CLIENT_ID="from-env")
    token = _CALLER_ID_VAR.set("from-header")
    try:
        assert resolve_auth().account_id == "from-header"
    finally:
        _CALLER_ID_VAR.reset(token)


def test_standalone_mode_is_unchanged(monkeypatch):
    """The default deployment must not be affected by any of this."""
    monkeypatch.setenv("DCT_AUTH_MODE", "standalone")
    monkeypatch.setenv("DCT_API_KEY", "key-abc")
    monkeypatch.setenv("DCT_CLIENT_ID", "ignored-in-standalone")
    ctx = resolve_auth()
    assert ctx.account_id == "standalone"
    assert ctx.api_key == "key-abc"
    assert ctx.auth_mode == "standalone"


# --------------------------------------------------------------------------- #
# Startup validation
# --------------------------------------------------------------------------- #


def test_startup_requires_client_id_for_embedded_stdio(env):
    """Fail at startup, not on the first tool call."""
    from dct_mcp_server.config.config import get_dct_config

    env(DCT_CLIENT_ID=None)
    with pytest.raises(ValueError, match="DCT_CLIENT_ID is required"):
        get_dct_config(require_key=True)


def test_startup_does_not_require_client_id_over_http(env):
    """Over HTTP the header supplies identity, so the env value is optional."""
    from dct_mcp_server.config.config import get_dct_config

    env(DCT_CLIENT_ID=None, DCT_TRANSPORT="http")
    config = get_dct_config(require_key=True)
    assert config["client_id"] is None
    assert config["auth_mode"] == "embedded"


# --------------------------------------------------------------------------- #
# Real stdio round-trip
# --------------------------------------------------------------------------- #


def _seed_spec(tmp_path: Path) -> Path:
    """Write a minimal OpenAPI spec plus a fresh cache-meta sidecar.

    Mirrors what the DCT appliance's seeding step does, so the server starts
    without needing to reach a live DCT instance.
    """
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "DCT (test)", "version": "1.0"},
        "paths": {
            "/vdbs": {
                "get": {
                    "operationId": "getVdbs",
                    "summary": "List VDBs.",
                    "tags": ["VDBs"],
                    "responses": {"200": {"description": "ok"}},
                }
            },
            "/vdbs/{vdbId}/delete": {
                "post": {
                    "operationId": "deleteVdb",
                    "summary": "Delete a VDB.",
                    "tags": ["VDBs"],
                    "responses": {"200": {"description": "ok"}},
                }
            },
        },
    }
    cache = tmp_path / "api-external-dynamic.yaml"
    cache.write_text(yaml.safe_dump(spec))
    (tmp_path / ".cache-meta.json").write_text(
        json.dumps(
            {
                "downloaded_at": datetime.now(timezone.utc).isoformat(),
                "dct_base_url": "seeded-by-test",
                "spec_path": str(cache),
            }
        )
    )
    return cache


async def _drive_server(child_env: dict) -> tuple[list[str], object]:
    """Spawn the server over stdio and return (tool names, discovery result)."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server = Path(sys.executable).parent / "dct-mcp-server"
    params = StdioServerParameters(
        command=str(server), args=[], env={**os.environ, **child_env}
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            result = await session.call_tool("discovery", {"action": "list_tags"})
            return names, result


def test_stdio_spawn_end_to_end(tmp_path):
    """Spawn the real server over stdio with identity in the environment.

    This is the transport the DCT assistant ships on. It proves four things at
    once: the process starts in embedded+stdio mode without an API key, the
    identity is accepted from the environment, the dynamic toolset registers,
    and a tool call round-trips over the pipe.
    """
    cache = _seed_spec(tmp_path)
    child_env = {
        **EMBEDDED_STDIO,
        "DCT_CLIENT_ID": "acct-4711",
        "DCT_SPEC_CACHE_PATH": str(cache),
        "DCT_BASE_URL": "http://gateway:8080/v3",
        "DCT_API_PATH_PREFIX": "",
        "DCT_VERIFY_SSL": "false",
        "IS_LOCAL_TELEMETRY_ENABLED": "false",
    }
    child_env.pop("DCT_API_KEY", None)

    names, result = asyncio.run(asyncio.wait_for(_drive_server(child_env), timeout=60))

    assert names == ["discovery", "execute"], f"unexpected toolset: {names}"
    payload = str(result.content)
    assert "VDBs" in payload, f"discovery did not return spec tags: {payload[:400]}"


def test_stdio_spawn_without_identity_fails(tmp_path):
    """Without DCT_CLIENT_ID the process must refuse to serve, not default."""
    import subprocess

    cache = _seed_spec(tmp_path)
    child_env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("DCT_API_KEY", "DCT_CLIENT_ID")
    }
    child_env.update(
        {
            **EMBEDDED_STDIO,
            "DCT_SPEC_CACHE_PATH": str(cache),
            "DCT_BASE_URL": "http://gateway:8080/v3",
        }
    )
    server = Path(sys.executable).parent / "dct-mcp-server"
    proc = subprocess.run(
        [str(server)],
        env=child_env,
        input="",
        capture_output=True,
        text=True,
        timeout=45,
    )
    combined = proc.stdout + proc.stderr
    assert proc.returncode != 0, "server started without a caller identity"
    assert "DCT_CLIENT_ID" in combined, f"unhelpful failure output: {combined[-500:]}"
