"""
Layer 1 — Unit test for job_tool.

Demonstrates the unit-test pattern: set the tool module's `client` global to a
mocked DCTAPIClient, call the tool function directly, assert routing.
"""

import dct_mcp_server.tools.job_endpoints_tool as job_module


def test_job_tool_search_routes_to_jobs_search_endpoint(mock_dct_client):
    """
    job_tool(action='search') should issue POST /jobs/search with the limit,
    cursor, and sort params forwarded via build_params.
    """
    # Inject the mock as the module-level client used by make_api_request
    job_module.client = mock_dct_client
    mock_dct_client.make_request.return_value = {"items": [{"id": "j-1"}]}

    result = job_module.job_tool(action="search", limit=10, sort="-start_time")

    # Tool returned what the client gave us
    assert result == {"items": [{"id": "j-1"}]}

    # And it called the client with the right method, endpoint, and params
    mock_dct_client.make_request.assert_called_once()
    call_args = mock_dct_client.make_request.call_args
    assert call_args.args[0] == "POST"
    assert call_args.args[1] == "/jobs/search"
    assert call_args.kwargs["params"]["limit"] == 10
    assert call_args.kwargs["params"]["sort"] == "-start_time"


def test_job_tool_get_requires_job_id(mock_dct_client):
    """
    job_tool(action='get') without job_id should short-circuit with an error
    dict and NOT call the API.
    """
    job_module.client = mock_dct_client

    result = job_module.job_tool(action="get")

    assert "error" in result
    assert "job_id" in result["error"]
    mock_dct_client.make_request.assert_not_called()
