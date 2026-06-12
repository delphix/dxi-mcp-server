"""
Shared pytest fixtures for the DCT MCP Server test suite.

PoC scope: provides a mock DCTAPIClient suitable for Layer 1 unit tests, and
sets minimal env vars so Layer 2 integration tests can instantiate a real
DCTAPIClient against respx-mocked HTTP.
"""

import os
from unittest.mock import AsyncMock, MagicMock

# Warm up pydantic's generic-model registry before any mcp.server.fastmcp import.
# pytest-cov instruments target modules before the test file's own imports run,
# which means meta_tools.py can trigger `from mcp.server.fastmcp import Context`
# before pydantic.root_model is registered in sys.modules → KeyError.
# Importing RootModel here (in conftest) ensures pydantic self-registers first.
from pydantic import RootModel  # noqa: F401

import pytest


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
