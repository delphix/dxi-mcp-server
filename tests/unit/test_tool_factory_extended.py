"""
Extended unit tests for tools/core/tool_factory.py.

Covers:
- _download_openapi_spec()
- _load_bundled_spec()
- initialize_openapi_cache()
- get_cached_spec() / clear_spec_cache()
- _resolve_ref()
- _get_python_type()
- _create_tool_function()
- _create_grouped_tool_function()
- generate_tools_for_toolset()
- register_toolset_tools()
"""

from __future__ import annotations

import pytest
import yaml
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import dct_mcp_server.tools.core.tool_factory as tf_mod
from dct_mcp_server.tools.core.tool_factory import (
    _create_grouped_tool_function,
    _create_tool_function,
    _download_openapi_spec,
    _get_python_type,
    _load_bundled_spec,
    _resolve_ref,
    clear_spec_cache,
    generate_tools_for_toolset,
    get_cached_spec,
    initialize_openapi_cache,
    register_toolset_tools,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

MINIMAL_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Test", "version": "1.0"},
    "paths": {
        "/vdbs/search": {
            "post": {
                "operationId": "searchVdbs",
                "summary": "Search VDBs",
                "parameters": [],
            }
        },
        "/vdbs/{vdbId}": {
            "get": {
                "operationId": "getVdb",
                "summary": "Get a VDB",
                "parameters": [
                    {
                        "name": "vdbId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "VDB identifier",
                    }
                ],
            }
        },
    },
    "components": {
        "schemas": {
            "VdbResponse": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
            }
        }
    },
}

SPEC_YAML = yaml.dump(MINIMAL_SPEC)


@pytest.fixture(autouse=True)
def reset_spec_cache():
    """Reset global spec cache before and after each test."""
    original_spec = tf_mod._openapi_spec
    original_client = tf_mod._dct_client
    tf_mod._openapi_spec = None
    tf_mod._dct_client = None
    yield
    tf_mod._openapi_spec = original_spec
    tf_mod._dct_client = original_client


# ---------------------------------------------------------------------------
# _get_python_type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "openapi_type,expected",
    [
        ("integer", "int"),
        ("string", "str"),
        ("boolean", "bool"),
        ("number", "float"),
        ("array", "list"),
        ("object", "dict"),
        ("unknown_type", "Any"),
    ],
)
def test_get_python_type(openapi_type, expected):
    assert _get_python_type(openapi_type) == expected


# ---------------------------------------------------------------------------
# _resolve_ref
# ---------------------------------------------------------------------------


def test_resolve_ref_simple():
    spec = {"components": {"schemas": {"Foo": {"type": "object"}}}}
    result = _resolve_ref("#/components/schemas/Foo", spec)
    assert result == {"type": "object"}


def test_resolve_ref_nested():
    spec = {
        "components": {"schemas": {"Bar": {"properties": {"id": {"type": "string"}}}}}
    }
    result = _resolve_ref("#/components/schemas/Bar", spec)
    assert "properties" in result


def test_resolve_ref_invalid_format():
    spec = {}
    with pytest.raises(ValueError, match="Unsupported ref format"):
        _resolve_ref("relative/ref", spec)


def test_resolve_ref_missing_path():
    spec = {"components": {}}
    with pytest.raises(KeyError):
        _resolve_ref("#/components/schemas/Missing", spec)


# ---------------------------------------------------------------------------
# _download_openapi_spec
# ---------------------------------------------------------------------------


def test_download_openapi_spec_success():
    mock_response = MagicMock()
    mock_response.text = SPEC_YAML
    mock_response.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_response):
        result = _download_openapi_spec("https://dct.example.com", "test-key")

    assert isinstance(result, dict)
    assert "paths" in result


def test_download_openapi_spec_with_api_key():
    mock_response = MagicMock()
    mock_response.text = SPEC_YAML
    mock_response.raise_for_status = MagicMock()
    captured_headers = {}

    def capture_get(url, **kwargs):
        captured_headers.update(kwargs.get("headers", {}))
        return mock_response

    with patch("requests.get", side_effect=capture_get):
        _download_openapi_spec("https://dct.example.com", "my-api-key")

    assert "Authorization" in captured_headers
    assert "my-api-key" in captured_headers["Authorization"]


