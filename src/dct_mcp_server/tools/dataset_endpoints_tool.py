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
    """Build parameters dictionary excluding None and empty string values."""
    return {k: v for k, v in kwargs.items() if v is not None and v != ''}

@log_tool_execution
def vdb_tool(
    action: str,  # One of: search, get, start, stop, enable, disable, refresh_by_timestamp, refresh_by_snapshot, refresh_from_bookmark, rollback_by_timestamp, rollback_by_snapshot, rollback_from_bookmark, list_snapshots, list_bookmarks
    abort: Optional[bool] = None,
    attempt_cleanup: Optional[bool] = None,
    attempt_start: Optional[bool] = None,
    container_mode: Optional[bool] = None,
    cursor: Optional[str] = None,
    filter_expression: Optional[str] = None,
    limit: Optional[int] = None,
    ownership_spec: Optional[str] = None,
    permission: Optional[str] = None,
    sort: Optional[str] = None,
    vdb_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Unified tool for VDB operations.
    
    This tool supports 14 actions: search, get, start, stop, enable, disable, refresh_by_timestamp, refresh_by_snapshot, refresh_from_bookmark, rollback_by_timestamp, rollback_by_snapshot, rollback_from_bookmark, list_snapshots, list_bookmarks
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search for VDBs.
    Method: POST
    Endpoint: /vdbs/search
    Required Parameters: limit, cursor, sort, permission
    
    Filterable Fields:
        - id: The VDB object entity ID.
        - database_type: The database type of this VDB.
        - name: The logical name of this VDB.
        - description: The container description of this VDB.
        - database_name: The name of the database on the target environment or in ...
        - namespace_id: The namespace id of this VDB.
        - namespace_name: The namespace name of this VDB.
        - is_replica: Is this a replicated object.
        - is_locked: Is this VDB locked.
        - locked_by: The ID of the account that locked this VDB.
        - locked_by_name: The name of the account that locked this VDB.
        - database_version: The database version of this VDB.
        - jdbc_connection_string: The JDBC connection URL for this VDB.
        - size: The total size of this VDB, in bytes.
        - storage_size: The actual space used by this VDB, in bytes.
        - unvirtualized_space: The disk space, in bytes, that it would take to store the...
        - engine_id: A reference to the Engine that this VDB belongs to.
        - status: The runtime status of the VDB. 'Unknown' if all attempts ...
        - masked: The VDB is masked or not.
        - content_type: The content type of the vdb.
        - parent_timeflow_timestamp: The timestamp for parent timeflow.
        - parent_timeflow_timezone: The timezone for parent timeflow.
        - environment_id: A reference to the Environment that hosts this VDB.
        - ip_address: The IP address of the VDB's host.
        - fqdn: The FQDN of the VDB's host.
        - parent_id: A reference to the parent dataset of this VDB.
        - parent_dsource_id: A reference to the parent dSource of this VDB.
        - root_parent_id: A reference to the root parent dataset of this VDB which ...
        - group_name: The name of the group containing this VDB.
        - engine_name: Name of the Engine where this VDB is hosted
        - cdb_id: A reference to the CDB or VCDB associated with this VDB.
        - tags: 
        - creation_date: The date this VDB was created.
        - hooks: 
        - appdata_source_params: The JSON payload conforming to the DraftV4 schema based o...
        - template_id: A reference to the Database Template.
        - template_name: Name of the Database Template.
        - config_params: Database configuration parameter overrides.
        - environment_user_ref: The environment user reference.
        - additional_mount_points: Specifies additional locations on which to mount a subdir...
        - appdata_config_params: The parameters specified by the source config schema in t...
        - mount_point: Mount point for the VDB (Oracle, ASE, AppData).
        - current_timeflow_id: A reference to the currently active timeflow for this VDB.
        - previous_timeflow_id: A reference to the previous timeflow for this VDB.
        - last_refreshed_date: The date this VDB was last refreshed.
        - vdb_restart: Indicates whether the Engine should automatically restart...
        - is_appdata: Indicates whether this VDB has an AppData database.
        - exported_data_directory: ZFS exported data directory path.
        - vcdb_exported_data_directory: ZFS exported data directory path of the virtual CDB conta...
        - toolkit_id: The ID of the toolkit associated with this VDB.
        - plugin_version: The version of the plugin associated with this VDB.
        - primary_object_id: The ID of the parent object from which replication was done.
        - primary_engine_id: The ID of the parent engine from which replication was done.
        - primary_engine_name: The name of the parent engine from which replication was ...
        - replicas: The list of replicas replicated from this object.
        - invoke_datapatch: Indicates whether datapatch should be invoked.
        - enabled: True if VDB is enabled false if VDB is disabled.
        - node_listeners: The list of node listeners for this VDB.
        - instance_name: The instance name name of this single instance VDB.
        - instance_number: The instance number of this single instance VDB.
        - instances: 
        - oracle_services: 
        - repository_id: The repository id of this VDB.
        - containerization_state: 
        - parent_tde_keystore_path: Path to a copy of the parent's Oracle transparent data en...
        - target_vcdb_tde_keystore_path: Path to the keystore of the target vCDB.
        - tde_key_identifier: ID of the key created by Delphix, as recorded in v$encryp...
        - parent_pdb_tde_keystore_path: Path to a copy of the parent PDB's Oracle transparent dat...
        - target_pdb_tde_keystore_path: Path of the virtual PDB's Oracle transparent data encrypt...
        - recovery_model: Recovery model of the vdb database.
        - cdc_on_provision: Whether to enable CDC on provision for MSSql.
        - data_connection_id: The ID of the associated DataConnection.
        - mssql_ag_backup_location: Shared backup location to be used for VDB provision on AG...
        - mssql_ag_backup_based: Indicates whether to do fast operations for VDB on AG whi...
        - mssql_ag_replicas: Indicates the mssql replica sources constitutes in MSSQL ...
        - database_unique_name: The unique name of the database.
        - db_username: The user name of the database.
        - new_db_id: Indicates whether Delphix will generate a new DBID during...
        - redo_log_groups: Number of Online Redo Log Groups.
        - redo_log_size_in_mb: Online Redo Log size in MB.
        - custom_env_vars: 
        - active_instances: 
        - nfs_version: The NFS version that was last used to mount this source."
        - nfs_version_reason: 
        - nfs_encryption_enabled: Flag indicating whether the data transfer is encrypted or...
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> vdb_tool(action='search', limit=..., cursor=..., sort=..., permission=...)
    
    ACTION: get
    ----------------------------------------
    Summary: Get a VDB by ID.
    Method: GET
    Endpoint: /vdbs/{vdbId}
    Required Parameters: vdb_id
    
    Example:
        >>> vdb_tool(action='get', vdb_id='example-vdb-123')
    
    ACTION: start
    ----------------------------------------
    Summary: Start a VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/start
    Required Parameters: vdb_id
    
    Example:
        >>> vdb_tool(action='start', vdb_id='example-vdb-123')
    
    ACTION: stop
    ----------------------------------------
    Summary: Stop a VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/stop
    Required Parameters: vdb_id
    
    Example:
        >>> vdb_tool(action='stop', vdb_id='example-vdb-123')
    
    ACTION: enable
    ----------------------------------------
    Summary: Enable a VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/enable
    Required Parameters: vdb_id
    
    Example:
        >>> vdb_tool(action='enable', vdb_id='example-vdb-123')
    
    ACTION: disable
    ----------------------------------------
    Summary: Disable a VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/disable
    Required Parameters: vdb_id
    
    Example:
        >>> vdb_tool(action='disable', vdb_id='example-vdb-123')
    
    ACTION: refresh_by_timestamp
    ----------------------------------------
    Summary: Refresh a VDB by timestamp.
    Method: POST
    Endpoint: /vdbs/{vdbId}/refresh_by_timestamp
    Required Parameters: vdb_id
    
    Example:
        >>> vdb_tool(action='refresh_by_timestamp', vdb_id='example-vdb-123')
    
    ACTION: refresh_by_snapshot
    ----------------------------------------
    Summary: Refresh a VDB by snapshot.
    Method: POST
    Endpoint: /vdbs/{vdbId}/refresh_by_snapshot
    Required Parameters: vdb_id
    
    Example:
        >>> vdb_tool(action='refresh_by_snapshot', vdb_id='example-vdb-123')
    
    ACTION: refresh_from_bookmark
    ----------------------------------------
    Summary: Refresh a VDB from bookmark with a single VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/refresh_from_bookmark
    Required Parameters: vdb_id
    
    Example:
        >>> vdb_tool(action='refresh_from_bookmark', vdb_id='example-vdb-123')
    
    ACTION: rollback_by_timestamp
    ----------------------------------------
    Summary: Rollback a VDB by timestamp.
    Method: POST
    Endpoint: /vdbs/{vdbId}/rollback_by_timestamp
    Required Parameters: vdb_id
    
    Example:
        >>> vdb_tool(action='rollback_by_timestamp', vdb_id='example-vdb-123')
    
    ACTION: rollback_by_snapshot
    ----------------------------------------
    Summary: Rollback a VDB by snapshot.
    Method: POST
    Endpoint: /vdbs/{vdbId}/rollback_by_snapshot
    Required Parameters: vdb_id
    
    Example:
        >>> vdb_tool(action='rollback_by_snapshot', vdb_id='example-vdb-123')
    
    ACTION: rollback_from_bookmark
    ----------------------------------------
    Summary: Rollback a VDB from a bookmark with only the same VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/rollback_from_bookmark
    Required Parameters: vdb_id
    
    Example:
        >>> vdb_tool(action='rollback_from_bookmark', vdb_id='example-vdb-123')
    
    ACTION: list_snapshots
    ----------------------------------------
    Summary: List Snapshots for a VDB.
    Method: GET
    Endpoint: /vdbs/{vdbId}/snapshots
    Required Parameters: limit, cursor, vdb_id
    
    Example:
        >>> vdb_tool(action='list_snapshots', limit=..., cursor=..., vdb_id='example-vdb-123')
    
    ACTION: list_bookmarks
    ----------------------------------------
    Summary: List Bookmarks compatible with this VDB.
    Method: GET
    Endpoint: /vdbs/{vdbId}/bookmarks
    Required Parameters: limit, cursor, sort, vdb_id
    
    Example:
        >>> vdb_tool(action='list_bookmarks', limit=..., cursor=..., sort=..., vdb_id='example-vdb-123')
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, start, stop, enable, disable, refresh_by_timestamp, refresh_by_snapshot, refresh_from_bookmark, rollback_by_timestamp, rollback_by_snapshot, rollback_from_bookmark, list_snapshots, list_bookmarks
        abort (bool): Whether to issue 'shutdown abort' to shutdown Oracle Virtual DB instances.
            [Optional for all actions]
        attempt_cleanup (bool): Whether to attempt a cleanup of the VDB before the disable.
            [Optional for all actions]
        attempt_start (bool): Whether to attempt a startup of the VDB after the enable.
            [Optional for all actions]
        container_mode (bool): Whether the database is running inside a container.
            [Optional for all actions]
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search, list_snapshots, list_bookmarks]
        filter_expression (str): Filter expression to narrow results (e.g., "name CONTAINS 'prod'")
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search, list_snapshots, list_bookmarks]
        ownership_spec (str): The uid:gid string that NFS mounts should belong to.
            [Optional for all actions]
        permission (str): Restrict the objects, which are allowed.
            [Required for: search]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search, list_bookmarks]
        vdb_id (str): The unique identifier for the vdb.
            [Required for: get, start, stop, enable, disable, refresh_by_timestamp, refresh_by_snapshot, refresh_from_bookmark, rollback_by_timestamp, rollback_by_snapshot, rollback_from_bookmark, list_snapshots, list_bookmarks]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'search':
        params = build_params(limit=limit, cursor=cursor, sort=sort, permission=permission)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/vdbs/search', params=params, json_body=body)
    elif action == 'get':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action get'}
        endpoint = f'/vdbs/{vdb_id}'
        params = build_params()
        return make_api_request('GET', endpoint, params=params)
    elif action == 'start':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action start'}
        endpoint = f'/vdbs/{vdb_id}/start'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'stop':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action stop'}
        endpoint = f'/vdbs/{vdb_id}/stop'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'enable':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action enable'}
        endpoint = f'/vdbs/{vdb_id}/enable'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'disable':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action disable'}
        endpoint = f'/vdbs/{vdb_id}/disable'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'refresh_by_timestamp':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action refresh_by_timestamp'}
        endpoint = f'/vdbs/{vdb_id}/refresh_by_timestamp'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'refresh_by_snapshot':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action refresh_by_snapshot'}
        endpoint = f'/vdbs/{vdb_id}/refresh_by_snapshot'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'refresh_from_bookmark':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action refresh_from_bookmark'}
        endpoint = f'/vdbs/{vdb_id}/refresh_from_bookmark'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'rollback_by_timestamp':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action rollback_by_timestamp'}
        endpoint = f'/vdbs/{vdb_id}/rollback_by_timestamp'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'rollback_by_snapshot':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action rollback_by_snapshot'}
        endpoint = f'/vdbs/{vdb_id}/rollback_by_snapshot'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'rollback_from_bookmark':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action rollback_from_bookmark'}
        endpoint = f'/vdbs/{vdb_id}/rollback_from_bookmark'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'list_snapshots':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action list_snapshots'}
        endpoint = f'/vdbs/{vdb_id}/snapshots'
        params = build_params(limit=limit, cursor=cursor)
        return make_api_request('GET', endpoint, params=params)
    elif action == 'list_bookmarks':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action list_bookmarks'}
        endpoint = f'/vdbs/{vdb_id}/bookmarks'
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        return make_api_request('GET', endpoint, params=params)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, start, stop, enable, disable, refresh_by_timestamp, refresh_by_snapshot, refresh_from_bookmark, rollback_by_timestamp, rollback_by_snapshot, rollback_from_bookmark, list_snapshots, list_bookmarks'}

