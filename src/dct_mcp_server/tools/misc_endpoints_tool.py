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
def instance_tool(
    action: str,  # One of: search_cdbs, get_cdb, update_cdb, delete_cdb, enable_cdb, disable_cdb, get_cdb_tags, add_cdb_tags, delete_cdb_tags, search_vcdbs, get_vcdb, update_vcdb, delete_vcdb, enable_vcdb, disable_vcdb, start_vcdb, stop_vcdb, get_vcdb_tags, add_vcdb_tags, delete_vcdb_tags
    abort: Optional[bool] = None,
    attempt_cleanup: Optional[bool] = None,
    attempt_start: Optional[bool] = None,
    auto_restart: Optional[bool] = None,
    backup_level_enabled: Optional[bool] = None,
    bandwidth_limit: Optional[int] = None,
    cdb_id: Optional[str] = None,
    check_logical: Optional[bool] = None,
    compressed_linking_enabled: Optional[bool] = None,
    config_params: Optional[dict] = None,
    cursor: Optional[str] = None,
    custom_env_files: Optional[list] = None,
    custom_env_vars: Optional[dict] = None,
    db_password: Optional[str] = None,
    db_template_id: Optional[str] = None,
    db_username: Optional[str] = None,
    delete_all_dependent_datasets: Optional[bool] = None,
    description: Optional[str] = None,
    diagnose_no_logging_faults: Optional[bool] = None,
    encrypted_linking_enabled: Optional[bool] = None,
    environment_user_id: Optional[str] = None,
    files_per_set: Optional[int] = None,
    filter_expression: Optional[str] = None,
    force: Optional[bool] = None,
    instance_name: Optional[str] = None,
    instance_number: Optional[int] = None,
    instances: Optional[list] = None,
    invoke_datapatch: Optional[bool] = None,
    key: Optional[str] = None,
    limit: Optional[int] = 100,
    logsync_enabled: Optional[bool] = None,
    logsync_interval: Optional[int] = None,
    logsync_mode: Optional[str] = None,
    node_listeners: Optional[list] = None,
    non_sys_password: Optional[str] = None,
    non_sys_username: Optional[str] = None,
    number_of_connections: Optional[int] = None,
    okv_client_id: Optional[str] = None,
    oracle_rac_custom_env_files: Optional[list] = None,
    oracle_rac_custom_env_vars: Optional[list] = None,
    oracle_services: Optional[list] = None,
    rman_channels: Optional[int] = None,
    sort: Optional[str] = None,
    tags: Optional[list] = None,
    tde_key_identifier: Optional[str] = None,
    tde_keystore_config_type: Optional[str] = None,
    tde_keystore_password: Optional[str] = None,
    tde_kms_pkcs11_config_path: Optional[str] = None,
    value: Optional[str] = None,
    vcdb_id: Optional[str] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for INSTANCE operations.
    
    This tool supports 20 actions: search_cdbs, get_cdb, update_cdb, delete_cdb, enable_cdb, disable_cdb, get_cdb_tags, add_cdb_tags, delete_cdb_tags, search_vcdbs, get_vcdb, update_vcdb, delete_vcdb, enable_vcdb, disable_vcdb, start_vcdb, stop_vcdb, get_vcdb_tags, add_vcdb_tags, delete_vcdb_tags
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search_cdbs
    ----------------------------------------
    Summary: Search for CDBs (Oracle only).
    Method: POST
    Endpoint: /cdbs/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - id: The CDB object entity ID.
        - name: The name of this CDB.
        - description: The container description of this Linked CDB.
        - diagnose_no_logging_faults: If true, NOLOGGING operations on this container are treat...
        - namespace_id: The namespace id of this CDB.
        - namespace_name: The namespace name of this CDB.
        - is_replica: Is this a replicated object.
        - database_version: The version of this CDB.
        - environment_id: A reference to the Environment that hosts this CDB.
        - size: The total size of the data files used by this CDB, in bytes.
        - rman_channels: Number of parallel channels to use.
        - files_per_set: Number of data files to include in each RMAN backup set.
        - encrypted_linking_enabled: True if SnapSync data from the source should be retrieved...
        - compressed_linking_enabled: True if SnapSync data from the source should be compresse...
        - bandwidth_limit: Bandwidth limit (MB/s) for SnapSync and LogSync network t...
        - number_of_connections: Total number of transport connections to use during SnapS...
        - backup_level_enabled: Boolean value indicates whether LEVEL-based incremental b...
        - check_logical: True if extended block checking should be used for this l...
        - jdbc_connection_string: The JDBC connection URL for this CDB.
        - engine_id: A reference to the Engine that this CDB belongs to.
        - is_linked: Whether this CDB is linked or not.
        - tags: 
        - group_name: The name of the group containing this CDB.
        - status: The runtime status of the vCDB.
        - enabled: Whether the CDB is enabled or not.
        - instance_name: The instance name of this single instance CDB.
        - instance_number: The instance number of this single instance CDB.
        - instances: 
        - oracle_services: 
        - repository_id: The repository id of this CDB.
        - logsync_enabled: True if LogSync is enabled for this dSource.
        - logsync_mode: 
        - logsync_interval: Interval between LogSync requests, in seconds.
        - tde_keystore_config_type: 
        - database_name: The database name of this container database.
        - database_unique_name: The unique name of the container database.
        - tde_kms_pkcs11_config_path: The path to the TDE KMS PKC11 configuration file.
        - is_tde_keystore_password_set: True if TDE keystore password is set for this container d...
        - environment_user_ref: The environment user reference.
        - db_username: The name of the database user.
        - non_sys_username: The username of a database user that does not have admini...
        - okv_client_id: The id of the OKV client used for TDE keystore access.
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> instance_tool(action='search_cdbs', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get_cdb
    ----------------------------------------
    Summary: Get a CDB by ID (Oracle only).
    Method: GET
    Endpoint: /cdbs/{cdbId}
    Required Parameters: cdb_id
    
    Example:
        >>> instance_tool(action='get_cdb', cdb_id='example-cdb-123')
    
    ACTION: update_cdb
    ----------------------------------------
    Summary: Update a CDB.
    Method: PATCH
    Endpoint: /cdbs/{cdbId}/update
    Required Parameters: cdb_id
    Key Parameters (provide as applicable): oracle_services, logsync_enabled, logsync_mode, logsync_interval, tde_keystore_password, tde_keystore_config_type, tde_kms_pkcs11_config_path, description, diagnose_no_logging_faults, environment_user_id, rman_channels, files_per_set, encrypted_linking_enabled, compressed_linking_enabled, bandwidth_limit, number_of_connections, backup_level_enabled, check_logical, db_username, db_password, non_sys_username, non_sys_password, okv_client_id, instance_name, instance_number, instances
    
    Example:
        >>> instance_tool(action='update_cdb', cdb_id='example-cdb-123', oracle_services=..., logsync_enabled=..., logsync_mode=..., logsync_interval=..., tde_keystore_password=..., tde_keystore_config_type=..., tde_kms_pkcs11_config_path=..., description=..., diagnose_no_logging_faults=..., environment_user_id='example-environment_user-123', rman_channels=..., files_per_set=..., encrypted_linking_enabled=..., compressed_linking_enabled=..., bandwidth_limit=..., number_of_connections=..., backup_level_enabled=..., check_logical=..., db_username=..., db_password=..., non_sys_username=..., non_sys_password=..., okv_client_id='example-okv_client-123', instance_name=..., instance_number=..., instances=...)
    
    ACTION: delete_cdb
    ----------------------------------------
    Summary: Delete a CDB.
    Method: POST
    Endpoint: /cdbs/{cdbId}/delete
    Required Parameters: cdb_id
    Key Parameters (provide as applicable): force, delete_all_dependent_datasets
    
    Example:
        >>> instance_tool(action='delete_cdb', cdb_id='example-cdb-123', force=..., delete_all_dependent_datasets=...)
    
    ACTION: enable_cdb
    ----------------------------------------
    Summary: Enable a CDB.
    Method: POST
    Endpoint: /cdbs/{cdbId}/enable
    Required Parameters: cdb_id
    Key Parameters (provide as applicable): attempt_start
    
    Example:
        >>> instance_tool(action='enable_cdb', cdb_id='example-cdb-123', attempt_start=...)
    
    ACTION: disable_cdb
    ----------------------------------------
    Summary: Disable a CDB.
    Method: POST
    Endpoint: /cdbs/{cdbId}/disable
    Required Parameters: cdb_id
    Key Parameters (provide as applicable): attempt_cleanup
    
    Example:
        >>> instance_tool(action='disable_cdb', cdb_id='example-cdb-123', attempt_cleanup=...)
    
    ACTION: get_cdb_tags
    ----------------------------------------
    Summary: Get tags for a CDB.
    Method: GET
    Endpoint: /cdbs/{cdbId}/tags
    Required Parameters: cdb_id
    
    Example:
        >>> instance_tool(action='get_cdb_tags', cdb_id='example-cdb-123')
    
    ACTION: add_cdb_tags
    ----------------------------------------
    Summary: Create tags for a CDB.
    Method: POST
    Endpoint: /cdbs/{cdbId}/tags
    Required Parameters: cdb_id, tags
    
    Example:
        >>> instance_tool(action='add_cdb_tags', cdb_id='example-cdb-123', tags=...)
    
    ACTION: delete_cdb_tags
    ----------------------------------------
    Summary: Delete tags for a CDB.
    Method: POST
    Endpoint: /cdbs/{cdbId}/tags/delete
    Required Parameters: cdb_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> instance_tool(action='delete_cdb_tags', cdb_id='example-cdb-123', tags=..., key=..., value=...)
    
    ACTION: search_vcdbs
    ----------------------------------------
    Summary: Search for vCDBs (Oracle only).
    Method: POST
    Endpoint: /vcdbs/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - id: The vCDB object entity ID.
        - name: The name of this vCDB.
        - description: The container description of this virtual CDB.
        - database_name: The name of the container database in the Oracle DBMS.
        - namespace_id: The namespace id of this vCDB.
        - namespace_name: The namespace name of this vCDB.
        - is_replica: Is this a replicated object.
        - database_version: The version of this vCDB.
        - environment_id: A reference to the Environment that hosts this vCDB.
        - size: The total size of the data files used by this vCDB, in by...
        - engine_id: A reference to the Engine that this vCDB belongs to.
        - status: The runtime status of the vCDB.
        - parent_id: A reference to the parent CDB of this vCDB.
        - creation_date: The date this vCDB was created.
        - group_name: The name of the group containing this vCDB.
        - enabled: Whether the vCDB is enabled or not.
        - content_type: The content type of the vcdb.
        - vcdb_restart: Indicates whether the Engine should automatically restart...
        - tags: 
        - invoke_datapatch: Indicates whether datapatch should be invoked.
        - node_listeners: The list of node listeners for this VCDB.
        - instance_name: The instance name of this single instance VCDB.
        - instance_number: The instance number of this single instance VCDB.
        - instances: 
        - oracle_services: 
        - repository_id: The repository id of this Virtual CDB.
        - containerization_state: 
        - tde_key_identifier: ID of the key created by Delphix, as recorded in v$encryp...
        - tde_keystore_config_type: 
        - is_tde_keystore_password_set: True if TDE keystore password is set for this container d...
        - database_unique_name: The unique name of the database.
        - db_username: The user name of the database.
        - redo_log_groups: Number of Online Redo Log Groups.
        - redo_log_size_in_mb: Online Redo Log size in MB.
        - config_params: Database configuration parameter overrides.
        - custom_env_vars: 
        - active_instances: 
        - nfs_version: The NFS version that was last used to mount this source."
        - nfs_version_reason: 
        - nfs_encryption_enabled: Flag indicating whether the data transfer is encrypted or...
        - environment_user_ref: The environment user reference.
        - db_template_id: The database template ID for this Virtual CDB.
        - db_template_name: Name of the Database Template.
        - okv_client_id: The id of the OKV client used for TDE keystore access.
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> instance_tool(action='search_vcdbs', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get_vcdb
    ----------------------------------------
    Summary: Get a vCDB by ID (Oracle only).
    Method: GET
    Endpoint: /vcdbs/{vcdbId}
    Required Parameters: vcdb_id
    
    Example:
        >>> instance_tool(action='get_vcdb', vcdb_id='example-vcdb-123')
    
    ACTION: update_vcdb
    ----------------------------------------
    Summary: Update a VCDB.
    Method: PATCH
    Endpoint: /vcdbs/{vcdbId}/update
    Required Parameters: vcdb_id
    Key Parameters (provide as applicable): oracle_services, tde_keystore_password, tde_keystore_config_type, description, environment_user_id, db_username, db_password, okv_client_id, instance_name, instance_number, instances, node_listeners, invoke_datapatch, tde_key_identifier, auto_restart, config_params, custom_env_vars, custom_env_files, oracle_rac_custom_env_files, oracle_rac_custom_env_vars, db_template_id
    
    Example:
        >>> instance_tool(action='update_vcdb', oracle_services=..., tde_keystore_password=..., tde_keystore_config_type=..., description=..., environment_user_id='example-environment_user-123', db_username=..., db_password=..., okv_client_id='example-okv_client-123', instance_name=..., instance_number=..., instances=..., vcdb_id='example-vcdb-123', node_listeners=..., invoke_datapatch=..., tde_key_identifier=..., auto_restart=..., config_params=..., custom_env_vars=..., custom_env_files=..., oracle_rac_custom_env_files=..., oracle_rac_custom_env_vars=..., db_template_id='example-db_template-123')
    
    ACTION: delete_vcdb
    ----------------------------------------
    Summary: Delete a vCDB.
    Method: POST
    Endpoint: /vcdbs/{vcdbId}/delete
    Required Parameters: vcdb_id
    Key Parameters (provide as applicable): force, delete_all_dependent_datasets
    
    Example:
        >>> instance_tool(action='delete_vcdb', force=..., delete_all_dependent_datasets=..., vcdb_id='example-vcdb-123')
    
    ACTION: enable_vcdb
    ----------------------------------------
    Summary: Enable a vCDB.
    Method: POST
    Endpoint: /vcdbs/{vcdbId}/enable
    Required Parameters: vcdb_id
    Key Parameters (provide as applicable): attempt_start
    
    Example:
        >>> instance_tool(action='enable_vcdb', attempt_start=..., vcdb_id='example-vcdb-123')
    
    ACTION: disable_vcdb
    ----------------------------------------
    Summary: Disable a vCDB.
    Method: POST
    Endpoint: /vcdbs/{vcdbId}/disable
    Required Parameters: vcdb_id
    Key Parameters (provide as applicable): attempt_cleanup
    
    Example:
        >>> instance_tool(action='disable_vcdb', attempt_cleanup=..., vcdb_id='example-vcdb-123')
    
    ACTION: start_vcdb
    ----------------------------------------
    Summary: Start a vCDB.
    Method: POST
    Endpoint: /vcdbs/{vcdbId}/start
    Required Parameters: vcdb_id
    Key Parameters (provide as applicable): instances
    
    Example:
        >>> instance_tool(action='start_vcdb', instances=..., vcdb_id='example-vcdb-123')
    
    ACTION: stop_vcdb
    ----------------------------------------
    Summary: Stop a vCDB.
    Method: POST
    Endpoint: /vcdbs/{vcdbId}/stop
    Required Parameters: vcdb_id
    Key Parameters (provide as applicable): instances, abort
    
    Example:
        >>> instance_tool(action='stop_vcdb', instances=..., vcdb_id='example-vcdb-123', abort=...)
    
    ACTION: get_vcdb_tags
    ----------------------------------------
    Summary: Get tags for a vCDB.
    Method: GET
    Endpoint: /vcdbs/{vcdbId}/tags
    Required Parameters: vcdb_id
    
    Example:
        >>> instance_tool(action='get_vcdb_tags', vcdb_id='example-vcdb-123')
    
    ACTION: add_vcdb_tags
    ----------------------------------------
    Summary: Create tags for a vCDB.
    Method: POST
    Endpoint: /vcdbs/{vcdbId}/tags
    Required Parameters: tags, vcdb_id
    
    Example:
        >>> instance_tool(action='add_vcdb_tags', tags=..., vcdb_id='example-vcdb-123')
    
    ACTION: delete_vcdb_tags
    ----------------------------------------
    Summary: Delete tags for a vCDB.
    Method: POST
    Endpoint: /vcdbs/{vcdbId}/tags/delete
    Required Parameters: vcdb_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> instance_tool(action='delete_vcdb_tags', tags=..., key=..., value=..., vcdb_id='example-vcdb-123')
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search_cdbs, get_cdb, update_cdb, delete_cdb, enable_cdb, disable_cdb, get_cdb_tags, add_cdb_tags, delete_cdb_tags, search_vcdbs, get_vcdb, update_vcdb, delete_vcdb, enable_vcdb, disable_vcdb, start_vcdb, stop_vcdb, get_vcdb_tags, add_vcdb_tags, delete_vcdb_tags
    
      -- General parameters (all database types) --
        abort (bool): Whether to issue 'shutdown abort' to shutdown Virtual Container DB instances....
            [Optional for all actions]
        attempt_cleanup (bool): Whether to attempt a cleanup of the CDB before the disable. (Default: True)
            [Optional for all actions]
        attempt_start (bool): Whether to attempt a startup of the CDB after the enable. (Default: True)
            [Optional for all actions]
        auto_restart (bool): Whether to enable VDB restart.
            [Optional for all actions]
        backup_level_enabled (bool): Boolean value indicates whether LEVEL-based incremental backups can be used o...
            [Optional for all actions]
        bandwidth_limit (int): Bandwidth limit (MB/s) for SnapSync and LogSync network traffic. A value of 0...
            [Optional for all actions]
        cdb_id (str): The unique identifier for the cdb.
            [Required for: get_cdb, update_cdb, delete_cdb, enable_cdb, disable_cdb, get_cdb_tags, add_cdb_tags, delete_cdb_tags]
        check_logical (bool): True if extended block checking should be used for this linked database.
            [Optional for all actions]
        compressed_linking_enabled (bool): True if SnapSync data from the source should be compressed over the network. ...
            [Optional for all actions]
        config_params (dict): Database configuration parameter overrides. (Pass as JSON object)
            [Optional for all actions]
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search_cdbs, search_vcdbs]
        custom_env_files (list): Environment files to be sourced when the Engine administers a VCDB. This path...
            [Optional for all actions]
        custom_env_vars (dict): Environment variable to be set when the engine administers a VCDB. See the En...
            [Optional for all actions]
        db_password (str): The password of the database user.
            [Optional for all actions]
        db_template_id (str): The ID of the target Virtual CDB Template.
            [Optional for all actions]
        db_username (str): The name of the database user.
            [Optional for all actions]
        delete_all_dependent_datasets (bool): Whether to delete all dependent datasets of the CDB. (Default: False)
            [Optional for all actions]
        description (str): The container description of this Linked CDB.
            [Optional for all actions]
        diagnose_no_logging_faults (bool): Request body parameter
            [Optional for all actions]
        encrypted_linking_enabled (bool): True if SnapSync data from the source should be retrieved through an encrypte...
            [Optional for all actions]
        environment_user_id (str): The environment user ID to use to connect to the environment.
            [Optional for all actions]
        files_per_set (int): Number of data files to include in each RMAN backup set.
            [Optional for all actions]
        filter_expression (str): Request body parameter
            [Optional for all actions]
        force (bool): Whether to continue the operation upon failures. (Default: False)
            [Optional for all actions]
        instance_name (str): The instance name of this single instance CDB. Must contain at least one non-...
            [Optional for all actions]
        instance_number (int): The instance number of this single instance CDB.
            [Optional for all actions]
        instances (list): The instances of this RAC database. (Pass as JSON array)
            [Optional for all actions]
        invoke_datapatch (bool): Indicates whether datapatch should be invoked.
            [Optional for all actions]
        key (str): Key of the tag
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search_cdbs, search_vcdbs]
        logsync_enabled (bool): True if LogSync is enabled for this CDB.
            [Optional for all actions]
        logsync_interval (int): Interval between LogSync requests, in seconds.
            [Optional for all actions]
        logsync_mode (str): LogSync operation mode for this dSource. Valid values: ARCHIVE_ONLY_MODE, ARC...
            [Optional for all actions]
        node_listeners (list): The list of node listener ids for this VCDB. (Pass as JSON array)
            [Optional for all actions]
        non_sys_password (str): The username of a database user that does not have administrative privileges.
            [Optional for all actions]
        non_sys_username (str): The username of a database user that does not have administrative privileges.
            [Optional for all actions]
        number_of_connections (int): Total number of transport connections to use during SnapSync.
            [Optional for all actions]
        okv_client_id (str): The id of the OKV client used for TDE keystore access. A blank string will un...
            [Optional for all actions]
        oracle_rac_custom_env_files (list): Environment files to be sourced when the Engine administers an Oracle RAC VCD...
            [Optional for all actions]
        oracle_rac_custom_env_vars (list): Environment variable to be set when the engine administers an Oracle RAC VCDB...
            [Optional for all actions]
        oracle_services (list): List of jdbc connection strings which are used to connect with the database. ...
            [Optional for all actions]
        rman_channels (int): Number of parallel channels to use.
            [Optional for all actions]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search_cdbs, search_vcdbs]
        tags (list): Array of tags with key value pairs (Pass as JSON array)
            [Required for: add_cdb_tags, add_vcdb_tags]
        tde_key_identifier (str): The master encryption key id of this database. A blank string will unset the ...
            [Optional for all actions]
        tde_keystore_config_type (str): Oracle TDE keystore configuration type. Valid values: FILE, OKV, HSM, OKV|FIL...
            [Optional for all actions]
        tde_keystore_password (str): For a CDB using software keystore, this is the password of the software keyst...
            [Optional for all actions]
        tde_kms_pkcs11_config_path (str): Path to the PKCS#11 configuration file for TDE KMS. A blank string will unset...
            [Optional for all actions]
        value (str): Value of the tag
            [Optional for all actions]
        vcdb_id (str): The unique identifier for the vcdb.
            [Required for: get_vcdb, update_vcdb, delete_vcdb, enable_vcdb, disable_vcdb, start_vcdb, stop_vcdb, get_vcdb_tags, add_vcdb_tags, delete_vcdb_tags]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'search_cdbs':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', '/cdbs/search', action, 'instance_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/cdbs/search', params=params, json_body=body)
    elif action == 'get_cdb':
        if cdb_id is None:
            return {'error': 'Missing required parameter: cdb_id for action get_cdb'}
        endpoint = f'/cdbs/{cdb_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'instance_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'update_cdb':
        if cdb_id is None:
            return {'error': 'Missing required parameter: cdb_id for action update_cdb'}
        endpoint = f'/cdbs/{cdb_id}/update'
        params = build_params()
        if not environment_user_id:
            environment_user_id = environment_user_ref or environment_user
        body = {k: v for k, v in {'oracle_services': oracle_services, 'logsync_enabled': logsync_enabled, 'logsync_mode': logsync_mode, 'logsync_interval': logsync_interval, 'tde_keystore_password': tde_keystore_password, 'tde_keystore_config_type': tde_keystore_config_type, 'tde_kms_pkcs11_config_path': tde_kms_pkcs11_config_path, 'description': description, 'diagnose_no_logging_faults': diagnose_no_logging_faults, 'environment_user_id': environment_user_id, 'rman_channels': rman_channels, 'files_per_set': files_per_set, 'encrypted_linking_enabled': encrypted_linking_enabled, 'compressed_linking_enabled': compressed_linking_enabled, 'bandwidth_limit': bandwidth_limit, 'number_of_connections': number_of_connections, 'backup_level_enabled': backup_level_enabled, 'check_logical': check_logical, 'db_username': db_username, 'db_password': db_password, 'non_sys_username': non_sys_username, 'non_sys_password': non_sys_password, 'okv_client_id': okv_client_id, 'instance_name': instance_name, 'instance_number': instance_number, 'instances': instances}.items() if v is not None}
        conf = check_confirmation('PATCH', endpoint, action, 'instance_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_cdb':
        if cdb_id is None:
            return {'error': 'Missing required parameter: cdb_id for action delete_cdb'}
        endpoint = f'/cdbs/{cdb_id}/delete'
        params = build_params()
        body = {k: v for k, v in {'force': force, 'delete_all_dependent_datasets': delete_all_dependent_datasets}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'instance_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'enable_cdb':
        if cdb_id is None:
            return {'error': 'Missing required parameter: cdb_id for action enable_cdb'}
        endpoint = f'/cdbs/{cdb_id}/enable'
        params = build_params()
        body = {k: v for k, v in {'attempt_start': attempt_start}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'instance_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'disable_cdb':
        if cdb_id is None:
            return {'error': 'Missing required parameter: cdb_id for action disable_cdb'}
        endpoint = f'/cdbs/{cdb_id}/disable'
        params = build_params()
        body = {k: v for k, v in {'attempt_cleanup': attempt_cleanup}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'instance_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'get_cdb_tags':
        if cdb_id is None:
            return {'error': 'Missing required parameter: cdb_id for action get_cdb_tags'}
        endpoint = f'/cdbs/{cdb_id}/tags'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'instance_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_cdb_tags':
        if cdb_id is None:
            return {'error': 'Missing required parameter: cdb_id for action add_cdb_tags'}
        endpoint = f'/cdbs/{cdb_id}/tags'
        params = build_params(tags=tags)
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'instance_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_cdb_tags':
        if cdb_id is None:
            return {'error': 'Missing required parameter: cdb_id for action delete_cdb_tags'}
        endpoint = f'/cdbs/{cdb_id}/tags/delete'
        params = build_params()
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'instance_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'search_vcdbs':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', '/vcdbs/search', action, 'instance_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/vcdbs/search', params=params, json_body=body)
    elif action == 'get_vcdb':
        if vcdb_id is None:
            return {'error': 'Missing required parameter: vcdb_id for action get_vcdb'}
        endpoint = f'/vcdbs/{vcdb_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'instance_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'update_vcdb':
        if vcdb_id is None:
            return {'error': 'Missing required parameter: vcdb_id for action update_vcdb'}
        endpoint = f'/vcdbs/{vcdb_id}/update'
        params = build_params()
        if not environment_user_id:
            environment_user_id = environment_user_ref or environment_user
        body = {k: v for k, v in {'oracle_services': oracle_services, 'okv_client_id': okv_client_id, 'instance_name': instance_name, 'instance_number': instance_number, 'instances': instances, 'node_listeners': node_listeners, 'invoke_datapatch': invoke_datapatch, 'tde_keystore_password': tde_keystore_password, 'tde_keystore_config_type': tde_keystore_config_type, 'tde_key_identifier': tde_key_identifier, 'db_username': db_username, 'db_password': db_password, 'auto_restart': auto_restart, 'environment_user_id': environment_user_id, 'config_params': config_params, 'custom_env_vars': custom_env_vars, 'custom_env_files': custom_env_files, 'oracle_rac_custom_env_files': oracle_rac_custom_env_files, 'oracle_rac_custom_env_vars': oracle_rac_custom_env_vars, 'description': description, 'db_template_id': db_template_id}.items() if v is not None}
        conf = check_confirmation('PATCH', endpoint, action, 'instance_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_vcdb':
        if vcdb_id is None:
            return {'error': 'Missing required parameter: vcdb_id for action delete_vcdb'}
        endpoint = f'/vcdbs/{vcdb_id}/delete'
        params = build_params()
        body = {k: v for k, v in {'force': force, 'delete_all_dependent_datasets': delete_all_dependent_datasets}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'instance_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'enable_vcdb':
        if vcdb_id is None:
            return {'error': 'Missing required parameter: vcdb_id for action enable_vcdb'}
        endpoint = f'/vcdbs/{vcdb_id}/enable'
        params = build_params()
        body = {k: v for k, v in {'attempt_start': attempt_start}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'instance_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'disable_vcdb':
        if vcdb_id is None:
            return {'error': 'Missing required parameter: vcdb_id for action disable_vcdb'}
        endpoint = f'/vcdbs/{vcdb_id}/disable'
        params = build_params()
        body = {k: v for k, v in {'attempt_cleanup': attempt_cleanup}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'instance_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'start_vcdb':
        if vcdb_id is None:
            return {'error': 'Missing required parameter: vcdb_id for action start_vcdb'}
        endpoint = f'/vcdbs/{vcdb_id}/start'
        params = build_params()
        body = {k: v for k, v in {'instances': instances}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'instance_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'stop_vcdb':
        if vcdb_id is None:
            return {'error': 'Missing required parameter: vcdb_id for action stop_vcdb'}
        endpoint = f'/vcdbs/{vcdb_id}/stop'
        params = build_params()
        body = {k: v for k, v in {'instances': instances, 'abort': abort}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'instance_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'get_vcdb_tags':
        if vcdb_id is None:
            return {'error': 'Missing required parameter: vcdb_id for action get_vcdb_tags'}
        endpoint = f'/vcdbs/{vcdb_id}/tags'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'instance_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_vcdb_tags':
        if vcdb_id is None:
            return {'error': 'Missing required parameter: vcdb_id for action add_vcdb_tags'}
        endpoint = f'/vcdbs/{vcdb_id}/tags'
        params = build_params(tags=tags)
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'instance_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_vcdb_tags':
        if vcdb_id is None:
            return {'error': 'Missing required parameter: vcdb_id for action delete_vcdb_tags'}
        endpoint = f'/vcdbs/{vcdb_id}/tags/delete'
        params = build_params()
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'instance_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search_cdbs, get_cdb, update_cdb, delete_cdb, enable_cdb, disable_cdb, get_cdb_tags, add_cdb_tags, delete_cdb_tags, search_vcdbs, get_vcdb, update_vcdb, delete_vcdb, enable_vcdb, disable_vcdb, start_vcdb, stop_vcdb, get_vcdb_tags, add_vcdb_tags, delete_vcdb_tags'}

@log_tool_execution
def staging_source_tool(
    action: str,  # One of: list, search, get, update, get_tags, add_tags, delete_tags
    cursor: Optional[str] = None,
    filter_expression: Optional[str] = None,
    key: Optional[str] = None,
    limit: Optional[int] = 100,
    oracle_services: Optional[list] = None,
    sort: Optional[str] = None,
    staging_source_id: Optional[str] = None,
    tags: Optional[list] = None,
    value: Optional[str] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for STAGING SOURCE operations.
    
    This tool supports 7 actions: list, search, get, update, get_tags, add_tags, delete_tags
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: list
    ----------------------------------------
    Summary: List all staging sources.
    Method: GET
    Endpoint: /staging-sources
    Required Parameters: limit, cursor, sort
    
    Example:
        >>> staging_source_tool(action='list', limit=..., cursor=..., sort=...)
    
    ACTION: search
    ----------------------------------------
    Summary: Search for Staging Sources.
    Method: POST
    Endpoint: /staging-sources/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - id: The Staging Source object entity ID.
        - name: The name of this staging source database.
        - database_type: The type of this staging source database.
        - database_name: The name of container database of associated with this st...
        - database_version: The version of container database associated with this st...
        - environment_id: A reference to the Environment that hosts this staging so...
        - data_uuid: A universal ID that uniquely identifies this staging sour...
        - ip_address: The IP address of the staging source's host.
        - fqdn: The FQDN of the staging source's host.
        - repository: The repository id for this staging source.
        - type: The type of source configuration for this staging source.
        - oracle_config_type: 
        - cdb_type: The cdb type for this staging source. (Oracle only)
        - dsource_id: The dsource_id associated with this staging source.
        - tags: 
        - oracle_services: 
        - environment_user_ref: The environment user reference.
        - recovery_model: Recovery model of the source database.
        - mount_base: The base mount point for the NFS or iSCSI LUN mounts.
        - data_connection_id: The ID of the associated DataConnection.
        - datafile_mount_path: The datafile mount point to use for the NFS mounts.
        - archive_mount_path: The archive mount point to use for the NFS mounts.
        - database_unique_name: The unique name of the database.
        - instance_name: The instance name of this staging database.
        - size: The total size of this Staging database, in bytes.
        - custom_env_vars: 
        - nfs_version: The NFS version that was last used to mount this source."
        - nfs_version_reason: 
        - nfs_encryption_enabled: Flag indicating whether the data transfer is encrypted or...
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> staging_source_tool(action='search', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get
    ----------------------------------------
    Summary: Get a staging source by ID.
    Method: GET
    Endpoint: /staging-sources/{stagingSourceId}
    Required Parameters: staging_source_id
    
    Example:
        >>> staging_source_tool(action='get', staging_source_id='example-staging_source-123')
    
    ACTION: update
    ----------------------------------------
    Summary: Update a Staging Source.
    Method: PATCH
    Endpoint: /staging-sources/{stagingSourceId}/update
    Required Parameters: staging_source_id
    Key Parameters (provide as applicable): oracle_services
    
    Example:
        >>> staging_source_tool(action='update', staging_source_id='example-staging_source-123', oracle_services=...)
    
    ACTION: get_tags
    ----------------------------------------
    Summary: Get tags for a Staging Source.
    Method: GET
    Endpoint: /staging-sources/{stagingSourceId}/tags
    Required Parameters: staging_source_id
    
    Example:
        >>> staging_source_tool(action='get_tags', staging_source_id='example-staging_source-123')
    
    ACTION: add_tags
    ----------------------------------------
    Summary: Create tags for a Staging Source.
    Method: POST
    Endpoint: /staging-sources/{stagingSourceId}/tags
    Required Parameters: staging_source_id, tags
    
    Example:
        >>> staging_source_tool(action='add_tags', staging_source_id='example-staging_source-123', tags=...)
    
    ACTION: delete_tags
    ----------------------------------------
    Summary: Delete tags for a Staging Source.
    Method: POST
    Endpoint: /staging-sources/{stagingSourceId}/tags/delete
    Required Parameters: staging_source_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> staging_source_tool(action='delete_tags', staging_source_id='example-staging_source-123', tags=..., key=..., value=...)
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: list, search, get, update, get_tags, add_tags, delete_tags
    
      -- General parameters (all database types) --
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: list, search]
        filter_expression (str): Request body parameter
            [Optional for all actions]
        key (str): Key of the tag
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: list, search]
        oracle_services (list): List of jdbc connection strings which are used to connect with the database. ...
            [Optional for all actions]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: list, search]
        staging_source_id (str): The unique identifier for the stagingSource.
            [Required for: get, update, get_tags, add_tags, delete_tags]
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
    if action == 'list':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('GET', '/staging-sources', action, 'staging_source_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', '/staging-sources', params=params)
    elif action == 'search':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', '/staging-sources/search', action, 'staging_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/staging-sources/search', params=params, json_body=body)
    elif action == 'get':
        if staging_source_id is None:
            return {'error': 'Missing required parameter: staging_source_id for action get'}
        endpoint = f'/staging-sources/{staging_source_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'staging_source_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'update':
        if staging_source_id is None:
            return {'error': 'Missing required parameter: staging_source_id for action update'}
        endpoint = f'/staging-sources/{staging_source_id}/update'
        params = build_params()
        body = {k: v for k, v in {'oracle_services': oracle_services}.items() if v is not None}
        conf = check_confirmation('PATCH', endpoint, action, 'staging_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'get_tags':
        if staging_source_id is None:
            return {'error': 'Missing required parameter: staging_source_id for action get_tags'}
        endpoint = f'/staging-sources/{staging_source_id}/tags'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'staging_source_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_tags':
        if staging_source_id is None:
            return {'error': 'Missing required parameter: staging_source_id for action add_tags'}
        endpoint = f'/staging-sources/{staging_source_id}/tags'
        params = build_params(tags=tags)
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'staging_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_tags':
        if staging_source_id is None:
            return {'error': 'Missing required parameter: staging_source_id for action delete_tags'}
        endpoint = f'/staging-sources/{staging_source_id}/tags/delete'
        params = build_params()
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'staging_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: list, search, get, update, get_tags, add_tags, delete_tags'}

@log_tool_execution
def staging_cdb_tool(
    action: str,  # One of: list, search, get, update, delete, enable, disable, upgrade, get_tags, add_tags, delete_tags
    allow_auto_staging_restart_on_host_reboot: Optional[bool] = None,
    attempt_cleanup: Optional[bool] = None,
    attempt_start: Optional[bool] = None,
    config_params: Optional[dict] = None,
    cursor: Optional[str] = None,
    custom_env_variables_pairs: Optional[list] = None,
    custom_env_variables_paths: Optional[list] = None,
    db_template_id: Optional[str] = None,
    delete_all_dependent_datasets: Optional[bool] = None,
    description: Optional[str] = None,
    environment_id: Optional[str] = None,
    environment_user_id: Optional[str] = None,
    filter_expression: Optional[str] = None,
    force: Optional[bool] = None,
    instance_name: Optional[str] = None,
    instance_number: Optional[int] = None,
    key: Optional[str] = None,
    limit: Optional[int] = 100,
    logsync_enabled: Optional[bool] = None,
    okv_client_id: Optional[str] = None,
    oracle_services: Optional[list] = None,
    physical_standby: Optional[bool] = None,
    repository_id: Optional[str] = None,
    sort: Optional[str] = None,
    staging_cdb_id: Optional[str] = None,
    tags: Optional[list] = None,
    tde_keystore_config_type: Optional[str] = None,
    tde_keystore_password: Optional[str] = None,
    tde_kms_pkcs11_config_path: Optional[str] = None,
    validate_snapshot_by_opening_db_in_read_mode: Optional[bool] = None,
    value: Optional[str] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for STAGING CDB operations.
    
    This tool supports 11 actions: list, search, get, update, delete, enable, disable, upgrade, get_tags, add_tags, delete_tags
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: list
    ----------------------------------------
    Summary: List all Staging CDBs.
    Method: GET
    Endpoint: /staging-cdbs
    Required Parameters: limit, cursor, sort
    
    Example:
        >>> staging_cdb_tool(action='list', limit=..., cursor=..., sort=...)
    
    ACTION: search
    ----------------------------------------
    Summary: Search for Staging CDBs.
    Method: POST
    Endpoint: /staging-cdbs/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - id: The Staging CDB object entity ID.
        - name: The name of this Staging CDB.
        - namespace_id: The namespace id of this Staging CDB.
        - namespace_name: The namespace name of this Staging CDB.
        - is_replica: Is this a replicated object.
        - database_version: The version of this Staging CDB.
        - environment_id: A reference to the Environment that hosts this Staging CDB.
        - size: The total size of the data files used by this Staging CDB...
        - jdbc_connection_string: The JDBC connection URL for this Staging CDB.
        - engine_id: A reference to the Engine that this Staging CDB belongs to.
        - tags: 
        - group_name: The name of the group containing this Staging CDB.
        - status: The runtime status of the Staging CDB.
        - enabled: Whether the Staging CDB is enabled or not.
        - instance_name: The instance name of this single instance Staging CDB.
        - instance_number: The instance number of this single instance Staging CDB.
        - oracle_services: 
        - repository_id: The repository id of this Staging CDB.
        - tde_keystore_config_type: 
        - database_name: The database name of this Staging CDB.
        - database_unique_name: The unique name of the Staging CDB.
        - tde_kms_pkcs11_config_path: The path to the TDE KMS PKC11 configuration file.
        - is_tde_keystore_password_set: True if TDE keystore password is set for this Staging CDB.
        - auto_staging_push_restart: Whether to automatically restart staging push operations.
        - configure_staging_db_params: Whether to configure staging database parameters.
        - physical_standby: Whether this is a physical standby database.
        - validate_snapshot_by_opening_db_in_read_mode: Whether to validate snapshots by opening the database in ...
        - mount_base: The base mount point for the NFS mount on the staging env...
        - datafile_mount_path: The datafile mount point for the NFS mount on the staging...
        - archive_mount_path: The archive mount point for the NFS mount on the staging ...
        - custom_env_vars: 
        - nfs_version: The NFS version that was last used to mount this source."
        - nfs_version_reason: 
        - nfs_encryption_enabled: Flag indicating whether the data transfer is encrypted or...
        - logsync_enabled: Whether logsync is enabled for this Staging CDB.
        - description: Description of this Staging CDB.
        - config_params: Database configuration parameter overrides.
        - db_template_id: The database template ID for this Staging CDB.
        - db_template_name: Name of the Database Template.
        - environment_user_ref: The environment user reference.
        - okv_client_id: The id of the OKV client used for TDE keystore access.
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> staging_cdb_tool(action='search', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get
    ----------------------------------------
    Summary: Get a Staging CDB by ID.
    Method: GET
    Endpoint: /staging-cdbs/{stagingCdbId}
    Required Parameters: staging_cdb_id
    
    Example:
        >>> staging_cdb_tool(action='get', staging_cdb_id='example-staging_cdb-123')
    
    ACTION: update
    ----------------------------------------
    Summary: Update a Staging CDB.
    Method: PATCH
    Endpoint: /staging-cdbs/{stagingCdbId}
    Required Parameters: staging_cdb_id
    Key Parameters (provide as applicable): oracle_services, logsync_enabled, tde_keystore_password, tde_keystore_config_type, tde_kms_pkcs11_config_path, allow_auto_staging_restart_on_host_reboot, physical_standby, validate_snapshot_by_opening_db_in_read_mode, custom_env_variables_pairs, custom_env_variables_paths, environment_id, repository_id, environment_user_id, description, config_params, db_template_id, okv_client_id, instance_name, instance_number
    
    Example:
        >>> staging_cdb_tool(action='update', staging_cdb_id='example-staging_cdb-123', oracle_services=..., logsync_enabled=..., tde_keystore_password=..., tde_keystore_config_type=..., tde_kms_pkcs11_config_path=..., allow_auto_staging_restart_on_host_reboot=..., physical_standby=..., validate_snapshot_by_opening_db_in_read_mode=..., custom_env_variables_pairs=..., custom_env_variables_paths=..., environment_id='example-environment-123', repository_id='example-repository-123', environment_user_id='example-environment_user-123', description=..., config_params=..., db_template_id='example-db_template-123', okv_client_id='example-okv_client-123', instance_name=..., instance_number=...)
    
    ACTION: delete
    ----------------------------------------
    Summary: Delete a staging CDB.
    Method: POST
    Endpoint: /staging-cdbs/{stagingCdbId}/delete
    Required Parameters: staging_cdb_id
    Key Parameters (provide as applicable): force, delete_all_dependent_datasets
    
    Example:
        >>> staging_cdb_tool(action='delete', staging_cdb_id='example-staging_cdb-123', force=..., delete_all_dependent_datasets=...)
    
    ACTION: enable
    ----------------------------------------
    Summary: Enable a staging CDB.
    Method: POST
    Endpoint: /staging-cdbs/{stagingCdbId}/enable
    Required Parameters: staging_cdb_id
    Key Parameters (provide as applicable): attempt_start
    
    Example:
        >>> staging_cdb_tool(action='enable', staging_cdb_id='example-staging_cdb-123', attempt_start=...)
    
    ACTION: disable
    ----------------------------------------
    Summary: Disable a staging CDB.
    Method: POST
    Endpoint: /staging-cdbs/{stagingCdbId}/disable
    Required Parameters: staging_cdb_id
    Key Parameters (provide as applicable): attempt_cleanup
    
    Example:
        >>> staging_cdb_tool(action='disable', staging_cdb_id='example-staging_cdb-123', attempt_cleanup=...)
    
    ACTION: upgrade
    ----------------------------------------
    Summary: Upgrade Oracle staging CDB.
    Method: POST
    Endpoint: /staging-cdbs/{stagingCdbId}/upgrade
    Required Parameters: staging_cdb_id, repository_id, environment_user_id
    
    Example:
        >>> staging_cdb_tool(action='upgrade', staging_cdb_id='example-staging_cdb-123', repository_id='example-repository-123', environment_user_id='example-environment_user-123')
    
    ACTION: get_tags
    ----------------------------------------
    Summary: Get tags for a staging CDB.
    Method: GET
    Endpoint: /staging-cdbs/{stagingCdbId}/tags
    Required Parameters: staging_cdb_id
    
    Example:
        >>> staging_cdb_tool(action='get_tags', staging_cdb_id='example-staging_cdb-123')
    
    ACTION: add_tags
    ----------------------------------------
    Summary: Create tags for a staging CDB.
    Method: POST
    Endpoint: /staging-cdbs/{stagingCdbId}/tags
    Required Parameters: staging_cdb_id, tags
    
    Example:
        >>> staging_cdb_tool(action='add_tags', staging_cdb_id='example-staging_cdb-123', tags=...)
    
    ACTION: delete_tags
    ----------------------------------------
    Summary: Delete tags for a staging CDB.
    Method: POST
    Endpoint: /staging-cdbs/{stagingCdbId}/tags/delete
    Required Parameters: staging_cdb_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> staging_cdb_tool(action='delete_tags', staging_cdb_id='example-staging_cdb-123', tags=..., key=..., value=...)
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: list, search, get, update, delete, enable, disable, upgrade, get_tags, add_tags, delete_tags
    
      -- General parameters (all database types) --
        allow_auto_staging_restart_on_host_reboot (bool): Whether to automatically restart staging operations on host reboot.
            [Optional for all actions]
        attempt_cleanup (bool): Whether to attempt a cleanup of the CDB before the disable. (Default: True)
            [Optional for all actions]
        attempt_start (bool): Whether to attempt a startup of the CDB after the enable. (Default: True)
            [Optional for all actions]
        config_params (dict): Database configuration parameter overrides. (Pass as JSON object)
            [Optional for all actions]
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: list, search]
        custom_env_variables_pairs (list): An array of name value pair of environment variables. (Pass as JSON array)
            [Optional for all actions]
        custom_env_variables_paths (list): An array of strings of whitespace-separated parameters to be passed to the so...
            [Optional for all actions]
        db_template_id (str): The ID of the database template to apply to this Staging CDB.
            [Optional for all actions]
        delete_all_dependent_datasets (bool): Whether to delete all dependent datasets of the Staging CDB. (Default: False)
            [Optional for all actions]
        description (str): Description of this Staging CDB.
            [Optional for all actions]
        environment_id (str): The ID of the environment to move this Staging CDB to.
            [Optional for all actions]
        environment_user_id (str): The ID of the environment user to use for this Staging CDB.
            [Required for: upgrade]
        filter_expression (str): Request body parameter
            [Optional for all actions]
        force (bool): Whether to continue the operation upon failures. (Default: False)
            [Optional for all actions]
        instance_name (str): The instance name of this single instance CDB. Must contain at least one non-...
            [Optional for all actions]
        instance_number (int): The instance number of this single instance CDB.
            [Optional for all actions]
        key (str): Key of the tag
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: list, search]
        logsync_enabled (bool): True if LogSync is enabled for this Staging CDB.
            [Optional for all actions]
        okv_client_id (str): The id of the OKV client used for TDE keystore access. A blank string will un...
            [Optional for all actions]
        oracle_services (list): List of jdbc connection strings which are used to connect with the database. ...
            [Optional for all actions]
        physical_standby (bool): Whether this Staging CDB is a physical standby database.
            [Optional for all actions]
        repository_id (str): The ID of the repository to move this Staging CDB to.
            [Required for: upgrade]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: list, search]
        staging_cdb_id (str): The unique identifier for the stagingCdb.
            [Required for: get, update, delete, enable, disable, upgrade, get_tags, add_tags, delete_tags]
        tags (list): Array of tags with key value pairs (Pass as JSON array)
            [Required for: add_tags]
        tde_keystore_config_type (str): Oracle TDE keystore configuration type. Valid values: FILE, OKV, HSM, OKV|FIL...
            [Optional for all actions]
        tde_keystore_password (str): For a Staging CDB using software keystore, this is the password of the softwa...
            [Optional for all actions]
        tde_kms_pkcs11_config_path (str): Path to the PKCS#11 configuration file for TDE KMS.  A blank string will unse...
            [Optional for all actions]
        validate_snapshot_by_opening_db_in_read_mode (bool): Whether to validate snapshots by opening the database in read mode.
            [Optional for all actions]
        value (str): Value of the tag
            [Optional for all actions]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'list':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('GET', '/staging-cdbs', action, 'staging_cdb_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', '/staging-cdbs', params=params)
    elif action == 'search':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', '/staging-cdbs/search', action, 'staging_cdb_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/staging-cdbs/search', params=params, json_body=body)
    elif action == 'get':
        if staging_cdb_id is None:
            return {'error': 'Missing required parameter: staging_cdb_id for action get'}
        endpoint = f'/staging-cdbs/{staging_cdb_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'staging_cdb_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'update':
        if staging_cdb_id is None:
            return {'error': 'Missing required parameter: staging_cdb_id for action update'}
        endpoint = f'/staging-cdbs/{staging_cdb_id}'
        params = build_params()
        if not environment_user_id:
            environment_user_id = environment_user_ref or environment_user
        body = {k: v for k, v in {'oracle_services': oracle_services, 'logsync_enabled': logsync_enabled, 'tde_keystore_password': tde_keystore_password, 'tde_keystore_config_type': tde_keystore_config_type, 'tde_kms_pkcs11_config_path': tde_kms_pkcs11_config_path, 'allow_auto_staging_restart_on_host_reboot': allow_auto_staging_restart_on_host_reboot, 'physical_standby': physical_standby, 'validate_snapshot_by_opening_db_in_read_mode': validate_snapshot_by_opening_db_in_read_mode, 'custom_env_variables_pairs': custom_env_variables_pairs, 'custom_env_variables_paths': custom_env_variables_paths, 'environment_id': environment_id, 'repository_id': repository_id, 'environment_user_id': environment_user_id, 'description': description, 'config_params': config_params, 'db_template_id': db_template_id, 'okv_client_id': okv_client_id, 'instance_name': instance_name, 'instance_number': instance_number}.items() if v is not None}
        conf = check_confirmation('PATCH', endpoint, action, 'staging_cdb_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete':
        if staging_cdb_id is None:
            return {'error': 'Missing required parameter: staging_cdb_id for action delete'}
        endpoint = f'/staging-cdbs/{staging_cdb_id}/delete'
        params = build_params()
        body = {k: v for k, v in {'force': force, 'delete_all_dependent_datasets': delete_all_dependent_datasets}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'staging_cdb_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'enable':
        if staging_cdb_id is None:
            return {'error': 'Missing required parameter: staging_cdb_id for action enable'}
        endpoint = f'/staging-cdbs/{staging_cdb_id}/enable'
        params = build_params()
        body = {k: v for k, v in {'attempt_start': attempt_start}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'staging_cdb_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'disable':
        if staging_cdb_id is None:
            return {'error': 'Missing required parameter: staging_cdb_id for action disable'}
        endpoint = f'/staging-cdbs/{staging_cdb_id}/disable'
        params = build_params()
        body = {k: v for k, v in {'attempt_cleanup': attempt_cleanup}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'staging_cdb_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'upgrade':
        if staging_cdb_id is None:
            return {'error': 'Missing required parameter: staging_cdb_id for action upgrade'}
        endpoint = f'/staging-cdbs/{staging_cdb_id}/upgrade'
        params = build_params()
        if not environment_user_id:
            environment_user_id = environment_user_ref or environment_user
        body = {k: v for k, v in {'repository_id': repository_id, 'environment_user_id': environment_user_id}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'staging_cdb_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'get_tags':
        if staging_cdb_id is None:
            return {'error': 'Missing required parameter: staging_cdb_id for action get_tags'}
        endpoint = f'/staging-cdbs/{staging_cdb_id}/tags'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'staging_cdb_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_tags':
        if staging_cdb_id is None:
            return {'error': 'Missing required parameter: staging_cdb_id for action add_tags'}
        endpoint = f'/staging-cdbs/{staging_cdb_id}/tags'
        params = build_params(tags=tags)
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'staging_cdb_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_tags':
        if staging_cdb_id is None:
            return {'error': 'Missing required parameter: staging_cdb_id for action delete_tags'}
        endpoint = f'/staging-cdbs/{staging_cdb_id}/tags/delete'
        params = build_params()
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'staging_cdb_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: list, search, get, update, delete, enable, disable, upgrade, get_tags, add_tags, delete_tags'}

@log_tool_execution
def cdb_dsource_tool(
    action: str,  # One of: list, search, get, attach_cdb, detach_cdb, enable, disable, delete, upgrade
    attempt_cleanup: Optional[bool] = None,
    attempt_start: Optional[bool] = None,
    backup_level_enabled: Optional[bool] = None,
    bandwidth_limit: Optional[int] = None,
    cdb_d_source_id: Optional[str] = None,
    check_logical: Optional[bool] = None,
    compressed_linking_enabled: Optional[bool] = None,
    cursor: Optional[str] = None,
    delete_all_dependent_datasets: Optional[bool] = None,
    double_sync: Optional[bool] = None,
    encrypted_linking_enabled: Optional[bool] = None,
    environment_user: Optional[str] = None,
    environment_user_id: Optional[str] = None,
    external_file_path: Optional[str] = None,
    files_per_set: Optional[int] = None,
    filter_expression: Optional[str] = None,
    force: Optional[bool] = None,
    limit: Optional[int] = 100,
    link_now: Optional[bool] = None,
    number_of_connections: Optional[int] = None,
    operations: Optional[list] = None,
    oracle_fallback_credentials: Optional[str] = None,
    oracle_fallback_user: Optional[str] = None,
    repository_id: Optional[str] = None,
    rman_channels: Optional[int] = None,
    sort: Optional[str] = None,
    source_id: Optional[str] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for CDB DSOURCE operations.
    
    This tool supports 9 actions: list, search, get, attach_cdb, detach_cdb, enable, disable, delete, upgrade
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: list
    ----------------------------------------
    Summary: List all CDB dSources (Oracle only).
    Method: GET
    Endpoint: /cdb-dsources
    Required Parameters: limit, cursor, sort
    
    Example:
        >>> cdb_dsource_tool(action='list', limit=..., cursor=..., sort=...)
    
    ACTION: search
    ----------------------------------------
    Summary: Search for CDB dSources (Oracle only).
    Method: POST
    Endpoint: /cdb-dsources/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - id: The CDB object entity ID.
        - engine_id: A reference to the Engine that this CDB belongs to.
        - name: The name of this CDB.
        - enabled: Whether the CDB is enabled or not.
        - status: The runtime status of the vCDB.
        - description: The container description of this Linked CDB.
        - cdb_source_id: The container description of this Linked CDB.
        - is_detached: Is this a detached CDB container.
        - logsync_enabled: True if LogSync is enabled for this dSource.
        - logsync_mode: 
        - logsync_interval: Interval between LogSync requests, in seconds.
        - size: The total size of the data files used by this CDB, in bytes.
        - namespace_id: The namespace id of this CDB.
        - namespace_name: The namespace name of this CDB.
        - is_replica: Is this a replicated object.
        - group_name: The name of the group containing this CDB.
        - diagnose_no_logging_faults: If true, NOLOGGING operations on this container are treat...
        - rman_channels: Number of parallel channels to use.
        - files_per_set: Number of data files to include in each RMAN backup set.
        - encrypted_linking_enabled: True if SnapSync data from the source should be retrieved...
        - compressed_linking_enabled: True if SnapSync data from the source should be compresse...
        - bandwidth_limit: Bandwidth limit (MB/s) for SnapSync and LogSync network t...
        - number_of_connections: Total number of transport connections to use during SnapS...
        - backup_level_enabled: Boolean value indicates whether LEVEL-based incremental b...
        - check_logical: True if extended block checking should be used for this l...
        - tags: 
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> cdb_dsource_tool(action='search', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get
    ----------------------------------------
    Summary: Get a CDB dSource by ID (Oracle only).
    Method: GET
    Endpoint: /cdb-dsources/{cdbDSourceId}
    Required Parameters: cdb_d_source_id
    
    Example:
        >>> cdb_dsource_tool(action='get', cdb_d_source_id='example-cdb_d_source-123')
    
    ACTION: attach_cdb
    ----------------------------------------
    Summary: Attaches an Oracle CDB to an Oracle database.
    Method: POST
    Endpoint: /cdb-dsources/{cdbDSourceId}/attach-cdb
    Required Parameters: cdb_d_source_id, source_id
    
    Example:
        >>> cdb_dsource_tool(action='attach_cdb', cdb_d_source_id='example-cdb_d_source-123', source_id='example-source-123')
    
    ACTION: detach_cdb
    ----------------------------------------
    Summary: Detaches an Oracle CDB from an Oracle database.
    Method: POST
    Endpoint: /cdb-dsources/{cdbDSourceId}/detach-cdb
    Required Parameters: cdb_d_source_id
    
    Example:
        >>> cdb_dsource_tool(action='detach_cdb', cdb_d_source_id='example-cdb_d_source-123')
    
    ACTION: enable
    ----------------------------------------
    Summary: Enable a CDB dSource.
    Method: POST
    Endpoint: /cdb-dsources/{cdbDSourceId}/enable
    Required Parameters: cdb_d_source_id
    Key Parameters (provide as applicable): attempt_start
    
    Example:
        >>> cdb_dsource_tool(action='enable', cdb_d_source_id='example-cdb_d_source-123', attempt_start=...)
    
    ACTION: disable
    ----------------------------------------
    Summary: Disable a CDB dSource.
    Method: POST
    Endpoint: /cdb-dsources/{cdbDSourceId}/disable
    Required Parameters: cdb_d_source_id
    Key Parameters (provide as applicable): attempt_cleanup
    
    Example:
        >>> cdb_dsource_tool(action='disable', cdb_d_source_id='example-cdb_d_source-123', attempt_cleanup=...)
    
    ACTION: delete
    ----------------------------------------
    Summary: Delete a CDB dSource.
    Method: POST
    Endpoint: /cdb-dsources/{cdbDSourceId}/delete
    Required Parameters: cdb_d_source_id
    Key Parameters (provide as applicable): force, delete_all_dependent_datasets
    
    Example:
        >>> cdb_dsource_tool(action='delete', cdb_d_source_id='example-cdb_d_source-123', force=..., delete_all_dependent_datasets=...)
    
    ACTION: upgrade
    ----------------------------------------
    Summary: Upgrade Oracle CDB dSource
    Method: POST
    Endpoint: /cdb-dsources/{cdbDSourceId}/upgrade
    Required Parameters: cdb_d_source_id, repository_id, environment_user_id
    
    Example:
        >>> cdb_dsource_tool(action='upgrade', cdb_d_source_id='example-cdb_d_source-123', repository_id='example-repository-123', environment_user_id='example-environment_user-123')
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: list, search, get, attach_cdb, detach_cdb, enable, disable, delete, upgrade
    
      -- General parameters (all database types) --
        attempt_cleanup (bool): Whether to attempt a cleanup of the CDB before the disable. (Default: True)
            [Optional for all actions]
        attempt_start (bool): Whether to attempt a startup of the CDB after the enable. (Default: True)
            [Optional for all actions]
        backup_level_enabled (bool): Boolean value indicates whether LEVEL-based incremental backups can be used o...
            [Optional for all actions]
        bandwidth_limit (int): Bandwidth limit (MB/s) for SnapSync and LogSync network traffic. A value of 0...
            [Optional for all actions]
        cdb_d_source_id (str): The unique identifier for the cdbDSource.
            [Required for: get, attach_cdb, detach_cdb, enable, disable, delete, upgrade]
        check_logical (bool): True if extended block checking should be used for this linked database. (Def...
            [Optional for all actions]
        compressed_linking_enabled (bool): True if SnapSync data from the source should be compressed over the network. ...
            [Optional for all actions]
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: list, search]
        delete_all_dependent_datasets (bool): Whether to delete all dependent datasets of the CDB. (Default: False)
            [Optional for all actions]
        double_sync (bool): True if two SnapSyncs should be performed in immediate succession to reduce t...
            [Optional for all actions]
        encrypted_linking_enabled (bool): True if SnapSync data from the source should be retrieved through an encrypte...
            [Optional for all actions]
        environment_user (str): Reference to the user that should be used in the host.
            [Optional for all actions]
        environment_user_id (str): Reference of the environment user to use for CDB/vCDB upgrade.
            [Required for: upgrade]
        external_file_path (str): External file path.
            [Optional for all actions]
        files_per_set (int): Number of data files to include in each RMAN backup set. (Default: 5)
            [Optional for all actions]
        filter_expression (str): Request body parameter
            [Optional for all actions]
        force (bool): If true, attach will succeed even if the resetlogs of the new database does n...
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: list, search]
        link_now (bool): True if initial load should be done immediately. (Default: False)
            [Optional for all actions]
        number_of_connections (int): Total number of transport connections to use during SnapSync. (Default: 1)
            [Optional for all actions]
        operations (list): Operations to perform after syncing a created dSource and before running the ...
            [Optional for all actions]
        oracle_fallback_credentials (str): Password for fallback username.
            [Optional for all actions]
        oracle_fallback_user (str): The database fallback username. Optional if bequeath connections are enabled ...
            [Optional for all actions]
        repository_id (str): The id of the CDB/vCDB repository to upgrade to.
            [Required for: upgrade]
        rman_channels (int): Number of parallel channels to use. (Default: 2)
            [Optional for all actions]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: list, search]
        source_id (str): Id of the source to attach.
            [Required for: attach_cdb]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'list':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('GET', '/cdb-dsources', action, 'cdb_dsource_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', '/cdb-dsources', params=params)
    elif action == 'search':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', '/cdb-dsources/search', action, 'cdb_dsource_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/cdb-dsources/search', params=params, json_body=body)
    elif action == 'get':
        if cdb_d_source_id is None:
            return {'error': 'Missing required parameter: cdb_d_source_id for action get'}
        endpoint = f'/cdb-dsources/{cdb_d_source_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'cdb_dsource_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'attach_cdb':
        if cdb_d_source_id is None:
            return {'error': 'Missing required parameter: cdb_d_source_id for action attach_cdb'}
        endpoint = f'/cdb-dsources/{cdb_d_source_id}/attach-cdb'
        params = build_params()
        body = {k: v for k, v in {'backup_level_enabled': backup_level_enabled, 'bandwidth_limit': bandwidth_limit, 'check_logical': check_logical, 'compressed_linking_enabled': compressed_linking_enabled, 'double_sync': double_sync, 'encrypted_linking_enabled': encrypted_linking_enabled, 'environment_user': environment_user, 'external_file_path': external_file_path, 'files_per_set': files_per_set, 'force': force, 'link_now': link_now, 'number_of_connections': number_of_connections, 'operations': operations, 'oracle_fallback_user': oracle_fallback_user, 'oracle_fallback_credentials': oracle_fallback_credentials, 'rman_channels': rman_channels, 'source_id': source_id}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'cdb_dsource_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'detach_cdb':
        if cdb_d_source_id is None:
            return {'error': 'Missing required parameter: cdb_d_source_id for action detach_cdb'}
        endpoint = f'/cdb-dsources/{cdb_d_source_id}/detach-cdb'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'cdb_dsource_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'enable':
        if cdb_d_source_id is None:
            return {'error': 'Missing required parameter: cdb_d_source_id for action enable'}
        endpoint = f'/cdb-dsources/{cdb_d_source_id}/enable'
        params = build_params()
        body = {k: v for k, v in {'attempt_start': attempt_start}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'cdb_dsource_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'disable':
        if cdb_d_source_id is None:
            return {'error': 'Missing required parameter: cdb_d_source_id for action disable'}
        endpoint = f'/cdb-dsources/{cdb_d_source_id}/disable'
        params = build_params()
        body = {k: v for k, v in {'attempt_cleanup': attempt_cleanup}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'cdb_dsource_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete':
        if cdb_d_source_id is None:
            return {'error': 'Missing required parameter: cdb_d_source_id for action delete'}
        endpoint = f'/cdb-dsources/{cdb_d_source_id}/delete'
        params = build_params()
        body = {k: v for k, v in {'force': force, 'delete_all_dependent_datasets': delete_all_dependent_datasets}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'cdb_dsource_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'upgrade':
        if cdb_d_source_id is None:
            return {'error': 'Missing required parameter: cdb_d_source_id for action upgrade'}
        endpoint = f'/cdb-dsources/{cdb_d_source_id}/upgrade'
        params = build_params()
        if not environment_user_id:
            environment_user_id = environment_user_ref or environment_user
        body = {k: v for k, v in {'repository_id': repository_id, 'environment_user_id': environment_user_id}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'cdb_dsource_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: list, search, get, attach_cdb, detach_cdb, enable, disable, delete, upgrade'}

@log_tool_execution
def group_tool(
    action: str,  # One of: list, search, get
    cursor: Optional[str] = None,
    filter_expression: Optional[str] = None,
    group_id: Optional[str] = None,
    limit: Optional[int] = 100,
    sort: Optional[str] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for GROUP operations.
    
    This tool supports 3 actions: list, search, get
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: list
    ----------------------------------------
    Summary: List all dataset groups.
    Method: GET
    Endpoint: /groups
    Required Parameters: limit, cursor, sort
    
    Example:
        >>> group_tool(action='list', limit=..., cursor=..., sort=...)
    
    ACTION: search
    ----------------------------------------
    Summary: Search for dataset groups.
    Method: POST
    Endpoint: /groups/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - id: The dataset group ID.
        - name: The name of this dataset group.
        - namespace_id: The namespace id of this dataset group.
        - namespace_name: The namespace name of this dataset group.
        - is_replica: Is this a replicated object.
        - engine_id: Id of the Engine that this dataset group belongs to.
        - engine_name: Name of the Engine that this dataset group belongs to.
        - namespace: The namespace of this dataset group.
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> group_tool(action='search', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get
    ----------------------------------------
    Summary: Get a dataset group by ID or Name.
    Method: GET
    Endpoint: /groups/{groupId}
    Required Parameters: group_id
    
    Example:
        >>> group_tool(action='get', group_id='example-group-123')
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: list, search, get
    
      -- General parameters (all database types) --
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: list, search]
        filter_expression (str): Request body parameter
            [Optional for all actions]
        group_id (str): The unique identifier for the group.
            [Required for: get]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: list, search]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: list, search]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'list':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('GET', '/groups', action, 'group_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', '/groups', params=params)
    elif action == 'search':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', '/groups/search', action, 'group_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/groups/search', params=params, json_body=body)
    elif action == 'get':
        if group_id is None:
            return {'error': 'Missing required parameter: group_id for action get'}
        endpoint = f'/groups/{group_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'group_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: list, search, get'}

@log_tool_execution
def vault_tool(
    action: str,  # One of: list_hashicorp_vaults, create_hashicorp_vault, search_hashicorp_vaults, get_hashicorp_vault, delete_hashicorp_vault, get_hashicorp_vault_tags, add_hashicorp_vault_tags, delete_hashicorp_vault_tags, list_kerberos_configs, search_kerberos_configs, get_kerberos_config
    cursor: Optional[str] = None,
    env_variables: Optional[dict] = None,
    filter_expression: Optional[str] = None,
    id: Optional[int] = None,
    kerberos_config_id: Optional[str] = None,
    key: Optional[str] = None,
    limit: Optional[int] = 100,
    login_command_args: Optional[list] = None,
    sort: Optional[str] = None,
    tags: Optional[list] = None,
    value: Optional[str] = None,
    vault_id: Optional[str] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for VAULT operations.
    
    This tool supports 11 actions: list_hashicorp_vaults, create_hashicorp_vault, search_hashicorp_vaults, get_hashicorp_vault, delete_hashicorp_vault, get_hashicorp_vault_tags, add_hashicorp_vault_tags, delete_hashicorp_vault_tags, list_kerberos_configs, search_kerberos_configs, get_kerberos_config
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: list_hashicorp_vaults
    ----------------------------------------
    Summary: Returns a list of configured Hashicorp vaults.
    Method: GET
    Endpoint: /management/vaults/hashicorp
    Required Parameters: limit, cursor, sort
    
    Example:
        >>> vault_tool(action='list_hashicorp_vaults', limit=..., cursor=..., sort=...)
    
    ACTION: create_hashicorp_vault
    ----------------------------------------
    Summary: Configure a new Hashicorp Vault
    Method: POST
    Endpoint: /management/vaults/hashicorp
    Key Parameters (provide as applicable): id, env_variables, login_command_args, tags
    
    Example:
        >>> vault_tool(action='create_hashicorp_vault', id=..., env_variables=..., login_command_args=..., tags=...)
    
    ACTION: search_hashicorp_vaults
    ----------------------------------------
    Summary: Search for configured Hashicorp vaults.
    Method: POST
    Endpoint: /management/vaults/hashicorp/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - id: 
        - env_variables: Environment variables to set when invoking the Vault CLI ...
        - login_command_args: Arguments to the "vault" CLI tool to be used to fetch a c...
        - tags: 
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> vault_tool(action='search_hashicorp_vaults', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get_hashicorp_vault
    ----------------------------------------
    Summary: Get a Hashicorp vault by id
    Method: GET
    Endpoint: /management/vaults/hashicorp/{vaultId}
    Required Parameters: vault_id
    
    Example:
        >>> vault_tool(action='get_hashicorp_vault', vault_id='example-vault-123')
    
    ACTION: delete_hashicorp_vault
    ----------------------------------------
    Summary: Delete a Hashicorp vault by id
    Method: DELETE
    Endpoint: /management/vaults/hashicorp/{vaultId}
    Required Parameters: vault_id
    
    Example:
        >>> vault_tool(action='delete_hashicorp_vault', vault_id='example-vault-123')
    
    ACTION: get_hashicorp_vault_tags
    ----------------------------------------
    Summary: Get tags for a Hashicorp vault.
    Method: GET
    Endpoint: /management/vaults/hashicorp/{vaultId}/tags
    Required Parameters: vault_id
    
    Example:
        >>> vault_tool(action='get_hashicorp_vault_tags', vault_id='example-vault-123')
    
    ACTION: add_hashicorp_vault_tags
    ----------------------------------------
    Summary: Create tags for a Hashicorp vault.
    Method: POST
    Endpoint: /management/vaults/hashicorp/{vaultId}/tags
    Required Parameters: tags, vault_id
    
    Example:
        >>> vault_tool(action='add_hashicorp_vault_tags', tags=..., vault_id='example-vault-123')
    
    ACTION: delete_hashicorp_vault_tags
    ----------------------------------------
    Summary: Delete tags for a Hashicorp vault.
    Method: POST
    Endpoint: /management/vaults/hashicorp/{vaultId}/tags/delete
    Required Parameters: vault_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> vault_tool(action='delete_hashicorp_vault_tags', tags=..., vault_id='example-vault-123', key=..., value=...)
    
    ACTION: list_kerberos_configs
    ----------------------------------------
    Summary: List all kerberos configs.
    Method: GET
    Endpoint: /kerberos-configs
    Required Parameters: limit, cursor, sort
    
    Example:
        >>> vault_tool(action='list_kerberos_configs', limit=..., cursor=..., sort=...)
    
    ACTION: search_kerberos_configs
    ----------------------------------------
    Summary: Search for Kerberos Configs.
    Method: POST
    Endpoint: /kerberos-configs/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - id: The kerberos config ID.
        - name: The name of the kerberos config object.
        - namespace_id: The namespace id of this kerberos config object.
        - namespace_name: The namespace name of this kerberos config object.
        - is_replica: Is this a replicated object.
        - engine_id: Id of the Engine that this kerberos config object belongs...
        - engine_name: Name of the Engine that this kerberos config object belon...
        - realm: Kerberos Realm name.
        - principal: Kerberos principal name.
        - enabled: The kerberos is enabled or not.
        - keytab: Kerberos keytab.
        - kdc_servers: One of more KDC servers.
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> vault_tool(action='search_kerberos_configs', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get_kerberos_config
    ----------------------------------------
    Summary: Get a kerberos config by ID or Name.
    Method: GET
    Endpoint: /kerberos-configs/{kerberosConfigId}
    Required Parameters: kerberos_config_id
    
    Example:
        >>> vault_tool(action='get_kerberos_config', kerberos_config_id='example-kerberos_config-123')
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: list_hashicorp_vaults, create_hashicorp_vault, search_hashicorp_vaults, get_hashicorp_vault, delete_hashicorp_vault, get_hashicorp_vault_tags, add_hashicorp_vault_tags, delete_hashicorp_vault_tags, list_kerberos_configs, search_kerberos_configs, get_kerberos_config
    
      -- General parameters (all database types) --
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: list_hashicorp_vaults, search_hashicorp_vaults, list_kerberos_configs, search_kerberos_configs]
        env_variables (dict): Environment variables to set when invoking the Vault CLI tool. The environmen...
            [Optional for all actions]
        filter_expression (str): Request body parameter
            [Optional for all actions]
        id (int): Request body parameter
            [Optional for all actions]
        kerberos_config_id (str): The unique identifier for the kerberosConfig.
            [Required for: get_kerberos_config]
        key (str): Key of the tag
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: list_hashicorp_vaults, search_hashicorp_vaults, list_kerberos_configs, search_kerberos_configs]
        login_command_args (list): Arguments to the "vault" CLI tool to be used to fetch a client token (or "log...
            [Optional for all actions]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: list_hashicorp_vaults, search_hashicorp_vaults, list_kerberos_configs, search_kerberos_configs]
        tags (list): Request body parameter (Pass as JSON array)
            [Required for: add_hashicorp_vault_tags]
        value (str): Value of the tag
            [Optional for all actions]
        vault_id (str): The unique identifier for the vault.
            [Required for: get_hashicorp_vault, delete_hashicorp_vault, get_hashicorp_vault_tags, add_hashicorp_vault_tags, delete_hashicorp_vault_tags]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'list_hashicorp_vaults':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('GET', '/management/vaults/hashicorp', action, 'vault_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', '/management/vaults/hashicorp', params=params)
    elif action == 'create_hashicorp_vault':
        params = build_params()
        body = {k: v for k, v in {'id': id, 'env_variables': env_variables, 'login_command_args': login_command_args, 'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', '/management/vaults/hashicorp', action, 'vault_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/management/vaults/hashicorp', params=params, json_body=body if body else None)
    elif action == 'search_hashicorp_vaults':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', '/management/vaults/hashicorp/search', action, 'vault_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/management/vaults/hashicorp/search', params=params, json_body=body)
    elif action == 'get_hashicorp_vault':
        if vault_id is None:
            return {'error': 'Missing required parameter: vault_id for action get_hashicorp_vault'}
        endpoint = f'/management/vaults/hashicorp/{vault_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'vault_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'delete_hashicorp_vault':
        if vault_id is None:
            return {'error': 'Missing required parameter: vault_id for action delete_hashicorp_vault'}
        endpoint = f'/management/vaults/hashicorp/{vault_id}'
        params = build_params()
        conf = check_confirmation('DELETE', endpoint, action, 'vault_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'get_hashicorp_vault_tags':
        if vault_id is None:
            return {'error': 'Missing required parameter: vault_id for action get_hashicorp_vault_tags'}
        endpoint = f'/management/vaults/hashicorp/{vault_id}/tags'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'vault_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_hashicorp_vault_tags':
        if vault_id is None:
            return {'error': 'Missing required parameter: vault_id for action add_hashicorp_vault_tags'}
        endpoint = f'/management/vaults/hashicorp/{vault_id}/tags'
        params = build_params(tags=tags)
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'vault_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_hashicorp_vault_tags':
        if vault_id is None:
            return {'error': 'Missing required parameter: vault_id for action delete_hashicorp_vault_tags'}
        endpoint = f'/management/vaults/hashicorp/{vault_id}/tags/delete'
        params = build_params()
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'vault_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'list_kerberos_configs':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('GET', '/kerberos-configs', action, 'vault_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', '/kerberos-configs', params=params)
    elif action == 'search_kerberos_configs':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', '/kerberos-configs/search', action, 'vault_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/kerberos-configs/search', params=params, json_body=body)
    elif action == 'get_kerberos_config':
        if kerberos_config_id is None:
            return {'error': 'Missing required parameter: kerberos_config_id for action get_kerberos_config'}
        endpoint = f'/kerberos-configs/{kerberos_config_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'vault_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: list_hashicorp_vaults, create_hashicorp_vault, search_hashicorp_vaults, get_hashicorp_vault, delete_hashicorp_vault, get_hashicorp_vault_tags, add_hashicorp_vault_tags, delete_hashicorp_vault_tags, list_kerberos_configs, search_kerberos_configs, get_kerberos_config'}

@log_tool_execution
def diagnostic_tool(
    action: str,  # One of: check_engine_connectivity, check_database_connectivity, check_netbackup_connectivity, check_commvault_connectivity, test_network_latency, get_network_latency_result, test_network_dsp, get_network_dsp_result, test_network_throughput, get_network_throughput_result, validate_file_mapping_by_snapshot, validate_file_mapping_by_location, validate_file_mapping_by_timestamp, validate_file_mapping_by_bookmark
    azure_vault_name: Optional[str] = None,
    azure_vault_secret_key: Optional[str] = None,
    azure_vault_username_key: Optional[str] = None,
    block_size: Optional[int] = None,
    bookmark_ids: Optional[list] = None,
    commserve_host_name: Optional[str] = None,
    compression: Optional[bool] = None,
    credentials_type: Optional[str] = None,
    cyberark_vault_query_string: Optional[str] = None,
    destination_type: Optional[str] = None,
    direction: Optional[str] = None,
    duration: Optional[int] = None,
    encryption: Optional[bool] = None,
    engine_id: Optional[str] = None,
    environment_id: Optional[str] = None,
    environment_user: Optional[str] = None,
    environment_user_id: Optional[str] = None,
    file_mapping_rules: Optional[str] = None,
    file_system_layout: Optional[dict] = None,
    hashicorp_vault_engine: Optional[str] = None,
    hashicorp_vault_secret_key: Optional[str] = None,
    hashicorp_vault_secret_path: Optional[str] = None,
    hashicorp_vault_username_key: Optional[str] = None,
    host: Optional[str] = None,
    host_id: Optional[str] = None,
    job_id: Optional[str] = None,
    locations: Optional[list] = None,
    master_server_name: Optional[str] = None,
    num_connections: Optional[int] = None,
    os_name: Optional[str] = None,
    password: Optional[str] = None,
    port: Optional[int] = None,
    queue_depth: Optional[int] = None,
    receive_socket_buffer: Optional[int] = None,
    request_count: Optional[int] = None,
    request_size: Optional[int] = None,
    send_socket_buffer: Optional[int] = None,
    snapshot_ids: Optional[list] = None,
    source_client_name: Optional[str] = None,
    source_data_id: Optional[str] = None,
    source_id: Optional[str] = None,
    staging_client_name: Optional[str] = None,
    staging_environment: Optional[str] = None,
    target_engine_address: Optional[str] = None,
    target_engine_id: Optional[str] = None,
    target_engine_password: Optional[str] = None,
    target_engine_user: Optional[str] = None,
    timestamps: Optional[list] = None,
    use_engine_public_key: Optional[bool] = None,
    use_kerberos_authentication: Optional[bool] = None,
    username: Optional[str] = None,
    vault: Optional[str] = None,
    vault_id: Optional[str] = None,
    xport_scheduler: Optional[str] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for DIAGNOSTIC operations.
    
    This tool supports 14 actions: check_engine_connectivity, check_database_connectivity, check_netbackup_connectivity, check_commvault_connectivity, test_network_latency, get_network_latency_result, test_network_dsp, get_network_dsp_result, test_network_throughput, get_network_throughput_result, validate_file_mapping_by_snapshot, validate_file_mapping_by_location, validate_file_mapping_by_timestamp, validate_file_mapping_by_bookmark
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: check_engine_connectivity
    ----------------------------------------
    Summary: Checks connectivity between an engine and a remote host machine on a given port.
    Method: POST
    Endpoint: /connectivity/check
    Required Parameters: engine_id, host, port
    Key Parameters (provide as applicable): use_engine_public_key, os_name, staging_environment, username, password, vault_id, hashicorp_vault_engine, hashicorp_vault_secret_path, hashicorp_vault_username_key, hashicorp_vault_secret_key, azure_vault_name, azure_vault_username_key, azure_vault_secret_key, cyberark_vault_query_string, use_kerberos_authentication
    
    Example:
        >>> diagnostic_tool(action='check_engine_connectivity', engine_id='example-engine-123', use_engine_public_key=..., os_name=..., staging_environment=..., host=..., port=..., username=..., password=..., vault_id='example-vault-123', hashicorp_vault_engine=..., hashicorp_vault_secret_path=..., hashicorp_vault_username_key=..., hashicorp_vault_secret_key=..., azure_vault_name=..., azure_vault_username_key=..., azure_vault_secret_key=..., cyberark_vault_query_string=..., use_kerberos_authentication=...)
    
    ACTION: check_database_connectivity
    ----------------------------------------
    Summary: Tests the validity of the supplied database credentials, returning an error if unable to connect to the database.
    Method: POST
    Endpoint: /database/connectivity/check
    Required Parameters: credentials_type, source_id
    Key Parameters (provide as applicable): username, password, hashicorp_vault_engine, hashicorp_vault_secret_path, hashicorp_vault_username_key, hashicorp_vault_secret_key, azure_vault_name, azure_vault_username_key, azure_vault_secret_key, cyberark_vault_query_string, vault, environment_id, environment_user
    
    Example:
        >>> diagnostic_tool(action='check_database_connectivity', username=..., password=..., hashicorp_vault_engine=..., hashicorp_vault_secret_path=..., hashicorp_vault_username_key=..., hashicorp_vault_secret_key=..., azure_vault_name=..., azure_vault_username_key=..., azure_vault_secret_key=..., cyberark_vault_query_string=..., credentials_type=..., source_id='example-source-123', vault=..., environment_id='example-environment-123', environment_user=...)
    
    ACTION: check_netbackup_connectivity
    ----------------------------------------
    Summary: Checks whether the specified NetBackup master server and client are able to communicate on the given environment.
    Method: POST
    Endpoint: /netbackup/connectivity/check
    Required Parameters: environment_id, environment_user_id, master_server_name, source_client_name
    
    Example:
        >>> diagnostic_tool(action='check_netbackup_connectivity', environment_id='example-environment-123', environment_user_id='example-environment_user-123', master_server_name=..., source_client_name=...)
    
    ACTION: check_commvault_connectivity
    ----------------------------------------
    Summary: Tests whether the CommServe host is accessible from the given environment and Commvault agent.
    Method: POST
    Endpoint: /commvault/connectivity/check
    Required Parameters: environment_id, environment_user_id, source_client_name, commserve_host_name, staging_client_name
    
    Example:
        >>> diagnostic_tool(action='check_commvault_connectivity', environment_id='example-environment-123', environment_user_id='example-environment_user-123', source_client_name=..., commserve_host_name=..., staging_client_name=...)
    
    ACTION: test_network_latency
    ----------------------------------------
    Summary: Create Latency Network Performance Test
    Method: POST
    Endpoint: /network-performance/test/latency
    Required Parameters: engine_id, host_id
    Key Parameters (provide as applicable): request_count, request_size
    
    Example:
        >>> diagnostic_tool(action='test_network_latency', engine_id='example-engine-123', host_id='example-host-123', request_count=..., request_size=...)
    
    ACTION: get_network_latency_result
    ----------------------------------------
    Summary: Retrieve Network Latency Test Result
    Method: GET
    Endpoint: /network-performance/test/latency/{jobId}
    Required Parameters: job_id
    
    Example:
        >>> diagnostic_tool(action='get_network_latency_result', job_id='example-job-123')
    
    ACTION: test_network_dsp
    ----------------------------------------
    Summary: Create DSP Network Performance Test
    Method: POST
    Endpoint: /network-performance/test/dsp
    Required Parameters: engine_id
    Key Parameters (provide as applicable): host_id, direction, num_connections, duration, destination_type, compression, encryption, queue_depth, block_size, send_socket_buffer, receive_socket_buffer, xport_scheduler, target_engine_id, target_engine_address, target_engine_user, target_engine_password
    
    Example:
        >>> diagnostic_tool(action='test_network_dsp', engine_id='example-engine-123', host_id='example-host-123', direction=..., num_connections=..., duration=..., destination_type=..., compression=..., encryption=..., queue_depth=..., block_size=..., send_socket_buffer=..., receive_socket_buffer=..., xport_scheduler=..., target_engine_id='example-target_engine-123', target_engine_address=..., target_engine_user=..., target_engine_password=...)
    
    ACTION: get_network_dsp_result
    ----------------------------------------
    Summary: Retrieve Network DSP Test Result
    Method: GET
    Endpoint: /network-performance/test/dsp/{jobId}
    Required Parameters: job_id
    
    Example:
        >>> diagnostic_tool(action='get_network_dsp_result', job_id='example-job-123')
    
    ACTION: test_network_throughput
    ----------------------------------------
    Summary: Create Throughput Network Performance Test
    Method: POST
    Endpoint: /network-performance/test/throughput
    Required Parameters: engine_id, host_id
    Key Parameters (provide as applicable): port, direction, num_connections, duration, block_size, send_socket_buffer
    
    Example:
        >>> diagnostic_tool(action='test_network_throughput', engine_id='example-engine-123', port=..., host_id='example-host-123', direction=..., num_connections=..., duration=..., block_size=..., send_socket_buffer=...)
    
    ACTION: get_network_throughput_result
    ----------------------------------------
    Summary: Retrieve Network Throughput Test Result
    Method: GET
    Endpoint: /network-performance/test/throughput/{jobId}
    Required Parameters: job_id
    
    Example:
        >>> diagnostic_tool(action='get_network_throughput_result', job_id='example-job-123')
    
    ACTION: validate_file_mapping_by_snapshot
    ----------------------------------------
    Summary: Validate file mapping using snapshots
    Method: POST
    Endpoint: /file-mapping/validate-file-mapping-by-snapshot
    Required Parameters: snapshot_ids, file_mapping_rules
    Key Parameters (provide as applicable): file_system_layout
    
    Example:
        >>> diagnostic_tool(action='validate_file_mapping_by_snapshot', snapshot_ids=..., file_mapping_rules=..., file_system_layout=...)
    
    ACTION: validate_file_mapping_by_location
    ----------------------------------------
    Summary: Validate file mapping using location
    Method: POST
    Endpoint: /file-mapping/validate-file-mapping-by-location
    Required Parameters: file_mapping_rules, source_data_id, locations
    Key Parameters (provide as applicable): file_system_layout
    
    Example:
        >>> diagnostic_tool(action='validate_file_mapping_by_location', file_mapping_rules=..., file_system_layout=..., source_data_id='example-source_data-123', locations=...)
    
    ACTION: validate_file_mapping_by_timestamp
    ----------------------------------------
    Summary: Validate file mapping using timestamp
    Method: POST
    Endpoint: /file-mapping/validate-file-mapping-by-timestamp
    Required Parameters: file_mapping_rules, source_data_id, timestamps
    Key Parameters (provide as applicable): file_system_layout
    
    Example:
        >>> diagnostic_tool(action='validate_file_mapping_by_timestamp', file_mapping_rules=..., file_system_layout=..., source_data_id='example-source_data-123', timestamps=...)
    
    ACTION: validate_file_mapping_by_bookmark
    ----------------------------------------
    Summary: Validate file mapping using bookmark
    Method: POST
    Endpoint: /file-mapping/validate-file-mapping-by-bookmark
    Required Parameters: file_mapping_rules, bookmark_ids
    Key Parameters (provide as applicable): file_system_layout
    
    Example:
        >>> diagnostic_tool(action='validate_file_mapping_by_bookmark', file_mapping_rules=..., file_system_layout=..., bookmark_ids=...)
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: check_engine_connectivity, check_database_connectivity, check_netbackup_connectivity, check_commvault_connectivity, test_network_latency, get_network_latency_result, test_network_dsp, get_network_dsp_result, test_network_throughput, get_network_throughput_result, validate_file_mapping_by_snapshot, validate_file_mapping_by_location, validate_file_mapping_by_timestamp, validate_file_mapping_by_bookmark
    
      -- General parameters (all database types) --
        azure_vault_name (str): Azure key vault name (ORACLE, ASE and MSSQL_DOMAIN_USER only).
            [Optional for all actions]
        azure_vault_secret_key (str): Azure vault key for the password in the key-value store (ORACLE, ASE and MSSQ...
            [Optional for all actions]
        azure_vault_username_key (str): Azure vault key for the username in the key-value store (ORACLE, ASE and MSSQ...
            [Optional for all actions]
        block_size (int): The size of each transmit request in bytes. (Default: 1048576)
            [Optional for all actions]
        bookmark_ids (list): The list of bookmark IDs to use for file mapping. (Pass as JSON array)
            [Required for: validate_file_mapping_by_bookmark]
        commserve_host_name (str): The hostname of the CommServe server to connect to.
            [Required for: check_commvault_connectivity]
        compression (bool): Whether or not compression is used for the test. (Default: False)
            [Optional for all actions]
        credentials_type (str): The type of credentials. Valid values: MSSQL_ENVIRONMENT_USER, MSSQL_DOMAIN_U...
            [Required for: check_database_connectivity]
        cyberark_vault_query_string (str): Query to find a credential in the CyberArk vault.
            [Optional for all actions]
        destination_type (str): Whether the test is testing connectivity to a Delphix Engine or remote host. ...
            [Optional for all actions]
        direction (str): Whether the test is a transmit or receive test. Valid values: TRANSMIT, RECEI...
            [Optional for all actions]
        duration (int): The duration of the test in seconds. Note that when numConnections is 0, an i...
            [Optional for all actions]
        encryption (bool): Whether or not encryption is used for the test. (Default: False)
            [Optional for all actions]
        engine_id (str): The ID of the engine to check.
            [Required for: check_engine_connectivity, test_network_latency, test_network_dsp, test_network_throughput]
        environment_id (str): Id of the environment to which environment user belongs (MSSQL_ENVIRONMENT_US...
            [Required for: check_netbackup_connectivity, check_commvault_connectivity]
        environment_user (str): Reference to the environment user (MSSQL_ENVIRONMENT_USER only).
            [Optional for all actions]
        environment_user_id (str): Id of the environment user.
            [Required for: check_netbackup_connectivity, check_commvault_connectivity]
        file_mapping_rules (str): File mapping rules for the VDB provisioning.
            [Required for: validate_file_mapping_by_snapshot, validate_file_mapping_by_location, validate_file_mapping_by_timestamp, validate_file_mapping_by_bookmark]
        file_system_layout (dict): Request body parameter (Pass as JSON object)
            [Optional for all actions]
        hashicorp_vault_engine (str): Vault engine name where the credential is stored.
            [Optional for all actions]
        hashicorp_vault_secret_key (str): Key for the password in the key-value store.
            [Optional for all actions]
        hashicorp_vault_secret_path (str): Path in the vault engine where the credential is stored.
            [Optional for all actions]
        hashicorp_vault_username_key (str): Key for the username in the key-value store.
            [Optional for all actions]
        host (str): The hostname of the remote host machine to check.
            [Required for: check_engine_connectivity]
        host_id (str): Identifier of host that must exist within an associated with engine.
            [Required for: test_network_latency, test_network_throughput]
        job_id (str): The unique identifier for the job.
            [Required for: get_network_latency_result, get_network_dsp_result, get_network_throughput_result]
        locations (list): The list of locations to use for source files to be mapped. (Pass as JSON array)
            [Required for: validate_file_mapping_by_location]
        master_server_name (str): The name of the NetBackup master server to attempt to connect to.
            [Required for: check_netbackup_connectivity]
        num_connections (int): The number of connections to use for the test. The special value 0 (the defau...
            [Optional for all actions]
        os_name (str): Operating system type of the environment. Valid values: UNIX, WINDOWS.
            [Optional for all actions]
        password (str): The password of the remote host machine to check.
            [Optional for all actions]
        port (int): The port of the remote host machine to check. For Windows, port on which Delp...
            [Required for: check_engine_connectivity]
        queue_depth (int): The queue depth used for the DSP throughput test. (Default: 64)
            [Optional for all actions]
        receive_socket_buffer (int): The size of the receive socket buffer in bytes. (Default: 1048576)
            [Optional for all actions]
        request_count (int): Number of requests to send. (Default: 20)
            [Optional for all actions]
        request_size (int): The size of requests to send (bytes). (Default: 16)
            [Optional for all actions]
        send_socket_buffer (int): The size of the send socket buffer in bytes. (Default: 1048576)
            [Optional for all actions]
        snapshot_ids (list): The list of snapshots to use for source files to be mapped. (Pass as JSON array)
            [Required for: validate_file_mapping_by_snapshot]
        source_client_name (str): The name of the NetBackup client to attempt to connect with.
            [Required for: check_netbackup_connectivity, check_commvault_connectivity]
        source_data_id (str): The ID of the source object (dSource or VDB) to provision from.
            [Required for: validate_file_mapping_by_location, validate_file_mapping_by_timestamp]
        source_id (str): Source database config Id.
            [Required for: check_database_connectivity]
        staging_client_name (str): The name of the Staging Client in CommServe.
            [Required for: check_commvault_connectivity]
        staging_environment (str): Id of the connector environment which is used to connect to this source envir...
            [Optional for all actions]
        target_engine_address (str): Address of other target Delphix Engine.
            [Optional for all actions]
        target_engine_id (str): engine id which test exc
            [Optional for all actions]
        target_engine_password (str): Password for the other target Delphix Engine.
            [Optional for all actions]
        target_engine_user (str): Username for the other target Delphix Engine.
            [Optional for all actions]
        timestamps (list): The list of timestamps to use for source files to be mapped. (Pass as JSON ar...
            [Required for: validate_file_mapping_by_timestamp]
        use_engine_public_key (bool): Whether to use public key authentication.
            [Optional for all actions]
        use_kerberos_authentication (bool): Whether to use kerberos authentication.
            [Optional for all actions]
        username (str): The username of the remote host machine to check. Username is mandatory input...
            [Optional for all actions]
        vault (str): The name or reference of the vault from which to read the database credential...
            [Optional for all actions]
        vault_id (str): The DCT id or name of the vault from which to read the host credentials.
            [Optional for all actions]
        xport_scheduler (str): The transport scheduler to use. Valid values: ROUND_ROBIN, LEAST_QUEUE. (Defa...
            [Optional for all actions]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'check_engine_connectivity':
        params = build_params(host=host, port=port)
        body = {k: v for k, v in {'engine_id': engine_id, 'use_engine_public_key': use_engine_public_key, 'os_name': os_name, 'staging_environment': staging_environment, 'host': host, 'port': port, 'username': username, 'password': password, 'vault_id': vault_id, 'hashicorp_vault_engine': hashicorp_vault_engine, 'hashicorp_vault_secret_path': hashicorp_vault_secret_path, 'hashicorp_vault_username_key': hashicorp_vault_username_key, 'hashicorp_vault_secret_key': hashicorp_vault_secret_key, 'azure_vault_name': azure_vault_name, 'azure_vault_username_key': azure_vault_username_key, 'azure_vault_secret_key': azure_vault_secret_key, 'cyberark_vault_query_string': cyberark_vault_query_string, 'use_kerberos_authentication': use_kerberos_authentication}.items() if v is not None}
        conf = check_confirmation('POST', '/connectivity/check', action, 'diagnostic_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/connectivity/check', params=params, json_body=body if body else None)
    elif action == 'check_database_connectivity':
        params = build_params(credentials_type=credentials_type)
        body = {k: v for k, v in {'credentials_type': credentials_type, 'source_id': source_id, 'username': username, 'password': password, 'vault': vault, 'hashicorp_vault_engine': hashicorp_vault_engine, 'hashicorp_vault_secret_path': hashicorp_vault_secret_path, 'hashicorp_vault_username_key': hashicorp_vault_username_key, 'hashicorp_vault_secret_key': hashicorp_vault_secret_key, 'azure_vault_name': azure_vault_name, 'azure_vault_username_key': azure_vault_username_key, 'azure_vault_secret_key': azure_vault_secret_key, 'cyberark_vault_query_string': cyberark_vault_query_string, 'environment_id': environment_id, 'environment_user': environment_user}.items() if v is not None}
        conf = check_confirmation('POST', '/database/connectivity/check', action, 'diagnostic_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/database/connectivity/check', params=params, json_body=body if body else None)
    elif action == 'check_netbackup_connectivity':
        params = build_params(master_server_name=master_server_name, source_client_name=source_client_name)
        if not environment_user_id:
            environment_user_id = environment_user_ref or environment_user
        body = {k: v for k, v in {'environment_id': environment_id, 'environment_user_id': environment_user_id, 'master_server_name': master_server_name, 'source_client_name': source_client_name}.items() if v is not None}
        conf = check_confirmation('POST', '/netbackup/connectivity/check', action, 'diagnostic_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/netbackup/connectivity/check', params=params, json_body=body if body else None)
    elif action == 'check_commvault_connectivity':
        params = build_params(source_client_name=source_client_name, commserve_host_name=commserve_host_name, staging_client_name=staging_client_name)
        if not environment_user_id:
            environment_user_id = environment_user_ref or environment_user
        body = {k: v for k, v in {'environment_id': environment_id, 'environment_user_id': environment_user_id, 'commserve_host_name': commserve_host_name, 'source_client_name': source_client_name, 'staging_client_name': staging_client_name}.items() if v is not None}
        conf = check_confirmation('POST', '/commvault/connectivity/check', action, 'diagnostic_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/commvault/connectivity/check', params=params, json_body=body if body else None)
    elif action == 'test_network_latency':
        params = build_params()
        body = {k: v for k, v in {'engine_id': engine_id, 'host_id': host_id, 'request_count': request_count, 'request_size': request_size}.items() if v is not None}
        conf = check_confirmation('POST', '/network-performance/test/latency', action, 'diagnostic_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/network-performance/test/latency', params=params, json_body=body if body else None)
    elif action == 'get_network_latency_result':
        if job_id is None:
            return {'error': 'Missing required parameter: job_id for action get_network_latency_result'}
        endpoint = f'/network-performance/test/latency/{job_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'diagnostic_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'test_network_dsp':
        params = build_params()
        body = {k: v for k, v in {'engine_id': engine_id, 'host_id': host_id, 'direction': direction, 'num_connections': num_connections, 'duration': duration, 'destination_type': destination_type, 'compression': compression, 'encryption': encryption, 'queue_depth': queue_depth, 'block_size': block_size, 'send_socket_buffer': send_socket_buffer, 'receive_socket_buffer': receive_socket_buffer, 'xport_scheduler': xport_scheduler, 'target_engine_id': target_engine_id, 'target_engine_address': target_engine_address, 'target_engine_user': target_engine_user, 'target_engine_password': target_engine_password}.items() if v is not None}
        conf = check_confirmation('POST', '/network-performance/test/dsp', action, 'diagnostic_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/network-performance/test/dsp', params=params, json_body=body if body else None)
    elif action == 'get_network_dsp_result':
        if job_id is None:
            return {'error': 'Missing required parameter: job_id for action get_network_dsp_result'}
        endpoint = f'/network-performance/test/dsp/{job_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'diagnostic_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'test_network_throughput':
        params = build_params()
        body = {k: v for k, v in {'engine_id': engine_id, 'host_id': host_id, 'direction': direction, 'num_connections': num_connections, 'duration': duration, 'port': port, 'block_size': block_size, 'send_socket_buffer': send_socket_buffer}.items() if v is not None}
        conf = check_confirmation('POST', '/network-performance/test/throughput', action, 'diagnostic_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/network-performance/test/throughput', params=params, json_body=body if body else None)
    elif action == 'get_network_throughput_result':
        if job_id is None:
            return {'error': 'Missing required parameter: job_id for action get_network_throughput_result'}
        endpoint = f'/network-performance/test/throughput/{job_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'diagnostic_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'validate_file_mapping_by_snapshot':
        params = build_params(snapshot_ids=snapshot_ids, file_mapping_rules=file_mapping_rules)
        body = {k: v for k, v in {'snapshot_ids': snapshot_ids, 'file_mapping_rules': file_mapping_rules, 'file_system_layout': file_system_layout}.items() if v is not None}
        conf = check_confirmation('POST', '/file-mapping/validate-file-mapping-by-snapshot', action, 'diagnostic_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/file-mapping/validate-file-mapping-by-snapshot', params=params, json_body=body if body else None)
    elif action == 'validate_file_mapping_by_location':
        params = build_params(file_mapping_rules=file_mapping_rules, locations=locations)
        body = {k: v for k, v in {'source_data_id': source_data_id, 'locations': locations, 'file_mapping_rules': file_mapping_rules, 'file_system_layout': file_system_layout}.items() if v is not None}
        conf = check_confirmation('POST', '/file-mapping/validate-file-mapping-by-location', action, 'diagnostic_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/file-mapping/validate-file-mapping-by-location', params=params, json_body=body if body else None)
    elif action == 'validate_file_mapping_by_timestamp':
        params = build_params(file_mapping_rules=file_mapping_rules, timestamps=timestamps)
        body = {k: v for k, v in {'source_data_id': source_data_id, 'timestamps': timestamps, 'file_mapping_rules': file_mapping_rules, 'file_system_layout': file_system_layout}.items() if v is not None}
        conf = check_confirmation('POST', '/file-mapping/validate-file-mapping-by-timestamp', action, 'diagnostic_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/file-mapping/validate-file-mapping-by-timestamp', params=params, json_body=body if body else None)
    elif action == 'validate_file_mapping_by_bookmark':
        params = build_params(file_mapping_rules=file_mapping_rules, bookmark_ids=bookmark_ids)
        body = {k: v for k, v in {'bookmark_ids': bookmark_ids, 'file_mapping_rules': file_mapping_rules, 'file_system_layout': file_system_layout}.items() if v is not None}
        conf = check_confirmation('POST', '/file-mapping/validate-file-mapping-by-bookmark', action, 'diagnostic_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/file-mapping/validate-file-mapping-by-bookmark', params=params, json_body=body if body else None)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: check_engine_connectivity, check_database_connectivity, check_netbackup_connectivity, check_commvault_connectivity, test_network_latency, get_network_latency_result, test_network_dsp, get_network_dsp_result, test_network_throughput, get_network_throughput_result, validate_file_mapping_by_snapshot, validate_file_mapping_by_location, validate_file_mapping_by_timestamp, validate_file_mapping_by_bookmark'}


def register_tools(app, dct_client):
    global client
    client = dct_client
    logger.info(f'Registering tools for misc_endpoints...')
    try:
        logger.info(f'  Registering tool function: instance_tool')
        app.add_tool(instance_tool, name="instance_tool")
        logger.info(f'  Registering tool function: staging_source_tool')
        app.add_tool(staging_source_tool, name="staging_source_tool")
        logger.info(f'  Registering tool function: staging_cdb_tool')
        app.add_tool(staging_cdb_tool, name="staging_cdb_tool")
        logger.info(f'  Registering tool function: cdb_dsource_tool')
        app.add_tool(cdb_dsource_tool, name="cdb_dsource_tool")
        logger.info(f'  Registering tool function: group_tool')
        app.add_tool(group_tool, name="group_tool")
        logger.info(f'  Registering tool function: vault_tool')
        app.add_tool(vault_tool, name="vault_tool")
        logger.info(f'  Registering tool function: diagnostic_tool')
        app.add_tool(diagnostic_tool, name="diagnostic_tool")
    except Exception as e:
        logger.error(f'Error registering tools for misc_endpoints: {e}')
    logger.info(f'Tools registration finished for misc_endpoints.')
