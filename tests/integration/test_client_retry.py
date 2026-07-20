"""
Layer 2 — DCTAPIClient retry / backoff / error-mapping (respx).

DCT_MAX_RETRIES is 3 in the test env. Backoff sleeps are patched to instant by the
`no_backoff` autouse fixture, so these run fast while still exercising the real loop.
"""

import httpx
import pytest
import respx

from dct_mcp_server.core.exceptions import DCTClientError

BASE = "https://dct.test/dct/v3"


@respx.mock
async def test_retries_on_5xx_then_succeeds(client, no_backoff):
    route = respx.get(f"{BASE}/jobs").mock(
        side_effect=[
            httpx.Response(503, json={"error": "unavailable"}),
            httpx.Response(503, json={"error": "unavailable"}),
            httpx.Response(200, json={"items": [{"id": "j-1"}]}),
        ]
    )
    result = await client.make_request("GET", "jobs")
    assert result == {"items": [{"id": "j-1"}]}
    assert route.call_count == 3
    assert no_backoff.await_count == 2  # slept between the two failures


@respx.mock
async def test_all_5xx_raises_after_max_retries(client, no_backoff):
    route = respx.get(f"{BASE}/jobs").mock(
        return_value=httpx.Response(503, json={"e": 1})
    )
    with pytest.raises(DCTClientError):
        await client.make_request("GET", "jobs")
    assert route.call_count == 3  # DCT_MAX_RETRIES
    assert no_backoff.await_count == 2  # max_retries - 1 backoffs


@respx.mock
@pytest.mark.parametrize("code", [500, 502, 503])
async def test_5xx_codes_are_retried(client, code):
    route = respx.get(f"{BASE}/jobs").mock(
        side_effect=[
            httpx.Response(code, json={}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    result = await client.make_request("GET", "jobs")
    assert result == {"ok": True}
    assert route.call_count == 2


@respx.mock
@pytest.mark.parametrize("code", [400, 401, 403, 404, 409, 422])
async def test_4xx_fails_fast_without_retry(client, no_backoff, code):
    route = respx.get(f"{BASE}/jobs/bad").mock(
        return_value=httpx.Response(code, json={"e": "x"})
    )
    with pytest.raises(DCTClientError):
        await client.make_request("GET", "jobs/bad")
    assert route.call_count == 1  # 4xx must not retry
    assert no_backoff.await_count == 0


@respx.mock
async def test_connection_error_is_retried_then_raises(client, no_backoff):
    route = respx.get(f"{BASE}/jobs").mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(DCTClientError):
        await client.make_request("GET", "jobs")
    assert route.call_count == 3  # transport errors are retried up to max_retries
    assert no_backoff.await_count == 2


@respx.mock
async def test_connection_error_then_success(client):
    route = respx.get(f"{BASE}/jobs").mock(
        side_effect=[httpx.ConnectError("boom"), httpx.Response(200, json={"ok": True})]
    )
    result = await client.make_request("GET", "jobs")
    assert result == {"ok": True}
    assert route.call_count == 2


@respx.mock
async def test_error_message_carries_status_and_body(client):
    respx.get(f"{BASE}/jobs/bad").mock(
        return_value=httpx.Response(404, text="not found here")
    )
    with pytest.raises(DCTClientError) as exc:
        await client.make_request("GET", "jobs/bad")
    msg = str(exc.value)
    assert "404" in msg and "not found here" in msg