@log_tool_execution
def vdb_group_tool(
    action: str,  # One of: search, get, refresh, refresh_from_bookmark, refresh_by_snapshot, refresh_by_timestamp, rollback, lock, unlock, start, stop, enable, disable, list_bookmarks
    account_id: Optional[int] = None,
    bookmark_id: Optional[str] = None,
    cursor: Optional[str] = None,
    filter_expression: Optional[str] = None,
    is_refresh_to_nearest: Optional[bool] = None,
    limit: Optional[int] = None,
    sort: Optional[str] = None,
    vdb_group_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Unified tool for VDB GROUP operations.
    
    This tool supports 14 actions: search, get, refresh, refresh_from_bookmark, refresh_by_snapshot, refresh_by_timestamp, rollback, lock, unlock, start, stop, enable, disable, list_bookmarks
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search for VDB Groups.
    Method: POST
    Endpoint: /vdb-groups/search
    Required Parameters: limit, cursor, sort
    
    Filterable Fields:
        - id: A unique identifier for the entity.
        - name: A unique name for the entity.
        - vdb_ids: The list of VDB IDs in this VDB Group.
        - is_locked: Indicates whether the VDB Group is locked.
        - locked_by: The Id of the account that locked the VDB Group.
        - locked_by_name: The name of the account that locked the VDB Group.
        - vdb_group_source: Source of the vdb group, default is DCT. In case of self-...
        - ss_data_layout_id: Data-layout Id for engine-managed vdb groups.
        - vdbs: Dictates order of operations on VDBs. Operations can be p...
        - database_type: The database type of the VDB Group. If all VDBs in the gr...
        - status: The status of the VDB Group. If all VDBs in the VDB Group...
        - last_successful_refresh_to_bookmark_id: The bookmark ID to which the VDB Group was last successfu...
        - last_successful_refresh_time: The time at which the VDB Group was last successfully ref...
        - tags: 
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> vdb_group_tool(action='search', limit=..., cursor=..., sort=...)
    
    ACTION: get
    ----------------------------------------
    Summary: Get a VDB Group by name.
    Method: GET
    Endpoint: /vdb-groups/{vdbGroupId}
    Required Parameters: vdb_group_id
    
    Example:
        >>> vdb_group_tool(action='get', vdb_group_id='example-vdb_group-123')
    
    ACTION: refresh
    ----------------------------------------
    Summary: Refresh a VDB Group from bookmark.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/refresh
    Required Parameters: vdb_group_id, bookmark_id
    
    Example:
        >>> vdb_group_tool(action='refresh', vdb_group_id='example-vdb_group-123', bookmark_id='example-bookmark-123')
    
    ACTION: refresh_from_bookmark
    ----------------------------------------
    Summary: Refresh a VDB Group from bookmark.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/refresh_from_bookmark
    Required Parameters: vdb_group_id, bookmark_id
    
    Example:
        >>> vdb_group_tool(action='refresh_from_bookmark', vdb_group_id='example-vdb_group-123', bookmark_id='example-bookmark-123')
    
    ACTION: refresh_by_snapshot
    ----------------------------------------
    Summary: Refresh a VDB Group by snapshot.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/refresh_by_snapshot
    Required Parameters: vdb_group_id
    
    Example:
        >>> vdb_group_tool(action='refresh_by_snapshot', vdb_group_id='example-vdb_group-123')
    
    ACTION: refresh_by_timestamp
    ----------------------------------------
    Summary: Refresh a VDB Group by timestamp.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/refresh_by_timestamp
    Required Parameters: vdb_group_id
    
    Example:
        >>> vdb_group_tool(action='refresh_by_timestamp', vdb_group_id='example-vdb_group-123')
    
    ACTION: rollback
    ----------------------------------------
    Summary: Rollback a VDB Group from a bookmark.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/rollback
    Required Parameters: vdb_group_id, bookmark_id
    
    Example:
        >>> vdb_group_tool(action='rollback', vdb_group_id='example-vdb_group-123', bookmark_id='example-bookmark-123')
    
    ACTION: lock
    ----------------------------------------
    Summary: Lock a VDB Group.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/lock
    Required Parameters: vdb_group_id
    
    Example:
        >>> vdb_group_tool(action='lock', vdb_group_id='example-vdb_group-123')
    
    ACTION: unlock
    ----------------------------------------
    Summary: Unlock a VDB Group.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/unlock
    Required Parameters: vdb_group_id
    
    Example:
        >>> vdb_group_tool(action='unlock', vdb_group_id='example-vdb_group-123')
    
    ACTION: start
    ----------------------------------------
    Summary: Start a VDB Group.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/start
    Required Parameters: vdb_group_id
    
    Example:
        >>> vdb_group_tool(action='start', vdb_group_id='example-vdb_group-123')
    
    ACTION: stop
    ----------------------------------------
    Summary: Stop a VDB Group.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/stop
    Required Parameters: vdb_group_id
    
    Example:
        >>> vdb_group_tool(action='stop', vdb_group_id='example-vdb_group-123')
    
    ACTION: enable
    ----------------------------------------
    Summary: Enable a VDB Group.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/enable
    Required Parameters: vdb_group_id
    
    Example:
        >>> vdb_group_tool(action='enable', vdb_group_id='example-vdb_group-123')
    
    ACTION: disable
    ----------------------------------------
    Summary: Disable a VDB Group.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/disable
    Required Parameters: vdb_group_id
    
    Example:
        >>> vdb_group_tool(action='disable', vdb_group_id='example-vdb_group-123')
    
    ACTION: list_bookmarks
    ----------------------------------------
    Summary: List bookmarks compatible with this VDB Group.
    Method: GET
    Endpoint: /vdb-groups/{vdbGroupId}/bookmarks
    Required Parameters: limit, cursor, sort, vdb_group_id
    
    Example:
        >>> vdb_group_tool(action='list_bookmarks', limit=..., cursor=..., sort=..., vdb_group_id='example-vdb_group-123')
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, refresh, refresh_from_bookmark, refresh_by_snapshot, refresh_by_timestamp, rollback, lock, unlock, start, stop, enable, disable, list_bookmarks
        account_id (int): Id of the account on whose behalf this request is being made. Only accounts h...
            [Optional for all actions]
        bookmark_id (str): ID of a bookmark to refresh this VDB Group to.
            [Required for: refresh, refresh_from_bookmark, rollback]
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search, list_bookmarks]
        filter_expression (str): Filter expression to narrow results (e.g., "name CONTAINS 'prod'")
            [Optional for all actions]
        is_refresh_to_nearest (bool): If true, and the provided timestamp is not found for the VDB mapping, the sys...
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search, list_bookmarks]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search, list_bookmarks]
        vdb_group_id (str): The unique identifier for the vdbGroup.
            [Required for: get, refresh, refresh_from_bookmark, refresh_by_snapshot, refresh_by_timestamp, rollback, lock, unlock, start, stop, enable, disable, list_bookmarks]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'search':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/vdb-groups/search', params=params, json_body=body)
    elif action == 'get':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action get'}
        endpoint = f'/vdb-groups/{vdb_group_id}'
        params = build_params()
        return make_api_request('GET', endpoint, params=params)
    elif action == 'refresh':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action refresh'}
        endpoint = f'/vdb-groups/{vdb_group_id}/refresh'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'refresh_from_bookmark':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action refresh_from_bookmark'}
        endpoint = f'/vdb-groups/{vdb_group_id}/refresh_from_bookmark'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'refresh_by_snapshot':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action refresh_by_snapshot'}
        endpoint = f'/vdb-groups/{vdb_group_id}/refresh_by_snapshot'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'refresh_by_timestamp':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action refresh_by_timestamp'}
        endpoint = f'/vdb-groups/{vdb_group_id}/refresh_by_timestamp'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'rollback':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action rollback'}
        endpoint = f'/vdb-groups/{vdb_group_id}/rollback'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'lock':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action lock'}
        endpoint = f'/vdb-groups/{vdb_group_id}/lock'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'unlock':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action unlock'}
        endpoint = f'/vdb-groups/{vdb_group_id}/unlock'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'start':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action start'}
        endpoint = f'/vdb-groups/{vdb_group_id}/start'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'stop':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action stop'}
        endpoint = f'/vdb-groups/{vdb_group_id}/stop'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'enable':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action enable'}
        endpoint = f'/vdb-groups/{vdb_group_id}/enable'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'disable':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action disable'}
        endpoint = f'/vdb-groups/{vdb_group_id}/disable'
        params = build_params()
        return make_api_request('POST', endpoint, params=params)
    elif action == 'list_bookmarks':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action list_bookmarks'}
        endpoint = f'/vdb-groups/{vdb_group_id}/bookmarks'
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        return make_api_request('GET', endpoint, params=params)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, refresh, refresh_from_bookmark, refresh_by_snapshot, refresh_by_timestamp, rollback, lock, unlock, start, stop, enable, disable, list_bookmarks'}

