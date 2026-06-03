from mcp.server.fastmcp import FastMCP
from typing import Dict,Any,Optional
from dct_mcp_server.core.decorators import log_tool_execution
from dct_mcp_server.config import get_confirmation_for_operation, requires_confirmation
from datetime import datetime, timezone
import asyncio
import logging

client = None
logger = logging.getLogger(__name__)

class _SafeDict(dict):
    """Returns '{key}' for missing keys so unresolvable placeholders stay readable."""
    def __missing__(self, key):
        return f"{{{key}}}"

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

def check_confirmation(method: str, api_path: str, action: str, tool_name: str, confirmed: bool = False, context: dict = None) -> Optional[Dict[str, Any]]:
    """Check if operation requires confirmation. Returns confirmation response or None if confirmed/not needed."""
    confirmation = get_confirmation_for_operation(method, api_path)

    if confirmation["level"] == "none":
        return None

    if confirmation.get("conditional"):
        level = confirmation["level"]
        threshold = confirmation.get("threshold_days")

        if level == "retention_check" and context and threshold is not None:
            retain_forever = context.get("retain_forever")
            expiration_date = context.get("expiration_date")

            if retain_forever:
                return None

            if expiration_date is not None:
                try:
                    exp = datetime.fromisoformat(str(expiration_date).replace("Z", "+00:00"))
                    days_until = (exp - datetime.now(timezone.utc)).days
                    if days_until > threshold:
                        return None
                    context = dict(context)
                    context["days"] = max(0, days_until)
                except (ValueError, TypeError):
                    pass

    if confirmed:
        return None

    message = confirmation.get("message", "Please confirm this operation.")
    if context:
        message = message.format_map(_SafeDict(context))

    return {
        "status": "confirmation_required",
        "confirmation_level": confirmation["level"],
        "confirmation_message": message,
        "action": action,
        "tool": tool_name,
        "api_path": api_path,
        "instructions": "STOP: You MUST display the confirmation_message to the user and wait for their EXPLICIT approval before re-calling with confirmed=True. Do NOT proceed without user consent."
    }

async def make_api_request(method: str, endpoint: str, params: dict = None, json_body: dict = None):
    """Utility function to make API requests with consistent parameter handling."""
    return await client.make_request(method, endpoint, params=params or {}, json=json_body)

def build_params(**kwargs):
    """Build parameters dictionary excluding None and empty string values."""
    return {k: v for k, v in kwargs.items() if v is not None and v != ''}