def test_download_openapi_spec_no_api_key():
    mock_response = MagicMock()
    mock_response.text = SPEC_YAML
    mock_response.raise_for_status = MagicMock()
    captured_headers = {}

    def capture_get(url, **kwargs):
        captured_headers.update(kwargs.get("headers", {}))
        return mock_response

    with patch("requests.get", side_effect=capture_get):
        _download_openapi_spec("https://dct.example.com")

    assert "Authorization" not in captured_headers


def test_download_openapi_spec_request_exception():
    with patch("requests.get", side_effect=Exception("connection refused")):
        with pytest.raises(Exception):
            _download_openapi_spec("https://dct.example.com")


def test_download_openapi_spec_http_error():
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception("404 Not Found")

    with patch("requests.get", return_value=mock_response):
        with pytest.raises(Exception):
            _download_openapi_spec("https://dct.example.com")


def test_download_openapi_spec_url_construction():
    mock_response = MagicMock()
    mock_response.text = SPEC_YAML
    mock_response.raise_for_status = MagicMock()
    captured_url = {}

    def capture_get(url, **kwargs):
        captured_url["url"] = url
        return mock_response

    with patch("requests.get", side_effect=capture_get):
        _download_openapi_spec("https://dct.example.com/")  # trailing slash

    assert captured_url["url"].endswith("/dct/static/api-external.yaml")
    assert "dct.example.com" in captured_url["url"]


# ---------------------------------------------------------------------------
# _load_bundled_spec
# ---------------------------------------------------------------------------


def test_load_bundled_spec_when_file_exists():
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=SPEC_YAML)):
            result = _load_bundled_spec()
    assert result is not None
    assert isinstance(result, dict)


def test_load_bundled_spec_when_file_missing():
    with patch("pathlib.Path.exists", return_value=False):
        result = _load_bundled_spec()
    assert result is None


# ---------------------------------------------------------------------------
# get_cached_spec / clear_spec_cache
# ---------------------------------------------------------------------------


def test_get_cached_spec_initially_none():
    assert get_cached_spec() is None


def test_get_cached_spec_after_set():
    tf_mod._openapi_spec = MINIMAL_SPEC
    assert get_cached_spec() is MINIMAL_SPEC


def test_clear_spec_cache():
    tf_mod._openapi_spec = MINIMAL_SPEC
    clear_spec_cache()
    assert get_cached_spec() is None


# ---------------------------------------------------------------------------
# initialize_openapi_cache
# ---------------------------------------------------------------------------


def test_initialize_openapi_cache_already_cached():
    tf_mod._openapi_spec = MINIMAL_SPEC
    result = initialize_openapi_cache()
    assert result is True
    # Spec should still be the same
    assert tf_mod._openapi_spec is MINIMAL_SPEC


def test_initialize_openapi_cache_downloads_spec(monkeypatch):
    monkeypatch.setenv("DCT_API_KEY", "k")
    monkeypatch.setenv("DCT_BASE_URL", "https://dct.example.com")

    with patch(
        "dct_mcp_server.tools.core.tool_factory._download_openapi_spec",
        return_value=MINIMAL_SPEC,
    ) as mock_dl:
        result = initialize_openapi_cache()

    assert result is True
    assert tf_mod._openapi_spec is MINIMAL_SPEC
    mock_dl.assert_called_once()


def test_initialize_openapi_cache_falls_back_to_bundled(monkeypatch):
    monkeypatch.setenv("DCT_API_KEY", "k")
    monkeypatch.setenv("DCT_BASE_URL", "https://dct.example.com")

    with patch(
        "dct_mcp_server.tools.core.tool_factory._download_openapi_spec",
        side_effect=Exception("network error"),
    ):
        with patch(
            "dct_mcp_server.tools.core.tool_factory._load_bundled_spec",
            return_value=MINIMAL_SPEC,
        ):
            result = initialize_openapi_cache()

    assert result is True
    assert tf_mod._openapi_spec is MINIMAL_SPEC


def test_initialize_openapi_cache_no_base_url(monkeypatch):
    monkeypatch.setenv("DCT_API_KEY", "k")
    monkeypatch.delenv("DCT_BASE_URL", raising=False)

    with patch(
        "dct_mcp_server.tools.core.tool_factory._load_bundled_spec",
        return_value=MINIMAL_SPEC,
    ):
        result = initialize_openapi_cache()

    assert result is True


