"""
Shared pytest fixtures for the DCT MCP Server test suite.

PoC scope: provides a mock DCTAPIClient suitable for Layer 1 unit tests, and
sets minimal env vars so Layer 2 integration tests can instantiate a real
DCTAPIClient against respx-mocked HTTP.
"""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch):
    """
    Ensure DCT_API_KEY and DCT_BASE_URL are set for any test that instantiates
    DCTAPIClient. Tests can override via their own monkeypatch.setenv calls.
    """
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
