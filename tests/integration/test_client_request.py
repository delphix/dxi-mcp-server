"""
Layer 2 — DCTAPIClient request construction & response parsing (respx).

Covers what unit tests (which mock make_request) cannot see: URL building with the
/dct/v3 prefix, the `apk ` auth header and default headers, body/param passthrough,
HTTP method handling, and JSON vs non-JSON response parsing.
"""

import httpx
import pytest
import respx

from dct_mcp_server.dct_client.client import DCTAPIClient

BASE = "https://dct.test/dct/v3"


# --- URL building -----------------------------------------------------------

@respx.mock
@pytest.mark.parametrize("endpoint", ["/vdbs/search", "vdbs/search"])
async def test_url_built_with_dct_v3_prefix_regardless_of_leading_slash(client, endpoint):
    route = respx.post(f"{BASE}/vdbs/search").mock(return_value=httpx.Response(200, json={}))
    await client.make_request("POST", endpoint)
    assert route.called
    assert str(route.calls.last.request.url) == f"{BASE}/vdbs/search"


@respx.mock
async def test_url_handles_nested_path(client):
    route = respx.post(f"{BASE}/vdbs/v-1/start").mock(return_value=httpx.Response(200, json={}))
    await client.make_request("POST", "/vdbs/v-1/start")
    assert str(route.calls.last.request.url) == f"{BASE}/vdbs/v-1/start"


@respx.mock
async def test_no_double_slash_when_base_url_has_trailing_slash(monkeypatch):
    """base_url is rstrip('/')-ed in the constructor — a trailing slash must not double up."""
    monkeypatch.setenv("DCT_BASE_URL", "https://dct.test/")
    route = respx.get(f"{BASE}/jobs").mock(return_value=httpx.Response(200, json={}))
    c = DCTAPIClient()
    try:
        await c.make_request("GET", "/jobs")
        assert str(route.calls.last.request.url) == f"{BASE}/jobs"
    finally:
        await c.close()


# --- Headers ----------------------------------------------------------------

@respx.mock
async def test_sends_apk_prefixed_auth_header(client):
    route = respx.get(f"{BASE}/jobs").mock(return_value=httpx.Response(200, json={}))
    await client.make_request("GET", "jobs")
    assert route.calls.last.request.headers["authorization"] == "apk test-api-key"


@respx.mock
async def test_default_headers_present(client):
    route = respx.get(f"{BASE}/jobs").mock(return_value=httpx.Response(200, json={}))
    await client.make_request("GET", "jobs")
    h = route.calls.last.request.headers
    assert h["content-type"] == "application/json"
    assert h["accept"] == "application/json"
    assert h["user-agent"].startswith("dct-mcp-server/")


# --- Body & params passthrough ---------------------------------------------

@respx.mock
async def test_json_body_passthrough(client):
    route = respx.post(f"{BASE}/vdbs/search").mock(return_value=httpx.Response(200, json={}))
    await client.make_request("POST", "vdbs/search", json={"filter_expression": "name CONTAINS 'x'"})
    import json as _json
    assert _json.loads(route.calls.last.request.content) == {"filter_expression": "name CONTAINS 'x'"}


@respx.mock
async def test_query_params_passthrough(client):
    route = respx.get(f"{BASE}/jobs").mock(return_value=httpx.Response(200, json={}))
    await client.make_request("GET", "jobs", params={"limit": 10, "sort": "-start_time"})
    sent = route.calls.last.request.url
    assert sent.params["limit"] == "10"
    assert sent.params["sort"] == "-start_time"


@respx.mock
async def test_json_used_over_data_when_both_given(client):
    route = respx.post(f"{BASE}/jobs").mock(return_value=httpx.Response(200, json={}))
    await client.make_request("POST", "jobs", data={"from": "data"}, json={"from": "json"})
    import json as _json
    assert _json.loads(route.calls.last.request.content) == {"from": "json"}


# --- HTTP methods -----------------------------------------------------------

@respx.mock
@pytest.mark.parametrize("method", ["GET", "POST", "DELETE", "PATCH"])
async def test_methods_route_through(client, method):
    route = respx.route(method=method, url=f"{BASE}/thing").mock(return_value=httpx.Response(200, json={}))
    await client.make_request(method, "thing")
    assert route.called
    assert route.calls.last.request.method == method


# --- Response parsing -------------------------------------------------------

@respx.mock
async def test_json_response_parsed(client):
    respx.get(f"{BASE}/jobs").mock(
        return_value=httpx.Response(200, json={"items": [{"id": "j-1"}]})
    )
    result = await client.make_request("GET", "jobs")
    assert result == {"items": [{"id": "j-1"}]}


@respx.mock
async def test_non_json_response_wrapped(client):
    respx.get(f"{BASE}/raw").mock(
        return_value=httpx.Response(200, text="plain text", headers={"content-type": "text/plain"})
    )
    result = await client.make_request("GET", "raw")
    assert result == {"response": "plain text"}
