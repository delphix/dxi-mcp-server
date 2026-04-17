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
def engine_tool(
    action: str,  # One of: search, get, update, get_tags, add_tags, delete_tags, register, unregister, get_auto_tagging, get_compliance_settings, search_compliance_settings
    auto_tagging_config: Optional[dict] = None,
    connection_status: Optional[str] = None,
    connection_status_details: Optional[str] = None,
    cpu_core_count: Optional[int] = None,
    cursor: Optional[str] = None,
    data_storage_capacity: Optional[int] = None,
    data_storage_used: Optional[int] = None,
    engine_connection_status: Optional[str] = None,
    engine_connection_status_details: Optional[str] = None,
    engine_id: Optional[str] = None,
    filter_expression: Optional[str] = None,
    hashicorp_vault_id: Optional[int] = None,
    hashicorp_vault_masking_password_command_args: Optional[list] = None,
    hashicorp_vault_masking_username_command_args: Optional[list] = None,
    hashicorp_vault_password_command_args: Optional[list] = None,
    hashicorp_vault_username_command_args: Optional[list] = None,
    hostname: Optional[str] = None,
    hyperscale_instance_ids: Optional[list] = None,
    hyperscale_truststore_filename: Optional[str] = None,
    hyperscale_truststore_password: Optional[str] = None,
    id: Optional[str] = None,
    insecure_ssl: Optional[bool] = None,
    key: Optional[str] = None,
    limit: Optional[int] = 100,
    masking_allocated_memory: Optional[int] = None,
    masking_available_cores: Optional[int] = None,
    masking_hashicorp_vault_id: Optional[int] = None,
    masking_jobs_running: Optional[int] = None,
    masking_max_concurrent_jobs: Optional[int] = None,
    masking_memory_used: Optional[int] = None,
    masking_password: Optional[str] = None,
    masking_username: Optional[str] = None,
    memory_size: Optional[int] = None,
    name: Optional[str] = None,
    password: Optional[str] = None,
    platform: Optional[str] = None,
    priority_cache_max_bytes: Optional[int] = None,
    priority_cache_used_bytes: Optional[int] = None,
    sort: Optional[str] = None,
    ssh_public_key: Optional[str] = None,
    status: Optional[str] = None,
    storage_cache_bytes: Optional[int] = None,
    tags: Optional[list] = None,
    type: Optional[str] = None,
    unsafe_ssl_hostname_check: Optional[bool] = None,
    username: Optional[str] = None,
    using_continuous_vault: Optional[bool] = None,
    using_object_storage: Optional[bool] = None,
    uuid: Optional[str] = None,
    value: Optional[str] = None,
    version: Optional[str] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for ENGINE operations.
    
    This tool supports 11 actions: search, get, update, get_tags, add_tags, delete_tags, register, unregister, get_auto_tagging, get_compliance_settings, search_compliance_settings
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search for engines.
    Method: POST
    Endpoint: /management/engines/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - id: The Engine object entity ID.
        - uuid: The unique identifier generated by this engine.
        - type: The type of this engine.
        - version: The engine version.
        - name: The name of this engine.
        - ssh_public_key: The ssh public key of this engine.
        - hostname: The hostname of this engine.
        - cpu_core_count: The total number of CPU cores on this engine.
        - memory_size: The total amount of memory on this engine, in bytes.
        - data_storage_capacity: The total amount of storage allocated for engine objects ...
        - data_storage_used: The amount of storage used by engine objects and system m...
        - insecure_ssl: Allow connections to the engine over HTTPs without valida...
        - unsafe_ssl_hostname_check: Ignore validation of the name associated to the TLS certi...
        - status: the status of the engine

        - connection_status: The status of the connection to the engine. Deprecated; u...
        - engine_connection_status: The state of the connection to the engine.
        - connection_status_details: If set, details about the status of the connection to the...
        - engine_connection_status_details: If set, details about the state of the connection to the ...
        - username: The virtualization domain admin username.
        - password: The virtualization domain admin password.
        - masking_username: The masking admin username.
        - masking_password: The masking admin password.
        - hashicorp_vault_username_command_args: Arguments to pass to the Vault CLI tool to retrieve the v...
        - hashicorp_vault_masking_username_command_args: Arguments to pass to the Vault CLI tool to retrieve the m...
        - hashicorp_vault_password_command_args: Arguments to pass to the Vault CLI tool to retrieve the v...
        - hashicorp_vault_masking_password_command_args: Arguments to pass to the Vault CLI tool to retrieve the m...
        - masking_hashicorp_vault_id: Reference to the Hashicorp vault to use to retrieve maski...
        - hashicorp_vault_id: Reference to the Hashicorp vault to use to retrieve virtu...
        - tags: The tags to be created for this engine.
        - masking_memory_used: The current amount of memory used by running masking jobs...
        - masking_allocated_memory: The maximum amount of memory available for running maskin...
        - masking_jobs_running: The number of masking jobs currently running.
        - masking_max_concurrent_jobs: The maximum number of masking jobs that can be running at...
        - masking_available_cores: The number of CPU cores available to the masking engine.
        - hyperscale_instance_ids: List of Hyperscale Instances that this engine is connecte...
        - hyperscale_truststore_filename: File name of a truststore which can be used to validate t...
        - hyperscale_truststore_password: Password to read the truststore as expected by associated...
        - using_object_storage: true if the engine is using an object store (like AWS S3)...
        - using_continuous_vault: true if the engine is using an object store (like AWS S3)...
        - platform: The infrastructure or environment where the engine is dep...
        - storage_cache_bytes: Total number of bytes of storage reserved for storage cache
        - priority_cache_max_bytes: Total number of bytes of storage available for VDB priori...
        - priority_cache_used_bytes: Total number of bytes of storage allocated to existing pr...
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> engine_tool(action='search', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get
    ----------------------------------------
    Summary: Returns a registered engine by ID.
    Method: GET
    Endpoint: /management/engines/{engineId}
    Required Parameters: engine_id
    
    Example:
        >>> engine_tool(action='get', engine_id='example-engine-123')
    
    ACTION: update
    ----------------------------------------
    Summary: Update a registered engine.
    Method: PATCH
    Endpoint: /management/engines/{engineId}
    Required Parameters: engine_id
    Key Parameters (provide as applicable): id, uuid, type, version, name, ssh_public_key, hostname, cpu_core_count, memory_size, data_storage_capacity, data_storage_used, insecure_ssl, unsafe_ssl_hostname_check, status, connection_status, engine_connection_status, connection_status_details, engine_connection_status_details, username, password, masking_username, masking_password, hashicorp_vault_username_command_args, hashicorp_vault_masking_username_command_args, hashicorp_vault_password_command_args, hashicorp_vault_masking_password_command_args, masking_hashicorp_vault_id, hashicorp_vault_id, tags, masking_memory_used, masking_allocated_memory, masking_jobs_running, masking_max_concurrent_jobs, masking_available_cores, hyperscale_instance_ids, hyperscale_truststore_filename, hyperscale_truststore_password, using_object_storage, using_continuous_vault, platform, storage_cache_bytes, priority_cache_max_bytes, priority_cache_used_bytes
    
    Example:
        >>> engine_tool(action='update', engine_id='example-engine-123', id=..., uuid=..., type=..., version=..., name=..., ssh_public_key=..., hostname=..., cpu_core_count=..., memory_size=..., data_storage_capacity=..., data_storage_used=..., insecure_ssl=..., unsafe_ssl_hostname_check=..., status=..., connection_status=..., engine_connection_status=..., connection_status_details=..., engine_connection_status_details=..., username=..., password=..., masking_username=..., masking_password=..., hashicorp_vault_username_command_args=..., hashicorp_vault_masking_username_command_args=..., hashicorp_vault_password_command_args=..., hashicorp_vault_masking_password_command_args=..., masking_hashicorp_vault_id='example-masking_hashicorp_vault-123', hashicorp_vault_id='example-hashicorp_vault-123', tags=..., masking_memory_used=..., masking_allocated_memory=..., masking_jobs_running=..., masking_max_concurrent_jobs=..., masking_available_cores=..., hyperscale_instance_ids=..., hyperscale_truststore_filename=..., hyperscale_truststore_password=..., using_object_storage=..., using_continuous_vault=..., platform=..., storage_cache_bytes=..., priority_cache_max_bytes=..., priority_cache_used_bytes=...)
    
    ACTION: get_tags
    ----------------------------------------
    Summary: Get tags for a Engine.
    Method: GET
    Endpoint: /management/engines/{engineId}/tags
    Required Parameters: engine_id
    
    Example:
        >>> engine_tool(action='get_tags', engine_id='example-engine-123')
    
    ACTION: add_tags
    ----------------------------------------
    Summary: Create tags for an Engine.
    Method: POST
    Endpoint: /management/engines/{engineId}/tags
    Required Parameters: engine_id, tags
    
    Example:
        >>> engine_tool(action='add_tags', engine_id='example-engine-123', tags=...)
    
    ACTION: delete_tags
    ----------------------------------------
    Summary: Delete tags for an Engine.
    Method: POST
    Endpoint: /management/engines/{engineId}/tags/delete
    Required Parameters: engine_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> engine_tool(action='delete_tags', engine_id='example-engine-123', tags=..., key=..., value=...)
    
    ACTION: register
    ----------------------------------------
    Summary: Register an engine.
    Method: POST
    Endpoint: /management/engines
    Required Parameters: name, hostname
    Key Parameters (provide as applicable): insecure_ssl, unsafe_ssl_hostname_check, username, password, masking_username, masking_password, hashicorp_vault_username_command_args, hashicorp_vault_masking_username_command_args, hashicorp_vault_password_command_args, hashicorp_vault_masking_password_command_args, masking_hashicorp_vault_id, hashicorp_vault_id, tags, auto_tagging_config
    
    Example:
        >>> engine_tool(action='register', name=..., hostname=..., insecure_ssl=..., unsafe_ssl_hostname_check=..., username=..., password=..., masking_username=..., masking_password=..., hashicorp_vault_username_command_args=..., hashicorp_vault_masking_username_command_args=..., hashicorp_vault_password_command_args=..., hashicorp_vault_masking_password_command_args=..., masking_hashicorp_vault_id='example-masking_hashicorp_vault-123', hashicorp_vault_id='example-hashicorp_vault-123', tags=..., auto_tagging_config=...)
    
    ACTION: unregister
    ----------------------------------------
    Summary: Unregister an engine.
    Method: DELETE
    Endpoint: /management/engines/{engineId}
    Required Parameters: engine_id
    
    Example:
        >>> engine_tool(action='unregister', engine_id='example-engine-123')
    
    ACTION: get_auto_tagging
    ----------------------------------------
    Summary: Returns the engine's auto tagging configuration.
    Method: GET
    Endpoint: /management/engines/{engineId}/auto-tagging
    Required Parameters: engine_id
    
    Example:
        >>> engine_tool(action='get_auto_tagging', engine_id='example-engine-123')
    
    ACTION: get_compliance_settings
    ----------------------------------------
    Summary: Returns a compliance engine's application settings.
    Method: GET
    Endpoint: /management/engines/{engineId}/compliance-application-settings
    Required Parameters: limit, cursor, sort, engine_id
    
    Example:
        >>> engine_tool(action='get_compliance_settings', limit=..., cursor=..., sort=..., engine_id='example-engine-123')
    
    ACTION: search_compliance_settings
    ----------------------------------------
    Summary: Search a compliance engine's application settings.
    Method: POST
    Endpoint: /management/engines/{engineId}/compliance-application-settings/search
    Required Parameters: limit, cursor, sort, engine_id
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - id: The ID of the application setting.
        - group: The group of the application setting.
        - name: The name of the application setting.
        - value: The value of the application setting.
        - value_type: The type of the value of the application setting.
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> engine_tool(action='search_compliance_settings', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'", engine_id='example-engine-123')
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, update, get_tags, add_tags, delete_tags, register, unregister, get_auto_tagging, get_compliance_settings, search_compliance_settings
    
      -- General parameters (all database types) --
        auto_tagging_config (dict): Configuration settings for auto tagging. (Pass as JSON object)
            [Optional for all actions]
        connection_status (str): The status of the connection to the engine. Deprecated; use "engine_connectio...
            [Optional for all actions]
        connection_status_details (str): If set, details about the status of the connection to the engine. Deprecated;...
            [Optional for all actions]
        cpu_core_count (int): The total number of CPU cores on this engine.
            [Optional for all actions]
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search, get_compliance_settings, search_compliance_settings]
        data_storage_capacity (int): The total amount of storage allocated for engine objects and system metadata,...
            [Optional for all actions]
        data_storage_used (int): The amount of storage used by engine objects and system metadata, in bytes.
            [Optional for all actions]
        engine_connection_status (str): The state of the connection to the engine. Valid values: ONLINE, CONNECTION_E...
            [Optional for all actions]
        engine_connection_status_details (str): If set, details about the state of the connection to the engine.
            [Optional for all actions]
        engine_id (str): The unique identifier for the engine.
            [Required for: get, update, get_tags, add_tags, delete_tags, unregister, get_auto_tagging, get_compliance_settings, search_compliance_settings]
        filter_expression (str): Request body parameter
            [Optional for all actions]
        hashicorp_vault_id (int): Reference to the Hashicorp vault to use to retrieve virtualization engine cre...
            [Optional for all actions]
        hashicorp_vault_masking_password_command_args (list): Arguments to pass to the Vault CLI tool to retrieve the masking password for ...
            [Optional for all actions]
        hashicorp_vault_masking_username_command_args (list): Arguments to pass to the Vault CLI tool to retrieve the masking username for ...
            [Optional for all actions]
        hashicorp_vault_password_command_args (list): Arguments to pass to the Vault CLI tool to retrieve the virtualization passwo...
            [Optional for all actions]
        hashicorp_vault_username_command_args (list): Arguments to pass to the Vault CLI tool to retrieve the virtualization userna...
            [Optional for all actions]
        hostname (str): The hostname of this engine.
            [Required for: register]
        hyperscale_instance_ids (list): List of Hyperscale Instances that this engine is connected to. (Pass as JSON ...
            [Optional for all actions]
        hyperscale_truststore_filename (str): File name of a truststore which can be used to validate the TLS certificate o...
            [Optional for all actions]
        hyperscale_truststore_password (str): Password to read the truststore as expected by associated hyperscale instances.

            [Optional for all actions]
        id (str): The Engine object entity ID.
            [Optional for all actions]
        insecure_ssl (bool): Allow connections to the engine over HTTPs without validating the TLS certifi...
            [Optional for all actions]
        key (str): Key of the tag
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search, get_compliance_settings, search_compliance_settings]
        masking_allocated_memory (int): The maximum amount of memory available for running masking jobs in bytes.
            [Optional for all actions]
        masking_available_cores (int): The number of CPU cores available to the masking engine.
            [Optional for all actions]
        masking_hashicorp_vault_id (int): Reference to the Hashicorp vault to use to retrieve masking engine credentials.
            [Optional for all actions]
        masking_jobs_running (int): The number of masking jobs currently running.
            [Optional for all actions]
        masking_max_concurrent_jobs (int): The maximum number of masking jobs that can be running at the same time.
            [Optional for all actions]
        masking_memory_used (int): The current amount of memory used by running masking jobs in bytes.
            [Optional for all actions]
        masking_password (str): The masking admin password.
            [Optional for all actions]
        masking_username (str): The masking admin username.
            [Optional for all actions]
        memory_size (int): The total amount of memory on this engine, in bytes.
            [Optional for all actions]
        name (str): The name of this engine.
            [Required for: register]
        password (str): The virtualization domain admin password.
            [Optional for all actions]
        platform (str): The infrastructure or environment where the engine is deployed or built, incl...
            [Optional for all actions]
        priority_cache_max_bytes (int): Total number of bytes of storage available for VDB priority caching
            [Optional for all actions]
        priority_cache_used_bytes (int): Total number of bytes of storage allocated to existing priority cache enabled...
            [Optional for all actions]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search, get_compliance_settings, search_compliance_settings]
        ssh_public_key (str): The ssh public key of this engine.
            [Optional for all actions]
        status (str): the status of the engine
 Valid values: CREATED, DELETING.
            [Optional for all actions]
        storage_cache_bytes (int): Total number of bytes of storage reserved for storage cache
            [Optional for all actions]
        tags (list): The tags to be created for this engine. (Pass as JSON array)
            [Required for: add_tags]
        type (str): The type of this engine. Valid values: VIRTUALIZATION, MASKING, BOTH, UNSET.
            [Optional for all actions]
        unsafe_ssl_hostname_check (bool): Ignore validation of the name associated to the TLS certificate when connecti...
            [Optional for all actions]
        username (str): The virtualization domain admin username.
            [Optional for all actions]
        using_continuous_vault (bool): true if the engine is using an object store (like AWS S3) to store data |
fal...
            [Optional for all actions]
        using_object_storage (bool): true if the engine is using an object store (like AWS S3) to store data |
fal...
            [Optional for all actions]
        uuid (str): The unique identifier generated by this engine.
            [Optional for all actions]
        value (str): Value of the tag
            [Optional for all actions]
        version (str): The engine version.
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
        conf = check_confirmation('POST', '/management/engines/search', action, 'engine_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/management/engines/search', params=params, json_body=body)
    elif action == 'get':
        if engine_id is None:
            return {'error': 'Missing required parameter: engine_id for action get'}
        endpoint = f'/management/engines/{engine_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'engine_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'update':
        if engine_id is None:
            return {'error': 'Missing required parameter: engine_id for action update'}
        endpoint = f'/management/engines/{engine_id}'
        params = build_params()
        body = {k: v for k, v in {'id': id, 'uuid': uuid, 'type': type, 'version': version, 'name': name, 'ssh_public_key': ssh_public_key, 'hostname': hostname, 'cpu_core_count': cpu_core_count, 'memory_size': memory_size, 'data_storage_capacity': data_storage_capacity, 'data_storage_used': data_storage_used, 'insecure_ssl': insecure_ssl, 'unsafe_ssl_hostname_check': unsafe_ssl_hostname_check, 'status': status, 'connection_status': connection_status, 'engine_connection_status': engine_connection_status, 'connection_status_details': connection_status_details, 'engine_connection_status_details': engine_connection_status_details, 'username': username, 'password': password, 'masking_username': masking_username, 'masking_password': masking_password, 'hashicorp_vault_username_command_args': hashicorp_vault_username_command_args, 'hashicorp_vault_masking_username_command_args': hashicorp_vault_masking_username_command_args, 'hashicorp_vault_password_command_args': hashicorp_vault_password_command_args, 'hashicorp_vault_masking_password_command_args': hashicorp_vault_masking_password_command_args, 'masking_hashicorp_vault_id': masking_hashicorp_vault_id, 'hashicorp_vault_id': hashicorp_vault_id, 'tags': tags, 'masking_memory_used': masking_memory_used, 'masking_allocated_memory': masking_allocated_memory, 'masking_jobs_running': masking_jobs_running, 'masking_max_concurrent_jobs': masking_max_concurrent_jobs, 'masking_available_cores': masking_available_cores, 'hyperscale_instance_ids': hyperscale_instance_ids, 'hyperscale_truststore_filename': hyperscale_truststore_filename, 'hyperscale_truststore_password': hyperscale_truststore_password, 'using_object_storage': using_object_storage, 'using_continuous_vault': using_continuous_vault, 'platform': platform, 'storage_cache_bytes': storage_cache_bytes, 'priority_cache_max_bytes': priority_cache_max_bytes, 'priority_cache_used_bytes': priority_cache_used_bytes}.items() if v is not None}
        conf = check_confirmation('PATCH', endpoint, action, 'engine_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'get_tags':
        if engine_id is None:
            return {'error': 'Missing required parameter: engine_id for action get_tags'}
        endpoint = f'/management/engines/{engine_id}/tags'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'engine_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_tags':
        if engine_id is None:
            return {'error': 'Missing required parameter: engine_id for action add_tags'}
        endpoint = f'/management/engines/{engine_id}/tags'
        params = build_params(tags=tags)
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'engine_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_tags':
        if engine_id is None:
            return {'error': 'Missing required parameter: engine_id for action delete_tags'}
        endpoint = f'/management/engines/{engine_id}/tags/delete'
        params = build_params()
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'engine_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'register':
        params = build_params(name=name, hostname=hostname)
        body = {k: v for k, v in {'name': name, 'hostname': hostname, 'username': username, 'password': password, 'masking_username': masking_username, 'masking_password': masking_password, 'hashicorp_vault_username_command_args': hashicorp_vault_username_command_args, 'hashicorp_vault_masking_username_command_args': hashicorp_vault_masking_username_command_args, 'hashicorp_vault_password_command_args': hashicorp_vault_password_command_args, 'hashicorp_vault_masking_password_command_args': hashicorp_vault_masking_password_command_args, 'hashicorp_vault_id': hashicorp_vault_id, 'masking_hashicorp_vault_id': masking_hashicorp_vault_id, 'insecure_ssl': insecure_ssl, 'unsafe_ssl_hostname_check': unsafe_ssl_hostname_check, 'auto_tagging_config': auto_tagging_config, 'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', '/management/engines', action, 'engine_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/management/engines', params=params, json_body=body if body else None)
    elif action == 'unregister':
        if engine_id is None:
            return {'error': 'Missing required parameter: engine_id for action unregister'}
        endpoint = f'/management/engines/{engine_id}'
        params = build_params()
        conf = check_confirmation('DELETE', endpoint, action, 'engine_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'get_auto_tagging':
        if engine_id is None:
            return {'error': 'Missing required parameter: engine_id for action get_auto_tagging'}
        endpoint = f'/management/engines/{engine_id}/auto-tagging'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'engine_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'get_compliance_settings':
        if engine_id is None:
            return {'error': 'Missing required parameter: engine_id for action get_compliance_settings'}
        endpoint = f'/management/engines/{engine_id}/compliance-application-settings'
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('GET', endpoint, action, 'engine_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'search_compliance_settings':
        if engine_id is None:
            return {'error': 'Missing required parameter: engine_id for action search_compliance_settings'}
        endpoint = f'/management/engines/{engine_id}/compliance-application-settings/search'
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', endpoint, action, 'engine_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, update, get_tags, add_tags, delete_tags, register, unregister, get_auto_tagging, get_compliance_settings, search_compliance_settings'}


def register_tools(app, dct_client):
    global client
    client = dct_client
    logger.info(f'Registering tools for engine_endpoints...')
    try:
        logger.info(f'  Registering tool function: engine_tool')
        app.add_tool(engine_tool, name="engine_tool")
    except Exception as e:
        logger.error(f'Error registering tools for engine_endpoints: {e}')
    logger.info(f'Tools registration finished for engine_endpoints.')
