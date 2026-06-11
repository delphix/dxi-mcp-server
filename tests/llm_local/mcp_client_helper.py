"""
MCP client helper — replaces direct `requests` API calls with proper MCP tool calls
via the `delphix-dct` server configured in `.mcp.json`.

This is the canonical way to talk to the DCT in all tests:
  - Uses the same server config as the interactive Claude Code session
  - No hardcoded credentials in test code (all come from .mcp.json + env vars)
  - No direct HTTP calls that bypass the MCP layer

Usage:
    async with mcp_dct(toolset="continuous_data_admin") as client:
        result = await client.call_tool("engine_tool", {"action": "search", "limit": 10})
        items = _payload(result).get("items", [])

Or use the sync helper for idempotence checks in setup/teardown:
    engines = mcp_search_sync("engine_tool", "search")
    dsources = mcp_search_sync("dsource_tool", "search")
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MCP_JSON = _REPO_ROOT / ".mcp.json"
MCP_SERVER_NAME = "delphix-dct"


def _build_transport(toolset: str) -> StdioTransport:
    """
    Build a StdioTransport for the `delphix-dct` server from `.mcp.json`,
    overriding DCT_TOOLSET with the requested toolset.
    Reads DCT_API_KEY and DCT_BASE_URL from the current environment.
    """
    base_url = os.environ.get("DCT_BASE_URL", "")
    api_key = os.environ.get("DCT_API_KEY", "")

    if not base_url or not api_key:
        raise RuntimeError(
            "DCT_BASE_URL and DCT_API_KEY must be set to use the MCP client helper."
        )

    # Read the server definition from .mcp.json
    mcp_config = json.loads(_MCP_JSON.read_text())
    server = mcp_config["mcpServers"][MCP_SERVER_NAME]

    server_env = {
        # Resolve env vars from the current process — handles ${VAR} substitution
        k: os.path.expandvars(v) if isinstance(v, str) else v
        for k, v in server.get("env", {}).items()
    }
    # Override with the requested toolset and explicit credentials
    server_env.update({
        "DCT_API_KEY": api_key,
        "DCT_BASE_URL": base_url,
        "DCT_TOOLSET": toolset,
        "DCT_VERIFY_SSL": "false",
        "DCT_LOG_LEVEL": "ERROR",
        "DCT_TIMEOUT": "30",
        "DCT_MAX_RETRIES": "3",
    })

    return StdioTransport(
        command=server["command"],
        args=server.get("args", []),
        env={**os.environ, **server_env},
    )


@asynccontextmanager
async def mcp_dct(toolset: str = "continuous_data_admin"):
    """
    Async context manager: yields a connected fastmcp.Client for the given toolset.

        async with mcp_dct("continuous_data_admin") as client:
            result = await client.call_tool("engine_tool", {"action": "search"})
    """
    async with Client(_build_transport(toolset)) as client:
        yield client


def payload(result) -> dict:
    """Unwrap a fastmcp CallToolResult into the raw DCT response dict."""
    sc = result.structured_content or {}
    return sc.get("result", sc)


# ── Sync wrappers for use in idempotence checks (setup/teardown) ─────────────

def _run(coro):
    """Run a coroutine synchronously (for use in sync pytest test functions)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=30)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def mcp_search(tool: str, action: str = "search", limit: int = 20,
               toolset: str = "continuous_data_admin") -> list:
    """
    Synchronous convenience: call `tool(action=action, limit=limit)` via MCP
    and return the `items` list. Returns [] if DCT not reachable.

    Replaces direct `requests.post(f"{base}/dct/v3/{endpoint}/search")` calls
    in setup/teardown idempotence checks.
    """
    if not os.environ.get("DCT_BASE_URL") or not os.environ.get("DCT_API_KEY"):
        return []

    async def _search():
        try:
            async with mcp_dct(toolset) as client:
                result = await client.call_tool(
                    tool, {"action": action, "limit": limit}, raise_on_error=False
                )
                if result.is_error:
                    return []
                return payload(result).get("items", [])
        except Exception:
            return []

    return _run(_search())
