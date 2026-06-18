"""
Async unit tests for DCTAPIClient retry and backoff behaviour (DLPXECO-14014).

All httpx I/O is mocked via ``unittest.mock.AsyncMock`` patched onto
``httpx.AsyncClient.request`` — no real network calls are made.  The conftest.py
session fixture sets ``DCT_API_KEY=test-key`` and ``DCT_BASE_URL=http://localhost:9999``
so that ``DCTAPIClient.__init__`` → ``get_dct_config()`` completes without raising.

``asyncio.sleep`` is patched to a no-op AsyncMock in all retry tests so the suite
runs in well under 5 seconds even with multiple retry attempts.

All functions in this module were AI-generated.  Each test carries an
``# AI-generated`` comment on the first line of its body.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from dct_mcp_server.core.exceptions import DCTClientError
from dct_mcp_server.dct_client.client import DCTAPIClient


def _make_response(
    status_code: int,
    json_body=None,
    text_body: str = "",
    content_type: str = "application/json",
):
    """Build a minimal mock httpx.Response for use in request mocks."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.headers = {"content-type": content_type}
    if json_body is not None:
        response.json.return_value = json_body
    response.text = text_body

    if status_code >= 400:
        # raise_for_status() should raise HTTPStatusError
        http_error = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=response,
        )
        response.raise_for_status.side_effect = http_error
    else:
        response.raise_for_status.return_value = None

    return response


# ---------------------------------------------------------------------------
# Success cases
# ---------------------------------------------------------------------------


async def test_make_request_success_returns_json():
    # AI-generated
    expected = {"id": "vdb-1", "name": "test-vdb"}
    mock_response = _make_response(200, json_body=expected)

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        client = DCTAPIClient()
        result = await client.make_request("GET", "/vdbs/vdb-1")

    assert result == expected


async def test_make_request_non_json_response_returns_response_key():
    # AI-generated — non-JSON content type should return {"response": <text>}
    mock_response = _make_response(
        200, text_body="plain text content", content_type="text/plain"
    )

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        client = DCTAPIClient()
        result = await client.make_request("GET", "/some/endpoint")

    assert result == {"response": "plain text content"}


# ---------------------------------------------------------------------------
# 4xx — no retry
# ---------------------------------------------------------------------------


async def test_make_request_4xx_raises_immediately_no_retry():
    # AI-generated — 4xx errors should raise DCTClientError after exactly 1 attempt
    mock_response = _make_response(404, text_body="Not Found")

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        client = DCTAPIClient()
        client.max_retries = 3  # set retries high to prove only 1 call is made

        with pytest.raises(DCTClientError):
            await client.make_request("GET", "/vdbs/nonexistent")

    assert mock_request.call_count == 1, (
        f"Expected exactly 1 attempt for 4xx, got {mock_request.call_count}"
    )


# ---------------------------------------------------------------------------
# 5xx — retry up to max_retries
# ---------------------------------------------------------------------------


async def test_make_request_5xx_retries_up_to_max():
    # AI-generated — 5xx should retry up to max_retries and then raise DCTClientError
    mock_response = _make_response(503, text_body="Service Unavailable")

    with (
        patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_request.return_value = mock_response
        client = DCTAPIClient()
        client.max_retries = 3

        with pytest.raises(DCTClientError):
            await client.make_request("POST", "/vdbs/search")

    assert mock_request.call_count == 3, (
        f"Expected exactly 3 attempts with max_retries=3, got {mock_request.call_count}"
    )


async def test_make_request_5xx_succeeds_on_second_attempt():
    # AI-generated — 503 on attempt 1, 200 on attempt 2 → success; mock called twice
    fail_response = _make_response(503, text_body="Service Unavailable")
    ok_response = _make_response(200, json_body={"status": "ok"})

    with (
        patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_request.side_effect = [fail_response, ok_response]
        client = DCTAPIClient()
        client.max_retries = 3

        result = await client.make_request("GET", "/vdbs/vdb-1")

    assert result == {"status": "ok"}
    assert mock_request.call_count == 2, (
        f"Expected exactly 2 attempts (fail then succeed), got {mock_request.call_count}"
    )


# ---------------------------------------------------------------------------
# Exponential backoff
# ---------------------------------------------------------------------------


async def test_make_request_exponential_backoff_called():
    # AI-generated — asyncio.sleep should be called with 2**0=1 and 2**1=2 for retries
    mock_response = _make_response(503, text_body="Service Unavailable")

    with (
        patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request,
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        mock_request.return_value = mock_response
        client = DCTAPIClient()
        client.max_retries = 3

        with pytest.raises(DCTClientError):
            await client.make_request("GET", "/vdbs/vdb-1")

    sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
    assert 2**0 in sleep_calls, f"Expected sleep(1) in calls, got: {sleep_calls}"
    assert 2**1 in sleep_calls, f"Expected sleep(2) in calls, got: {sleep_calls}"


async def test_make_request_single_retry_no_sleep():
    # AI-generated  (EC-7: max_retries=1 — single attempt, no sleep called)
    mock_response = _make_response(503, text_body="Service Unavailable")

    with (
        patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request,
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        mock_request.return_value = mock_response
        client = DCTAPIClient()
        client.max_retries = 1

        with pytest.raises(DCTClientError):
            await client.make_request("GET", "/vdbs/vdb-1")

    assert mock_request.call_count == 1
    assert mock_sleep.call_count == 0, (
        "asyncio.sleep should not be called when max_retries=1 (no retry gap needed)"
    )


# ---------------------------------------------------------------------------
# Connection errors
# ---------------------------------------------------------------------------


async def test_make_request_connection_error_retries():
    # AI-generated — httpx.ConnectError should trigger retries and ultimately raise DCTClientError
    with (
        patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_request.side_effect = httpx.ConnectError("Connection refused")
        client = DCTAPIClient()
        client.max_retries = 3

        with pytest.raises(DCTClientError):
            await client.make_request("GET", "/vdbs/vdb-1")

    assert mock_request.call_count == 3


# ---------------------------------------------------------------------------
# Authorization header
# ---------------------------------------------------------------------------


def test_authorization_header_prepends_apk():
    # AI-generated — DCTAPIClient must prepend "apk " to the API key automatically
    client = DCTAPIClient()
    auth_header = client.headers.get("Authorization", "")
    assert auth_header.startswith("apk "), (
        f"Expected Authorization header to start with 'apk ', got: {auth_header!r}"
    )
    # The raw key value (without "apk " prefix) should follow
    assert "test-key" in auth_header, (
        f"Expected 'test-key' in Authorization header, got: {auth_header!r}"
    )
