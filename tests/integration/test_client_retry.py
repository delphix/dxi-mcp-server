"""
Layer 2 — Integration test for DCTAPIClient.

Uses respx to intercept httpx at the socket. Verifies wire-level behavior
that unit tests (which mock make_request) cannot see:
  - Auth header is built with the `apk ` prefix
  - 5xx responses are retried with exponential backoff
  - 4xx responses fail fast without retry
"""

import httpx
import pytest
import respx

from dct_mcp_server.core.exceptions import DCTClientError
from dct_mcp_server.dct_client.client import DCTAPIClient


@respx.mock
async def test_client_retries_on_5xx_then_succeeds():
    """5xx responses should retry; final 200 wins."""
    route = respx.get("https://dct.test/dct/v3/jobs").mock(
        side_effect=[
            httpx.Response(503, json={"error": "unavailable"}),
            httpx.Response(503, json={"error": "unavailable"}),
            httpx.Response(200, json={"items": [{"id": "j-1"}]}),
        ]
    )

    client = DCTAPIClient()
    try:
        result = await client.make_request("GET", "jobs")
        assert route.call_count == 3, "should have retried twice before succeeding"
        assert result == {"items": [{"id": "j-1"}]}
    finally:
        await client.close()


@respx.mock
async def test_client_does_not_retry_on_4xx():
    """4xx responses should fail fast — no retries."""
    route = respx.get("https://dct.test/dct/v3/jobs/bad").mock(
        return_value=httpx.Response(404, json={"error": "not found"})
    )

    client = DCTAPIClient()
    try:
        with pytest.raises(DCTClientError):
            await client.make_request("GET", "jobs/bad")
        assert route.call_count == 1, "4xx must not be retried"
    finally:
        await client.close()


@respx.mock
async def test_client_sends_apk_prefixed_auth_header():
    """Authorization header must be exactly 'apk <key>' — the client adds the prefix."""
    route = respx.get("https://dct.test/dct/v3/jobs").mock(
        return_value=httpx.Response(200, json={"items": []})
    )

    client = DCTAPIClient()
    try:
        await client.make_request("GET", "jobs")
        sent = route.calls.last.request
        assert sent.headers["authorization"] == "apk test-api-key"
    finally:
        await client.close()
