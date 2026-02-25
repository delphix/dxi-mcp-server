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
def replication_tool(
    action: str,  # One of: search, get, create, update, delete, execute, add_tags
    automatic_replication: Optional[bool] = None,
    bandwidth_limit: Optional[int] = None,
    cursor: Optional[str] = None,
    description: Optional[str] = None,
    enable_tag_replication: Optional[bool] = None,
    encrypted: Optional[bool] = None,
    filter_expression: Optional[str] = None,
    limit: Optional[int] = None,
    name: Optional[str] = None,
    nfs_share: Optional[str] = None,
    number_of_connections: Optional[int] = None,
    replicate_entire_engine: Optional[bool] = None,
    replication_mode: Optional[str] = None,
    replication_profile_id: Optional[str] = None,
    schedule: Optional[str] = None,
    sort: Optional[str] = None,
    target_engine_id: Optional[str] = None,
    target_host: Optional[str] = None,
    target_port: Optional[int] = None,
    use_system_socks_setting: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for REPLICATION operations.
    
    This tool supports 7 actions: search, get, create, update, delete, execute, add_tags
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search for ReplicationProfiles.
    Method: POST
    Endpoint: /replication-profiles/search
    Required Parameters: limit, cursor, sort
    
    Filterable Fields:
        - id: The ReplicationProfile ID.
        - name: The ReplicationProfile name.
        - replication_mode: The ReplicationProfile mode.
        - engine_id: The ID of the engine that the ReplicationProfile belongs to.
        - target_engine_id: The ID of the replication target engine.
        - target_host: Hostname of the replication target engine.
        - target_port: Target TCP port number for the Delphix Session Protocol.
        - nfs_share: The NFS share path for the replication target. This param...
        - type: The ReplicationProfile type.
        - description: The ReplicationProfile description.
        - last_execution_status: The status of the last execution of the ReplicationProfile.
        - last_execution_status_timestamp: The timestamp of the last execution status.
        - schedule: Replication schedule in the form of a quartz-formatted st...
        - replication_tag: Globally unique identifier for this ReplicationProfile.
        - replication_objects: The objects that are replicated by this ReplicationProfile.
        - tags: The tags that are applied to this ReplicationProfile.
        - enable_tag_replication: Indicates whether tag replication from primary object to ...
        - bandwidth_limit: Bandwidth limit (MB/s) for replication network traffic. A...
        - number_of_connections: Total number of transport connections to use.
        - encrypted: Encrypt replication network traffic.
        - automatic_replication: Indication whether the replication spec schedule is enabl...
        - use_system_socks_setting: Connect to the replication target host via the system-wid...
        - vdb_ids: The VDBs that are replicated by this ReplicationProfile.
        - dsource_ids: The dSources that are replicated by this ReplicationProfile.
        - cdb_ids: The CDBs that are replicated by this ReplicationProfile.
        - vcdb_ids: The vCDBs that are replicated by this ReplicationProfile.
        - group_ids: The groups that are replicated by this ReplicationProfile.
        - replicate_entire_engine: Whether to replicate the entire engine. This is mutually ...
        - data_layout_ids: The data-layouts that are replicated by this ReplicationP...
        - last_send_timestamp: The timestamp of the last successful offline send operati...
        - last_offline_serialization_point_id: The ID of the last offline serialization point sent. This...
        - last_offline_receive_data_dir: The relative path of the directory containing the most re...
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> replication_tool(action='search', limit=..., cursor=..., sort=...)
    
    ACTION: get
    ----------------------------------------
    Summary: Get a ReplicationProfile by ID.
    Method: GET
    Endpoint: /replication-profiles/{replicationProfileId}
    Required Parameters: replication_profile_id
    
    Example:
        >>> replication_tool(action='get', replication_profile_id='example-replication_profile-123')
    
    ACTION: create
    ----------------------------------------
    Summary: Create a ReplicationProfile.
    Method: POST
    Endpoint: /replication-profiles
    
    Example:
        >>> replication_tool(action='create')
    
    ACTION: update
    ----------------------------------------
    Summary: Update a ReplicationProfile.
    Method: PATCH
    Endpoint: /replication-profiles/{replicationProfileId}
    Required Parameters: replication_profile_id
    
    Example:
        >>> replication_tool(action='update', replication_profile_id='example-replication_profile-123')
    
    ACTION: delete
    ----------------------------------------
    Summary: Delete a ReplicationProfile.
    Method: DELETE
    Endpoint: /replication-profiles/{replicationProfileId}
    Required Parameters: replication_profile_id
    
    Example:
        >>> replication_tool(action='delete', replication_profile_id='example-replication_profile-123')
    
    ACTION: execute
    ----------------------------------------
    Summary: Execute a ReplicationProfile.
    Method: POST
    Endpoint: /replication-profiles/{replicationProfileId}/execute
    Required Parameters: replication_profile_id
    
    Example:
        >>> replication_tool(action='execute', replication_profile_id='example-replication_profile-123')
    
    ACTION: add_tags
    ----------------------------------------
    Summary: Create tags for a ReplicationProfile.
    Method: POST
    Endpoint: /replication-profiles/{replicationProfileId}/tags
    Required Parameters: replication_profile_id
    
    Example:
        >>> replication_tool(action='add_tags', replication_profile_id='example-replication_profile-123')
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, create, update, delete, execute, add_tags
        automatic_replication (bool): Indication whether the replication spec schedule is enabled or not.
            [Optional for all actions]
        bandwidth_limit (int): Bandwidth limit (MB/s) for replication network traffic. A value of 0 means no...
            [Optional for all actions]
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search]
        description (str): The ReplicationProfile description.
            [Optional for all actions]
        enable_tag_replication (bool): Indicates whether tag replication from primary object to replica object is en...
            [Optional for all actions]
        encrypted (bool): Encrypt replication network traffic. This field is specific to network replic...
            [Optional for all actions]
        filter_expression (str): Filter expression to narrow results (e.g., "name CONTAINS 'prod'")
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search]
        name (str): The ReplicationProfile name.
            [Optional for all actions]
        nfs_share (str): The NFS share path for the replication target. This field is specific to offl...
            [Optional for all actions]
        number_of_connections (int): Total number of transport connections to use. This field is specific to netwo...
            [Optional for all actions]
        replicate_entire_engine (bool): Whether to replicate the entire engine. This is mutually exclusive with the v...
            [Optional for all actions]
        replication_mode (str): The ReplicationProfile mode.
            [Optional for all actions]
        replication_profile_id (str): The unique identifier for the replicationProfile.
            [Required for: get, update, delete, execute, add_tags]
        schedule (str): Replication schedule in the form of a quartz-formatted string.
            [Optional for all actions]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search]
        target_engine_id (str): The ID of the replication target engine. This field is specific to network re...
            [Optional for all actions]
        target_host (str): Hostname of the replication target engine. If none is provided and the target...
            [Optional for all actions]
        target_port (int): Target TCP port number for the Delphix Session Protocol. This field is specif...
            [Optional for all actions]
        use_system_socks_setting (bool): Connect to the replication target host via the system-wide SOCKS proxy. This ...
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
        return make_api_request('POST', '/replication-profiles/search', params=params, json_body=body)
    elif action == 'get':
        if replication_profile_id is None:
            return {'error': 'Missing required parameter: replication_profile_id for action get'}
        endpoint = f'/replication-profiles/{replication_profile_id}'
        params = build_params()
        return make_api_request('GET', endpoint, params=params)
    elif action == 'create':
        params = build_params()
        return make_api_request('POST', '/replication-profiles', params=params)
    elif action == 'update':
        if replication_profile_id is None:
            return {'error': 'Missing required parameter: replication_profile_id for action update'}
        endpoint = f'/replication-profiles/{replication_profile_id}'
        params = build_params()
        return make_api_request('PATCH', endpoint, params=params)
    elif action == 'delete':
        if replication_profile_id is None:
            return {'error': 'Missing required parameter: replication_profile_id for action delete'}
        endpoint = f'/replication-profiles/{replication_profile_id}'
        params = build_params()
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'execute':
        if replication_profile_id is None:
            return {'error': 'Missing required parameter: replication_profile_id for action execute'}
        endpoint = f'/replication-profiles/{replication_profile_id}/execute'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'add_tags':
        if replication_profile_id is None:
            return {'error': 'Missing required parameter: replication_profile_id for action add_tags'}
        endpoint = f'/replication-profiles/{replication_profile_id}/tags'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, create, update, delete, execute, add_tags'}


def register_tools(app, dct_client):
    global client
    client = dct_client
    logger.info(f'Registering tools for policy_endpoints...')
    try:
        logger.info(f'  Registering tool function: replication_tool')
        app.add_tool(replication_tool, name="replication_tool")
    except Exception as e:
        logger.error(f'Error registering tools for policy_endpoints: {e}')
    logger.info(f'Tools registration finished for policy_endpoints.')