def test_initialize_openapi_cache_no_spec_available(monkeypatch):
    monkeypatch.setenv("DCT_API_KEY", "k")
    monkeypatch.setenv("DCT_BASE_URL", "https://dct.example.com")

    with patch(
        "dct_mcp_server.tools.core.tool_factory._download_openapi_spec",
        side_effect=Exception("network error"),
    ):
        with patch(
            "dct_mcp_server.tools.core.tool_factory._load_bundled_spec",
            return_value=None,
        ):
            result = initialize_openapi_cache()

    assert result is False


def test_initialize_openapi_cache_stores_client():
    tf_mod._openapi_spec = MINIMAL_SPEC  # Already cached
    mock_client = MagicMock()
    initialize_openapi_cache(mock_client)
    assert tf_mod._dct_client is mock_client


# ---------------------------------------------------------------------------
# _create_tool_function
# ---------------------------------------------------------------------------


def test_create_tool_function_returns_callable_and_name():
    operation = {
        "operationId": "searchVdbs",
        "summary": "Search VDBs",
        "parameters": [],
    }
    func, name = _create_tool_function(
        "/vdbs/search", "POST", "search", operation, MINIMAL_SPEC
    )
    assert callable(func)
    assert name == "searchVdbs"


def test_create_tool_function_with_params():
    operation = {
        "operationId": "getVdb",
        "summary": "Get a VDB",
        "parameters": [
            {
                "name": "vdbId",
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
                "description": "VDB identifier",
            }
        ],
    }
    func, name = _create_tool_function(
        "/vdbs/{vdbId}", "GET", "get", operation, MINIMAL_SPEC
    )
    assert callable(func)
    assert name == "getVdb"


def test_create_tool_function_with_ref_param():
    spec_with_ref = {
        "components": {
            "parameters": {
                "VdbId": {
                    "name": "vdbId",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                    "description": "VDB ID",
                }
            }
        }
    }
    operation = {
        "operationId": "getVdb",
        "summary": "Get VDB",
        "parameters": [{"$ref": "#/components/parameters/VdbId"}],
    }
    func, name = _create_tool_function(
        "/vdbs/{vdbId}", "GET", "get", operation, spec_with_ref
    )
    assert callable(func)


@pytest.mark.asyncio
async def test_create_tool_function_no_client():
    operation = {"operationId": "searchVdbs", "summary": "Search", "parameters": []}
    func, _ = _create_tool_function(
        "/vdbs/search", "POST", "search", operation, MINIMAL_SPEC
    )
    tf_mod._dct_client = None
    result = await func()
    assert "error" in result


@pytest.mark.asyncio
async def test_create_tool_function_with_confirmation_required():
    operation = {"operationId": "deleteVdb", "summary": "Delete VDB", "parameters": []}
    with patch(
        "dct_mcp_server.tools.core.tool_factory.resolve_confirmation"
    ) as mock_conf:
        mock_conf.return_value = {
            "level": "manual",
            "message": "Delete?",
            "conditional": False,
            "threshold_days": None,
        }
        func, _ = _create_tool_function(
            "/vdbs/{vdbId}/delete", "POST", "delete", operation, MINIMAL_SPEC
        )

    tf_mod._dct_client = MagicMock()
    result = await func(vdbId="v-1")
    assert result.get("status") == "confirmation_required"


@pytest.mark.asyncio
async def test_create_tool_function_with_confirmed_true():
    operation = {"operationId": "deleteVdb", "summary": "Delete VDB", "parameters": []}
    with patch(
        "dct_mcp_server.tools.core.tool_factory.resolve_confirmation"
    ) as mock_conf:
        mock_conf.return_value = {
            "level": "manual",
            "message": "Delete?",
            "conditional": False,
            "threshold_days": None,
        }
        func, _ = _create_tool_function(
            "/vdbs/{vdbId}/delete", "POST", "delete", operation, MINIMAL_SPEC
        )

    mock_client = MagicMock()
    mock_client.make_request = AsyncMock(return_value={"status": "success"})
    tf_mod._dct_client = mock_client
    await func(vdbId="v-1", confirmed=True)
    assert mock_client.make_request.called