@log_tool_execution
async def vdb_tool(
    action: str,  # One of: search, get, start, stop, enable, disable, refresh_by_timestamp, refresh_by_snapshot, refresh_from_bookmark, rollback_by_timestamp, rollback_by_snapshot, rollback_from_bookmark, list_snapshots, list_bookmarks, get_tags, add_tags, delete_tags
    abort: Optional[bool] = None,
    attempt_cleanup: Optional[bool] = None,
    attempt_start: Optional[bool] = None,
    bookmark_id: Optional[str] = None,
    container_mode: Optional[bool] = None,
    cursor: Optional[str] = None,
    dataset_id: Optional[str] = None,
    filter_expression: Optional[str] = None,
    instances: Optional[list] = None,
    key: Optional[str] = None,
    limit: Optional[int] = 100,
    ownership_spec: Optional[str] = None,
    permission: Optional[str] = None,
    snapshot_id: Optional[str] = None,
    sort: Optional[str] = None,
    tags: Optional[list] = None,
    timeflow_id: Optional[str] = None,
    timestamp: Optional[str] = None,
    timestamp_in_database_timezone: Optional[str] = None,
    value: Optional[str] = None,
    vdb_id: Optional[str] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for VDB operations.
    
    This tool supports 17 actions: search, get, start, stop, enable, disable, refresh_by_timestamp, refresh_by_snapshot, refresh_from_bookmark, rollback_by_timestamp, rollback_by_snapshot, rollback_from_bookmark, list_snapshots, list_bookmarks, get_tags, add_tags, delete_tags
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search for VDBs.
    Method: POST
    Endpoint: /vdbs/search
    Required Parameters: limit, cursor, sort, permission
    Key Parameters (provide as applicable): filter_expression
    
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
        - cache_priority: When set to a value other than NORMAL (valid only for obj...
        - mssql_incremental_export_backup_frequency_minutes: Frequency in minutes for incremental export backups for V...
        - recycle_bin: Indicates whether the VDB is in recycle bin or not.
        - recycle_days: Number of days to retain VDB in the recycle bin before it...
        - recycle_bin_date: The date this VDB was moved to recycle bin.
        - recycle_bin_account_id: The ID of the account that moved this VDB to recycle bin.
        - truncate_log_on_checkpoint: True if configured to truncate log on checkpoint (ASE only).
        - durability_level: SAP ASE database durability level (ASE only).
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> vdb_tool(action='search', limit=..., cursor=..., sort=..., permission=..., filter_expression="name CONTAINS 'test'")
    
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
    Key Parameters (provide as applicable): instances
    
    Example:
        >>> vdb_tool(action='start', vdb_id='example-vdb-123', instances=...)
    
    ACTION: stop
    ----------------------------------------
    Summary: Stop a VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/stop
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): instances, abort
    
    Example:
        >>> vdb_tool(action='stop', vdb_id='example-vdb-123', instances=..., abort=...)
    
    ACTION: enable
    ----------------------------------------
    Summary: Enable a VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/enable
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): attempt_start, container_mode, ownership_spec
    
    Example:
        >>> vdb_tool(action='enable', vdb_id='example-vdb-123', attempt_start=..., container_mode=..., ownership_spec=...)
    
    ACTION: disable
    ----------------------------------------
    Summary: Disable a VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/disable
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): container_mode, attempt_cleanup
    
    Example:
        >>> vdb_tool(action='disable', vdb_id='example-vdb-123', container_mode=..., attempt_cleanup=...)
    
    ACTION: refresh_by_timestamp
    ----------------------------------------
    Summary: Refresh a VDB by timestamp.
    Method: POST
    Endpoint: /vdbs/{vdbId}/refresh_by_timestamp
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): timestamp, timestamp_in_database_timezone, timeflow_id, dataset_id
    
    Example:
        >>> vdb_tool(action='refresh_by_timestamp', vdb_id='example-vdb-123', timestamp=..., timestamp_in_database_timezone=..., timeflow_id='example-timeflow-123', dataset_id='example-dataset-123')
    
    ACTION: refresh_by_snapshot
    ----------------------------------------
    Summary: Refresh a VDB by snapshot.
    Method: POST
    Endpoint: /vdbs/{vdbId}/refresh_by_snapshot
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): snapshot_id
    
    Example:
        >>> vdb_tool(action='refresh_by_snapshot', vdb_id='example-vdb-123', snapshot_id='example-snapshot-123')
    
    ACTION: refresh_from_bookmark
    ----------------------------------------
    Summary: Refresh a VDB from bookmark with a single VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/refresh_from_bookmark
    Required Parameters: vdb_id, bookmark_id
    
    Example:
        >>> vdb_tool(action='refresh_from_bookmark', vdb_id='example-vdb-123', bookmark_id='example-bookmark-123')
    
    ACTION: rollback_by_timestamp
    ----------------------------------------
    Summary: Rollback a VDB by timestamp.
    Method: POST
    Endpoint: /vdbs/{vdbId}/rollback_by_timestamp
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): timestamp, timestamp_in_database_timezone, timeflow_id
    
    Example:
        >>> vdb_tool(action='rollback_by_timestamp', vdb_id='example-vdb-123', timestamp=..., timestamp_in_database_timezone=..., timeflow_id='example-timeflow-123')
    
    ACTION: rollback_by_snapshot
    ----------------------------------------
    Summary: Rollback a VDB by snapshot.
    Method: POST
    Endpoint: /vdbs/{vdbId}/rollback_by_snapshot
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): snapshot_id
    
    Example:
        >>> vdb_tool(action='rollback_by_snapshot', vdb_id='example-vdb-123', snapshot_id='example-snapshot-123')
    
    ACTION: rollback_from_bookmark
    ----------------------------------------
    Summary: Rollback a VDB from a bookmark with only the same VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/rollback_from_bookmark
    Required Parameters: vdb_id, bookmark_id
    
    Example:
        >>> vdb_tool(action='rollback_from_bookmark', vdb_id='example-vdb-123', bookmark_id='example-bookmark-123')
    
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
    
    ACTION: get_tags
    ----------------------------------------
    Summary: Get tags for a VDB.
    Method: GET
    Endpoint: /vdbs/{vdbId}/tags
    Required Parameters: vdb_id
    
    Example:
        >>> vdb_tool(action='get_tags', vdb_id='example-vdb-123')
    
    ACTION: add_tags
    ----------------------------------------
    Summary: Create tags for a VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/tags
    Required Parameters: vdb_id, tags
    
    Example:
        >>> vdb_tool(action='add_tags', vdb_id='example-vdb-123', tags=...)
    
    ACTION: delete_tags
    ----------------------------------------
    Summary: Delete tags for a VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/tags/delete
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> vdb_tool(action='delete_tags', vdb_id='example-vdb-123', tags=..., key=..., value=...)
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, start, stop, enable, disable, refresh_by_timestamp, refresh_by_snapshot, refresh_from_bookmark, rollback_by_timestamp, rollback_by_snapshot, rollback_from_bookmark, list_snapshots, list_bookmarks, get_tags, add_tags, delete_tags
    
      -- General parameters (all database types) --
        abort (bool): Whether to issue 'shutdown abort' to shutdown Oracle Virtual DB instances. (D...
            [Optional for all actions]
        attempt_cleanup (bool): Whether to attempt a cleanup of the VDB before the disable. (Default: True)
            [Optional for all actions]
        attempt_start (bool): Whether to attempt a startup of the VDB after the enable. (Default: True)
            [Optional for all actions]
        bookmark_id (str): The ID of the bookmark from which to execute the operation. The bookmark must...
            [Required for: refresh_from_bookmark, rollback_from_bookmark]
        container_mode (bool): Whether the database is running inside a container.
            [Optional for all actions]
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search, list_snapshots, list_bookmarks]
        dataset_id (str): ID of the dataset to refresh to, mutually exclusive with timeflow_id.
            [Optional for all actions]
        filter_expression (str): Request body parameter
            [Optional for all actions]
        instances (list): List of specific Oracle Virtual Database Instances to start. (Pass as JSON ar...
            [Optional for all actions]
        key (str): Key of the tag
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search, list_snapshots, list_bookmarks]
        ownership_spec (str): The uid:gid string that NFS mounts should belong to.
            [Optional for all actions]
        permission (str): Restrict the objects, which are allowed.
            [Required for: search]
        snapshot_id (str): The ID of the snapshot from which to execute the operation. If the snapshot_i...
            [Optional for all actions]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search, list_bookmarks]
        tags (list): Array of tags with key value pairs (Pass as JSON array)
            [Required for: add_tags]
        timeflow_id (str): ID of the timeflow to refresh to, mutually exclusive with dataset_id.
            [Optional for all actions]
        timestamp (str): The point in time from which to execute the operation. Mutually exclusive wit...
            [Optional for all actions]
        timestamp_in_database_timezone (str): The point in time from which to execute the operation, expressed as a date-ti...
            [Optional for all actions]
        value (str): Value of the tag
            [Optional for all actions]
        vdb_id (str): The unique identifier for the vdb.
            [Required for: get, start, stop, enable, disable, refresh_by_timestamp, refresh_by_snapshot, refresh_from_bookmark, rollback_by_timestamp, rollback_by_snapshot, rollback_from_bookmark, list_snapshots, list_bookmarks, get_tags, add_tags, delete_tags]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'search':
        params = build_params(limit=limit, cursor=cursor, sort=sort, permission=permission)
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', '/vdbs/search', action, 'vdb_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return await make_api_request('POST', '/vdbs/search', params=params, json_body=body)
    elif action == 'get':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action get'}
        endpoint = f'/vdbs/{vdb_id}'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('GET', endpoint, action, 'vdb_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('GET', endpoint, params=params)
    elif action == 'start':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action start'}
        endpoint = f'/vdbs/{vdb_id}/start'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'instances': instances}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'stop':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action stop'}
        endpoint = f'/vdbs/{vdb_id}/stop'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'instances': instances, 'abort': abort}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'enable':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action enable'}
        endpoint = f'/vdbs/{vdb_id}/enable'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'attempt_start': attempt_start, 'container_mode': container_mode, 'ownership_spec': ownership_spec}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'disable':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action disable'}
        endpoint = f'/vdbs/{vdb_id}/disable'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'attempt_cleanup': attempt_cleanup, 'container_mode': container_mode}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'refresh_by_timestamp':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action refresh_by_timestamp'}
        endpoint = f'/vdbs/{vdb_id}/refresh_by_timestamp'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'timestamp': timestamp, 'timestamp_in_database_timezone': timestamp_in_database_timezone, 'timeflow_id': timeflow_id, 'dataset_id': dataset_id}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'refresh_by_snapshot':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action refresh_by_snapshot'}
        endpoint = f'/vdbs/{vdb_id}/refresh_by_snapshot'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'snapshot_id': snapshot_id}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'refresh_from_bookmark':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action refresh_from_bookmark'}
        endpoint = f'/vdbs/{vdb_id}/refresh_from_bookmark'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'bookmark_id': bookmark_id}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'rollback_by_timestamp':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action rollback_by_timestamp'}
        endpoint = f'/vdbs/{vdb_id}/rollback_by_timestamp'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'timestamp': timestamp, 'timestamp_in_database_timezone': timestamp_in_database_timezone, 'timeflow_id': timeflow_id}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'rollback_by_snapshot':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action rollback_by_snapshot'}
        endpoint = f'/vdbs/{vdb_id}/rollback_by_snapshot'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'snapshot_id': snapshot_id}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'rollback_from_bookmark':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action rollback_from_bookmark'}
        endpoint = f'/vdbs/{vdb_id}/rollback_from_bookmark'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'bookmark_id': bookmark_id}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'list_snapshots':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action list_snapshots'}
        endpoint = f'/vdbs/{vdb_id}/snapshots'
        params = build_params(limit=limit, cursor=cursor)
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('GET', endpoint, action, 'vdb_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('GET', endpoint, params=params)
    elif action == 'list_bookmarks':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action list_bookmarks'}
        endpoint = f'/vdbs/{vdb_id}/bookmarks'
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('GET', endpoint, action, 'vdb_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('GET', endpoint, params=params)
    elif action == 'get_tags':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action get_tags'}
        endpoint = f'/vdbs/{vdb_id}/tags'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('GET', endpoint, action, 'vdb_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('GET', endpoint, params=params)
    elif action == 'add_tags':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action add_tags'}
        endpoint = f'/vdbs/{vdb_id}/tags'
        params = build_params(tags=tags)
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_tags':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action delete_tags'}
        endpoint = f'/vdbs/{vdb_id}/tags/delete'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, start, stop, enable, disable, refresh_by_timestamp, refresh_by_snapshot, refresh_from_bookmark, rollback_by_timestamp, rollback_by_snapshot, rollback_from_bookmark, list_snapshots, list_bookmarks, get_tags, add_tags, delete_tags'}

@log_tool_execution
async def vdb_group_tool(
    action: str,  # One of: search, get, refresh, refresh_from_bookmark, refresh_by_snapshot, refresh_by_timestamp, rollback, lock, unlock, start, stop, enable, disable, list_bookmarks, get_tags, add_tags, delete_tags
    account_id: Optional[int] = None,
    bookmark_id: Optional[str] = None,
    cursor: Optional[str] = None,
    filter_expression: Optional[str] = None,
    is_refresh_to_nearest: Optional[bool] = None,
    key: Optional[str] = None,
    limit: Optional[int] = 100,
    sort: Optional[str] = None,
    tags: Optional[list] = None,
    value: Optional[str] = None,
    vdb_disable_param_mappings: Optional[list] = None,
    vdb_enable_param_mappings: Optional[list] = None,
    vdb_group_id: Optional[str] = None,
    vdb_snapshot_mappings: Optional[list] = None,
    vdb_start_param_mappings: Optional[list] = None,
    vdb_stop_param_mappings: Optional[list] = None,
    vdb_timestamp_mappings: Optional[list] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for VDB GROUP operations.
    
    This tool supports 17 actions: search, get, refresh, refresh_from_bookmark, refresh_by_snapshot, refresh_by_timestamp, rollback, lock, unlock, start, stop, enable, disable, list_bookmarks, get_tags, add_tags, delete_tags
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search for VDB Groups.
    Method: POST
    Endpoint: /vdb-groups/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
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
        >>> vdb_group_tool(action='search', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
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
    Key Parameters (provide as applicable): vdb_snapshot_mappings
    
    Example:
        >>> vdb_group_tool(action='refresh_by_snapshot', vdb_group_id='example-vdb_group-123', vdb_snapshot_mappings=...)
    
    ACTION: refresh_by_timestamp
    ----------------------------------------
    Summary: Refresh a VDB Group by timestamp.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/refresh_by_timestamp
    Required Parameters: vdb_group_id
    Key Parameters (provide as applicable): vdb_timestamp_mappings, is_refresh_to_nearest
    
    Example:
        >>> vdb_group_tool(action='refresh_by_timestamp', vdb_group_id='example-vdb_group-123', vdb_timestamp_mappings=..., is_refresh_to_nearest=...)
    
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
    Key Parameters (provide as applicable): account_id
    
    Example:
        >>> vdb_group_tool(action='lock', vdb_group_id='example-vdb_group-123', account_id='example-account-123')
    
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
    Key Parameters (provide as applicable): vdb_start_param_mappings
    
    Example:
        >>> vdb_group_tool(action='start', vdb_group_id='example-vdb_group-123', vdb_start_param_mappings=...)
    
    ACTION: stop
    ----------------------------------------
    Summary: Stop a VDB Group.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/stop
    Required Parameters: vdb_group_id
    Key Parameters (provide as applicable): vdb_stop_param_mappings
    
    Example:
        >>> vdb_group_tool(action='stop', vdb_group_id='example-vdb_group-123', vdb_stop_param_mappings=...)
    
    ACTION: enable
    ----------------------------------------
    Summary: Enable a VDB Group.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/enable
    Required Parameters: vdb_group_id
    Key Parameters (provide as applicable): vdb_enable_param_mappings
    
    Example:
        >>> vdb_group_tool(action='enable', vdb_group_id='example-vdb_group-123', vdb_enable_param_mappings=...)
    
    ACTION: disable
    ----------------------------------------
    Summary: Disable a VDB Group.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/disable
    Required Parameters: vdb_group_id
    Key Parameters (provide as applicable): vdb_disable_param_mappings
    
    Example:
        >>> vdb_group_tool(action='disable', vdb_group_id='example-vdb_group-123', vdb_disable_param_mappings=...)
    
    ACTION: list_bookmarks
    ----------------------------------------
    Summary: List bookmarks compatible with this VDB Group.
    Method: GET
    Endpoint: /vdb-groups/{vdbGroupId}/bookmarks
    Required Parameters: limit, cursor, sort, vdb_group_id
    
    Example:
        >>> vdb_group_tool(action='list_bookmarks', limit=..., cursor=..., sort=..., vdb_group_id='example-vdb_group-123')
    
    ACTION: get_tags
    ----------------------------------------
    Summary: Get tags for a VDB Group.
    Method: GET
    Endpoint: /vdb-groups/{vdbGroupId}/tags
    Required Parameters: vdb_group_id
    
    Example:
        >>> vdb_group_tool(action='get_tags', vdb_group_id='example-vdb_group-123')
    
    ACTION: add_tags
    ----------------------------------------
    Summary: Create tags for a VDB Group.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/tags
    Required Parameters: vdb_group_id, tags
    
    Example:
        >>> vdb_group_tool(action='add_tags', vdb_group_id='example-vdb_group-123', tags=...)
    
    ACTION: delete_tags
    ----------------------------------------
    Summary: Delete tags for a VDB Group.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/tags/delete
    Required Parameters: vdb_group_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> vdb_group_tool(action='delete_tags', vdb_group_id='example-vdb_group-123', tags=..., key=..., value=...)
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, refresh, refresh_from_bookmark, refresh_by_snapshot, refresh_by_timestamp, rollback, lock, unlock, start, stop, enable, disable, list_bookmarks, get_tags, add_tags, delete_tags
    
      -- General parameters (all database types) --
        account_id (int): Id of the account on whose behalf this request is being made. Only accounts h...
            [Optional for all actions]
        bookmark_id (str): ID of a bookmark to refresh this VDB Group to.
            [Required for: refresh, refresh_from_bookmark, rollback]
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search, list_bookmarks]
        filter_expression (str): Request body parameter
            [Optional for all actions]
        is_refresh_to_nearest (bool): If true, and the provided timestamp is not found for the VDB mapping, the sys...
            [Optional for all actions]
        key (str): Key of the tag
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search, list_bookmarks]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search, list_bookmarks]
        tags (list): Array of tags with key value pairs (Pass as JSON array)
            [Required for: add_tags]
        value (str): Value of the tag
            [Optional for all actions]
        vdb_disable_param_mappings (list): Request body parameter (Pass as JSON array)
            [Optional for all actions]
        vdb_enable_param_mappings (list): Request body parameter (Pass as JSON array)
            [Optional for all actions]
        vdb_group_id (str): The unique identifier for the vdbGroup.
            [Required for: get, refresh, refresh_from_bookmark, refresh_by_snapshot, refresh_by_timestamp, rollback, lock, unlock, start, stop, enable, disable, list_bookmarks, get_tags, add_tags, delete_tags]
        vdb_snapshot_mappings (list): List of the pair of VDB and snapshot to refresh from. If this is not set, all...
            [Optional for all actions]
        vdb_start_param_mappings (list): Request body parameter (Pass as JSON array)
            [Optional for all actions]
        vdb_stop_param_mappings (list): Request body parameter (Pass as JSON array)
            [Optional for all actions]
        vdb_timestamp_mappings (list): List of the pair of VDB and timestamp to refresh from. If this is not set, al...
            [Optional for all actions]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'search':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', '/vdb-groups/search', action, 'vdb_group_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return await make_api_request('POST', '/vdb-groups/search', params=params, json_body=body)
    elif action == 'get':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action get'}
        endpoint = f'/vdb-groups/{vdb_group_id}'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('GET', endpoint, action, 'vdb_group_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('GET', endpoint, params=params)
    elif action == 'refresh':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action refresh'}
        endpoint = f'/vdb-groups/{vdb_group_id}/refresh'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_group_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'bookmark_id': bookmark_id}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'refresh_from_bookmark':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action refresh_from_bookmark'}
        endpoint = f'/vdb-groups/{vdb_group_id}/refresh_from_bookmark'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_group_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'bookmark_id': bookmark_id}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'refresh_by_snapshot':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action refresh_by_snapshot'}
        endpoint = f'/vdb-groups/{vdb_group_id}/refresh_by_snapshot'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_group_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'vdb_snapshot_mappings': vdb_snapshot_mappings}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'refresh_by_timestamp':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action refresh_by_timestamp'}
        endpoint = f'/vdb-groups/{vdb_group_id}/refresh_by_timestamp'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_group_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'vdb_timestamp_mappings': vdb_timestamp_mappings, 'is_refresh_to_nearest': is_refresh_to_nearest}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'rollback':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action rollback'}
        endpoint = f'/vdb-groups/{vdb_group_id}/rollback'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_group_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'bookmark_id': bookmark_id}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'lock':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action lock'}
        endpoint = f'/vdb-groups/{vdb_group_id}/lock'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_group_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'account_id': account_id}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'unlock':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action unlock'}
        endpoint = f'/vdb-groups/{vdb_group_id}/unlock'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_group_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('POST', endpoint, params=params)
    elif action == 'start':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action start'}
        endpoint = f'/vdb-groups/{vdb_group_id}/start'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_group_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'vdb_start_param_mappings': vdb_start_param_mappings}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'stop':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action stop'}
        endpoint = f'/vdb-groups/{vdb_group_id}/stop'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_group_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'vdb_stop_param_mappings': vdb_stop_param_mappings}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'enable':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action enable'}
        endpoint = f'/vdb-groups/{vdb_group_id}/enable'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_group_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'vdb_enable_param_mappings': vdb_enable_param_mappings}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'disable':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action disable'}
        endpoint = f'/vdb-groups/{vdb_group_id}/disable'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_group_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'vdb_disable_param_mappings': vdb_disable_param_mappings}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'list_bookmarks':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action list_bookmarks'}
        endpoint = f'/vdb-groups/{vdb_group_id}/bookmarks'
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('GET', endpoint, action, 'vdb_group_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('GET', endpoint, params=params)
    elif action == 'get_tags':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action get_tags'}
        endpoint = f'/vdb-groups/{vdb_group_id}/tags'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('GET', endpoint, action, 'vdb_group_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('GET', endpoint, params=params)
    elif action == 'add_tags':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action add_tags'}
        endpoint = f'/vdb-groups/{vdb_group_id}/tags'
        params = build_params(tags=tags)
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_group_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_tags':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action delete_tags'}
        endpoint = f'/vdb-groups/{vdb_group_id}/tags/delete'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'vdb_group_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, refresh, refresh_from_bookmark, refresh_by_snapshot, refresh_by_timestamp, rollback, lock, unlock, start, stop, enable, disable, list_bookmarks, get_tags, add_tags, delete_tags'}

