"""
Unit tests for dct_mcp_server.tools.core.dynamic.

Tests the discovery (sync) and execute (async) tool factory functions:
  _make_discovery_fn → discovery closure
  _make_execute_fn   → execute closure (async)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dct_mcp_server.tools.core.dynamic import _make_discovery_fn, _make_execute_fn

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_VALID_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "DCT", "version": "1"},
    "paths": {
        "/vdbs": {
            "get": {
                "operationId": "listVdbs",
                "summary": "List VDBs",
                "tags": ["VDBs"],
            }
        },
        "/vdbs/{vdbId}": {
            "get": {
                "operationId": "getVdb",
                "summary": "Get a VDB",
                "tags": ["VDBs"],
            },
            "delete": {
                "operationId": "deleteVdb",
                "summary": "Delete a VDB",
                "tags": ["VDBs"],
            },
        },
        "/vdbs/search": {
            "post": {
                "operationId": "searchVdbs",
                "summary": "Search VDBs",
                "tags": ["VDBs"],
            }
        },
        "/environments": {
            "get": {
                "operationId": "listEnvironments",
                "summary": "List environments",
                "tags": ["Environments"],
            }
        },
    },
}


def _make_app_mock():
    return MagicMock()


def _make_client_mock(return_value=None):
    client = MagicMock()
    client.make_request = AsyncMock(return_value=return_value or {"items": []})
    return client


@pytest.fixture
def discovery_spec_loaded():
    """Return a discovery function backed by _VALID_SPEC."""
    app = _make_app_mock()
    fn = _make_discovery_fn(app)
    with patch(
        "dct_mcp_server.tools.core.dynamic.get_cached_spec",
        return_value=_VALID_SPEC,
    ):
        yield fn


@pytest.fixture
def discovery_no_spec():
    """Return a discovery function backed by no spec (None)."""
    app = _make_app_mock()
    fn = _make_discovery_fn(app)
    with patch(
        "dct_mcp_server.tools.core.dynamic.get_cached_spec",
        return_value=None,
    ):
        yield fn


# =========================================================================== #
# discovery — spec not loaded
# =========================================================================== #


def test_discovery_spec_not_loaded_returns_error(discovery_no_spec):
    result = discovery_no_spec(action="list_tags")
    assert result["status"] == "error"
    assert result["code"] == "SPEC_NOT_LOADED"


# =========================================================================== #
# discovery — list_tags
# =========================================================================== #


def test_discovery_list_tags_returns_tags_key(discovery_spec_loaded):
    result = discovery_spec_loaded(action="list_tags")
    assert "tags" in result
    assert isinstance(result["tags"], list)


def test_discovery_list_tags_includes_vdbs(discovery_spec_loaded):
    result = discovery_spec_loaded(action="list_tags")
    tag_names = [t["name"] for t in result["tags"]]
    assert "VDBs" in tag_names


def test_discovery_list_tags_operation_count(discovery_spec_loaded):
    result = discovery_spec_loaded(action="list_tags")
    vdbs_entry = next(t for t in result["tags"] if t["name"] == "VDBs")
    # 4 operations tagged VDBs in _VALID_SPEC
    assert vdbs_entry["operation_count"] == 4


# =========================================================================== #
# discovery — list_operations
# =========================================================================== #


def test_discovery_list_operations_returns_operations_key(discovery_spec_loaded):
    result = discovery_spec_loaded(action="list_operations")
    assert "operations" in result
    assert "total_count" in result


def test_discovery_list_operations_total_count(discovery_spec_loaded):
    result = discovery_spec_loaded(action="list_operations")
    assert result["total_count"] == 5  # 5 operations in _VALID_SPEC


def test_discovery_list_operations_tag_filter(discovery_spec_loaded):
    result = discovery_spec_loaded(action="list_operations", tag="Environments")
    assert result["total_count"] == 1
    assert result["operations"][0]["path"] == "/environments"


def test_discovery_list_operations_method_filter(discovery_spec_loaded):
    result = discovery_spec_loaded(action="list_operations", method="DELETE")
    methods = {op["method"] for op in result["operations"]}
    assert methods == {"DELETE"}


def test_discovery_list_operations_keyword_filter(discovery_spec_loaded):
    result = discovery_spec_loaded(action="list_operations", keyword="search")
    for op in result["operations"]:
        combined = (op["operationId"] + " " + op["summary"]).lower()
        assert "search" in combined


def test_discovery_list_operations_pagination(discovery_spec_loaded):
    result = discovery_spec_loaded(action="list_operations", page=1, page_size=2)
    assert len(result["operations"]) <= 2
    assert result["total_pages"] >= 1


# =========================================================================== #
# discovery — get_operation_schema
# =========================================================================== #


def test_discovery_get_operation_schema_missing_path_returns_error(
    discovery_spec_loaded,
):
    result = discovery_spec_loaded(
        action="get_operation_schema",
        path=None,
        operation_method="GET",
    )
    assert result["status"] == "error"
    assert result["code"] == "MISSING_PARAMETER"
    assert "path" in result["message"]


def test_discovery_get_operation_schema_missing_method_returns_error(
    discovery_spec_loaded,
):
    result = discovery_spec_loaded(
        action="get_operation_schema",
        path="/vdbs",
        operation_method=None,
    )
    assert result["status"] == "error"
    assert result["code"] == "MISSING_PARAMETER"
    assert "operation_method" in result["message"]


def test_discovery_get_operation_schema_valid_returns_schema(discovery_spec_loaded):
    result = discovery_spec_loaded(
        action="get_operation_schema",
        path="/vdbs",
        operation_method="GET",
    )
    assert result.get("path") == "/vdbs"
    assert result.get("method") == "GET"
    assert "operationId" in result


# =========================================================================== #
# discovery — unknown action
# =========================================================================== #


def test_discovery_unknown_action_returns_error(discovery_spec_loaded):
    result = discovery_spec_loaded(action="do_something_weird")
    assert result["status"] == "error"
    assert result["code"] == "UNKNOWN_ACTION"


# =========================================================================== #
# execute — spec not loaded
# =========================================================================== #


async def test_execute_spec_not_loaded_returns_error():
    app = _make_app_mock()
    client = _make_client_mock()
    fn = _make_execute_fn(app, client)
    with patch(
        "dct_mcp_server.tools.core.dynamic.get_cached_spec",
        return_value=None,
    ):
        result = await fn(path="/vdbs", method="GET")
    assert result["status"] == "error"
    assert result["code"] == "SPEC_NOT_LOADED"


# =========================================================================== #
# execute — path param substitution
# =========================================================================== #


async def test_execute_resolves_path_params():
    """Path params provided → resolved path is dispatched successfully."""
    app = _make_app_mock()
    client = _make_client_mock(return_value={"id": "vdb-123"})
    fn = _make_execute_fn(app, client)

    # Patch confirmation so it doesn't block
    with patch(
        "dct_mcp_server.tools.core.dynamic.get_cached_spec",
        return_value=_VALID_SPEC,
    ):
        with patch(
            "dct_mcp_server.tools.core.dynamic.check_confirmation",
            return_value={
                "requires_confirmation": False,
                "confirmation_level": None,
                "message_template": None,
            },
        ):
            result = await fn(
                path="/vdbs/{vdbId}",
                method="GET",
                path_params={"vdbId": "vdb-123"},
            )

    assert result["status"] == "success"
    client.make_request.assert_called_once()
    call_kwargs = client.make_request.call_args
    assert "vdb-123" in call_kwargs[1].get(
        "endpoint", call_kwargs[0][1] if len(call_kwargs[0]) > 1 else ""
    )


async def test_execute_missing_path_params_returns_validation_error():
    app = _make_app_mock()
    client = _make_client_mock()
    fn = _make_execute_fn(app, client)

    with patch(
        "dct_mcp_server.tools.core.dynamic.get_cached_spec",
        return_value=_VALID_SPEC,
    ):
        result = await fn(
            path="/vdbs/{vdbId}",
            method="GET",
            path_params={},  # vdbId not provided
        )

    assert result["status"] == "error"
    assert result["code"] == "VALIDATION_ERROR"
    assert "vdbId" in result.get("missing_path_params", [])


# =========================================================================== #
# execute — operation not found
# =========================================================================== #


async def test_execute_path_not_in_spec_returns_not_found():
    app = _make_app_mock()
    client = _make_client_mock()
    fn = _make_execute_fn(app, client)

    with patch(
        "dct_mcp_server.tools.core.dynamic.get_cached_spec",
        return_value=_VALID_SPEC,
    ):
        result = await fn(path="/nonexistent/path", method="GET")

    assert result["status"] == "error"
    assert result["code"] == "OPERATION_NOT_FOUND"


async def test_execute_method_not_available_returns_not_found():
    app = _make_app_mock()
    client = _make_client_mock()
    fn = _make_execute_fn(app, client)

    with patch(
        "dct_mcp_server.tools.core.dynamic.get_cached_spec",
        return_value=_VALID_SPEC,
    ):
        # /vdbs only has GET, not POST
        result = await fn(path="/vdbs", method="POST")

    assert result["status"] == "error"
    assert result["code"] == "OPERATION_NOT_FOUND"


# =========================================================================== #
# execute — confirmation gate
# =========================================================================== #


async def test_execute_destructive_without_confirmed_returns_confirmation_required():
    app = _make_app_mock()
    client = _make_client_mock()
    fn = _make_execute_fn(app, client)

    with patch(
        "dct_mcp_server.tools.core.dynamic.get_cached_spec",
        return_value=_VALID_SPEC,
    ):
        with patch(
            "dct_mcp_server.tools.core.dynamic.check_confirmation",
            return_value={
                "requires_confirmation": True,
                "confirmation_level": "manual",
                "message_template": "Confirm deletion",
            },
        ):
            result = await fn(
                path="/vdbs/vdb-123",
                method="DELETE",
                confirmed=False,
            )

    assert result["status"] == "confirmation_required"
    assert result["confirmation_level"] == "manual"


async def test_execute_with_valid_token_skips_confirmation_gate():
    from dct_mcp_server.tools.core.confirmation_token import make_confirmation_token

    app = _make_app_mock()
    client = _make_client_mock(return_value={"deleted": True})
    fn = _make_execute_fn(app, client)

    token = make_confirmation_token("DELETE", "/vdbs/vdb-123")

    with patch(
        "dct_mcp_server.tools.core.dynamic.get_cached_spec",
        return_value=_VALID_SPEC,
    ):
        with patch(
            "dct_mcp_server.tools.core.dynamic.check_confirmation",
            return_value={
                "requires_confirmation": True,
                "confirmation_level": "manual",
                "message_template": "Confirm deletion",
            },
        ):
            result = await fn(
                path="/vdbs/vdb-123",
                method="DELETE",
                confirmation_token=token,
            )

    assert result["status"] == "success"
    client.make_request.assert_called_once()


# =========================================================================== #
# execute — DCTClientError
# =========================================================================== #


async def test_execute_dct_client_error_returns_dct_api_error():
    from dct_mcp_server.core.exceptions import DCTClientError

    app = _make_app_mock()
    client = _make_client_mock()
    client.make_request = AsyncMock(side_effect=DCTClientError("HTTP 404 Not Found"))
    fn = _make_execute_fn(app, client)

    with patch(
        "dct_mcp_server.tools.core.dynamic.get_cached_spec",
        return_value=_VALID_SPEC,
    ):
        with patch(
            "dct_mcp_server.tools.core.dynamic.check_confirmation",
            return_value={
                "requires_confirmation": False,
                "confirmation_level": None,
                "message_template": None,
            },
        ):
            result = await fn(path="/vdbs", method="GET")

    assert result["status"] == "error"
    assert result["code"] == "DCT_API_ERROR"
    assert result["http_status"] == 404


# =========================================================================== #
# execute — success path (GET read)
# =========================================================================== #


async def test_execute_successful_get_returns_success():
    app = _make_app_mock()
    client = _make_client_mock(return_value={"items": [{"id": "vdb-1"}]})
    fn = _make_execute_fn(app, client)

    with patch(
        "dct_mcp_server.tools.core.dynamic.get_cached_spec",
        return_value=_VALID_SPEC,
    ):
        result = await fn(path="/vdbs", method="GET")

    assert result["status"] == "success"
    assert result["operation_type"] == "read"
    assert result["response"] == {"items": [{"id": "vdb-1"}]}


# =========================================================================== #
# execute — operation_type classification
# =========================================================================== #


async def test_execute_delete_operation_type_is_destructive():
    app = _make_app_mock()
    client = _make_client_mock(return_value={})
    fn = _make_execute_fn(app, client)

    with patch(
        "dct_mcp_server.tools.core.dynamic.get_cached_spec",
        return_value=_VALID_SPEC,
    ):
        with patch(
            "dct_mcp_server.tools.core.dynamic.check_confirmation",
            return_value={
                "requires_confirmation": False,
                "confirmation_level": None,
                "message_template": None,
            },
        ):
            result = await fn(
                path="/vdbs/vdb-123",
                method="DELETE",
                confirmed=True,
            )

    assert result["status"] == "success"
    assert result["operation_type"] == "destructive"


async def test_execute_post_operation_type_is_mutating():
    app = _make_app_mock()
    client = _make_client_mock(return_value={"id": "new-vdb"})
    fn = _make_execute_fn(app, client)

    with patch(
        "dct_mcp_server.tools.core.dynamic.get_cached_spec",
        return_value=_VALID_SPEC,
    ):
        with patch(
            "dct_mcp_server.tools.core.dynamic.check_confirmation",
            return_value={
                "requires_confirmation": False,
                "confirmation_level": None,
                "message_template": None,
            },
        ):
            result = await fn(
                path="/vdbs/search",
                method="POST",
                body={"filter_expression": ""},
            )

    assert result["status"] == "success"
    assert result["operation_type"] == "mutating"


# =========================================================================== #
# register_dynamic_tools — registration contract
# =========================================================================== #


def test_register_dynamic_tools_registers_two_tools():
    """register_dynamic_tools must call app.add_tool exactly twice."""
    from dct_mcp_server.tools.core.dynamic import register_dynamic_tools

    app = MagicMock()
    client = MagicMock()
    register_dynamic_tools(app, client)
    assert app.add_tool.call_count == 2


def test_register_dynamic_tools_names_are_discovery_and_execute():
    """The two tools must be named 'discovery' and 'execute'."""
    from dct_mcp_server.tools.core.dynamic import register_dynamic_tools

    app = MagicMock()
    register_dynamic_tools(app, MagicMock())
    names = {call.kwargs.get("name") for call in app.add_tool.call_args_list}
    assert names == {"discovery", "execute"}


# =========================================================================== #
# discovery — get_operation_schema space-separated format
# =========================================================================== #


def test_discovery_get_operation_schema_space_separated_overrides_method(
    discovery_spec_loaded,
):
    """'POST /vdbs/search' in path should override the operation_method argument."""
    result = discovery_spec_loaded(
        action="get_operation_schema",
        path="POST /vdbs/search",
        operation_method="GET",  # should be overridden by the space-separated prefix
    )
    assert (
        result.get("status") != "error" or result.get("code") != "OPERATION_NOT_FOUND"
    )
    assert result.get("method") == "POST"


# =========================================================================== #
# execute — GET with body stripped
# =========================================================================== #


async def test_execute_get_with_body_strips_body():
    """Body passed to a GET request must be silently discarded."""
    app = _make_app_mock()
    client = _make_client_mock(return_value={"items": []})
    fn = _make_execute_fn(app, client)

    with patch(
        "dct_mcp_server.tools.core.dynamic.get_cached_spec",
        return_value=_VALID_SPEC,
    ):
        result = await fn(
            path="/vdbs",
            method="GET",
            body={"should_be_ignored": True},
        )

    assert result["status"] == "success"
    _, call_kwargs = client.make_request.call_args
    assert call_kwargs.get("json") is None


# =========================================================================== #
# execute — /dct/v3 prefix stripped for spec lookup
# =========================================================================== #

_SPEC_NO_DCT_PREFIX = {
    "openapi": "3.0.0",
    "info": {"title": "DCT", "version": "1"},
    "paths": {
        "/vdbs": {
            "get": {
                "operationId": "listVdbs",
                "summary": "List VDBs",
                "tags": ["VDBs"],
            }
        }
    },
}


async def test_execute_strips_dct_v3_prefix_for_spec_lookup():
    """execute must find /vdbs in the spec even when caller passes /dct/v3/vdbs."""
    app = _make_app_mock()
    client = _make_client_mock(return_value={"items": []})
    fn = _make_execute_fn(app, client)

    with patch(
        "dct_mcp_server.tools.core.dynamic.get_cached_spec",
        return_value=_SPEC_NO_DCT_PREFIX,
    ):
        result = await fn(path="/dct/v3/vdbs", method="GET")

    assert result["status"] == "success"


# =========================================================================== #
# execute — unexpected (non-DCTClientError) exception
# =========================================================================== #


async def test_execute_unexpected_exception_returns_error():
    """Any non-DCTClientError exception must surface as DCT_API_ERROR with http_status=None."""
    app = _make_app_mock()
    client = _make_client_mock()
    client.make_request = AsyncMock(side_effect=RuntimeError("connection reset"))
    fn = _make_execute_fn(app, client)

    with patch(
        "dct_mcp_server.tools.core.dynamic.get_cached_spec",
        return_value=_VALID_SPEC,
    ):
        result = await fn(path="/vdbs", method="GET")

    assert result["status"] == "error"
    assert result["code"] == "DCT_API_ERROR"
    assert result["http_status"] is None
    assert "connection reset" in result["message"]


# =========================================================================== #
# _classify_operation_type — full method coverage
# =========================================================================== #


def test_classify_put_is_mutating():
    from dct_mcp_server.tools.core.dynamic import _classify_operation_type

    assert _classify_operation_type("PUT") == "mutating"


def test_classify_patch_is_mutating():
    from dct_mcp_server.tools.core.dynamic import _classify_operation_type

    assert _classify_operation_type("PATCH") == "mutating"


def test_classify_post_is_mutating():
    from dct_mcp_server.tools.core.dynamic import _classify_operation_type

    assert _classify_operation_type("POST") == "mutating"


# =========================================================================== #
# _validate_required_params — required query parameter
# =========================================================================== #


def test_validate_required_query_param_missing_returns_error():
    from dct_mcp_server.tools.core.dynamic import _validate_required_params

    operation = {
        "parameters": [
            {"name": "version", "in": "query", "required": True},
        ]
    }
    result = _validate_required_params(operation, {}, {}, None)
    assert result is not None
    assert result["code"] == "VALIDATION_ERROR"
    assert "query:version" in result["missing_fields"]


def test_validate_optional_query_param_absent_is_ok():
    from dct_mcp_server.tools.core.dynamic import _validate_required_params

    operation = {
        "parameters": [
            {"name": "limit", "in": "query", "required": False},
        ]
    }
    result = _validate_required_params(operation, {}, {}, None)
    assert result is None


# =========================================================================== #
# _extract_http_status — direct coverage
# =========================================================================== #


def test_extract_http_status_parses_404():
    from dct_mcp_server.tools.core.dynamic import _extract_http_status

    assert _extract_http_status("HTTP 404 Not Found") == 404


def test_extract_http_status_parses_500():
    from dct_mcp_server.tools.core.dynamic import _extract_http_status

    assert _extract_http_status("upstream returned HTTP 500") == 500


def test_extract_http_status_returns_none_for_no_match():
    from dct_mcp_server.tools.core.dynamic import _extract_http_status

    assert _extract_http_status("connection timed out") is None
