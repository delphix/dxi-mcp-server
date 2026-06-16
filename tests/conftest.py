"""
Shared pytest fixtures for the DCT MCP Server test suite.

PoC scope: provides a mock DCTAPIClient suitable for Layer 1 unit tests, and
sets minimal env vars so Layer 2 integration tests can instantiate a real
DCTAPIClient against respx-mocked HTTP.
"""

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Warm up pydantic's generic-model registry before any mcp.server.fastmcp import.
# pytest-cov instruments target modules before the test file's own imports run,
# which means meta_tools.py can trigger `from mcp.server.fastmcp import Context`
# before pydantic.root_model is registered in sys.modules → KeyError.
# Importing RootModel here (in conftest) ensures pydantic self-registers first.
from pydantic import RootModel  # noqa: F401

import pytest


def pytest_configure(config):
    """Load DCT credentials from .claude/settings.local.json into os.environ.

    Lets L4/L5 tests find real credentials when pytest is run directly
    (outside a Claude Code session). No-op if vars are already set.
    """
    if os.environ.get("DCT_API_KEY") and os.environ.get("DCT_BASE_URL"):
        return
    settings = Path(__file__).resolve().parents[1] / ".claude" / "settings.local.json"
    if not settings.exists():
        return
    try:
        data = json.loads(settings.read_text())
        env = data.get("env", {})
        for key in ("DCT_API_KEY", "DCT_BASE_URL"):
            if key not in os.environ and env.get(key):
                os.environ[key] = env[key]
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch, request):
    """
    Ensure DCT_API_KEY and DCT_BASE_URL are set for any test that instantiates
    DCTAPIClient. Tests can override via their own monkeypatch.setenv calls.

    Skipped for tests marked @pytest.mark.real_dct so the real DCT credentials
    passed via env / CLI flow through to the e2e fixtures unchanged.
    """
    if request.node.get_closest_marker("real_dct"):
        return
    monkeypatch.setenv("DCT_API_KEY", "test-api-key")
    monkeypatch.setenv("DCT_BASE_URL", "https://dct.test")
    monkeypatch.setenv("DCT_VERIFY_SSL", "false")
    monkeypatch.setenv("DCT_TIMEOUT", "30")
    monkeypatch.setenv("DCT_MAX_RETRIES", "3")
    monkeypatch.setenv("DCT_LOG_LEVEL", "ERROR")


@pytest.fixture
def mock_dct_client():
    """
    A MagicMock standing in for DCTAPIClient. The make_request method is an
    AsyncMock so tool functions awaiting it get a real coroutine.
    """
    client = MagicMock()
    client.make_request = AsyncMock(return_value={"items": []})
    return client
