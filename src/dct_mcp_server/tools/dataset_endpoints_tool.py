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
def source_tool(
    action: str,  # One of: search, get, add_tags
    cursor: Optional[str] = None,
    filter_expression: Optional[str] = None,
    limit: Optional[int] = None,
    sort: Optional[str] = None,
    source_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Unified tool for SOURCE operations.
    
    This tool supports 3 actions: search, get, add_tags
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search for Sources.
    Method: POST
    Endpoint: /sources/search
    Required Parameters: limit, cursor, sort
    
    Filterable Fields:
        - id: The Source object entity ID.
        - database_type: The type of this source database.
        - name: The name of this source database.
        - namespace_id: The namespace id of this source database.
        - namespace_name: The namespace name of this source database.
        - is_replica: Is this a replicated object.
        - database_version: The version of this source database.
        - environment_id: A reference to the Environment that hosts this source dat...
        - environment_name: name of environment that hosts this source database.
        - data_uuid: A universal ID that uniquely identifies this source datab...
        - ip_address: The IP address of the source's host.
        - fqdn: The FQDN of the source's host.
        - size: The total size of this source database, in bytes.
        - jdbc_connection_string: The JDBC connection URL for this source database.
        - plugin_version: The version of the plugin associated with this source dat...
        - toolkit_id: The ID of the toolkit associated with this source databas...
        - is_dsource: 
        - repository: The repository id for this source
        - recovery_model: Recovery model of the source database (MSSql Only).
        - mssql_source_type: The type of this mssql source database (MSSql Only).
        - appdata_source_type: The type of this appdata source database (Appdata Only).
        - is_pdb: If this source is of PDB type (Oracle Only).
        - tags: 
        - instance_name: The instance name of this single instance database source.
        - instance_number: The instance number of this single instance database source.
        - instances: 
        - oracle_services: 
        - user: The username of the database user.
        - environment_user_ref: The environment user reference.
        - non_sys_user: The username of a database user that does not have admini...
        - discovered: Whether this source was discovered.
        - linking_enabled: Whether this source should be used for linking.
        - cdb_type: The cdb type for this source. (Oracle only)
        - data_connection_id: The ID of the associated DataConnection.
        - database_name: The name of this source database.
        - database_unique_name: The unique name of the database.
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> source_tool(action='search', limit=..., cursor=..., sort=...)
    
    ACTION: get
    ----------------------------------------
    Summary: Get a source by ID.
    Method: GET
    Endpoint: /sources/{sourceId}
    Required Parameters: source_id
    
    Example:
        >>> source_tool(action='get', source_id='example-source-123')
    
    ACTION: add_tags
    ----------------------------------------
    Summary: Create tags for a Source.
    Method: POST
    Endpoint: /sources/{sourceId}/tags
    Required Parameters: source_id
    
    Example:
        >>> source_tool(action='add_tags', source_id='example-source-123')
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, add_tags
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search]
        filter_expression (str): Filter expression to narrow results (e.g., "name CONTAINS 'prod'")
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search]
        source_id (str): The unique identifier for the source.
            [Required for: get, add_tags]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'search':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/sources/search', params=params, json_body=body)
    elif action == 'get':
        if source_id is None:
            return {'error': 'Missing required parameter: source_id for action get'}
        endpoint = f'/sources/{source_id}'
        params = build_params()
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_tags':
        if source_id is None:
            return {'error': 'Missing required parameter: source_id for action add_tags'}
        endpoint = f'/sources/{source_id}/tags'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, add_tags'}

@log_tool_execution
def data_connection_tool(
    action: str,  # One of: search, get, update, add_tags
    cursor: Optional[str] = None,
    data_connection_id: Optional[str] = None,
    filter_expression: Optional[str] = None,
    limit: Optional[int] = None,
    name: Optional[str] = None,
    sort: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Unified tool for DATA CONNECTION operations.
    
    This tool supports 4 actions: search, get, update, add_tags
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search for data connections.
    Method: POST
    Endpoint: /data-connections/search
    Required Parameters: limit, cursor, sort
    
    Filterable Fields:
        - id: ID of the data connection.
        - name: Name of the data connection.
        - status: ACTIVE if used by a masking job or a linked dSource or VDB.
        - type: The type of the data connection.
        - platform: The dataset platform of the data connection.
        - dsource_count: The number of dSources linked from this data connection.
        - capabilities: Types of functionality supported by this data connection.
        - tags: The tags associated with this data connection.
        - hostname: The combined port and hostname or IP address of the data ...
        - database_name: The database name.
        - custom_driver_name: The name of the custom JDBC driver.
        - path: The path to the FILE data on the remote host.
        - size: The size of the data connection in bytes. This is equival...
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> data_connection_tool(action='search', limit=..., cursor=..., sort=...)
    
    ACTION: get
    ----------------------------------------
    Summary: Get a data connection by id.
    Method: GET
    Endpoint: /data-connections/{dataConnectionId}
    Required Parameters: data_connection_id
    
    Example:
        >>> data_connection_tool(action='get', data_connection_id='example-data_connection-123')
    
    ACTION: update
    ----------------------------------------
    Summary: Update a data connection.
    Method: PATCH
    Endpoint: /data-connections/{dataConnectionId}
    Required Parameters: data_connection_id
    
    Example:
        >>> data_connection_tool(action='update', data_connection_id='example-data_connection-123')
    
    ACTION: add_tags
    ----------------------------------------
    Summary: Create tags for a data connection.
    Method: POST
    Endpoint: /data-connections/{dataConnectionId}/tags
    Required Parameters: data_connection_id
    
    Example:
        >>> data_connection_tool(action='add_tags', data_connection_id='example-data_connection-123')
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, update, add_tags
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search]
        data_connection_id (str): The unique identifier for the dataConnection.
            [Required for: get, update, add_tags]
        filter_expression (str): Filter expression to narrow results (e.g., "name CONTAINS 'prod'")
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search]
        name (str): The data connection name
            [Optional for all actions]
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
        return make_api_request('POST', '/data-connections/search', params=params, json_body=body)
    elif action == 'get':
        if data_connection_id is None:
            return {'error': 'Missing required parameter: data_connection_id for action get'}
        endpoint = f'/data-connections/{data_connection_id}'
        params = build_params()
        return make_api_request('GET', endpoint, params=params)
    elif action == 'update':
        if data_connection_id is None:
            return {'error': 'Missing required parameter: data_connection_id for action update'}
        endpoint = f'/data-connections/{data_connection_id}'
        params = build_params()
        return make_api_request('PATCH', endpoint, params=params)
    elif action == 'add_tags':
        if data_connection_id is None:
            return {'error': 'Missing required parameter: data_connection_id for action add_tags'}
        endpoint = f'/data-connections/{data_connection_id}/tags'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, update, add_tags'}


def register_tools(app, dct_client):
    global client
    client = dct_client
    logger.info(f'Registering tools for dataset_endpoints...')
    try:
        logger.info(f'  Registering tool function: source_tool')
        app.add_tool(source_tool, name="source_tool")
        logger.info(f'  Registering tool function: data_connection_tool')
        app.add_tool(data_connection_tool, name="data_connection_tool")
    except Exception as e:
        logger.error(f'Error registering tools for dataset_endpoints: {e}')
    logger.info(f'Tools registration finished for dataset_endpoints.')