@log_tool_execution
def dsource_tool(
    action: str,  # One of: search, get, list_snapshots
    cursor: Optional[str] = None,
    dsource_id: Optional[str] = None,
    filter_expression: Optional[str] = None,
    limit: Optional[int] = None,
    permission: Optional[str] = None,
    sort: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Unified tool for DSOURCE operations.
    
    This tool supports 3 actions: search, get, list_snapshots
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search for dSources.
    Method: POST
    Endpoint: /dsources/search
    Required Parameters: limit, cursor, sort, permission
    
    Filterable Fields:
        - id: The dSource object entity ID.
        - database_type: The database type of this dSource.
        - name: The container name of this dSource.
        - description: The container description of this dSource.
        - namespace_id: The namespace id of this dSource.
        - namespace_name: The namespace name of this dSource.
        - is_replica: Is this a replicated object.
        - database_version: The database version of this dSource.
        - content_type: The content type of the dSource.
        - data_uuid: A universal ID that uniquely identifies the dSource datab...
        - storage_size: The actual space used by this dSource, in bytes.
        - plugin_version: The version of the plugin associated with this source dat...
        - creation_date: The date this dSource was created.
        - group_name: The name of the group containing this dSource.
        - enabled: A value indicating whether this dSource is enabled.
        - is_detached: A value indicating whether this dSource is detached.
        - engine_id: A reference to the Engine that this dSource belongs to.
        - source_id: A reference to the Source associated with this dSource.
        - staging_source_id: A reference to the Staging Source associated with this dS...
        - status: The runtime status of the dSource. 'Unknown' if all attem...
        - engine_name: Name of the Engine where this DSource is hosted
        - cdb_id: A reference to the CDB associated with this dSource.
        - current_timeflow_id: A reference to the currently active timeflow for this dSo...
        - previous_timeflow_id: A reference to the previous timeflow for this dSource.
        - is_appdata: Indicates whether this dSource has an AppData database.
        - toolkit_id: The ID of the toolkit associated with this dSource(AppDat...
        - unvirtualized_space: This is the sum of unvirtualized space from the dependant...
        - dependant_vdbs: The number of VDBs that are dependant on this dSource. Th...
        - appdata_source_params: The JSON payload conforming to the DraftV4 schema based o...
        - appdata_config_params: The parameters specified by the source config schema in t...
        - tags: 
        - primary_object_id: The ID of the parent object from which replication was done.
        - primary_engine_id: The ID of the parent engine from which replication was done.
        - primary_engine_name: The name of the parent engine from which replication was ...
        - replicas: The list of replicas replicated from this object.
        - hooks: 
        - sync_policy_id: The id of the snapshot policy associated with this dSource.
        - retention_policy_id: The id of the retention policy associated with this dSource.
        - replica_retention_policy_id: The id of the replica retention policy associated with th...
        - quota_policy_id: The id of the quota policy associated with this dSource.
        - logsync_enabled: True if LogSync is enabled for this dSource.
        - logsync_mode: 
        - logsync_interval: Interval between LogSync requests, in seconds.
        - exported_data_directory: ZFS exported data directory path.
        - template_id: A reference to the Non Virtual Database Template.
        - allow_auto_staging_restart_on_host_reboot: Indicates whether Delphix should automatically restart th...
        - physical_standby: Indicates whether this staging database is configured as ...
        - validate_by_opening_db_in_read_only_mode: Indicates whether this staging database snapshot is valid...
        - mssql_sync_strategy_managed_type: 
        - validated_sync_mode: Specifies the backup types ValidatedSync will use to sync...
        - shared_backup_locations: Shared source database backup locations.
        - backup_policy: Specify which node of an availability group to run the co...
        - compression_enabled: Specify whether the backups taken should be compressed or...
        - staging_database_name: The name of the staging database
        - db_state: User provided db state that is used to create staging pus...
        - encryption_key: The encryption key to use when restoring encrypted backups.
        - external_netbackup_config_master_name: The master server name of this NetBackup configuration.
        - external_netbackup_config_source_client_name: The source's client server name of this NetBackup configu...
        - external_netbackup_config_params: NetBackup configuration parameter overrides.
        - external_netbackup_config_templates: Optional config template selection for NetBackup configur...
        - external_commserve_host_name: The commserve host name of this Commvault configuration.
        - external_commvault_config_source_client_name: The source client name of this Commvault configuration.
        - external_commvault_config_staging_client_name: The staging client name of this Commvault configuration.
        - external_commvault_config_params: Commvault configuration parameter overrides.
        - external_commvault_config_templates: Optional config template selection for Commvault configur...
        - mssql_user_type: Database user type for Database authentication.
        - domain_user_credential_type: credential types.
        - mssql_database_username: The database user name for database user type.
        - mssql_user_environment_reference: The name or reference of the environment user for environ...
        - mssql_user_domain_username: Domain User name for password credentials.
        - mssql_user_domain_vault_username: Delphix display name for the vault user.
        - mssql_user_domain_vault: The name or reference of the vault.
        - mssql_user_domain_hashicorp_vault_engine: Vault engine name where the credential is stored.
        - mssql_user_domain_hashicorp_vault_secret_path: Path in the vault engine where the credential is stored.
        - mssql_user_domain_hashicorp_vault_username_key: Hashicorp vault key for the username in the key-value store.
        - mssql_user_domain_hashicorp_vault_secret_key: Hashicorp vault key for the password in the key-value store.
        - mssql_user_domain_azure_vault_name: Azure key vault name.
        - mssql_user_domain_azure_vault_username_key: Azure vault key in the key-value store.
        - mssql_user_domain_azure_vault_secret_key: Azure vault key in the key-value store.
        - mssql_user_domain_cyberark_vault_query_string: Query to find a credential in the CyberArk vault.
        - diagnose_no_logging_faults: If true, NOLOGGING operations on this container are treat...
        - pre_provisioning_enabled: If true, pre-provisioning will be performed after every s...
        - backup_level_enabled: Boolean value indicates whether LEVEL-based incremental b...
        - rman_channels: Number of parallel channels to use.
        - files_per_set: Number of data files to include in each RMAN backup set.
        - check_logical: True if extended block checking should be used for this l...
        - encrypted_linking_enabled: True if SnapSync data from the source should be retrieved...
        - compressed_linking_enabled: True if SnapSync data from the source should be compresse...
        - bandwidth_limit: Bandwidth limit (MB/s) for SnapSync and LogSync network t...
        - number_of_connections: Total number of transport connections to use during SnapS...
        - data_connection_id: The ID of the associated DataConnection.
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> dsource_tool(action='search', limit=..., cursor=..., sort=..., permission=...)
    
    ACTION: get
    ----------------------------------------
    Summary: Get a dSource by ID.
    Method: GET
    Endpoint: /dsources/{dsourceId}
    Required Parameters: dsource_id
    
    Example:
        >>> dsource_tool(action='get', dsource_id='example-dsource-123')
    
    ACTION: list_snapshots
    ----------------------------------------
    Summary: List Snapshots for a dSource.
    Method: GET
    Endpoint: /dsources/{dsourceId}/snapshots
    Required Parameters: limit, cursor, dsource_id
    
    Example:
        >>> dsource_tool(action='list_snapshots', limit=..., cursor=..., dsource_id='example-dsource-123')
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, list_snapshots
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search, list_snapshots]
        dsource_id (str): The unique identifier for the dsource.
            [Required for: get, list_snapshots]
        filter_expression (str): Filter expression to narrow results (e.g., "name CONTAINS 'prod'")
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search, list_snapshots]
        permission (str): Restrict the objects, which are allowed.
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
        params = build_params(limit=limit, cursor=cursor, sort=sort, permission=permission)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/dsources/search', params=params, json_body=body)
    elif action == 'get':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action get'}
        endpoint = f'/dsources/{dsource_id}'
        params = build_params()
        return make_api_request('GET', endpoint, params=params)
    elif action == 'list_snapshots':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action list_snapshots'}
        endpoint = f'/dsources/{dsource_id}/snapshots'
        params = build_params(limit=limit, cursor=cursor)
        return make_api_request('GET', endpoint, params=params)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, list_snapshots'}