@log_tool_execution
async def dsource_tool(
    action: str,  # One of: search, get, list_snapshots, get_tags
    cursor: Optional[str] = None,
    dsource_id: Optional[str] = None,
    filter_expression: Optional[str] = None,
    limit: Optional[int] = 100,
    permission: Optional[str] = None,
    sort: Optional[str] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for DSOURCE operations.
    
    This tool supports 4 actions: search, get, list_snapshots, get_tags
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search for dSources.
    Method: POST
    Endpoint: /dsources/search
    Required Parameters: limit, cursor, sort, permission
    Key Parameters (provide as applicable): filter_expression
    
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
        - excludes: List of subdirectories in the source to exclude when sync...
        - follow_symlinks: List of symlinks in the source to follow when syncing dat...
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
        - truncate_log_on_checkpoint: True if configured to truncate log on checkpoint (ASE only).
        - durability_level: SAP ASE database durability level (ASE only).
        - external_file_path: ASE External file path.
        - load_backup_path: ASE Source database backup location.
        - validated_sync_enabled: True if ASE validated sync mode is set to ENABLED
        - dump_history_file_enabled: Specifies if Dump History File is enabled for backup hist...
        - source_of_production_backup: Denotes whether it's a remote backup server or staging ba...
        - backup_password_set: True if ASE dump is password protected.
        - backup_server_name: Name of the ASE backup server instance.
        - backup_host: Host environment where the ASE backup server is located.
        - backup_host_user: OS user for the host where the ASE backup server is located.
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> dsource_tool(action='search', limit=..., cursor=..., sort=..., permission=..., filter_expression="name CONTAINS 'test'")
    
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
    
    ACTION: get_tags
    ----------------------------------------
    Summary: Get tags for a dSource.
    Method: GET
    Endpoint: /dsources/{dsourceId}/tags
    Required Parameters: dsource_id
    
    Example:
        >>> dsource_tool(action='get_tags', dsource_id='example-dsource-123')
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, list_snapshots, get_tags
    
      -- General parameters (all database types) --
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search, list_snapshots]
        dsource_id (str): The unique identifier for the dsource.
            [Required for: get, list_snapshots, get_tags]
        filter_expression (str): Request body parameter
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
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', '/dsources/search', action, 'dsource_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return await make_api_request('POST', '/dsources/search', params=params, json_body=body)
    elif action == 'get':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action get'}
        endpoint = f'/dsources/{dsource_id}'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('GET', endpoint, action, 'dsource_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('GET', endpoint, params=params)
    elif action == 'list_snapshots':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action list_snapshots'}
        endpoint = f'/dsources/{dsource_id}/snapshots'
        params = build_params(limit=limit, cursor=cursor)
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('GET', endpoint, action, 'dsource_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('GET', endpoint, params=params)
    elif action == 'get_tags':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action get_tags'}
        endpoint = f'/dsources/{dsource_id}/tags'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('GET', endpoint, action, 'dsource_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('GET', endpoint, params=params)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, list_snapshots, get_tags'}

@log_tool_execution
async def snapshot_tool(
    action: str,  # One of: search, get, get_timeflow_range, get_runtime, find_by_location, find_by_timestamp, get_tags, add_tags, delete_tags
    cursor: Optional[str] = None,
    filter_expression: Optional[str] = None,
    key: Optional[str] = None,
    limit: Optional[int] = 100,
    snapshot_id: Optional[str] = None,
    sort: Optional[str] = None,
    tags: Optional[list] = None,
    value: Optional[str] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for SNAPSHOT operations.
    
    This tool supports 9 actions: search, get, get_timeflow_range, get_runtime, find_by_location, find_by_timestamp, get_tags, add_tags, delete_tags
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search snapshots.
    Method: POST
    Endpoint: /snapshots/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
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
        - mssql_incremental_export_source_snapshot: True if this snapshot belongs to Incremental VDB and can ...
        - oracle_from_physical_standby_vdb: True if this snapshot was taken of a standby database.
        - oracle_redo_log_size_in_bytes: Online redo log size in bytes when this snapshot was taken.
        - tags: 
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> snapshot_tool(action='search', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
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
    
    ACTION: find_by_location
    ----------------------------------------
    Summary: Get the snapshots at this location for a dataset.
    Method: GET
    Endpoint: /snapshots/find_by_location
    
    Example:
        >>> snapshot_tool(action='find_by_location')
    
    ACTION: find_by_timestamp
    ----------------------------------------
    Summary: Get the snapshots at this timestamp for a dataset.
    Method: GET
    Endpoint: /snapshots/find_by_timestamp
    
    Example:
        >>> snapshot_tool(action='find_by_timestamp')
    
    ACTION: get_tags
    ----------------------------------------
    Summary: Get tags for a Snapshot.
    Method: GET
    Endpoint: /snapshots/{snapshotId}/tags
    Required Parameters: snapshot_id
    
    Example:
        >>> snapshot_tool(action='get_tags', snapshot_id='example-snapshot-123')
    
    ACTION: add_tags
    ----------------------------------------
    Summary: Create tags for a Snapshot.
    Method: POST
    Endpoint: /snapshots/{snapshotId}/tags
    Required Parameters: snapshot_id, tags
    
    Example:
        >>> snapshot_tool(action='add_tags', snapshot_id='example-snapshot-123', tags=...)
    
    ACTION: delete_tags
    ----------------------------------------
    Summary: Delete tags for a Snapshot.
    Method: POST
    Endpoint: /snapshots/{snapshotId}/tags/delete
    Required Parameters: snapshot_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> snapshot_tool(action='delete_tags', snapshot_id='example-snapshot-123', tags=..., key=..., value=...)
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, get_timeflow_range, get_runtime, find_by_location, find_by_timestamp, get_tags, add_tags, delete_tags
    
      -- General parameters (all database types) --
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search]
        filter_expression (str): Request body parameter
            [Optional for all actions]
        key (str): Key of the tag
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search]
        snapshot_id (str): The unique identifier for the snapshot.
            [Required for: get, get_timeflow_range, get_runtime, get_tags, add_tags, delete_tags]
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
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', '/snapshots/search', action, 'snapshot_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return await make_api_request('POST', '/snapshots/search', params=params, json_body=body)
    elif action == 'get':
        if snapshot_id is None:
            return {'error': 'Missing required parameter: snapshot_id for action get'}
        endpoint = f'/snapshots/{snapshot_id}'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('GET', endpoint, action, 'snapshot_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('GET', endpoint, params=params)
    elif action == 'get_timeflow_range':
        if snapshot_id is None:
            return {'error': 'Missing required parameter: snapshot_id for action get_timeflow_range'}
        endpoint = f'/snapshots/{snapshot_id}/timeflow_range'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('GET', endpoint, action, 'snapshot_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('GET', endpoint, params=params)
    elif action == 'get_runtime':
        if snapshot_id is None:
            return {'error': 'Missing required parameter: snapshot_id for action get_runtime'}
        endpoint = f'/snapshots/{snapshot_id}/runtime'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('GET', endpoint, action, 'snapshot_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('GET', endpoint, params=params)
    elif action == 'find_by_location':
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('GET', '/snapshots/find_by_location', action, 'snapshot_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('GET', '/snapshots/find_by_location', params=params)
    elif action == 'find_by_timestamp':
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('GET', '/snapshots/find_by_timestamp', action, 'snapshot_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('GET', '/snapshots/find_by_timestamp', params=params)
    elif action == 'get_tags':
        if snapshot_id is None:
            return {'error': 'Missing required parameter: snapshot_id for action get_tags'}
        endpoint = f'/snapshots/{snapshot_id}/tags'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('GET', endpoint, action, 'snapshot_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('GET', endpoint, params=params)
    elif action == 'add_tags':
        if snapshot_id is None:
            return {'error': 'Missing required parameter: snapshot_id for action add_tags'}
        endpoint = f'/snapshots/{snapshot_id}/tags'
        params = build_params(tags=tags)
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'snapshot_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_tags':
        if snapshot_id is None:
            return {'error': 'Missing required parameter: snapshot_id for action delete_tags'}
        endpoint = f'/snapshots/{snapshot_id}/tags/delete'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'snapshot_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, get_timeflow_range, get_runtime, find_by_location, find_by_timestamp, get_tags, add_tags, delete_tags'}

@log_tool_execution
async def bookmark_tool(
    action: str,  # One of: search, get, create, update, delete, get_vdb_groups, get_tags, add_tags, delete_tags
    bookmark_id: Optional[str] = None,
    bookmark_type: Optional[str] = None,
    cursor: Optional[str] = None,
    expiration: Optional[str] = None,
    filter_expression: Optional[str] = None,
    inherit_parent_tags: Optional[bool] = None,
    inherit_parent_vdb_tags: Optional[bool] = None,
    key: Optional[str] = None,
    limit: Optional[int] = 100,
    location: Optional[str] = None,
    make_current_account_owner: Optional[bool] = None,
    name: Optional[str] = None,
    paas_database_ids: Optional[list] = None,
    paas_instance_ids: Optional[list] = None,
    paas_snapshot_ids: Optional[list] = None,
    retain_forever: Optional[bool] = None,
    retention: Optional[int] = None,
    snapshot_ids: Optional[list] = None,
    sort: Optional[str] = None,
    tags: Optional[list] = None,
    timeflow_ids: Optional[list] = None,
    timestamp: Optional[str] = None,
    timestamp_in_database_timezone: Optional[str] = None,
    value: Optional[str] = None,
    vdb_group_id: Optional[str] = None,
    vdb_ids: Optional[list] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for BOOKMARK operations.
    
    This tool supports 9 actions: search, get, create, update, delete, get_vdb_groups, get_tags, add_tags, delete_tags
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search for bookmarks.
    Method: POST
    Endpoint: /bookmarks/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
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
        - paas_databases: The list of PaaS Database IDs and PaaS Database names ass...
        - paas_instances: The list of PaaS Instance IDs and PaaS Instance names ass...
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
        - primary_bookmark_expiration: The expiration for the primary bookmark.
        - replicas: The list of replicas replicated from this object.
        - tags: The tags to be created for this Bookmark.
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> bookmark_tool(action='search', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
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
    Required Parameters: name
    Key Parameters (provide as applicable): vdb_ids, vdb_group_id, snapshot_ids, timeflow_ids, timestamp, timestamp_in_database_timezone, location, paas_snapshot_ids, paas_database_ids, paas_instance_ids, retention, expiration, retain_forever, tags, bookmark_type, make_current_account_owner, inherit_parent_vdb_tags, inherit_parent_tags
    
    Example:
        >>> bookmark_tool(action='create', name=..., vdb_ids=..., vdb_group_id='example-vdb_group-123', snapshot_ids=..., timeflow_ids=..., timestamp=..., timestamp_in_database_timezone=..., location=..., paas_snapshot_ids=..., paas_database_ids=..., paas_instance_ids=..., retention=..., expiration=..., retain_forever=..., tags=..., bookmark_type=..., make_current_account_owner=..., inherit_parent_vdb_tags=..., inherit_parent_tags=...)
    
    ACTION: update
    ----------------------------------------
    Summary: Update a bookmark
    Method: PATCH
    Endpoint: /bookmarks/{bookmarkId}
    Required Parameters: bookmark_id
    Key Parameters (provide as applicable): name, expiration, retain_forever, bookmark_type
    
    Example:
        >>> bookmark_tool(action='update', bookmark_id='example-bookmark-123', name=..., expiration=..., retain_forever=..., bookmark_type=...)
    
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
    
    ACTION: get_tags
    ----------------------------------------
    Summary: Get tags for a Bookmark.
    Method: GET
    Endpoint: /bookmarks/{bookmarkId}/tags
    Required Parameters: bookmark_id
    
    Example:
        >>> bookmark_tool(action='get_tags', bookmark_id='example-bookmark-123')
    
    ACTION: add_tags
    ----------------------------------------
    Summary: Create tags for a Bookmark.
    Method: POST
    Endpoint: /bookmarks/{bookmarkId}/tags
    Required Parameters: bookmark_id, tags
    
    Example:
        >>> bookmark_tool(action='add_tags', bookmark_id='example-bookmark-123', tags=...)
    
    ACTION: delete_tags
    ----------------------------------------
    Summary: Delete tags for a Bookmark.
    Method: POST
    Endpoint: /bookmarks/{bookmarkId}/tags/delete
    Required Parameters: bookmark_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> bookmark_tool(action='delete_tags', bookmark_id='example-bookmark-123', tags=..., key=..., value=...)
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, create, update, delete, get_vdb_groups, get_tags, add_tags, delete_tags
    
      -- General parameters (all database types) --
        bookmark_id (str): The unique identifier for the bookmark.
            [Required for: get, update, delete, get_vdb_groups, get_tags, add_tags, delete_tags]
        bookmark_type (str): Type of the bookmark, either PUBLIC or PRIVATE. Valid values: PUBLIC, PRIVATE...
            [Optional for all actions]
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search, get_vdb_groups]
        expiration (str): The expiration for this bookmark. Mutually exclusive with retention and retai...
            [Optional for all actions]
        filter_expression (str): Request body parameter
            [Optional for all actions]
        inherit_parent_tags (bool): Whether this bookmark should inherit tags from the parent dataset. (Default: ...
            [Optional for all actions]
        inherit_parent_vdb_tags (bool): This field has been deprecated in favour of new field 'inherit_parent_tags'. ...
            [Optional for all actions]
        key (str): Key of the tag
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search, get_vdb_groups]
        location (str): The location to create bookmark from. Mutually exclusive with snapshot_ids, t...
            [Optional for all actions]
        make_current_account_owner (bool): Whether the account creating this bookmark must be configured as owner of the...
            [Optional for all actions]
        name (str): The user-defined name of this bookmark.
            [Required for: create]
        paas_database_ids (list): The IDs of the PaaS Database associated with the PaaS snapshot. This paramete...
            [Optional for all actions]
        paas_instance_ids (list): The IDs of the PaaS Instance associated with the PaaS Database. This paramete...
            [Optional for all actions]
        paas_snapshot_ids (list): The IDs of the PaaS snapshot to create the Bookmark on. This parameter is mut...
            [Optional for all actions]
        retain_forever (bool): Indicates that the bookmark should be retained forever.
            [Optional for all actions]
        retention (int): The retention policy for this bookmark, in days. A value of -1 indicates the ...
            [Optional for all actions]
        snapshot_ids (list): The IDs of the snapshots that will be part of the Bookmark. This parameter is...
            [Optional for all actions]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search, get_vdb_groups]
        tags (list): The tags to be created for this Bookmark. (Pass as JSON array)
            [Required for: add_tags]
        timeflow_ids (list): The array of timeflow Id. Only allowed to set when timestamp, timestamp_in_da...
            [Optional for all actions]
        timestamp (str): The point in time from which to execute the operation. Mutually exclusive wit...
            [Optional for all actions]
        timestamp_in_database_timezone (str): The point in time from which to execute the operation, expressed as a date-ti...
            [Optional for all actions]
        value (str): Value of the tag
            [Optional for all actions]
        vdb_group_id (str): The ID of the VDB group to create the Bookmark on. This parameter is mutually...
            [Optional for all actions]
        vdb_ids (list): The IDs of the VDBs to create the Bookmark on. This parameter is mutually exc...
            [Optional for all actions]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'search':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', '/bookmarks/search', action, 'bookmark_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return await make_api_request('POST', '/bookmarks/search', params=params, json_body=body)
    elif action == 'get':
        if bookmark_id is None:
            return {'error': 'Missing required parameter: bookmark_id for action get'}
        endpoint = f'/bookmarks/{bookmark_id}'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('GET', endpoint, action, 'bookmark_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('GET', endpoint, params=params)
    elif action == 'create':
        params = build_params(name=name)
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', '/bookmarks', action, 'bookmark_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name, 'vdb_ids': vdb_ids, 'vdb_group_id': vdb_group_id, 'snapshot_ids': snapshot_ids, 'timeflow_ids': timeflow_ids, 'timestamp': timestamp, 'timestamp_in_database_timezone': timestamp_in_database_timezone, 'location': location, 'paas_snapshot_ids': paas_snapshot_ids, 'paas_database_ids': paas_database_ids, 'paas_instance_ids': paas_instance_ids, 'retention': retention, 'expiration': expiration, 'retain_forever': retain_forever, 'tags': tags, 'bookmark_type': bookmark_type, 'make_current_account_owner': make_current_account_owner, 'inherit_parent_vdb_tags': inherit_parent_vdb_tags, 'inherit_parent_tags': inherit_parent_tags}.items() if v is not None}
        return await make_api_request('POST', '/bookmarks', params=params, json_body=body if body else None)
    elif action == 'update':
        if bookmark_id is None:
            return {'error': 'Missing required parameter: bookmark_id for action update'}
        endpoint = f'/bookmarks/{bookmark_id}'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('PATCH', endpoint, action, 'bookmark_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name, 'expiration': expiration, 'retain_forever': retain_forever, 'bookmark_type': bookmark_type}.items() if v is not None}
        return await make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete':
        if bookmark_id is None:
            return {'error': 'Missing required parameter: bookmark_id for action delete'}
        endpoint = f'/bookmarks/{bookmark_id}'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('DELETE', endpoint, action, 'bookmark_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('DELETE', endpoint, params=params)
    elif action == 'get_vdb_groups':
        if bookmark_id is None:
            return {'error': 'Missing required parameter: bookmark_id for action get_vdb_groups'}
        endpoint = f'/bookmarks/{bookmark_id}/vdb-groups'
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('GET', endpoint, action, 'bookmark_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('GET', endpoint, params=params)
    elif action == 'get_tags':
        if bookmark_id is None:
            return {'error': 'Missing required parameter: bookmark_id for action get_tags'}
        endpoint = f'/bookmarks/{bookmark_id}/tags'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('GET', endpoint, action, 'bookmark_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('GET', endpoint, params=params)
    elif action == 'add_tags':
        if bookmark_id is None:
            return {'error': 'Missing required parameter: bookmark_id for action add_tags'}
        endpoint = f'/bookmarks/{bookmark_id}/tags'
        params = build_params(tags=tags)
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'bookmark_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_tags':
        if bookmark_id is None:
            return {'error': 'Missing required parameter: bookmark_id for action delete_tags'}
        endpoint = f'/bookmarks/{bookmark_id}/tags/delete'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'bookmark_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, create, update, delete, get_vdb_groups, get_tags, add_tags, delete_tags'}

@log_tool_execution
async def timeflow_tool(
    action: str,  # One of: list, search, get, update, delete, get_snapshot_day_range, repair, get_tags, add_tags, delete_tags
    azure_vault_name: Optional[str] = None,
    azure_vault_secret_key: Optional[str] = None,
    azure_vault_username_key: Optional[str] = None,
    cursor: Optional[str] = None,
    cyberark_vault_query_string: Optional[str] = None,
    directory: Optional[str] = None,
    end_location: Optional[str] = None,
    filter_expression: Optional[str] = None,
    hashicorp_vault_engine: Optional[str] = None,
    hashicorp_vault_secret_key: Optional[str] = None,
    hashicorp_vault_secret_path: Optional[str] = None,
    hashicorp_vault_username_key: Optional[str] = None,
    host: Optional[str] = None,
    key: Optional[str] = None,
    key_pair_private_key: Optional[str] = None,
    key_pair_public_key: Optional[str] = None,
    limit: Optional[int] = 100,
    name: Optional[str] = None,
    password: Optional[str] = None,
    port: Optional[int] = None,
    sort: Optional[str] = None,
    ssh_verification_strategy: Optional[str] = None,
    start_location: Optional[str] = None,
    tags: Optional[list] = None,
    timeflow_id: Optional[str] = None,
    use_engine_public_key: Optional[bool] = None,
    use_kerberos_authentication: Optional[bool] = None,
    username: Optional[str] = None,
    value: Optional[str] = None,
    vault_id: Optional[str] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for TIMEFLOW operations.
    
    This tool supports 10 actions: list, search, get, update, delete, get_snapshot_day_range, repair, get_tags, add_tags, delete_tags
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: list
    ----------------------------------------
    Summary: Retrieve the list of timeflows.
    Method: GET
    Endpoint: /timeflows
    Required Parameters: limit, cursor, sort
    
    Example:
        >>> timeflow_tool(action='list', limit=..., cursor=..., sort=...)
    
    ACTION: search
    ----------------------------------------
    Summary: Search timeflows.
    Method: POST
    Endpoint: /timeflows/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - id: The Timeflow ID.
        - engine_id: The ID of the engine the timeflow belongs to.
        - namespace: Alternate namespace for this object, for replicated and r...
        - namespace_id: The namespace id of this timeflows.
        - namespace_name: The namespace name of this timeflows.
        - is_replica: Is this a replicated object.
        - name: The timeflow's name.
        - dataset_id: The ID of the timeflow's dSource or VDB.
        - creation_type: The source action that created the timeflow.
        - parent_snapshot_id: The ID of the timeflow's parent snapshot.
        - parent_point_location: The location on the parent timeflow from which this timef...
        - parent_point_timestamp: The timestamp on the parent timeflow from which this time...
        - parent_point_timeflow_id: A reference to the parent timeflow from which this timefl...
        - parent_vdb_id: The ID of the parent VDB. This is mutually exclusive with...
        - parent_dsource_id: The ID of the parent dSource. This is mutually exclusive ...
        - source_vdb_id: The ID of the source VDB. This is mutually exclusive with...
        - source_dsource_id: The ID of the source dSource. This is mutually exclusive ...
        - source_data_timestamp: The timestamp on the root ancestor timeflow from which th...
        - oracle_incarnation_id: Oracle-specific incarnation identifier for this timeflow.
        - oracle_cdb_timeflow_id: A reference to the mirror CDB timeflow if this is a timef...
        - oracle_tde_uuid: The unique identifier for timeflow-specific TDE objects t...
        - mssql_database_guid: MSSQL-specific recovery branch identifier for this timeflow.
        - is_active: Whether this timeflow is currently active or not.
        - creation_timestamp: The time when the timeflow was created.
        - activation_timestamp: The time when this timeflow became active.
        - tags: 
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> timeflow_tool(action='search', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get
    ----------------------------------------
    Summary: Get a Timeflow by ID.
    Method: GET
    Endpoint: /timeflows/{timeflowId}
    Required Parameters: timeflow_id
    
    Example:
        >>> timeflow_tool(action='get', timeflow_id='example-timeflow-123')
    
    ACTION: update
    ----------------------------------------
    Summary: Update values of a timeflow.
    Method: PATCH
    Endpoint: /timeflows/{timeflowId}
    Required Parameters: timeflow_id
    Key Parameters (provide as applicable): name
    
    Example:
        >>> timeflow_tool(action='update', timeflow_id='example-timeflow-123', name=...)
    
    ACTION: delete
    ----------------------------------------
    Summary: Delete a timeflow.
    Method: DELETE
    Endpoint: /timeflows/{timeflowId}
    Required Parameters: timeflow_id
    
    Example:
        >>> timeflow_tool(action='delete', timeflow_id='example-timeflow-123')
    
    ACTION: get_snapshot_day_range
    ----------------------------------------
    Summary: Returns the count of TimeFlow snapshots of the Timeflow aggregated by day.
    Method: GET
    Endpoint: /timeflows/{timeflowId}/timeflowSnapshotDayRange
    Required Parameters: timeflow_id
    
    Example:
        >>> timeflow_tool(action='get_snapshot_day_range', timeflow_id='example-timeflow-123')
    
    ACTION: repair
    ----------------------------------------
    Summary: Repair a Timeflow.
    Method: POST
    Endpoint: /timeflows/{timeflowId}/repair
    Required Parameters: timeflow_id, host, username, directory, start_location, end_location
    Key Parameters (provide as applicable): port, use_engine_public_key, password, key_pair_private_key, key_pair_public_key, vault_id, hashicorp_vault_engine, hashicorp_vault_secret_path, hashicorp_vault_username_key, hashicorp_vault_secret_key, azure_vault_name, azure_vault_username_key, azure_vault_secret_key, cyberark_vault_query_string, use_kerberos_authentication, ssh_verification_strategy
    
    Example:
        >>> timeflow_tool(action='repair', timeflow_id='example-timeflow-123', host=..., port=..., username=..., directory=..., start_location=..., end_location=..., use_engine_public_key=..., password=..., key_pair_private_key=..., key_pair_public_key=..., vault_id='example-vault-123', hashicorp_vault_engine=..., hashicorp_vault_secret_path=..., hashicorp_vault_username_key=..., hashicorp_vault_secret_key=..., azure_vault_name=..., azure_vault_username_key=..., azure_vault_secret_key=..., cyberark_vault_query_string=..., use_kerberos_authentication=..., ssh_verification_strategy=...)
    
    ACTION: get_tags
    ----------------------------------------
    Summary: Get tags for a Timeflow.
    Method: GET
    Endpoint: /timeflows/{timeflowId}/tags
    Required Parameters: timeflow_id
    
    Example:
        >>> timeflow_tool(action='get_tags', timeflow_id='example-timeflow-123')
    
    ACTION: add_tags
    ----------------------------------------
    Summary: Create tags for a Timeflow.
    Method: POST
    Endpoint: /timeflows/{timeflowId}/tags
    Required Parameters: timeflow_id, tags
    
    Example:
        >>> timeflow_tool(action='add_tags', timeflow_id='example-timeflow-123', tags=...)
    
    ACTION: delete_tags
    ----------------------------------------
    Summary: Delete tags for a Timeflow.
    Method: POST
    Endpoint: /timeflows/{timeflowId}/tags/delete
    Required Parameters: timeflow_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> timeflow_tool(action='delete_tags', timeflow_id='example-timeflow-123', tags=..., key=..., value=...)
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: list, search, get, update, delete, get_snapshot_day_range, repair, get_tags, add_tags, delete_tags
    
      -- General parameters (all database types) --
        azure_vault_name (str): Azure key vault name (ORACLE, ASE and MSSQL_DOMAIN_USER only).
            [Optional for all actions]
        azure_vault_secret_key (str): Azure vault key for the password in the key-value store (ORACLE, ASE and MSSQ...
            [Optional for all actions]
        azure_vault_username_key (str): Azure vault key for the username in the key-value store (ORACLE, ASE and MSSQ...
            [Optional for all actions]
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: list, search]
        cyberark_vault_query_string (str): Query to find a credential in the CyberArk vault.
            [Optional for all actions]
        directory (str): Location of the missing logs on the host.
            [Required for: repair]
        end_location (str): The database specific identifier specifying the end location of the missing log.
            [Required for: repair]
        filter_expression (str): Request body parameter
            [Optional for all actions]
        hashicorp_vault_engine (str): Vault engine name where the credential is stored.
            [Optional for all actions]
        hashicorp_vault_secret_key (str): Key for the password in the key-value store.
            [Optional for all actions]
        hashicorp_vault_secret_path (str): Path in the vault engine where the credential is stored.
            [Optional for all actions]
        hashicorp_vault_username_key (str): Key for the username in the key-value store.
            [Optional for all actions]
        host (str): Hostname of the remote host.
            [Required for: repair]
        key (str): Key of the tag
            [Optional for all actions]
        key_pair_private_key (str): The private key of the key pair credentials.
            [Optional for all actions]
        key_pair_public_key (str): The public key of the key pair credentials.
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: list, search]
        name (str): The name of the timeflow.
            [Optional for all actions]
        password (str): The password of the user to connect to remote host machine.
            [Optional for all actions]
        port (int): Port to connect to remote host. (Default: 22)
            [Optional for all actions]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: list, search]
        ssh_verification_strategy (str): Mechanism to use for ssh host verification.
            [Optional for all actions]
        start_location (str): The database specific identifier specifying the start location of the missing...
            [Required for: repair]
        tags (list): Array of tags with key value pairs (Pass as JSON array)
            [Required for: add_tags]
        timeflow_id (str): The unique identifier for the timeflow.
            [Required for: get, update, delete, get_snapshot_day_range, repair, get_tags, add_tags, delete_tags]
        use_engine_public_key (bool): Whether to use public key authentication.
            [Optional for all actions]
        use_kerberos_authentication (bool): Whether to use kerberos authentication.
            [Optional for all actions]
        username (str): Username to connect to remote host.
            [Required for: repair]
        value (str): Value of the tag
            [Optional for all actions]
        vault_id (str): The DCT id or name of the vault from which to read the host credentials.
            [Optional for all actions]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'list':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('GET', '/timeflows', action, 'timeflow_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('GET', '/timeflows', params=params)
    elif action == 'search':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', '/timeflows/search', action, 'timeflow_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return await make_api_request('POST', '/timeflows/search', params=params, json_body=body)
    elif action == 'get':
        if timeflow_id is None:
            return {'error': 'Missing required parameter: timeflow_id for action get'}
        endpoint = f'/timeflows/{timeflow_id}'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('GET', endpoint, action, 'timeflow_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('GET', endpoint, params=params)
    elif action == 'update':
        if timeflow_id is None:
            return {'error': 'Missing required parameter: timeflow_id for action update'}
        endpoint = f'/timeflows/{timeflow_id}'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('PATCH', endpoint, action, 'timeflow_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name}.items() if v is not None}
        return await make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete':
        if timeflow_id is None:
            return {'error': 'Missing required parameter: timeflow_id for action delete'}
        endpoint = f'/timeflows/{timeflow_id}'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('DELETE', endpoint, action, 'timeflow_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('DELETE', endpoint, params=params)
    elif action == 'get_snapshot_day_range':
        if timeflow_id is None:
            return {'error': 'Missing required parameter: timeflow_id for action get_snapshot_day_range'}
        endpoint = f'/timeflows/{timeflow_id}/timeflowSnapshotDayRange'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('GET', endpoint, action, 'timeflow_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('GET', endpoint, params=params)
    elif action == 'repair':
        if timeflow_id is None:
            return {'error': 'Missing required parameter: timeflow_id for action repair'}
        endpoint = f'/timeflows/{timeflow_id}/repair'
        params = build_params(host=host, username=username, directory=directory, start_location=start_location, end_location=end_location)
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'timeflow_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'host': host, 'port': port, 'username': username, 'directory': directory, 'start_location': start_location, 'end_location': end_location, 'use_engine_public_key': use_engine_public_key, 'password': password, 'key_pair_private_key': key_pair_private_key, 'key_pair_public_key': key_pair_public_key, 'vault_id': vault_id, 'hashicorp_vault_engine': hashicorp_vault_engine, 'hashicorp_vault_secret_path': hashicorp_vault_secret_path, 'hashicorp_vault_username_key': hashicorp_vault_username_key, 'hashicorp_vault_secret_key': hashicorp_vault_secret_key, 'azure_vault_name': azure_vault_name, 'azure_vault_username_key': azure_vault_username_key, 'azure_vault_secret_key': azure_vault_secret_key, 'cyberark_vault_query_string': cyberark_vault_query_string, 'use_kerberos_authentication': use_kerberos_authentication, 'sshVerificationStrategy': ssh_verification_strategy}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'get_tags':
        if timeflow_id is None:
            return {'error': 'Missing required parameter: timeflow_id for action get_tags'}
        endpoint = f'/timeflows/{timeflow_id}/tags'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('GET', endpoint, action, 'timeflow_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        return await make_api_request('GET', endpoint, params=params)
    elif action == 'add_tags':
        if timeflow_id is None:
            return {'error': 'Missing required parameter: timeflow_id for action add_tags'}
        endpoint = f'/timeflows/{timeflow_id}/tags'
        params = build_params(tags=tags)
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'timeflow_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_tags':
        if timeflow_id is None:
            return {'error': 'Missing required parameter: timeflow_id for action delete_tags'}
        endpoint = f'/timeflows/{timeflow_id}/tags/delete'
        params = build_params()
        _ctx = {k: v for k, v in locals().items() if v is not None and not k.startswith('_')}
        conf = check_confirmation('POST', endpoint, action, 'timeflow_tool', confirmed or False, context=_ctx)
        if conf:
            return conf
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        return await make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: list, search, get, update, delete, get_snapshot_day_range, repair, get_tags, add_tags, delete_tags'}


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
        logger.info(f'  Registering tool function: timeflow_tool')
        app.add_tool(timeflow_tool, name="timeflow_tool")
    except Exception as e:
        logger.error(f'Error registering tools for dataset_endpoints: {e}')
    logger.info(f'Tools registration finished for dataset_endpoints.')
