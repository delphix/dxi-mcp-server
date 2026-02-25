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
def environment_tool(
    action: str,  # One of: search, get, create, update, delete, enable, disable, refresh, add_tags
    cursor: Optional[str] = None,
    environment_id: Optional[str] = None,
    filter_expression: Optional[str] = None,
    limit: Optional[int] = None,
    sort: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Unified tool for ENVIRONMENT operations.
    
    This tool supports 9 actions: search, get, create, update, delete, enable, disable, refresh, add_tags
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search for environments.
    Method: POST
    Endpoint: /environments/search
    Required Parameters: limit, cursor, sort
    
    Filterable Fields:
        - id: The Environment object entity ID.
        - name: The name of this environment.
        - namespace_id: The namespace id of this environment.
        - namespace_name: The namespace name of this environment.
        - is_replica: Is this a replicated object.
        - namespace: The namespace of this environment for replicated and rest...
        - engine_id: A reference to the Engine that this Environment connectio...
        - engine_name: A reference to the Engine that this Environment connectio...
        - enabled: True if this environment is enabled.
        - encryption_enabled: Flag indicating whether the data transfer is encrypted or...
        - description: The environment description.
        - is_cluster: True if this environment is a cluster of hosts.
        - cluster_home: Cluster home for RAC environment.
        - cluster_name: Cluster name for Oracle RAC environment.
        - cluster_user: Cluster user for Oracle RAC environment.
        - scan: The Single Client Access Name of the cluster (11.2 and gr...
        - remote_listener: The default remote_listener parameter to be used for data...
        - is_windows_target: True if this windows environment is a target environment.
        - staging_environment: ID of the staging environment.
        - hosts: The hosts that are part of this environment.
        - tags: The tags to be created for this environment.
        - repositories: Repositories associated with this environment. A Reposito...
        - listeners: Oracle listeners associated with this environment.
        - os_type: The operating system type of this environment.
        - env_users: Environment users associated with this environment.
        - ase_db_user_name: The username of the SAP ASE database user.
        - ase_enable_tls: True if SAP ASE environment configured with TLS/SSL to di...
        - ase_skip_server_certificate_validation: If True, ASE database connection will skip the server cer...
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> environment_tool(action='search', limit=..., cursor=..., sort=...)
    
    ACTION: get
    ----------------------------------------
    Summary: Returns an environment by ID.
    Method: GET
    Endpoint: /environments/{environmentId}
    Required Parameters: environment_id
    
    Example:
        >>> environment_tool(action='get', environment_id='example-environment-123')
    
    ACTION: create
    ----------------------------------------
    Summary: Create an environment.
    Method: POST
    Endpoint: /environments
    
    Example:
        >>> environment_tool(action='create')
    
    ACTION: update
    ----------------------------------------
    Summary: Update an environment by ID.
    Method: PATCH
    Endpoint: /environments/{environmentId}
    Required Parameters: environment_id
    
    Example:
        >>> environment_tool(action='update', environment_id='example-environment-123')
    
    ACTION: delete
    ----------------------------------------
    Summary: Delete an environment by ID.
    Method: DELETE
    Endpoint: /environments/{environmentId}
    Required Parameters: environment_id
    
    Example:
        >>> environment_tool(action='delete', environment_id='example-environment-123')
    
    ACTION: enable
    ----------------------------------------
    Summary: Enable a disabled environment.
    Method: POST
    Endpoint: /environments/{environmentId}/enable
    Required Parameters: environment_id
    
    Example:
        >>> environment_tool(action='enable', environment_id='example-environment-123')
    
    ACTION: disable
    ----------------------------------------
    Summary: Disable environment.
    Method: POST
    Endpoint: /environments/{environmentId}/disable
    Required Parameters: environment_id
    
    Example:
        >>> environment_tool(action='disable', environment_id='example-environment-123')
    
    ACTION: refresh
    ----------------------------------------
    Summary: Refresh environment.
    Method: POST
    Endpoint: /environments/{environmentId}/refresh
    Required Parameters: environment_id
    
    Example:
        >>> environment_tool(action='refresh', environment_id='example-environment-123')
    
    ACTION: add_tags
    ----------------------------------------
    Summary: Create tags for an Environment.
    Method: POST
    Endpoint: /environments/{environmentId}/tags
    Required Parameters: environment_id
    
    Example:
        >>> environment_tool(action='add_tags', environment_id='example-environment-123')
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, create, update, delete, enable, disable, refresh, add_tags
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search]
        environment_id (str): The unique identifier for the environment.
            [Required for: get, update, delete, enable, disable, refresh, add_tags]
        filter_expression (str): Filter expression to narrow results (e.g., "name CONTAINS 'prod'")
            [Optional for all actions]
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
        return make_api_request('POST', '/environments/search', params=params, json_body=body)
    elif action == 'get':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action get'}
        endpoint = f'/environments/{environment_id}'
        params = build_params()
        return make_api_request('GET', endpoint, params=params)
    elif action == 'create':
        params = build_params()
        return make_api_request('POST', '/environments', params=params)
    elif action == 'update':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action update'}
        endpoint = f'/environments/{environment_id}'
        params = build_params()
        return make_api_request('PATCH', endpoint, params=params)
    elif action == 'delete':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action delete'}
        endpoint = f'/environments/{environment_id}'
        params = build_params()
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'enable':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action enable'}
        endpoint = f'/environments/{environment_id}/enable'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'disable':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action disable'}
        endpoint = f'/environments/{environment_id}/disable'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'refresh':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action refresh'}
        endpoint = f'/environments/{environment_id}/refresh'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'add_tags':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action add_tags'}
        endpoint = f'/environments/{environment_id}/tags'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, create, update, delete, enable, disable, refresh, add_tags'}


def register_tools(app, dct_client):
    global client
    client = dct_client
    logger.info(f'Registering tools for environment_endpoints...')
    try:
        logger.info(f'  Registering tool function: environment_tool')
        app.add_tool(environment_tool, name="environment_tool")
    except Exception as e:
        logger.error(f'Error registering tools for environment_endpoints: {e}')
    logger.info(f'Tools registration finished for environment_endpoints.')