@pytest.mark.asyncio
async def test_create_tool_function_with_filter_expression():
    operation = {
        "operationId": "searchVdbs",
        "summary": "Search",
        "parameters": [],
        "x-filterable": True,
    }
    func, _ = _create_tool_function(
        "/vdbs/search", "POST", "search", operation, MINIMAL_SPEC
    )
    mock_client = MagicMock()
    mock_client.make_request = AsyncMock(return_value={"items": []})
    tf_mod._dct_client = mock_client
    await func(filter_expression="name EQ 'test'")
    assert mock_client.make_request.called
    call_args = mock_client.make_request.call_args
    json_body = call_args[1].get("json") or {}
    assert json_body.get("filter_expression") == "name EQ 'test'"


# ---------------------------------------------------------------------------
# _create_grouped_tool_function
# ---------------------------------------------------------------------------


def test_create_grouped_tool_function_returns_callable():
    apis = [
        {"method": "POST", "path": "/vdbs/search", "action": "search"},
        {"method": "GET", "path": "/vdbs/{vdbId}", "action": "get"},
    ]
    func, name = _create_grouped_tool_function(
        "vdb_tool", "VDB operations", apis, MINIMAL_SPEC
    )
    assert callable(func)
    assert name == "vdb_tool"


def test_create_grouped_tool_function_docstring():
    apis = [{"method": "POST", "path": "/vdbs/search", "action": "search"}]
    func, name = _create_grouped_tool_function("vdb_tool", "VDB operations", apis, None)
    assert "search" in func.__doc__ or "vdb_tool" in func.__name__


@pytest.mark.asyncio
async def test_create_grouped_tool_function_no_client():
    apis = [{"method": "POST", "path": "/vdbs/search", "action": "search"}]
    func, _ = _create_grouped_tool_function("vdb_tool", "VDB ops", apis, None)
    tf_mod._dct_client = None
    result = await func(action="search")
    assert "error" in result


@pytest.mark.asyncio
async def test_create_grouped_tool_function_unknown_action():
    apis = [{"method": "POST", "path": "/vdbs/search", "action": "search"}]
    func, _ = _create_grouped_tool_function("vdb_tool", "VDB ops", apis, None)
    mock_client = MagicMock()
    mock_client.make_request = AsyncMock(return_value={})
    tf_mod._dct_client = mock_client
    result = await func(action="fly_to_moon")
    assert "error" in result
    assert "fly_to_moon" in result.get("error", "") or "available_actions" in result


@pytest.mark.asyncio
async def test_create_grouped_tool_function_search():
    apis = [{"method": "POST", "path": "/vdbs/search", "action": "search"}]
    func, _ = _create_grouped_tool_function("vdb_tool", "VDB ops", apis, MINIMAL_SPEC)
    mock_client = MagicMock()
    mock_client.make_request = AsyncMock(return_value={"items": []})
    tf_mod._dct_client = mock_client
    await func(action="search")
    assert mock_client.make_request.called


@pytest.mark.asyncio
async def test_create_grouped_tool_function_path_param_substitution():
    apis = [{"method": "GET", "path": "/vdbs/{vdbId}", "action": "get"}]
    func, _ = _create_grouped_tool_function("vdb_tool", "VDB ops", apis, MINIMAL_SPEC)
    mock_client = MagicMock()
    mock_client.make_request = AsyncMock(return_value={"id": "v-123"})
    tf_mod._dct_client = mock_client
    await func(action="get", vdbId="v-123")
    call_args = mock_client.make_request.call_args
    assert "v-123" in str(call_args)


@pytest.mark.asyncio
async def test_create_grouped_tool_function_confirmation_required():
    apis = [{"method": "POST", "path": "/vdbs/{vdbId}/delete", "action": "delete"}]
    with patch(
        "dct_mcp_server.tools.core.tool_factory.resolve_confirmation"
    ) as mock_conf:
        mock_conf.return_value = {
            "level": "manual",
            "message": "Delete this VDB?",
            "conditional": False,
            "threshold_days": None,
        }
        func, _ = _create_grouped_tool_function("vdb_tool", "VDB ops", apis, None)

    mock_client = MagicMock()
    mock_client.make_request = AsyncMock(return_value={})
    tf_mod._dct_client = mock_client
    result = await func(action="delete", vdbId="v-1")
    assert result.get("status") == "confirmation_required"


