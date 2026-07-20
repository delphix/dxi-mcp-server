"""
Integration-layer fixtures (Layer 2).

These tests drive a real `DCTAPIClient` with httpx intercepted by respx, so they
see wire-level behavior unit tests can't (URL building, auth header, retry/backoff,
error mapping). The client reads `DCT_*` env from the root conftest's autouse fixture
(DCT_BASE_URL=https://dct.test, DCT_API_KEY=test-api-key, DCT_MAX_RETRIES=3).
"""

from unittest.mock import AsyncMock

import pytest

from dct_mcp_server.dct_client.client import DCTAPIClient

# Base the client builds: {DCT_BASE_URL}/dct/v3
BASE = "https://dct.test/dct/v3"


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    """
    Replace the client's exponential-backoff `asyncio.sleep` with an instant
    AsyncMock so retry tests run in milliseconds. Returned so tests can assert how
    many times backoff was attempted.
    """
    sleep = AsyncMock()
    monkeypatch.setattr("dct_mcp_server.dct_client.client.asyncio.sleep", sleep)
    return sleep


@pytest.fixture
async def client():
    """A DCTAPIClient bound to the test env; closed after the test."""
    c = DCTAPIClient()
    try:
        yield c
    finally:
        await c.close()
