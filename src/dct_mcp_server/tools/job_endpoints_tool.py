from mcp.server.fastmcp import FastMCP
from typing import Dict,Any,Optional
from dct_mcp_server.core.decorators import log_tool_execution
from dct_mcp_server.config import get_confirmation_for_operation, requires_confirmation
import asyncio
import logging
import threading
from functools import wraps

client = None
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIRMATION INTEGRATION
# =============================================================================
# For destructive operations (DELETE, POST .../delete), generated tools should:
# 1. Call requires_confirmation(method, path) to check if confirmation needed
# 2. If True, include confirmation_message in the response
# 3. LLM should use check_operation_confirmation meta-tool before executing
#
# Example usage in generated tool:
#   confirmation = get_confirmation_for_operation("DELETE", "/vdbs/{id}")
#   if confirmation["level"] != "none":
#       return {
#           "requires_confirmation": True,
#           "confirmation_level": confirmation["level"],
#           "confirmation_message": confirmation["message"],
#           "operation": "delete_vdb"
#       }
# =============================================================================

def check_confirmation(method: str, api_path: str, action: str, tool_name: str, confirmed: bool = False, request_params: Optional[Dict[str, Any]] = None, request_body: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Check if operation requires confirmation. Returns confirmation response or None if confirmed/not needed."""
    confirmation = get_confirmation_for_operation(method, api_path)
    if confirmation["level"] != "none" and not confirmed:
        # Merge query params and body into a single review dict so the LLM can
        # render the exact payload that will be sent. None values are already
        # stripped upstream by build_params / body filter.
        review: Dict[str, Any] = {}
        if request_params:
            review.update(request_params)
        if request_body:
            review.update(request_body)
        is_review_critical = action.startswith("provision_") or action.startswith("dsource_link_") or action == "dsource_create_snapshot"
        instructions = (
            "STOP: You MUST display the confirmation_message to the user and wait for their EXPLICIT "
            "approval before re-calling with confirmed=True. Do NOT proceed without user consent."
        )
        if is_review_critical:
            instructions = (
                "STOP — REVIEW AND SUBMIT: Before asking the user to confirm, render 'review_parameters' "
                "as a Markdown table with columns | Parameter | Value | (one row per key). Then show the "
                "'confirmation_message' and the endpoint (method + api_path). Wait for EXPLICIT user approval, "
                "then re-call with confirmed=True and the SAME parameters. Do NOT proceed without consent."
            )
        return {
            "status": "confirmation_required",
            "confirmation_level": confirmation["level"],
            "confirmation_message": confirmation.get("message", "Please confirm this operation."),
            "action": action,
            "tool": tool_name,
            "api_path": api_path,
            "method": method,
            "review_parameters": review,
            "instructions": instructions,
        }
    return None

def async_to_sync(async_func):
    """Utility decorator to convert async functions to sync with proper event loop handling."""
    @wraps(async_func)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create a task and run it synchronously
                result = None
                exception = None
                def run_in_thread():
                    nonlocal result, exception
                    try:
                        result = asyncio.run(async_func(*args, **kwargs))
                    except Exception as e:
                        exception = e
                thread = threading.Thread(target=run_in_thread)
                thread.start()
                thread.join()
                if exception:
                    raise exception
                return result
            else:
                return loop.run_until_complete(async_func(*args, **kwargs))
        except RuntimeError:
            return asyncio.run(async_func(*args, **kwargs))
    return wrapper

def make_api_request(method: str, endpoint: str, params: dict = None, json_body: dict = None):
    """Utility function to make API requests with consistent parameter handling."""
    @async_to_sync
    async def _make_request():
        return await client.make_request(method, endpoint, params=params or {}, json=json_body)
    return _make_request()

def build_params(**kwargs):
    """Build parameters dictionary excluding None and empty string values."""
    return {k: v for k, v in kwargs.items() if v is not None and v != ''}

@log_tool_execution
def job_tool(
    action: str,  # One of: search, get, abandon, get_result, get_tags, add_tags, delete_tags
    cursor: Optional[str] = None,
    filter_expression: Optional[str] = None,
    job_id: Optional[str] = None,
    key: Optional[str] = None,
    limit: Optional[int] = 100,
    sort: Optional[str] = '-start_time',
    tags: Optional[list] = None,
    value: Optional[str] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for JOB operations.
    
    This tool supports 7 actions: search, get, abandon, get_result, get_tags, add_tags, delete_tags
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search for jobs.
    Method: POST
    Endpoint: /jobs/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - id: The Job entity ID.
        - status: The status of the job.
        - is_waiting_for_telemetry: Indicates that the operations performed by this Job have ...
        - type: The type of job being done.
        - localized_type: The i18n translated type of job being done.
        - error_details: Details about the failure for FAILED jobs.
        - warning_message: Warnings for the job.
        - target_id: A reference to the job's target.
        - target_name: A reference to the job's target name.
        - start_time: The time the job started executing.
        - update_time: The time the job was last updated.
        - trace_id: traceId of the request which created this Job
        - engine_ids: IDs of the engines this Job is executing on.
        - tags: 
        - engines: 
        - account_id: The ID of the account who initiated this job.
        - account_name: The account name which initiated this job. It can be eith...
        - percent_complete: Completion percentage of the Job.
        - virtualization_tasks: 
        - tasks: 
        - execution_id: The ID of the associated masking execution, if any.
        - result_type: The type of the job result. This is the type of the objec...
        - result: The result of the job execution. This is JSON serialized ...
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> job_tool(action='search', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get
    ----------------------------------------
    Summary: Returns a job by ID.
    Method: GET
    Endpoint: /jobs/{jobId}
    Required Parameters: job_id
    
    Example:
        >>> job_tool(action='get', job_id='example-job-123')
    
    ACTION: abandon
    ----------------------------------------
    Summary: Abandons a job.
    Method: POST
    Endpoint: /jobs/{jobId}/abandon
    Required Parameters: job_id
    
    Example:
        >>> job_tool(action='abandon', job_id='example-job-123')
    
    ACTION: get_result
    ----------------------------------------
    Summary: Get job result.
    Method: GET
    Endpoint: /jobs/{jobId}/result
    Required Parameters: job_id
    
    Example:
        >>> job_tool(action='get_result', job_id='example-job-123')
    
    ACTION: get_tags
    ----------------------------------------
    Summary: Get tags for a Job.
    Method: GET
    Endpoint: /jobs/{jobId}/tags
    Required Parameters: job_id
    
    Example:
        >>> job_tool(action='get_tags', job_id='example-job-123')
    
    ACTION: add_tags
    ----------------------------------------
    Summary: Create tags for a Job.
    Method: POST
    Endpoint: /jobs/{jobId}/tags
    Required Parameters: job_id, tags
    
    Example:
        >>> job_tool(action='add_tags', job_id='example-job-123', tags=...)
    
    ACTION: delete_tags
    ----------------------------------------
    Summary: Delete tags for a Job.
    Method: POST
    Endpoint: /jobs/{jobId}/tags/delete
    Required Parameters: job_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> job_tool(action='delete_tags', job_id='example-job-123', tags=..., key=..., value=...)
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, abandon, get_result, get_tags, add_tags, delete_tags
    
      -- General parameters (all database types) --
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search]
        filter_expression (str): Request body parameter
            [Optional for all actions]
        job_id (str): The unique identifier for the job.
            [Required for: get, abandon, get_result, get_tags, add_tags, delete_tags]
        key (str): Key of the tag
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search]
        tags (list): Array of tags with key value pairs (Pass as JSON array)
            [Required for: add_tags]
        value (str): Value of the tag
            [Optional for all actions]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'search':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', '/jobs/search', action, 'job_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/jobs/search', params=params, json_body=body)
    elif action == 'get':
        if job_id is None:
            return {'error': 'Missing required parameter: job_id for action get'}
        endpoint = f'/jobs/{job_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'job_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'abandon':
        if job_id is None:
            return {'error': 'Missing required parameter: job_id for action abandon'}
        endpoint = f'/jobs/{job_id}/abandon'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'job_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'get_result':
        if job_id is None:
            return {'error': 'Missing required parameter: job_id for action get_result'}
        endpoint = f'/jobs/{job_id}/result'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'job_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'get_tags':
        if job_id is None:
            return {'error': 'Missing required parameter: job_id for action get_tags'}
        endpoint = f'/jobs/{job_id}/tags'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'job_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_tags':
        if job_id is None:
            return {'error': 'Missing required parameter: job_id for action add_tags'}
        endpoint = f'/jobs/{job_id}/tags'
        params = build_params(tags=tags)
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'job_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_tags':
        if job_id is None:
            return {'error': 'Missing required parameter: job_id for action delete_tags'}
        endpoint = f'/jobs/{job_id}/tags/delete'
        params = build_params()
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'job_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, abandon, get_result, get_tags, add_tags, delete_tags'}


def register_tools(app, dct_client):
    global client
    client = dct_client
    logger.info(f'Registering tools for job_endpoints...')
    try:
        logger.info(f'  Registering tool function: job_tool')
        app.add_tool(job_tool, name="job_tool")
    except Exception as e:
        logger.error(f'Error registering tools for job_endpoints: {e}')
    logger.info(f'Tools registration finished for job_endpoints.')
