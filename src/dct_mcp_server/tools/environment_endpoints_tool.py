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
def environment_source_tool(
    action: str,  # One of: search_environments, get_environment, create_environment, add_environment_users, set_environment_primary_user, update_environment_users, delete_environment_users, update_environment, delete_environment, enable_environment, disable_environment, refresh_environment, list_environment_hosts, update_environment_host, delete_environment_host, list_environment_listeners, get_environment_tags, add_environment_tags, delete_environment_tags, get_environment_compatible_repositories_by_snapshot, get_environment_compatible_repositories_by_timestamp, get_environment_compatible_repositories_by_location, update_environment_repository, delete_environment_repository, search_sources, list_sources, get_source, delete_source, verify_source_jdbc_connection, get_source_compatible_repositories, get_source_tags, add_source_tags, delete_source_tags, create_oracle_source, update_oracle_source, create_postgres_source, update_postgres_source, create_ase_source, update_ase_source, create_appdata_source, update_appdata_source
    allow_provisioning: Optional[bool] = None,
    ase_db_azure_vault_name: Optional[str] = None,
    ase_db_azure_vault_secret_key: Optional[str] = None,
    ase_db_azure_vault_username_key: Optional[str] = None,
    ase_db_cyberark_vault_query_string: Optional[str] = None,
    ase_db_hashicorp_vault_engine: Optional[str] = None,
    ase_db_hashicorp_vault_secret_key: Optional[str] = None,
    ase_db_hashicorp_vault_secret_path: Optional[str] = None,
    ase_db_hashicorp_vault_username_key: Optional[str] = None,
    ase_db_password: Optional[str] = None,
    ase_db_use_kerberos_authentication: Optional[bool] = None,
    ase_db_username: Optional[str] = None,
    ase_db_vault: Optional[str] = None,
    ase_db_vault_username: Optional[str] = None,
    ase_enable_tls: Optional[bool] = None,
    ase_skip_server_certificate_validation: Optional[bool] = None,
    azure_vault_name: Optional[str] = None,
    azure_vault_secret_key: Optional[str] = None,
    azure_vault_username_key: Optional[str] = None,
    bits: Optional[int] = None,
    cluster_address: Optional[str] = None,
    cluster_home: Optional[str] = None,
    cluster_user: Optional[str] = None,
    connector_authentication_key: Optional[str] = None,
    connector_port: Optional[int] = None,
    cursor: Optional[str] = None,
    custom_private_key: Optional[str] = None,
    custom_public_key: Optional[str] = None,
    cyberark_vault_query_string: Optional[str] = None,
    database_name: Optional[str] = None,
    database_password: Optional[str] = None,
    database_username: Optional[str] = None,
    description: Optional[str] = None,
    dsp_keystore_alias: Optional[str] = None,
    dsp_keystore_password: Optional[str] = None,
    dsp_keystore_path: Optional[str] = None,
    dsp_truststore_password: Optional[str] = None,
    dsp_truststore_path: Optional[str] = None,
    dump_history_file: Optional[str] = None,
    encryption_enabled: Optional[bool] = None,
    engine_id: Optional[str] = None,
    environment_id: Optional[str] = None,
    environment_user: Optional[str] = None,
    filter_expression: Optional[str] = None,
    hashicorp_vault_engine: Optional[str] = None,
    hashicorp_vault_secret_key: Optional[str] = None,
    hashicorp_vault_secret_path: Optional[str] = None,
    hashicorp_vault_username_key: Optional[str] = None,
    host_id: Optional[str] = None,
    hostname: Optional[str] = None,
    installation_path: Optional[str] = None,
    instance_name: Optional[str] = None,
    instance_owner: Optional[str] = None,
    instances: Optional[list] = None,
    is_cluster: Optional[bool] = None,
    is_staging: Optional[bool] = None,
    is_target: Optional[bool] = None,
    isql_path: Optional[str] = None,
    java_home: Optional[str] = None,
    jdbc_connection_string: Optional[str] = None,
    key: Optional[str] = None,
    limit: Optional[int] = 100,
    linking_enabled: Optional[bool] = None,
    location: Optional[str] = None,
    make_current_account_owner: Optional[bool] = None,
    name: Optional[str] = None,
    nfs_addresses: Optional[list] = None,
    oracle_base: Optional[str] = None,
    oracle_cluster_node_enabled: Optional[bool] = None,
    oracle_cluster_node_name: Optional[str] = None,
    oracle_cluster_node_virtual_ips: Optional[list] = None,
    oracle_config_type: Optional[str] = None,
    oracle_jdbc_keystore_password: Optional[str] = None,
    oracle_services: Optional[list] = None,
    oracle_tde_external_key_manager_credential: Optional[str] = None,
    oracle_tde_keystores_root_path: Optional[str] = None,
    oracle_tde_okv_home_path: Optional[str] = None,
    os_name: Optional[str] = None,
    parameters: Optional[dict] = None,
    password: Optional[str] = None,
    path: Optional[str] = None,
    port: Optional[int] = None,
    privilege_elevation_profile_reference: Optional[str] = None,
    protocol_addresses: Optional[list] = None,
    remote_listener: Optional[str] = None,
    repository_id: Optional[str] = None,
    scan: Optional[str] = None,
    service_principal_name: Optional[str] = None,
    snapshot_id: Optional[str] = None,
    sort: Optional[str] = None,
    source_data_id: Optional[str] = None,
    source_id: Optional[str] = None,
    ssh_port: Optional[int] = None,
    ssh_verification_strategy: Optional[str] = None,
    staging_environment: Optional[str] = None,
    tags: Optional[list] = None,
    timeflow_id: Optional[str] = None,
    timestamp: Optional[str] = None,
    toolkit_path: Optional[str] = None,
    type: Optional[str] = None,
    unique_name: Optional[str] = None,
    use_custom_key_pair: Optional[bool] = None,
    use_engine_public_key: Optional[bool] = None,
    use_kerberos_authentication: Optional[bool] = None,
    user: Optional[str] = None,
    user_ref: Optional[str] = None,
    username: Optional[str] = None,
    value: Optional[str] = None,
    vault: Optional[str] = None,
    vault_username: Optional[str] = None,
    version: Optional[str] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for ENVIRONMENT SOURCE operations.
    
    This tool supports 41 actions: search_environments, get_environment, create_environment, add_environment_users, set_environment_primary_user, update_environment_users, delete_environment_users, update_environment, delete_environment, enable_environment, disable_environment, refresh_environment, list_environment_hosts, update_environment_host, delete_environment_host, list_environment_listeners, get_environment_tags, add_environment_tags, delete_environment_tags, get_environment_compatible_repositories_by_snapshot, get_environment_compatible_repositories_by_timestamp, get_environment_compatible_repositories_by_location, update_environment_repository, delete_environment_repository, search_sources, list_sources, get_source, delete_source, verify_source_jdbc_connection, get_source_compatible_repositories, get_source_tags, add_source_tags, delete_source_tags, create_oracle_source, update_oracle_source, create_postgres_source, update_postgres_source, create_ase_source, update_ase_source, create_appdata_source, update_appdata_source
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search_environments
    ----------------------------------------
    Summary: Search for environments.
    Method: POST
    Endpoint: /environments/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - id: The Environment object entity ID.
        - name: The name of this environment.
        - namespace_id: The namespace id of this environment.
        - namespace_name: The namespace name of this environment.
        - is_replica: Is this a replicated object.
        - namespace: The namespace of this environment for replicated and rest...
        - engine_id: A reference to the Engine that this Environment connectio...
        - engine_name: A reference to the Engine that this Environment connectio...
        - address: The address of this environment. For a standalone environ...
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
        >>> environment_source_tool(action='search_environments', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get_environment
    ----------------------------------------
    Summary: Returns an environment by ID.
    Method: GET
    Endpoint: /environments/{environmentId}
    Required Parameters: environment_id
    
    Example:
        >>> environment_source_tool(action='get_environment', environment_id='example-environment-123')
    
    ACTION: create_environment
    ----------------------------------------
    Summary: Create an environment.
    Method: POST
    Endpoint: /environments
    Required Parameters: engine_id, os_name, hostname
    Key Parameters (provide as applicable): name, is_cluster, cluster_home, staging_environment, connector_port, connector_authentication_key, is_target, ssh_port, toolkit_path, username, password, vault, vault_username, hashicorp_vault_engine, hashicorp_vault_secret_path, hashicorp_vault_username_key, hashicorp_vault_secret_key, cyberark_vault_query_string, azure_vault_name, azure_vault_username_key, azure_vault_secret_key, use_kerberos_authentication, use_engine_public_key, use_custom_key_pair, custom_private_key, custom_public_key, nfs_addresses, ase_db_vault_username, ase_db_username, ase_db_password, ase_enable_tls, ase_skip_server_certificate_validation, ase_db_vault, ase_db_hashicorp_vault_engine, ase_db_hashicorp_vault_secret_path, ase_db_hashicorp_vault_username_key, ase_db_hashicorp_vault_secret_key, ase_db_cyberark_vault_query_string, ase_db_use_kerberos_authentication, ase_db_azure_vault_name, ase_db_azure_vault_username_key, ase_db_azure_vault_secret_key, java_home, dsp_keystore_path, dsp_keystore_password, dsp_keystore_alias, dsp_truststore_path, dsp_truststore_password, description, tags, make_current_account_owner
    
    Example:
        >>> environment_source_tool(action='create_environment', name=..., engine_id='example-engine-123', os_name=..., is_cluster=..., cluster_home=..., hostname=..., staging_environment=..., connector_port=..., connector_authentication_key=..., is_target=..., ssh_port=..., toolkit_path=..., username=..., password=..., vault=..., vault_username=..., hashicorp_vault_engine=..., hashicorp_vault_secret_path=..., hashicorp_vault_username_key=..., hashicorp_vault_secret_key=..., cyberark_vault_query_string=..., azure_vault_name=..., azure_vault_username_key=..., azure_vault_secret_key=..., use_kerberos_authentication=..., use_engine_public_key=..., use_custom_key_pair=..., custom_private_key=..., custom_public_key=..., nfs_addresses=..., ase_db_vault_username=..., ase_db_username=..., ase_db_password=..., ase_enable_tls=..., ase_skip_server_certificate_validation=..., ase_db_vault=..., ase_db_hashicorp_vault_engine=..., ase_db_hashicorp_vault_secret_path=..., ase_db_hashicorp_vault_username_key=..., ase_db_hashicorp_vault_secret_key=..., ase_db_cyberark_vault_query_string=..., ase_db_use_kerberos_authentication=..., ase_db_azure_vault_name=..., ase_db_azure_vault_username_key=..., ase_db_azure_vault_secret_key=..., java_home=..., dsp_keystore_path=..., dsp_keystore_password=..., dsp_keystore_alias=..., dsp_truststore_path=..., dsp_truststore_password=..., description=..., tags=..., make_current_account_owner=...)
    
    ACTION: add_environment_users
    ----------------------------------------
    Summary: Create environment user.
    Method: POST
    Endpoint: /environments/{environmentId}/users
    Required Parameters: environment_id
    Key Parameters (provide as applicable): username, password, vault, vault_username, hashicorp_vault_engine, hashicorp_vault_secret_path, hashicorp_vault_username_key, hashicorp_vault_secret_key, cyberark_vault_query_string, azure_vault_name, azure_vault_username_key, azure_vault_secret_key, use_kerberos_authentication, use_engine_public_key, use_custom_key_pair, custom_private_key, custom_public_key
    
    Example:
        >>> environment_source_tool(action='add_environment_users', environment_id='example-environment-123', username=..., password=..., vault=..., vault_username=..., hashicorp_vault_engine=..., hashicorp_vault_secret_path=..., hashicorp_vault_username_key=..., hashicorp_vault_secret_key=..., cyberark_vault_query_string=..., azure_vault_name=..., azure_vault_username_key=..., azure_vault_secret_key=..., use_kerberos_authentication=..., use_engine_public_key=..., use_custom_key_pair=..., custom_private_key=..., custom_public_key=...)
    
    ACTION: set_environment_primary_user
    ----------------------------------------
    Summary: Set primary environment user.
    Method: POST
    Endpoint: /environments/{environmentId}/users/{userRef}/primary
    Required Parameters: environment_id, user_ref
    
    Example:
        >>> environment_source_tool(action='set_environment_primary_user', environment_id='example-environment-123', user_ref=...)
    
    ACTION: update_environment_users
    ----------------------------------------
    Summary: Update environment user.
    Method: PUT
    Endpoint: /environments/{environmentId}/users/{userRef}
    Required Parameters: environment_id, user_ref
    Key Parameters (provide as applicable): username, password, vault, vault_username, hashicorp_vault_engine, hashicorp_vault_secret_path, hashicorp_vault_username_key, hashicorp_vault_secret_key, cyberark_vault_query_string, azure_vault_name, azure_vault_username_key, azure_vault_secret_key, use_kerberos_authentication, use_engine_public_key, use_custom_key_pair, custom_private_key, custom_public_key
    
    Example:
        >>> environment_source_tool(action='update_environment_users', environment_id='example-environment-123', username=..., password=..., vault=..., vault_username=..., hashicorp_vault_engine=..., hashicorp_vault_secret_path=..., hashicorp_vault_username_key=..., hashicorp_vault_secret_key=..., cyberark_vault_query_string=..., azure_vault_name=..., azure_vault_username_key=..., azure_vault_secret_key=..., use_kerberos_authentication=..., use_engine_public_key=..., use_custom_key_pair=..., custom_private_key=..., custom_public_key=..., user_ref=...)
    
    ACTION: delete_environment_users
    ----------------------------------------
    Summary: Delete environment user.
    Method: DELETE
    Endpoint: /environments/{environmentId}/users/{userRef}
    Required Parameters: environment_id, user_ref
    
    Example:
        >>> environment_source_tool(action='delete_environment_users', environment_id='example-environment-123', user_ref=...)
    
    ACTION: update_environment
    ----------------------------------------
    Summary: Update an environment by ID.
    Method: PATCH
    Endpoint: /environments/{environmentId}
    Required Parameters: environment_id
    Key Parameters (provide as applicable): name, cluster_home, staging_environment, ase_db_vault_username, ase_db_username, ase_db_password, ase_enable_tls, ase_skip_server_certificate_validation, ase_db_vault, ase_db_hashicorp_vault_engine, ase_db_hashicorp_vault_secret_path, ase_db_hashicorp_vault_username_key, ase_db_hashicorp_vault_secret_key, ase_db_cyberark_vault_query_string, ase_db_use_kerberos_authentication, ase_db_azure_vault_name, ase_db_azure_vault_username_key, ase_db_azure_vault_secret_key, description, cluster_address, cluster_user, scan, remote_listener, encryption_enabled
    
    Example:
        >>> environment_source_tool(action='update_environment', environment_id='example-environment-123', name=..., cluster_home=..., staging_environment=..., ase_db_vault_username=..., ase_db_username=..., ase_db_password=..., ase_enable_tls=..., ase_skip_server_certificate_validation=..., ase_db_vault=..., ase_db_hashicorp_vault_engine=..., ase_db_hashicorp_vault_secret_path=..., ase_db_hashicorp_vault_username_key=..., ase_db_hashicorp_vault_secret_key=..., ase_db_cyberark_vault_query_string=..., ase_db_use_kerberos_authentication=..., ase_db_azure_vault_name=..., ase_db_azure_vault_username_key=..., ase_db_azure_vault_secret_key=..., description=..., cluster_address=..., cluster_user=..., scan=..., remote_listener=..., encryption_enabled=...)
    
    ACTION: delete_environment
    ----------------------------------------
    Summary: Delete an environment by ID.
    Method: DELETE
    Endpoint: /environments/{environmentId}
    Required Parameters: environment_id
    
    Example:
        >>> environment_source_tool(action='delete_environment', environment_id='example-environment-123')
    
    ACTION: enable_environment
    ----------------------------------------
    Summary: Enable a disabled environment.
    Method: POST
    Endpoint: /environments/{environmentId}/enable
    Required Parameters: environment_id
    
    Example:
        >>> environment_source_tool(action='enable_environment', environment_id='example-environment-123')
    
    ACTION: disable_environment
    ----------------------------------------
    Summary: Disable environment.
    Method: POST
    Endpoint: /environments/{environmentId}/disable
    Required Parameters: environment_id
    
    Example:
        >>> environment_source_tool(action='disable_environment', environment_id='example-environment-123')
    
    ACTION: refresh_environment
    ----------------------------------------
    Summary: Refresh environment.
    Method: POST
    Endpoint: /environments/{environmentId}/refresh
    Required Parameters: environment_id
    
    Example:
        >>> environment_source_tool(action='refresh_environment', environment_id='example-environment-123')
    
    ACTION: list_environment_hosts
    ----------------------------------------
    Summary: Create a new Host.
    Method: POST
    Endpoint: /environments/{environmentId}/hosts
    Required Parameters: environment_id
    Key Parameters (provide as applicable): name, hostname, ssh_port, toolkit_path, nfs_addresses, java_home, dsp_keystore_path, dsp_keystore_password, dsp_keystore_alias, dsp_truststore_path, dsp_truststore_password, privilege_elevation_profile_reference, oracle_jdbc_keystore_password, oracle_tde_keystores_root_path, ssh_verification_strategy, oracle_cluster_node_virtual_ips
    
    Example:
        >>> environment_source_tool(action='list_environment_hosts', environment_id='example-environment-123', name=..., hostname=..., ssh_port=..., toolkit_path=..., nfs_addresses=..., java_home=..., dsp_keystore_path=..., dsp_keystore_password=..., dsp_keystore_alias=..., dsp_truststore_path=..., dsp_truststore_password=..., privilege_elevation_profile_reference=..., oracle_jdbc_keystore_password=..., oracle_tde_keystores_root_path=..., ssh_verification_strategy=..., oracle_cluster_node_virtual_ips=...)
    
    ACTION: update_environment_host
    ----------------------------------------
    Summary: Update a Host.
    Method: PATCH
    Endpoint: /environments/{environmentId}/hosts/{hostId}
    Required Parameters: environment_id, host_id
    Key Parameters (provide as applicable): hostname, connector_port, connector_authentication_key, ssh_port, toolkit_path, nfs_addresses, java_home, dsp_keystore_path, dsp_keystore_password, dsp_keystore_alias, dsp_truststore_path, dsp_truststore_password, oracle_jdbc_keystore_password, oracle_tde_keystores_root_path, ssh_verification_strategy, oracle_cluster_node_virtual_ips, oracle_cluster_node_name, oracle_cluster_node_enabled, oracle_tde_okv_home_path, oracle_tde_external_key_manager_credential
    
    Example:
        >>> environment_source_tool(action='update_environment_host', environment_id='example-environment-123', hostname=..., connector_port=..., connector_authentication_key=..., ssh_port=..., toolkit_path=..., nfs_addresses=..., java_home=..., dsp_keystore_path=..., dsp_keystore_password=..., dsp_keystore_alias=..., dsp_truststore_path=..., dsp_truststore_password=..., oracle_jdbc_keystore_password=..., oracle_tde_keystores_root_path=..., ssh_verification_strategy=..., oracle_cluster_node_virtual_ips=..., host_id='example-host-123', oracle_cluster_node_name=..., oracle_cluster_node_enabled=..., oracle_tde_okv_home_path=..., oracle_tde_external_key_manager_credential=...)
    
    ACTION: delete_environment_host
    ----------------------------------------
    Summary: Delete a Host.
    Method: DELETE
    Endpoint: /environments/{environmentId}/hosts/{hostId}
    Required Parameters: environment_id, host_id
    
    Example:
        >>> environment_source_tool(action='delete_environment_host', environment_id='example-environment-123', host_id='example-host-123')
    
    ACTION: list_environment_listeners
    ----------------------------------------
    Summary: Create Oracle listener.
    Method: POST
    Endpoint: /environments/{environmentId}/listeners
    Required Parameters: environment_id, type
    Key Parameters (provide as applicable): name, host_id, protocol_addresses
    
    Example:
        >>> environment_source_tool(action='list_environment_listeners', environment_id='example-environment-123', name=..., host_id='example-host-123', type=..., protocol_addresses=...)
    
    ACTION: get_environment_tags
    ----------------------------------------
    Summary: Get tags for an Environment.
    Method: GET
    Endpoint: /environments/{environmentId}/tags
    Required Parameters: environment_id
    
    Example:
        >>> environment_source_tool(action='get_environment_tags', environment_id='example-environment-123')
    
    ACTION: add_environment_tags
    ----------------------------------------
    Summary: Create tags for an Environment.
    Method: POST
    Endpoint: /environments/{environmentId}/tags
    Required Parameters: environment_id, tags
    
    Example:
        >>> environment_source_tool(action='add_environment_tags', environment_id='example-environment-123', tags=...)
    
    ACTION: delete_environment_tags
    ----------------------------------------
    Summary: Delete tags for an Environment.
    Method: POST
    Endpoint: /environments/{environmentId}/tags/delete
    Required Parameters: environment_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> environment_source_tool(action='delete_environment_tags', environment_id='example-environment-123', tags=..., key=..., value=...)
    
    ACTION: get_environment_compatible_repositories_by_snapshot
    ----------------------------------------
    Summary: Get compatible repositories corresponding to the snapshot.
    Method: POST
    Endpoint: /environments/compatible_repositories_by_snapshot
    Key Parameters (provide as applicable): environment_id, engine_id, source_data_id, snapshot_id
    
    Example:
        >>> environment_source_tool(action='get_environment_compatible_repositories_by_snapshot', environment_id='example-environment-123', engine_id='example-engine-123', source_data_id='example-source_data-123', snapshot_id='example-snapshot-123')
    
    ACTION: get_environment_compatible_repositories_by_timestamp
    ----------------------------------------
    Summary: Get compatible repositories corresponding to the timestamp.
    Method: POST
    Endpoint: /environments/compatible_repositories_by_timestamp
    Key Parameters (provide as applicable): environment_id, engine_id, source_data_id, timestamp, timeflow_id
    
    Example:
        >>> environment_source_tool(action='get_environment_compatible_repositories_by_timestamp', environment_id='example-environment-123', engine_id='example-engine-123', source_data_id='example-source_data-123', timestamp=..., timeflow_id='example-timeflow-123')
    
    ACTION: get_environment_compatible_repositories_by_location
    ----------------------------------------
    Summary: Get compatible repositories corresponding to the location.
    Method: POST
    Endpoint: /environments/compatible_repositories_by_location
    Key Parameters (provide as applicable): environment_id, engine_id, source_data_id, timeflow_id, location
    
    Example:
        >>> environment_source_tool(action='get_environment_compatible_repositories_by_location', environment_id='example-environment-123', engine_id='example-engine-123', source_data_id='example-source_data-123', timeflow_id='example-timeflow-123', location=...)
    
    ACTION: update_environment_repository
    ----------------------------------------
    Summary: Update a Repository.
    Method: PATCH
    Endpoint: /environments/{environmentId}/repository/{repositoryId}
    Required Parameters: environment_id, repository_id
    Key Parameters (provide as applicable): allow_provisioning, is_staging, version, oracle_base, bits, port, instance_owner, installation_path, dump_history_file, database_username, database_password, service_principal_name, isql_path
    
    Example:
        >>> environment_source_tool(action='update_environment_repository', environment_id='example-environment-123', repository_id='example-repository-123', allow_provisioning=..., is_staging=..., version=..., oracle_base=..., bits=..., port=..., instance_owner=..., installation_path=..., dump_history_file=..., database_username=..., database_password=..., service_principal_name=..., isql_path=...)
    
    ACTION: delete_environment_repository
    ----------------------------------------
    Summary: Delete a repository.
    Method: DELETE
    Endpoint: /environments/{environmentId}/repository/{repositoryId}
    Required Parameters: environment_id, repository_id
    
    Example:
        >>> environment_source_tool(action='delete_environment_repository', environment_id='example-environment-123', repository_id='example-repository-123')
    
    ACTION: search_sources
    ----------------------------------------
    Summary: Search for Sources.
    Method: POST
    Endpoint: /sources/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
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
        - mount_base: The base mount point for the NFS or iSCSI LUN mounts.
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
        >>> environment_source_tool(action='search_sources', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: list_sources
    ----------------------------------------
    Summary: List all sources.
    Method: GET
    Endpoint: /sources
    Required Parameters: limit, cursor, sort
    
    Example:
        >>> environment_source_tool(action='list_sources', limit=..., cursor=..., sort=...)
    
    ACTION: get_source
    ----------------------------------------
    Summary: Get a source by ID.
    Method: GET
    Endpoint: /sources/{sourceId}
    Required Parameters: source_id
    
    Example:
        >>> environment_source_tool(action='get_source', source_id='example-source-123')
    
    ACTION: delete_source
    ----------------------------------------
    Summary: Delete a source by ID.
    Method: DELETE
    Endpoint: /sources/{sourceId}
    Required Parameters: source_id
    
    Example:
        >>> environment_source_tool(action='delete_source', source_id='example-source-123')
    
    ACTION: verify_source_jdbc_connection
    ----------------------------------------
    Summary: Verify JDBC connection string for a source.
    Method: POST
    Endpoint: /sources/{sourceId}/jdbc-check
    Required Parameters: database_username, database_password, source_id, jdbc_connection_string
    
    Example:
        >>> environment_source_tool(action='verify_source_jdbc_connection', database_username=..., database_password=..., source_id='example-source-123', jdbc_connection_string=...)
    
    ACTION: get_source_compatible_repositories
    ----------------------------------------
    Summary: Returns a list of repositories that match the specified source.
    Method: GET
    Endpoint: /sources/{sourceId}/staging_compatible_repositories
    Required Parameters: source_id
    
    Example:
        >>> environment_source_tool(action='get_source_compatible_repositories', source_id='example-source-123')
    
    ACTION: get_source_tags
    ----------------------------------------
    Summary: Get tags for a Source.
    Method: GET
    Endpoint: /sources/{sourceId}/tags
    Required Parameters: source_id
    
    Example:
        >>> environment_source_tool(action='get_source_tags', source_id='example-source-123')
    
    ACTION: add_source_tags
    ----------------------------------------
    Summary: Create tags for a Source.
    Method: POST
    Endpoint: /sources/{sourceId}/tags
    Required Parameters: tags, source_id
    
    Example:
        >>> environment_source_tool(action='add_source_tags', tags=..., source_id='example-source-123')
    
    ACTION: delete_source_tags
    ----------------------------------------
    Summary: Delete tags for a Source.
    Method: POST
    Endpoint: /sources/{sourceId}/tags/delete
    Required Parameters: source_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> environment_source_tool(action='delete_source_tags', tags=..., key=..., value=..., source_id='example-source-123')
    
    ACTION: create_oracle_source
    ----------------------------------------
    Summary: Create an Oracle Source.
    Method: POST
    Endpoint: /sources/oracle
    Required Parameters: repository_id, oracle_config_type
    Key Parameters (provide as applicable): environment_id, engine_id, database_name, instances, unique_name, instance_name, oracle_services
    
    Example:
        >>> environment_source_tool(action='create_oracle_source', environment_id='example-environment-123', engine_id='example-engine-123', repository_id='example-repository-123', oracle_config_type=..., database_name=..., instances=..., unique_name=..., instance_name=..., oracle_services=...)
    
    ACTION: update_oracle_source
    ----------------------------------------
    Summary: Update an Oracle source by ID.
    Method: PATCH
    Endpoint: /sources/oracle/{sourceId}
    Required Parameters: source_id
    Key Parameters (provide as applicable): password, oracle_services, user, linking_enabled
    
    Example:
        >>> environment_source_tool(action='update_oracle_source', password=..., source_id='example-source-123', oracle_services=..., user=..., linking_enabled=...)
    
    ACTION: create_postgres_source
    ----------------------------------------
    Summary: Create a PostgreSQL source.
    Method: POST
    Endpoint: /sources/postgres
    Required Parameters: name
    Key Parameters (provide as applicable): environment_id, engine_id, repository_id
    
    Example:
        >>> environment_source_tool(action='create_postgres_source', environment_id='example-environment-123', name=..., engine_id='example-engine-123', repository_id='example-repository-123')
    
    ACTION: update_postgres_source
    ----------------------------------------
    Summary: Update a PostgreSQL source by ID.
    Method: PATCH
    Endpoint: /sources/postgres/{sourceId}
    Required Parameters: source_id
    Key Parameters (provide as applicable): name
    
    Example:
        >>> environment_source_tool(action='update_postgres_source', name=..., source_id='example-source-123')
    
    ACTION: create_ase_source
    ----------------------------------------
    Summary: Create an ASE source.
    Method: POST
    Endpoint: /sources/ase
    Required Parameters: repository_id, database_name
    Key Parameters (provide as applicable): environment_id, engine_id, linking_enabled, environment_user
    
    Example:
        >>> environment_source_tool(action='create_ase_source', environment_id='example-environment-123', engine_id='example-engine-123', repository_id='example-repository-123', database_name=..., linking_enabled=..., environment_user=...)
    
    ACTION: update_ase_source
    ----------------------------------------
    Summary: Update an ASE source by ID.
    Method: PATCH
    Endpoint: /sources/ase/{sourceId}
    Required Parameters: source_id
    Key Parameters (provide as applicable): environment_id, repository_id, database_username, database_password, database_name, linking_enabled, environment_user
    
    Example:
        >>> environment_source_tool(action='update_ase_source', environment_id='example-environment-123', repository_id='example-repository-123', database_username=..., database_password=..., source_id='example-source-123', database_name=..., linking_enabled=..., environment_user=...)
    
    ACTION: create_appdata_source
    ----------------------------------------
    Summary: Create an AppData source.
    Method: POST
    Endpoint: /sources/appdata
    Required Parameters: name, type, repository_id
    Key Parameters (provide as applicable): environment_id, engine_id, linking_enabled, environment_user, parameters, path
    
    Example:
        >>> environment_source_tool(action='create_appdata_source', environment_id='example-environment-123', name=..., engine_id='example-engine-123', type=..., repository_id='example-repository-123', linking_enabled=..., environment_user=..., parameters=..., path=...)
    
    ACTION: update_appdata_source
    ----------------------------------------
    Summary: Update a AppData source by ID.
    Method: PATCH
    Endpoint: /sources/appdata/{sourceId}
    Required Parameters: source_id
    Key Parameters (provide as applicable): environment_id, name, repository_id, linking_enabled, environment_user, parameters, path
    
    Example:
        >>> environment_source_tool(action='update_appdata_source', environment_id='example-environment-123', name=..., repository_id='example-repository-123', source_id='example-source-123', linking_enabled=..., environment_user=..., parameters=..., path=...)
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search_environments, get_environment, create_environment, add_environment_users, set_environment_primary_user, update_environment_users, delete_environment_users, update_environment, delete_environment, enable_environment, disable_environment, refresh_environment, list_environment_hosts, update_environment_host, delete_environment_host, list_environment_listeners, get_environment_tags, add_environment_tags, delete_environment_tags, get_environment_compatible_repositories_by_snapshot, get_environment_compatible_repositories_by_timestamp, get_environment_compatible_repositories_by_location, update_environment_repository, delete_environment_repository, search_sources, list_sources, get_source, delete_source, verify_source_jdbc_connection, get_source_compatible_repositories, get_source_tags, add_source_tags, delete_source_tags, create_oracle_source, update_oracle_source, create_postgres_source, update_postgres_source, create_ase_source, update_ase_source, create_appdata_source, update_appdata_source
    
      -- General parameters (all database types) --
        allow_provisioning (bool): Flag indicating whether the repository should be used for provisioning.
            [Optional for all actions]
        ase_db_azure_vault_name (str): Azure key vault name.
            [Optional for all actions]
        ase_db_azure_vault_secret_key (str): Azure vault key for the password in the key-value store.
            [Optional for all actions]
        ase_db_azure_vault_username_key (str): Azure vault key for the username in the key-value store.
            [Optional for all actions]
        ase_db_cyberark_vault_query_string (str): Query to find a credential in the CyberArk vault.
            [Optional for all actions]
        ase_db_hashicorp_vault_engine (str): Vault engine name where the credential is stored.
            [Optional for all actions]
        ase_db_hashicorp_vault_secret_key (str): Key for the password in the key-value store.
            [Optional for all actions]
        ase_db_hashicorp_vault_secret_path (str): Path in the vault engine where the credential is stored.
            [Optional for all actions]
        ase_db_hashicorp_vault_username_key (str): Key for the username in the key-value store.
            [Optional for all actions]
        ase_db_password (str): password of the SAP ASE database.
            [Optional for all actions]
        ase_db_use_kerberos_authentication (bool): Whether to use kerberos authentication for ASE DB discovery.
            [Optional for all actions]
        ase_db_username (str): username of the SAP ASE database.
            [Optional for all actions]
        ase_db_vault (str): The name or reference of the vault from which to read the ASE database creden...
            [Optional for all actions]
        ase_db_vault_username (str): Delphix display name for the vault user
            [Optional for all actions]
        ase_enable_tls (bool): True if you want to discover the SAP ASE instances configured with TLS/SSL.
            [Optional for all actions]
        ase_skip_server_certificate_validation (bool): Only valid for SAP ASE. Setting it to true will skip the server certificate v...
            [Optional for all actions]
        azure_vault_name (str): Azure key vault name.
            [Optional for all actions]
        azure_vault_secret_key (str): Azure vault key for the password in the key-value store.
            [Optional for all actions]
        azure_vault_username_key (str): Azure vault key for the username in the key-value store.
            [Optional for all actions]
        bits (int): 32 or 64 bits.
            [Optional for all actions]
        cluster_address (str): Address of the cluster. This property can be modified for Windows cluster only.
            [Optional for all actions]
        cluster_home (str): Absolute path to cluster home drectory. This parameter is mandatory for UNIX ...
            [Optional for all actions]
        cluster_user (str): A reference of the cluster user.
            [Optional for all actions]
        connector_authentication_key (str): Unique per Delphix key used to authenticate with the remote Delphix Connector.
            [Optional for all actions]
        connector_port (int): Specify port on which Delphix connector will run. This is mandatory parameter...
            [Optional for all actions]
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search_environments, search_sources, list_sources]
        custom_private_key (str): Private key to be used for authentication
            [Optional for all actions]
        custom_public_key (str): Public key to be used for authentication
            [Optional for all actions]
        cyberark_vault_query_string (str): Query to find a credential in the CyberArk vault.
            [Optional for all actions]
        database_name (str): The name of the database.
            [Required for: create_ase_source]
        database_password (str): The credentials of the ASE instance database user.
            [Required for: verify_source_jdbc_connection]
        database_username (str): The username of the ASE instance database.
            [Required for: verify_source_jdbc_connection]
        description (str): The environment description.
            [Optional for all actions]
        dsp_keystore_alias (str): DSP keystore alias.
            [Optional for all actions]
        dsp_keystore_password (str): DSP keystore password.
            [Optional for all actions]
        dsp_keystore_path (str): DSP keystore path.
            [Optional for all actions]
        dsp_truststore_password (str): DSP truststore password.
            [Optional for all actions]
        dsp_truststore_path (str): DSP truststore path.
            [Optional for all actions]
        dump_history_file (str): Fully qualified name of the dump history file.
            [Optional for all actions]
        encryption_enabled (bool): Flag indicating whether the data transfer is encrypted or not.
            [Optional for all actions]
        engine_id (str): The ID of the Engine onto which to create the environment.
            [Required for: create_environment]
        environment_id (str): The unique identifier for the environment.
            [Required for: get_environment, add_environment_users, set_environment_primary_user, update_environment_users, delete_environment_users, update_environment, delete_environment, enable_environment, disable_environment, refresh_environment, list_environment_hosts, update_environment_host, delete_environment_host, list_environment_listeners, get_environment_tags, add_environment_tags, delete_environment_tags, update_environment_repository, delete_environment_repository]
        environment_user (str): The environment user reference.
            [Optional for all actions]
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
        host_id (str): The unique identifier for the host.
            [Required for: update_environment_host, delete_environment_host]
        hostname (str): host address of the machine.
            [Required for: create_environment]
        installation_path (str): The SAP ASE instance home.
            [Optional for all actions]
        instance_name (str): The instance name of this single instance database.
            [Optional for all actions]
        instance_owner (str): The username of the account the SAP ASE or SQL Server instance is running as.
            [Optional for all actions]
        instances (list): The instances of this RAC database. (Pass as JSON array)
            [Optional for all actions]
        is_cluster (bool): Whether the environment to be created is a cluster. (Default: False)
            [Optional for all actions]
        is_staging (bool): Flag indicating whether this repository can be used by the Delphix Engine for...
            [Optional for all actions]
        is_target (bool): Whether the environment to be created is a target cluster environment. This p...
            [Optional for all actions]
        isql_path (str): The path to the isql binary to use for this SAP ASE instance.
            [Optional for all actions]
        java_home (str): The path to the user managed Java Development Kit (JDK). If not specified, th...
            [Optional for all actions]
        jdbc_connection_string (str): Oracle jdbc connection string to validate.
            [Required for: verify_source_jdbc_connection]
        key (str): Key of the tag
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search_environments, search_sources, list_sources]
        linking_enabled (bool): Whether this source should be used for linking. (Default: True)
            [Optional for all actions]
        location (str): location from where compatible repo to be fetched.
            [Optional for all actions]
        make_current_account_owner (bool): Whether the account creating this environment must be configured as owner of ...
            [Optional for all actions]
        name (str): The name of the environment.
            [Required for: create_postgres_source, create_appdata_source]
        nfs_addresses (list): array of ip address or hostnames (Pass as JSON array)
            [Optional for all actions]
        oracle_base (str): The Oracle base where database binaries are located.
            [Optional for all actions]
        oracle_cluster_node_enabled (bool): Whether the associated OracleClusterNode is enabled.
            [Optional for all actions]
        oracle_cluster_node_name (str): The name of the associated OracleClusterNode.
            [Optional for all actions]
        oracle_cluster_node_virtual_ips (list): The Virtual IP addresses associated with the OracleClusterNode. (Pass as JSON...
            [Optional for all actions]
        oracle_config_type (str): Request body parameter Valid values: OracleRACConfig, OracleSIConfig, OracleP...
            [Required for: create_oracle_source]
        oracle_jdbc_keystore_password (str): The password for the user managed Oracle JDBC keystore.
            [Optional for all actions]
        oracle_services (list): List of jdbc connection strings which are used to connect with the database. ...
            [Optional for all actions]
        oracle_tde_external_key_manager_credential (str): The credential of the tde keystore external keys management system like Oracl...
            [Optional for all actions]
        oracle_tde_keystores_root_path (str): The path to the root of the Oracle TDE keystores artifact directories.
            [Optional for all actions]
        oracle_tde_okv_home_path (str): The path to the Oracle Key Vault library installation on the database node.
            [Optional for all actions]
        os_name (str): Operating system type of the environment. Valid values: UNIX, WINDOWS.
            [Required for: create_environment]
        parameters (dict): The JSON payload conforming to the DraftV4 schema based on the type of applic...
            [Optional for all actions]
        password (str): Password of the OS.
            [Optional for all actions]
        path (str): The path to the data to be synced. This should only be passed for type=DIRECT.
            [Optional for all actions]
        port (int): The network port for connecting to the SAP ASE or SQL Server instance.
            [Optional for all actions]
        privilege_elevation_profile_reference (str): Reference to a profile for escalating user privileges.
            [Optional for all actions]
        protocol_addresses (list): The protocol addresses of the Oracle listener. (Pass as JSON array)
            [Optional for all actions]
        remote_listener (str): Request body parameter
            [Optional for all actions]
        repository_id (str): The unique identifier for the repository.
            [Required for: update_environment_repository, delete_environment_repository, create_oracle_source, create_ase_source, create_appdata_source]
        scan (str): Request body parameter
            [Optional for all actions]
        service_principal_name (str): The Kerberos Service Principal Name (SPN) of the database.
            [Optional for all actions]
        snapshot_id (str): The ID of the snapshot from which to execute the operation.
            [Optional for all actions]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search_environments, search_sources, list_sources]
        source_data_id (str): The ID of the source object (dSource or VDB) to get the compatible repos. All...
            [Optional for all actions]
        source_id (str): The unique identifier for the source.
            [Required for: get_source, delete_source, verify_source_jdbc_connection, get_source_compatible_repositories, get_source_tags, add_source_tags, delete_source_tags, update_oracle_source, update_postgres_source, update_ase_source, update_appdata_source]
        ssh_port (int): ssh port of the host. (Default: 22)
            [Optional for all actions]
        ssh_verification_strategy (str): Mechanism to use for ssh host verification.
            [Optional for all actions]
        staging_environment (str): Id of the connector environment which is used to connect to this source envir...
            [Optional for all actions]
        tags (list): The tags to be created for this environment. (Pass as JSON array)
            [Required for: add_environment_tags, add_source_tags]
        timeflow_id (str): ID of the timeflow from which compatible repos need to be fetched, mutually e...
            [Optional for all actions]
        timestamp (str): The point in time from which to execute the operation. If the timestamp is no...
            [Optional for all actions]
        toolkit_path (str): The path for the toolkit that resides on the host.
            [Optional for all actions]
        type (str): The type of source to create. Default is DIRECT. Valid values: DIRECT, STAGED...
            [Required for: list_environment_listeners, create_appdata_source]
        unique_name (str): The unique name of this database.
            [Optional for all actions]
        use_custom_key_pair (bool): Whether to use custom private and public key pair for authentication.
            [Optional for all actions]
        use_engine_public_key (bool): Whether to use public key authentication.
            [Optional for all actions]
        use_kerberos_authentication (bool): Whether to use kerberos authentication.
            [Optional for all actions]
        user (str): Database user for accessing this source.
            [Optional for all actions]
        user_ref (str): The unique identifier for the userRef.
            [Required for: set_environment_primary_user, update_environment_users, delete_environment_users]
        username (str): Username of the OS.
            [Optional for all actions]
        value (str): Value of the tag
            [Optional for all actions]
        vault (str): The name or reference of the vault from which to read the host credentials.
            [Optional for all actions]
        vault_username (str): Delphix display name for the vault user
            [Optional for all actions]
        version (str): Version of the repository.
            [Optional for all actions]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'search_environments':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', '/environments/search', action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/environments/search', params=params, json_body=body)
    elif action == 'get_environment':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action get_environment'}
        endpoint = f'/environments/{environment_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'create_environment':
        params = build_params(os_name=os_name, hostname=hostname)
        body = {k: v for k, v in {'name': name, 'engine_id': engine_id, 'os_name': os_name, 'is_cluster': is_cluster, 'cluster_home': cluster_home, 'hostname': hostname, 'staging_environment': staging_environment, 'connector_port': connector_port, 'connector_authentication_key': connector_authentication_key, 'is_target': is_target, 'ssh_port': ssh_port, 'toolkit_path': toolkit_path, 'username': username, 'password': password, 'vault': vault, 'vault_username': vault_username, 'hashicorp_vault_engine': hashicorp_vault_engine, 'hashicorp_vault_secret_path': hashicorp_vault_secret_path, 'hashicorp_vault_username_key': hashicorp_vault_username_key, 'hashicorp_vault_secret_key': hashicorp_vault_secret_key, 'cyberark_vault_query_string': cyberark_vault_query_string, 'azure_vault_name': azure_vault_name, 'azure_vault_username_key': azure_vault_username_key, 'azure_vault_secret_key': azure_vault_secret_key, 'use_kerberos_authentication': use_kerberos_authentication, 'use_engine_public_key': use_engine_public_key, 'use_custom_key_pair': use_custom_key_pair, 'custom_private_key': custom_private_key, 'custom_public_key': custom_public_key, 'nfs_addresses': nfs_addresses, 'ase_db_vault_username': ase_db_vault_username, 'ase_db_username': ase_db_username, 'ase_db_password': ase_db_password, 'ase_enable_tls': ase_enable_tls, 'ase_skip_server_certificate_validation': ase_skip_server_certificate_validation, 'ase_db_vault': ase_db_vault, 'ase_db_hashicorp_vault_engine': ase_db_hashicorp_vault_engine, 'ase_db_hashicorp_vault_secret_path': ase_db_hashicorp_vault_secret_path, 'ase_db_hashicorp_vault_username_key': ase_db_hashicorp_vault_username_key, 'ase_db_hashicorp_vault_secret_key': ase_db_hashicorp_vault_secret_key, 'ase_db_cyberark_vault_query_string': ase_db_cyberark_vault_query_string, 'ase_db_use_kerberos_authentication': ase_db_use_kerberos_authentication, 'ase_db_azure_vault_name': ase_db_azure_vault_name, 'ase_db_azure_vault_username_key': ase_db_azure_vault_username_key, 'ase_db_azure_vault_secret_key': ase_db_azure_vault_secret_key, 'java_home': java_home, 'dsp_keystore_path': dsp_keystore_path, 'dsp_keystore_password': dsp_keystore_password, 'dsp_keystore_alias': dsp_keystore_alias, 'dsp_truststore_path': dsp_truststore_path, 'dsp_truststore_password': dsp_truststore_password, 'description': description, 'tags': tags, 'make_current_account_owner': make_current_account_owner}.items() if v is not None}
        conf = check_confirmation('POST', '/environments', action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/environments', params=params, json_body=body if body else None)
    elif action == 'add_environment_users':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action add_environment_users'}
        endpoint = f'/environments/{environment_id}/users'
        params = build_params()
        body = {k: v for k, v in {'username': username, 'password': password, 'vault': vault, 'vault_username': vault_username, 'hashicorp_vault_engine': hashicorp_vault_engine, 'hashicorp_vault_secret_path': hashicorp_vault_secret_path, 'hashicorp_vault_username_key': hashicorp_vault_username_key, 'hashicorp_vault_secret_key': hashicorp_vault_secret_key, 'cyberark_vault_query_string': cyberark_vault_query_string, 'azure_vault_name': azure_vault_name, 'azure_vault_username_key': azure_vault_username_key, 'azure_vault_secret_key': azure_vault_secret_key, 'use_kerberos_authentication': use_kerberos_authentication, 'use_engine_public_key': use_engine_public_key, 'use_custom_key_pair': use_custom_key_pair, 'custom_private_key': custom_private_key, 'custom_public_key': custom_public_key}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'set_environment_primary_user':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action set_environment_primary_user'}
        if user_ref is None:
            return {'error': 'Missing required parameter: user_ref for action set_environment_primary_user'}
        endpoint = f'/environments/{environment_id}/users/{user_ref}/primary'
        params = build_params(user_ref=user_ref)
        conf = check_confirmation('POST', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'update_environment_users':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action update_environment_users'}
        if user_ref is None:
            return {'error': 'Missing required parameter: user_ref for action update_environment_users'}
        endpoint = f'/environments/{environment_id}/users/{user_ref}'
        params = build_params(user_ref=user_ref)
        body = {k: v for k, v in {'username': username, 'password': password, 'vault': vault, 'vault_username': vault_username, 'hashicorp_vault_engine': hashicorp_vault_engine, 'hashicorp_vault_secret_path': hashicorp_vault_secret_path, 'hashicorp_vault_username_key': hashicorp_vault_username_key, 'hashicorp_vault_secret_key': hashicorp_vault_secret_key, 'cyberark_vault_query_string': cyberark_vault_query_string, 'azure_vault_name': azure_vault_name, 'azure_vault_username_key': azure_vault_username_key, 'azure_vault_secret_key': azure_vault_secret_key, 'use_kerberos_authentication': use_kerberos_authentication, 'use_engine_public_key': use_engine_public_key, 'use_custom_key_pair': use_custom_key_pair, 'custom_private_key': custom_private_key, 'custom_public_key': custom_public_key}.items() if v is not None}
        conf = check_confirmation('PUT', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('PUT', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_environment_users':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action delete_environment_users'}
        if user_ref is None:
            return {'error': 'Missing required parameter: user_ref for action delete_environment_users'}
        endpoint = f'/environments/{environment_id}/users/{user_ref}'
        params = build_params(user_ref=user_ref)
        conf = check_confirmation('DELETE', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'update_environment':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action update_environment'}
        endpoint = f'/environments/{environment_id}'
        params = build_params()
        body = {k: v for k, v in {'name': name, 'staging_environment': staging_environment, 'cluster_address': cluster_address, 'cluster_home': cluster_home, 'cluster_user': cluster_user, 'scan': scan, 'remote_listener': remote_listener, 'ase_db_username': ase_db_username, 'ase_db_password': ase_db_password, 'ase_enable_tls': ase_enable_tls, 'ase_skip_server_certificate_validation': ase_skip_server_certificate_validation, 'ase_db_vault': ase_db_vault, 'ase_db_vault_username': ase_db_vault_username, 'ase_db_hashicorp_vault_engine': ase_db_hashicorp_vault_engine, 'ase_db_hashicorp_vault_secret_path': ase_db_hashicorp_vault_secret_path, 'ase_db_hashicorp_vault_username_key': ase_db_hashicorp_vault_username_key, 'ase_db_hashicorp_vault_secret_key': ase_db_hashicorp_vault_secret_key, 'ase_db_cyberark_vault_query_string': ase_db_cyberark_vault_query_string, 'ase_db_azure_vault_name': ase_db_azure_vault_name, 'ase_db_azure_vault_username_key': ase_db_azure_vault_username_key, 'ase_db_azure_vault_secret_key': ase_db_azure_vault_secret_key, 'ase_db_use_kerberos_authentication': ase_db_use_kerberos_authentication, 'encryption_enabled': encryption_enabled, 'description': description}.items() if v is not None}
        conf = check_confirmation('PATCH', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_environment':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action delete_environment'}
        endpoint = f'/environments/{environment_id}'
        params = build_params()
        conf = check_confirmation('DELETE', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'enable_environment':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action enable_environment'}
        endpoint = f'/environments/{environment_id}/enable'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'disable_environment':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action disable_environment'}
        endpoint = f'/environments/{environment_id}/disable'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'refresh_environment':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action refresh_environment'}
        endpoint = f'/environments/{environment_id}/refresh'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'list_environment_hosts':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action list_environment_hosts'}
        endpoint = f'/environments/{environment_id}/hosts'
        params = build_params()
        body = {k: v for k, v in {'name': name, 'hostname': hostname, 'nfs_addresses': nfs_addresses, 'ssh_port': ssh_port, 'privilege_elevation_profile_reference': privilege_elevation_profile_reference, 'dsp_keystore_alias': dsp_keystore_alias, 'dsp_keystore_password': dsp_keystore_password, 'dsp_keystore_path': dsp_keystore_path, 'dsp_truststore_password': dsp_truststore_password, 'dsp_truststore_path': dsp_truststore_path, 'java_home': java_home, 'toolkit_path': toolkit_path, 'oracle_jdbc_keystore_password': oracle_jdbc_keystore_password, 'oracle_tde_keystores_root_path': oracle_tde_keystores_root_path, 'ssh_verification_strategy': ssh_verification_strategy, 'oracle_cluster_node_virtual_ips': oracle_cluster_node_virtual_ips}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'update_environment_host':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action update_environment_host'}
        if host_id is None:
            return {'error': 'Missing required parameter: host_id for action update_environment_host'}
        endpoint = f'/environments/{environment_id}/hosts/{host_id}'
        params = build_params()
        body = {k: v for k, v in {'hostname': hostname, 'oracle_cluster_node_name': oracle_cluster_node_name, 'oracle_cluster_node_enabled': oracle_cluster_node_enabled, 'oracle_cluster_node_virtual_ips': oracle_cluster_node_virtual_ips, 'nfs_addresses': nfs_addresses, 'ssh_port': ssh_port, 'toolkit_path': toolkit_path, 'java_home': java_home, 'dsp_keystore_path': dsp_keystore_path, 'dsp_keystore_password': dsp_keystore_password, 'dsp_keystore_alias': dsp_keystore_alias, 'dsp_truststore_path': dsp_truststore_path, 'dsp_truststore_password': dsp_truststore_password, 'connector_port': connector_port, 'oracle_jdbc_keystore_password': oracle_jdbc_keystore_password, 'oracle_tde_keystores_root_path': oracle_tde_keystores_root_path, 'ssh_verification_strategy': ssh_verification_strategy, 'connector_authentication_key': connector_authentication_key, 'oracle_tde_okv_home_path': oracle_tde_okv_home_path, 'oracle_tde_external_key_manager_credential': oracle_tde_external_key_manager_credential}.items() if v is not None}
        conf = check_confirmation('PATCH', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_environment_host':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action delete_environment_host'}
        if host_id is None:
            return {'error': 'Missing required parameter: host_id for action delete_environment_host'}
        endpoint = f'/environments/{environment_id}/hosts/{host_id}'
        params = build_params()
        conf = check_confirmation('DELETE', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'list_environment_listeners':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action list_environment_listeners'}
        endpoint = f'/environments/{environment_id}/listeners'
        params = build_params(type=type)
        body = {k: v for k, v in {'type': type, 'name': name, 'protocol_addresses': protocol_addresses, 'host_id': host_id}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'get_environment_tags':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action get_environment_tags'}
        endpoint = f'/environments/{environment_id}/tags'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_environment_tags':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action add_environment_tags'}
        endpoint = f'/environments/{environment_id}/tags'
        params = build_params(tags=tags)
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_environment_tags':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action delete_environment_tags'}
        endpoint = f'/environments/{environment_id}/tags/delete'
        params = build_params()
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'get_environment_compatible_repositories_by_snapshot':
        params = build_params()
        body = {k: v for k, v in {'source_data_id': source_data_id, 'engine_id': engine_id, 'snapshot_id': snapshot_id, 'environment_id': environment_id}.items() if v is not None}
        conf = check_confirmation('POST', '/environments/compatible_repositories_by_snapshot', action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/environments/compatible_repositories_by_snapshot', params=params, json_body=body if body else None)
    elif action == 'get_environment_compatible_repositories_by_timestamp':
        params = build_params()
        body = {k: v for k, v in {'source_data_id': source_data_id, 'engine_id': engine_id, 'timestamp': timestamp, 'timeflow_id': timeflow_id, 'environment_id': environment_id}.items() if v is not None}
        conf = check_confirmation('POST', '/environments/compatible_repositories_by_timestamp', action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/environments/compatible_repositories_by_timestamp', params=params, json_body=body if body else None)
    elif action == 'get_environment_compatible_repositories_by_location':
        params = build_params()
        body = {k: v for k, v in {'source_data_id': source_data_id, 'engine_id': engine_id, 'location': location, 'timeflow_id': timeflow_id, 'environment_id': environment_id}.items() if v is not None}
        conf = check_confirmation('POST', '/environments/compatible_repositories_by_location', action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/environments/compatible_repositories_by_location', params=params, json_body=body if body else None)
    elif action == 'update_environment_repository':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action update_environment_repository'}
        if repository_id is None:
            return {'error': 'Missing required parameter: repository_id for action update_environment_repository'}
        endpoint = f'/environments/{environment_id}/repository/{repository_id}'
        params = build_params()
        body = {k: v for k, v in {'allow_provisioning': allow_provisioning, 'is_staging': is_staging, 'version': version, 'oracle_base': oracle_base, 'bits': bits, 'port': port, 'instance_owner': instance_owner, 'installation_path': installation_path, 'dump_history_file': dump_history_file, 'database_username': database_username, 'database_password': database_password, 'service_principal_name': service_principal_name, 'isql_path': isql_path}.items() if v is not None}
        conf = check_confirmation('PATCH', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_environment_repository':
        if environment_id is None:
            return {'error': 'Missing required parameter: environment_id for action delete_environment_repository'}
        if repository_id is None:
            return {'error': 'Missing required parameter: repository_id for action delete_environment_repository'}
        endpoint = f'/environments/{environment_id}/repository/{repository_id}'
        params = build_params()
        conf = check_confirmation('DELETE', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'search_sources':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', '/sources/search', action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/sources/search', params=params, json_body=body)
    elif action == 'list_sources':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('GET', '/sources', action, 'environment_source_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', '/sources', params=params)
    elif action == 'get_source':
        if source_id is None:
            return {'error': 'Missing required parameter: source_id for action get_source'}
        endpoint = f'/sources/{source_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'delete_source':
        if source_id is None:
            return {'error': 'Missing required parameter: source_id for action delete_source'}
        endpoint = f'/sources/{source_id}'
        params = build_params()
        conf = check_confirmation('DELETE', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'verify_source_jdbc_connection':
        if source_id is None:
            return {'error': 'Missing required parameter: source_id for action verify_source_jdbc_connection'}
        endpoint = f'/sources/{source_id}/jdbc-check'
        params = build_params(database_username=database_username, database_password=database_password, jdbc_connection_string=jdbc_connection_string)
        body = {k: v for k, v in {'database_username': database_username, 'database_password': database_password, 'jdbc_connection_string': jdbc_connection_string}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'get_source_compatible_repositories':
        if source_id is None:
            return {'error': 'Missing required parameter: source_id for action get_source_compatible_repositories'}
        endpoint = f'/sources/{source_id}/staging_compatible_repositories'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'get_source_tags':
        if source_id is None:
            return {'error': 'Missing required parameter: source_id for action get_source_tags'}
        endpoint = f'/sources/{source_id}/tags'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_source_tags':
        if source_id is None:
            return {'error': 'Missing required parameter: source_id for action add_source_tags'}
        endpoint = f'/sources/{source_id}/tags'
        params = build_params(tags=tags)
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_source_tags':
        if source_id is None:
            return {'error': 'Missing required parameter: source_id for action delete_source_tags'}
        endpoint = f'/sources/{source_id}/tags/delete'
        params = build_params()
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'create_oracle_source':
        params = build_params(oracle_config_type=oracle_config_type)
        body = {k: v for k, v in {'oracle_config_type': oracle_config_type, 'engine_id': engine_id, 'environment_id': environment_id, 'database_name': database_name, 'repository_id': repository_id, 'instances': instances, 'unique_name': unique_name, 'instance_name': instance_name, 'oracle_services': oracle_services}.items() if v is not None}
        conf = check_confirmation('POST', '/sources/oracle', action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/sources/oracle', params=params, json_body=body if body else None)
    elif action == 'update_oracle_source':
        if source_id is None:
            return {'error': 'Missing required parameter: source_id for action update_oracle_source'}
        endpoint = f'/sources/oracle/{source_id}'
        params = build_params()
        body = {k: v for k, v in {'oracle_services': oracle_services, 'user': user, 'password': password, 'linking_enabled': linking_enabled}.items() if v is not None}
        conf = check_confirmation('PATCH', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'create_postgres_source':
        params = build_params(name=name)
        body = {k: v for k, v in {'name': name, 'repository_id': repository_id, 'engine_id': engine_id, 'environment_id': environment_id}.items() if v is not None}
        conf = check_confirmation('POST', '/sources/postgres', action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/sources/postgres', params=params, json_body=body if body else None)
    elif action == 'update_postgres_source':
        if source_id is None:
            return {'error': 'Missing required parameter: source_id for action update_postgres_source'}
        endpoint = f'/sources/postgres/{source_id}'
        params = build_params()
        body = {k: v for k, v in {'name': name}.items() if v is not None}
        conf = check_confirmation('PATCH', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'create_ase_source':
        params = build_params(database_name=database_name)
        body = {k: v for k, v in {'database_name': database_name, 'repository_id': repository_id, 'linking_enabled': linking_enabled, 'environment_id': environment_id, 'environment_user': environment_user, 'engine_id': engine_id}.items() if v is not None}
        conf = check_confirmation('POST', '/sources/ase', action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/sources/ase', params=params, json_body=body if body else None)
    elif action == 'update_ase_source':
        if source_id is None:
            return {'error': 'Missing required parameter: source_id for action update_ase_source'}
        endpoint = f'/sources/ase/{source_id}'
        params = build_params()
        body = {k: v for k, v in {'database_name': database_name, 'repository_id': repository_id, 'linking_enabled': linking_enabled, 'environment_id': environment_id, 'environment_user': environment_user, 'database_username': database_username, 'database_password': database_password}.items() if v is not None}
        conf = check_confirmation('PATCH', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'create_appdata_source':
        params = build_params(name=name, type=type)
        body = {k: v for k, v in {'type': type, 'name': name, 'repository_id': repository_id, 'linking_enabled': linking_enabled, 'environment_user': environment_user, 'parameters': parameters, 'path': path, 'environment_id': environment_id, 'engine_id': engine_id}.items() if v is not None}
        conf = check_confirmation('POST', '/sources/appdata', action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/sources/appdata', params=params, json_body=body if body else None)
    elif action == 'update_appdata_source':
        if source_id is None:
            return {'error': 'Missing required parameter: source_id for action update_appdata_source'}
        endpoint = f'/sources/appdata/{source_id}'
        params = build_params()
        body = {k: v for k, v in {'name': name, 'repository_id': repository_id, 'environment_id': environment_id, 'linking_enabled': linking_enabled, 'environment_user': environment_user, 'parameters': parameters, 'path': path}.items() if v is not None}
        conf = check_confirmation('PATCH', endpoint, action, 'environment_source_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search_environments, get_environment, create_environment, add_environment_users, set_environment_primary_user, update_environment_users, delete_environment_users, update_environment, delete_environment, enable_environment, disable_environment, refresh_environment, list_environment_hosts, update_environment_host, delete_environment_host, list_environment_listeners, get_environment_tags, add_environment_tags, delete_environment_tags, get_environment_compatible_repositories_by_snapshot, get_environment_compatible_repositories_by_timestamp, get_environment_compatible_repositories_by_location, update_environment_repository, delete_environment_repository, search_sources, list_sources, get_source, delete_source, verify_source_jdbc_connection, get_source_compatible_repositories, get_source_tags, add_source_tags, delete_source_tags, create_oracle_source, update_oracle_source, create_postgres_source, update_postgres_source, create_ase_source, update_ase_source, create_appdata_source, update_appdata_source'}

@log_tool_execution
def toolkit_tool(
    action: str,  # One of: search, get, upload_toolkit, delete_toolkit, get_tags, add_tags, delete_tags
    cursor: Optional[str] = None,
    filter_expression: Optional[str] = None,
    key: Optional[str] = None,
    limit: Optional[int] = 100,
    sort: Optional[str] = None,
    tags: Optional[list] = None,
    toolkit_id: Optional[str] = None,
    value: Optional[str] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for TOOLKIT operations.
    
    This tool supports 7 actions: search, get, upload_toolkit, delete_toolkit, get_tags, add_tags, delete_tags
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search for toolkits.
    Method: POST
    Endpoint: /toolkits/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - id: Id of the toolkit.
        - type: Specifies whether this object is toolkit or plugin
        - reference: The object reference.
        - engine_name: Name of the engine.
        - engine_id: Id of the engine.
        - virtual_source_definition: Definition of how to provision virtual sources of this type
        - linked_source_definition: Definition of how to link sources of this type.
        - discovery_definition: Definition of how to discover sources of this type.
        - upgrade_definition: Definition of how to upgrade sources of this type.
        - snapshot_parameters_definition: The schema that defines the structure of the fields in Ap...
        - build_api: The Delphix API version that the toolkit was built against.
        - display_name: 
        - pretty_name: 
        - version: 
        - namespace: 
        - identifier: 
        - root_squash_enabled: 
        - default_locale: 
        - status: 
        - language: 
        - extended_start_stop_hooks: 
        - entry_point: 
        - lua_name: 
        - minimum_lua_version: 
        - host_types: 
        - snapshot_schema: 
        - resources: 
        - tags: Tags associated to this toolkit.
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> toolkit_tool(action='search', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get
    ----------------------------------------
    Summary: Get Toolkit by ID.
    Method: GET
    Endpoint: /toolkits/{toolkitId}
    Required Parameters: toolkit_id
    
    Example:
        >>> toolkit_tool(action='get', toolkit_id='example-toolkit-123')
    
    ACTION: upload_toolkit
    ----------------------------------------
    Summary: Upload toolkit to engines.
    Method: POST
    Endpoint: /toolkits/upload
    
    Example:
        >>> toolkit_tool(action='upload_toolkit')
    
    ACTION: delete_toolkit
    ----------------------------------------
    Summary: Delete a Toolkit by ID.
    Method: DELETE
    Endpoint: /toolkits/{toolkitId}
    Required Parameters: toolkit_id
    
    Example:
        >>> toolkit_tool(action='delete_toolkit', toolkit_id='example-toolkit-123')
    
    ACTION: get_tags
    ----------------------------------------
    Summary: Get tags for a Toolkit.
    Method: GET
    Endpoint: /toolkits/{toolkitId}/tags
    Required Parameters: toolkit_id
    
    Example:
        >>> toolkit_tool(action='get_tags', toolkit_id='example-toolkit-123')
    
    ACTION: add_tags
    ----------------------------------------
    Summary: Create tags for a toolkit.
    Method: POST
    Endpoint: /toolkits/{toolkitId}/tags
    Required Parameters: toolkit_id, tags
    
    Example:
        >>> toolkit_tool(action='add_tags', toolkit_id='example-toolkit-123', tags=...)
    
    ACTION: delete_tags
    ----------------------------------------
    Summary: Delete tags for a Toolkit.
    Method: POST
    Endpoint: /toolkits/{toolkitId}/tags/delete
    Required Parameters: toolkit_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> toolkit_tool(action='delete_tags', toolkit_id='example-toolkit-123', tags=..., key=..., value=...)
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, upload_toolkit, delete_toolkit, get_tags, add_tags, delete_tags
    
      -- General parameters (all database types) --
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search]
        filter_expression (str): Request body parameter
            [Optional for all actions]
        key (str): Key of the tag
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search]
        tags (list): Array of tags with key value pairs (Pass as JSON array)
            [Required for: add_tags]
        toolkit_id (str): The unique identifier for the toolkit.
            [Required for: get, delete_toolkit, get_tags, add_tags, delete_tags]
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
        conf = check_confirmation('POST', '/toolkits/search', action, 'toolkit_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/toolkits/search', params=params, json_body=body)
    elif action == 'get':
        if toolkit_id is None:
            return {'error': 'Missing required parameter: toolkit_id for action get'}
        endpoint = f'/toolkits/{toolkit_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'toolkit_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'upload_toolkit':
        params = build_params()
        conf = check_confirmation('POST', '/toolkits/upload', action, 'toolkit_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('POST', '/toolkits/upload', params=params)
    elif action == 'delete_toolkit':
        if toolkit_id is None:
            return {'error': 'Missing required parameter: toolkit_id for action delete_toolkit'}
        endpoint = f'/toolkits/{toolkit_id}'
        params = build_params()
        conf = check_confirmation('DELETE', endpoint, action, 'toolkit_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'get_tags':
        if toolkit_id is None:
            return {'error': 'Missing required parameter: toolkit_id for action get_tags'}
        endpoint = f'/toolkits/{toolkit_id}/tags'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'toolkit_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_tags':
        if toolkit_id is None:
            return {'error': 'Missing required parameter: toolkit_id for action add_tags'}
        endpoint = f'/toolkits/{toolkit_id}/tags'
        params = build_params(tags=tags)
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'toolkit_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_tags':
        if toolkit_id is None:
            return {'error': 'Missing required parameter: toolkit_id for action delete_tags'}
        endpoint = f'/toolkits/{toolkit_id}/tags/delete'
        params = build_params()
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'toolkit_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, upload_toolkit, delete_toolkit, get_tags, add_tags, delete_tags'}


def register_tools(app, dct_client):
    global client
    client = dct_client
    logger.info(f'Registering tools for environment_endpoints...')
    try:
        logger.info(f'  Registering tool function: environment_source_tool')
        app.add_tool(environment_source_tool, name="environment_source_tool")
        logger.info(f'  Registering tool function: toolkit_tool')
        app.add_tool(toolkit_tool, name="toolkit_tool")
    except Exception as e:
        logger.error(f'Error registering tools for environment_endpoints: {e}')
    logger.info(f'Tools registration finished for environment_endpoints.')
