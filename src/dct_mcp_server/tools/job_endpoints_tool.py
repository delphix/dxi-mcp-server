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

def check_confirmation(method: str, api_path: str) -> Optional[Dict[str, Any]]:
    """Check if operation requires confirmation. Returns confirmation details or None."""
    confirmation = get_confirmation_for_operation(method, api_path)
    if confirmation["level"] != "none":
        return {
            "requires_confirmation": True,
            "confirmation_level": confirmation["level"],
            "confirmation_message": confirmation.get("message", "Please confirm this operation."),
            "conditional": confirmation.get("conditional", False),
            "threshold_days": confirmation.get("threshold_days")
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
    """Build parameters dictionary excluding None values."""
    return {k: v for k, v in kwargs.items() if v is not None}

@log_tool_execution
def job_tool(
    action: str,  # One of: search, get, abandon
    cursor: Optional[str] = None,
    filter_expression: Optional[str] = None,
    job_id: Optional[str] = None,
    limit: Optional[int] = None,
    sort: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Unified tool for JOB operations.
    
    This tool supports 3 actions: search, get, abandon
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search for jobs.
    Method: POST
    Endpoint: /jobs/search
    Required Parameters: limit, cursor, sort
    
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
        >>> job_tool(action='search', limit=..., cursor=..., sort=...)
    
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
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, abandon
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search]
        filter_expression (str): Filter expression to narrow results (e.g., "name CONTAINS 'prod'")
            [Optional for all actions]
        job_id (str): The unique identifier for the job.
            [Required for: get, abandon]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'search':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/jobs/search', params=params, json_body=body)
    elif action == 'get':
        if job_id is None:
            return {'error': 'Missing required parameter: job_id for action get'}
        endpoint = f'/jobs/{job_id}'
        params = build_params()
        return make_api_request('GET', endpoint, params=params)
    elif action == 'abandon':
        if job_id is None:
            return {'error': 'Missing required parameter: job_id for action abandon'}
        endpoint = f'/jobs/{job_id}/abandon'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, abandon'}


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