@log_tool_execution
def snapshot_tool(
    action: str,  # One of: search, get, get_timeflow_range, get_runtime
    cursor: Optional[str] = None,
    filter_expression: Optional[str] = None,
    limit: Optional[int] = None,
    snapshot_id: Optional[str] = None,
    sort: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Unified tool for SNAPSHOT operations.
    
    This tool supports 4 actions: search, get, get_timeflow_range, get_runtime
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search snapshots.
    Method: POST
    Endpoint: /snapshots/search
    Required Parameters: limit, cursor, sort
    
    Filterable Fields:
        - id: The Snapshot ID.
        - engine_id: The id of the engine the snapshot belongs to.
        - namespace: Alternate namespace for this object, for replicated and r...
        - name: The snapshot's name.
        - namespace_id: The namespace id of this snapshot.
        - namespace_name: The namespace name of this snapshot.
        - is_replica: Is this a replicated object.
        - consistency: Indicates what type of recovery strategies must be invoke...
        - missing_non_logged_data: Indicates if a virtual database provisioned from this sna...
        - dataset_id: The ID of the Snapshot's dSource or VDB.
        - creation_time: The time when the snapshot was created.
        - start_timestamp: The timestamp within the parent TimeFlow at which this sn...
        - start_location: The database specific indentifier within the parent TimeF...
        - timestamp: The logical time of the data contained in this Snapshot.
        - location: Database specific identifier for the data contained in th...
        - retention: Retention policy, in days. A value of -1 indicates the sn...
        - expiration: The expiration date of this snapshot. If this is unset an...
        - retain_forever: Indicates that the snapshot is protected from retention, ...
        - effective_expiration: The effective expiration is that max of the snapshot expi...
        - effective_retain_forever: True if retain_forever is set or a Bookmark retains this ...
        - timeflow_id: The TimeFlow this snapshot was taken on.
        - timezone: Time zone of the source database at the time the snapshot...
        - version: Version of database source repository at the time the sna...
        - temporary: Indicates that this snapshot is in a transient state and ...
        - appdata_toolkit: The toolkit associated with this snapshot.
        - appdata_metadata: The JSON payload conforming to the DraftV4 schema based o...
        - ase_db_encryption_key: Database encryption key present for this snapshot.
        - mssql_internal_version: Internal version of the source database at the time the s...
        - mssql_backup_set_uuid: UUID of the source database backup that was restored for ...
        - mssql_backup_software_type: Backup software used to restore the source database backu...
        - mssql_backup_location_type: Backup software used to restore the source database backu...
        - mssql_empty_snapshot: True if the staging push dSource snapshot is empty.
        - oracle_from_physical_standby_vdb: True if this snapshot was taken of a standby database.
        - oracle_redo_log_size_in_bytes: Online redo log size in bytes when this snapshot was taken.
        - tags: 
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> snapshot_tool(action='search', limit=..., cursor=..., sort=...)
    
    ACTION: get
    ----------------------------------------
    Summary: Get a Snapshot by ID.
    Method: GET
    Endpoint: /snapshots/{snapshotId}
    Required Parameters: snapshot_id
    
    Example:
        >>> snapshot_tool(action='get', snapshot_id='example-snapshot-123')
    
    ACTION: get_timeflow_range
    ----------------------------------------
    Summary: Return the provisionable timeflow range based on a specific snapshot.
    Method: GET
    Endpoint: /snapshots/{snapshotId}/timeflow_range
    Required Parameters: snapshot_id
    
    Example:
        >>> snapshot_tool(action='get_timeflow_range', snapshot_id='example-snapshot-123')
    
    ACTION: get_runtime
    ----------------------------------------
    Summary: Get a runtime object of a snapshot by id
    Method: GET
    Endpoint: /snapshots/{snapshotId}/runtime
    Required Parameters: snapshot_id
    
    Example:
        >>> snapshot_tool(action='get_runtime', snapshot_id='example-snapshot-123')
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, get_timeflow_range, get_runtime
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search]
        filter_expression (str): Filter expression to narrow results (e.g., "name CONTAINS 'prod'")
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search]
        snapshot_id (str): The unique identifier for the snapshot.
            [Required for: get, get_timeflow_range, get_runtime]
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
        return make_api_request('POST', '/snapshots/search', params=params, json_body=body)
    elif action == 'get':
        if snapshot_id is None:
            return {'error': 'Missing required parameter: snapshot_id for action get'}
        endpoint = f'/snapshots/{snapshot_id}'
        params = build_params()
        return make_api_request('GET', endpoint, params=params)
    elif action == 'get_timeflow_range':
        if snapshot_id is None:
            return {'error': 'Missing required parameter: snapshot_id for action get_timeflow_range'}
        endpoint = f'/snapshots/{snapshot_id}/timeflow_range'
        params = build_params()
        return make_api_request('GET', endpoint, params=params)
    elif action == 'get_runtime':
        if snapshot_id is None:
            return {'error': 'Missing required parameter: snapshot_id for action get_runtime'}
        endpoint = f'/snapshots/{snapshot_id}/runtime'
        params = build_params()
        return make_api_request('GET', endpoint, params=params)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, get_timeflow_range, get_runtime'}