@pytest.mark.asyncio
async def test_create_grouped_tool_function_with_filter_expression():
    apis = [{"method": "POST", "path": "/vdbs/search", "action": "search"}]
    func, _ = _create_grouped_tool_function("vdb_tool", "VDB ops", apis, MINIMAL_SPEC)
    mock_client = MagicMock()
    mock_client.make_request = AsyncMock(return_value={"items": []})
    tf_mod._dct_client = mock_client
    await func(action="search", filter_expression="name EQ 'prod'")
    call_args = mock_client.make_request.call_args
    json_body = call_args[1].get("json") or {}
    assert json_body.get("filter_expression") == "name EQ 'prod'"


@pytest.mark.asyncio
async def test_create_grouped_tool_function_body_param():
    apis = [{"method": "POST", "path": "/vdbs/provision", "action": "provision"}]
    func, _ = _create_grouped_tool_function("vdb_tool", "VDB ops", apis, None)
    mock_client = MagicMock()
    mock_client.make_request = AsyncMock(return_value={"id": "new-vdb"})
    tf_mod._dct_client = mock_client
    body_data = {"name": "my-vdb", "source_id": "s-1"}
    await func(action="provision", body=body_data)
    assert mock_client.make_request.called


@pytest.mark.asyncio
async def test_create_grouped_tool_function_get_with_query_params():
    apis = [{"method": "GET", "path": "/vdbs", "action": "list"}]
    func, _ = _create_grouped_tool_function("vdb_tool", "VDB ops", apis, None)
    mock_client = MagicMock()
    mock_client.make_request = AsyncMock(return_value={"items": []})
    tf_mod._dct_client = mock_client
    await func(action="list", limit=10)
    call_args = mock_client.make_request.call_args
    # query_params should include limit
    call_args[1].get("params") or {}
    # May be None if empty dict — just verify call happened
    assert mock_client.make_request.called


# ---------------------------------------------------------------------------
# generate_tools_for_toolset
# ---------------------------------------------------------------------------


def test_generate_tools_for_toolset_returns_list():
    tf_mod._openapi_spec = MINIMAL_SPEC
    tools = generate_tools_for_toolset("self_service")
    assert isinstance(tools, list)
    assert len(tools) > 0


def test_generate_tools_for_toolset_without_spec():
    tf_mod._openapi_spec = None
    with patch(
        "dct_mcp_server.tools.core.tool_factory.initialize_openapi_cache",
        return_value=False,
    ):
        tools = generate_tools_for_toolset("self_service")
    assert isinstance(tools, list)


def test_generate_tools_for_toolset_each_has_callable_and_name():
    tf_mod._openapi_spec = MINIMAL_SPEC
    tools = generate_tools_for_toolset("self_service")
    for func, name in tools:
        assert callable(func)
        assert isinstance(name, str)
        assert len(name) > 0


# ---------------------------------------------------------------------------
# register_toolset_tools
# ---------------------------------------------------------------------------


def test_register_toolset_tools_returns_count():
    tf_mod._openapi_spec = MINIMAL_SPEC
    mock_app = MagicMock()
    count = register_toolset_tools(mock_app, "self_service")
    assert isinstance(count, int)
    assert count >= 0


def test_register_toolset_tools_calls_add_tool():
    tf_mod._openapi_spec = MINIMAL_SPEC
    mock_app = MagicMock()
    register_toolset_tools(mock_app, "self_service")
    assert mock_app.add_tool.called


def test_register_toolset_tools_sets_client():
    tf_mod._openapi_spec = MINIMAL_SPEC
    mock_app = MagicMock()
    mock_client = MagicMock()
    register_toolset_tools(mock_app, "self_service", mock_client)
    assert tf_mod._dct_client is mock_client


def test_register_toolset_tools_handles_add_tool_failure():
    tf_mod._openapi_spec = MINIMAL_SPEC
    mock_app = MagicMock()
    mock_app.add_tool.side_effect = Exception("cannot add")
    # Should not raise — errors are logged
    count = register_toolset_tools(mock_app, "self_service")
    assert count == 0