@log_tool_execution
def bookmark_tool(
    action: str,  # One of: search, get, create, update, delete, get_vdb_groups
    bookmark_id: Optional[str] = None,
    bookmark_type: Optional[str] = None,
    cursor: Optional[str] = None,
    expiration: Optional[str] = None,
    filter_expression: Optional[str] = None,
    limit: Optional[int] = None,
    name: Optional[str] = None,
    retain_forever: Optional[bool] = None,
    sort: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Unified tool for BOOKMARK operations.
    
    This tool supports 6 actions: search, get, create, update, delete, get_vdb_groups
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search for bookmarks.
    Method: POST
    Endpoint: /bookmarks/search
    Required Parameters: limit, cursor, sort
    
    Filterable Fields:
        - id: The Bookmark object entity ID.
        - name: The user-defined name of this bookmark.
        - creation_date: The date and time that this bookmark was created.
        - data_timestamp: The timestamp for the data that the bookmark refers to.
        - timeflow_id: The timeflow for the snapshot that the bookmark was creat...
        - location: The location for the data that the bookmark refers to.
        - vdb_ids: The list of VDB IDs associated with this bookmark.
        - dsource_ids: The list of dSource IDs associated with this bookmark.
        - vdb_group_id: The ID of the VDB group on which bookmark is created.
        - vdb_group_name: The name of the VDB group on which bookmark is created.
        - vdbs: The list of VDB IDs and VDB names associated with this bo...
        - dsources: The list of dSource IDs and dSource names associated with...
        - retention: The retention policy for this bookmark, in days. A value ...
        - expiration: The expiration for this bookmark. When unset, indicates t...
        - status: A message with details about operation progress or state ...
        - replicated_dataset: Whether this bookmark is created from a replicated datase...
        - bookmark_source: Source of the bookmark, default is DCT. In case of self-s...
        - bookmark_status: Status of the bookmark. It can have INACTIVE value for en...
        - ss_data_layout_id: Data-layout Id for engine-managed bookmarks.
        - ss_bookmark_reference: Engine reference of the self-service bookmark.
        - ss_bookmark_errors: List of errors if any, during bookmark creation in DCT fr...
        - bookmark_type: Type of the bookmark, either PUBLIC or PRIVATE.
        - namespace_id: The namespace id of this bookmark.
        - namespace_name: The namespace name of this bookmark.
        - is_replica: Is this a replicated bookmark.
        - primary_object_id: Id of the parent bookmark from which this bookmark was re...
        - primary_engine_id: The ID of the parent engine from which replication was done.
        - primary_engine_name: The name of the parent engine from which replication was ...
        - replicas: The list of replicas replicated from this object.
        - tags: The tags to be created for this Bookmark.
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> bookmark_tool(action='search', limit=..., cursor=..., sort=...)
    
    ACTION: get
    ----------------------------------------
    Summary: Get a bookmark by ID.
    Method: GET
    Endpoint: /bookmarks/{bookmarkId}
    Required Parameters: bookmark_id
    
    Example:
        >>> bookmark_tool(action='get', bookmark_id='example-bookmark-123')
    
    ACTION: create
    ----------------------------------------
    Summary: Create a bookmark at the current time.
    Method: POST
    Endpoint: /bookmarks
    
    Example:
        >>> bookmark_tool(action='create')
    
    ACTION: update
    ----------------------------------------
    Summary: Update a bookmark
    Method: PATCH
    Endpoint: /bookmarks/{bookmarkId}
    Required Parameters: bookmark_id
    
    Example:
        >>> bookmark_tool(action='update', bookmark_id='example-bookmark-123')
    
    ACTION: delete
    ----------------------------------------
    Summary: Delete a bookmark.
    Method: DELETE
    Endpoint: /bookmarks/{bookmarkId}
    Required Parameters: bookmark_id
    
    Example:
        >>> bookmark_tool(action='delete', bookmark_id='example-bookmark-123')
    
    ACTION: get_vdb_groups
    ----------------------------------------
    Summary: List VDB Groups compatible with this bookmark.
    Method: GET
    Endpoint: /bookmarks/{bookmarkId}/vdb-groups
    Required Parameters: limit, cursor, sort, bookmark_id
    
    Example:
        >>> bookmark_tool(action='get_vdb_groups', limit=..., cursor=..., sort=..., bookmark_id='example-bookmark-123')
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, create, update, delete, get_vdb_groups
        bookmark_id (str): The unique identifier for the bookmark.
            [Required for: get, update, delete, get_vdb_groups]
        bookmark_type (str): Type of the bookmark, either PUBLIC or PRIVATE.
            [Optional for all actions]
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search, get_vdb_groups]
        expiration (str): The expiration for this Bookmark. Mutually exclusive with retain_forever.
            [Optional for all actions]
        filter_expression (str): Filter expression to narrow results (e.g., "name CONTAINS 'prod'")
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search, get_vdb_groups]
        name (str): The user-defined name of this bookmark.
            [Optional for all actions]
        retain_forever (bool): Indicates that the Bookmark should be retained forever.
            [Optional for all actions]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search, get_vdb_groups]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'search':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/bookmarks/search', params=params, json_body=body)
    elif action == 'get':
        if bookmark_id is None:
            return {'error': 'Missing required parameter: bookmark_id for action get'}
        endpoint = f'/bookmarks/{bookmark_id}'
        params = build_params()
        return make_api_request('GET', endpoint, params=params)
    elif action == 'create':
        params = build_params()
        return make_api_request('POST', '/bookmarks', params=params)
    elif action == 'update':
        if bookmark_id is None:
            return {'error': 'Missing required parameter: bookmark_id for action update'}
        endpoint = f'/bookmarks/{bookmark_id}'
        params = build_params()
        return make_api_request('PATCH', endpoint, params=params)
    elif action == 'delete':
        if bookmark_id is None:
            return {'error': 'Missing required parameter: bookmark_id for action delete'}
        endpoint = f'/bookmarks/{bookmark_id}'
        params = build_params()
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'get_vdb_groups':
        if bookmark_id is None:
            return {'error': 'Missing required parameter: bookmark_id for action get_vdb_groups'}
        endpoint = f'/bookmarks/{bookmark_id}/vdb-groups'
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        return make_api_request('GET', endpoint, params=params)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, create, update, delete, get_vdb_groups'}


def register_tools(app, dct_client):
    global client
    client = dct_client
    logger.info(f'Registering tools for dataset_endpoints...')
    try:
        logger.info(f'  Registering tool function: vdb_tool')
        app.add_tool(vdb_tool, name="vdb_tool")
        logger.info(f'  Registering tool function: vdb_group_tool')
        app.add_tool(vdb_group_tool, name="vdb_group_tool")
        logger.info(f'  Registering tool function: dsource_tool')
        app.add_tool(dsource_tool, name="dsource_tool")
        logger.info(f'  Registering tool function: snapshot_tool')
        app.add_tool(snapshot_tool, name="snapshot_tool")
        logger.info(f'  Registering tool function: bookmark_tool')
        app.add_tool(bookmark_tool, name="bookmark_tool")
    except Exception as e:
        logger.error(f'Error registering tools for dataset_endpoints: {e}')
    logger.info(f'Tools registration finished for dataset_endpoints.')
