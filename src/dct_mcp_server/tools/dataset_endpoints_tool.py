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

def check_confirmation(method: str, api_path: str, action: str, tool_name: str, confirmed: bool = False) -> Optional[Dict[str, Any]]:
    """Check if operation requires confirmation. Returns confirmation response or None if confirmed/not needed."""
    confirmation = get_confirmation_for_operation(method, api_path)
    if confirmation["level"] != "none" and not confirmed:
        return {
            "status": "confirmation_required",
            "confirmation_level": confirmation["level"],
            "confirmation_message": confirmation.get("message", "Please confirm this operation."),
            "action": action,
            "tool": tool_name,
            "api_path": api_path,
            "instructions": "STOP: You MUST display the confirmation_message to the user and wait for their EXPLICIT approval before re-calling with confirmed=True. Do NOT proceed without user consent."
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
def data_tool(
    action: str,  # One of: list_vdbs, search_vdbs, get_vdb, update_vdb, provision_by_timestamp, provision_by_timestamp_defaults, provision_by_snapshot, provision_by_snapshot_defaults, provision_from_bookmark, provision_from_bookmark_defaults, provision_by_location, provision_by_location_defaults, provision_empty_vdb, delete_vdb, start_vdb, stop_vdb, enable_vdb, disable_vdb, refresh_vdb_by_timestamp, refresh_vdb_by_snapshot, refresh_vdb_from_bookmark, refresh_vdb_by_location, undo_vdb_refresh, rollback_vdb_by_timestamp, rollback_vdb_by_snapshot, rollback_vdb_from_bookmark, switch_vdb_timeflow, lock_vdb, unlock_vdb, migrate_vdb, get_migrate_compatible_repositories, upgrade_vdb, upgrade_oracle_vdb, get_upgrade_compatible_repositories, list_vdb_snapshots, snapshot_vdb, list_vdb_bookmarks, search_vdb_bookmarks, get_vdb_deletion_dependencies, verify_vdb_jdbc_connection, get_vdb_tags, add_vdb_tags, export_vdb_in_place, export_vdb_asm_in_place, export_vdb_by_snapshot, export_vdb_by_timestamp, export_vdb_by_location, export_vdb_from_bookmark, export_vdb_to_asm_by_snapshot, export_vdb_to_asm_by_timestamp, export_vdb_to_asm_by_location, export_vdb_to_asm_from_bookmark, export_cleanup, export_finalize, list_vdb_groups, search_vdb_groups, get_vdb_group, create_vdb_group, update_vdb_group, delete_vdb_group, provision_vdb_group_from_bookmark, refresh_vdb_group, refresh_vdb_group_from_bookmark, refresh_vdb_group_by_snapshot, refresh_vdb_group_by_timestamp, rollback_vdb_group, lock_vdb_group, unlock_vdb_group, start_vdb_group, stop_vdb_group, enable_vdb_group, disable_vdb_group, get_vdb_group_latest_snapshots, get_vdb_group_timestamp_summary, list_vdb_group_bookmarks, search_vdb_group_bookmarks, get_vdb_group_tags, add_vdb_group_tags, list_dsources, search_dsources, get_dsource, delete_dsource, enable_dsource, disable_dsource, list_dsource_snapshots, dsource_create_snapshot, upgrade_dsource, get_dsource_upgrade_compatible_repositories, get_dsource_deletion_dependencies, get_dsource_tags, add_dsource_tags, delete_dsource_tags, dsource_link_oracle, dsource_link_oracle_defaults, dsource_link_oracle_staging_push, dsource_link_oracle_staging_push_defaults, update_oracle_dsource, attach_oracle_dsource, detach_oracle_dsource, upgrade_oracle_dsource, dsource_link_ase, dsource_link_ase_defaults, update_ase_dsource, dsource_link_appdata, dsource_link_appdata_defaults, update_appdata_dsource, dsource_link_mssql, dsource_link_mssql_defaults, dsource_link_mssql_staging_push, dsource_link_mssql_staging_push_defaults, attach_mssql_staging_push_dsource, update_mssql_dsource, attach_mssql_dsource, detach_mssql_dsource, export_dsource_by_snapshot, export_dsource_by_timestamp, export_dsource_by_location, export_dsource_from_bookmark, export_dsource_to_asm_by_snapshot, export_dsource_to_asm_by_timestamp, export_dsource_to_asm_by_location, export_dsource_to_asm_from_bookmark
    abort: Optional[bool] = False,
    account_id: Optional[int] = None,
    additional_mount_points: Optional[list] = None,
    allow_auto_staging_restart_on_host_reboot: Optional[bool] = None,
    appdata_config_params: Optional[dict] = None,
    appdata_parameters: Optional[dict] = None,
    appdata_source_params: Optional[dict] = None,
    archive_directory: Optional[str] = None,
    archive_log: Optional[bool] = None,
    ase_backup_files: Optional[list] = None,
    attempt_cleanup: Optional[bool] = True,
    attempt_start: Optional[bool] = True,
    auto_restart: Optional[bool] = None,
    auto_select_repository: Optional[bool] = None,
    auto_staging_restart: Optional[bool] = False,
    auxiliary_template_id: Optional[str] = None,
    availability_group_backup_policy: Optional[str] = 'primary',
    backup_frequency_minutes: Optional[int] = 30,
    backup_host: Optional[str] = None,
    backup_host_user: Optional[str] = None,
    backup_level_enabled: Optional[bool] = None,
    backup_server_name: Optional[str] = None,
    bandwidth_limit: Optional[int] = 0,
    bookmark_id: Optional[str] = None,
    cache_priority: Optional[str] = None,
    cdb_id: Optional[str] = None,
    cdb_tde_keystore_password: Optional[str] = None,
    cdc_on_provision: Optional[bool] = None,
    check_logical: Optional[bool] = False,
    cleanup_target_container: Optional[bool] = False,
    cleanup_target_physical_files: Optional[bool] = False,
    cluster_node_ids: Optional[list] = None,
    cluster_node_instances: Optional[list] = None,
    compressed_linking_enabled: Optional[bool] = True,
    compression_enabled: Optional[bool] = False,
    config_params: Optional[dict] = None,
    config_settings_stg: Optional[list] = None,
    configure_clone: Optional[list] = None,
    container_mode: Optional[bool] = None,
    container_type: Optional[str] = None,
    crs_database_name: Optional[str] = None,
    cursor: Optional[str] = None,
    custom_env_files: Optional[list] = None,
    custom_env_variables_pairs: Optional[list] = None,
    custom_env_variables_paths: Optional[list] = None,
    custom_env_vars: Optional[dict] = None,
    data_directory: Optional[str] = None,
    database_name: Optional[str] = None,
    database_password: Optional[str] = None,
    database_unique_name: Optional[str] = None,
    database_username: Optional[str] = None,
    dataset_id: Optional[str] = None,
    db_azure_vault_name: Optional[str] = None,
    db_azure_vault_secret_key: Optional[str] = None,
    db_azure_vault_username_key: Optional[str] = None,
    db_cyberark_vault_query_string: Optional[str] = None,
    db_hashicorp_vault_engine: Optional[str] = None,
    db_hashicorp_vault_secret_key: Optional[str] = None,
    db_hashicorp_vault_secret_path: Optional[str] = None,
    db_hashicorp_vault_username_key: Optional[str] = None,
    db_password: Optional[str] = None,
    db_state: Optional[str] = 'RESTORING',
    db_unique_name: Optional[str] = None,
    db_user: Optional[str] = None,
    db_username: Optional[str] = None,
    db_vault: Optional[str] = None,
    db_vault_username: Optional[str] = None,
    default_data_diskgroup: Optional[str] = None,
    delete_all_dependent_vdbs: Optional[bool] = False,
    delphix_managed_backup_compression_enabled: Optional[bool] = False,
    delphix_managed_backup_policy: Optional[str] = 'primary',
    description: Optional[str] = None,
    diagnose_no_logging_faults: Optional[bool] = True,
    disable_commvault_config: Optional[bool] = None,
    disable_netbackup_config: Optional[bool] = None,
    do_not_resume: Optional[bool] = False,
    double_sync: Optional[bool] = False,
    drop_and_recreate_devices: Optional[bool] = False,
    dsource_id: Optional[str] = None,
    dump_credentials: Optional[str] = None,
    dump_history_file_enabled: Optional[bool] = False,
    enable_cdc: Optional[bool] = False,
    encrypted_linking_enabled: Optional[bool] = False,
    encryption_key: Optional[str] = None,
    engine_id: Optional[str] = None,
    environment_id: Optional[str] = None,
    environment_user: Optional[str] = None,
    environment_user_id: Optional[str] = None,
    environment_user_ref: Optional[str] = None,
    excludes: Optional[list] = None,
    external_commserve_host_name: Optional[str] = None,
    external_commvault_config_params: Optional[dict] = None,
    external_commvault_config_source_client_name: Optional[str] = None,
    external_commvault_config_staging_client_name: Optional[str] = None,
    external_commvault_config_templates: Optional[str] = None,
    external_directory: Optional[str] = None,
    external_file_path: Optional[str] = None,
    external_managed_shared_backup_locations: Optional[list] = None,
    external_managed_validate_sync_mode: Optional[str] = 'TRANSACTION_LOG',
    external_netbackup_config_master_name: Optional[str] = None,
    external_netbackup_config_params: Optional[dict] = None,
    external_netbackup_config_source_client_name: Optional[str] = None,
    external_netbackup_config_templates: Optional[str] = None,
    fallback_azure_vault_name: Optional[str] = None,
    fallback_azure_vault_secret_key: Optional[str] = None,
    fallback_azure_vault_username_key: Optional[str] = None,
    fallback_cyberark_vault_query_string: Optional[str] = None,
    fallback_hashicorp_vault_engine: Optional[str] = None,
    fallback_hashicorp_vault_secret_key: Optional[str] = None,
    fallback_hashicorp_vault_secret_path: Optional[str] = None,
    fallback_hashicorp_vault_username_key: Optional[str] = None,
    fallback_password: Optional[str] = None,
    fallback_username: Optional[str] = None,
    fallback_vault: Optional[str] = None,
    fallback_vault_username: Optional[str] = None,
    file_mapping_rules: Optional[str] = None,
    files_for_full_backup: Optional[list] = None,
    files_for_partial_full_backup: Optional[list] = None,
    files_per_set: Optional[int] = 5,
    filter_expression: Optional[str] = None,
    follow_symlinks: Optional[list] = None,
    force: Optional[bool] = False,
    force_full_backup: Optional[bool] = False,
    group_id: Optional[str] = None,
    hooks: Optional[dict] = None,
    instance_number: Optional[int] = None,
    instances: Optional[list] = None,
    invoke_datapatch: Optional[bool] = None,
    is_incremental_v2p: Optional[bool] = None,
    is_refresh_to_nearest: Optional[bool] = False,
    jdbc_connection_string: Optional[str] = None,
    key: Optional[str] = None,
    limit: Optional[int] = 100,
    link_now: Optional[bool] = False,
    link_type: Optional[str] = 'AppDataDirect',
    listener_ids: Optional[list] = None,
    load_backup_path: Optional[str] = None,
    location: Optional[str] = None,
    log_sync_enabled: Optional[bool] = False,
    log_sync_interval: Optional[int] = 5,
    log_sync_mode: Optional[str] = 'UNDEFINED',
    logsync_enabled: Optional[bool] = None,
    logsync_interval: Optional[int] = None,
    logsync_mode: Optional[str] = None,
    make_current_account_owner: Optional[bool] = True,
    masked: Optional[bool] = None,
    max_allowed_backups_pending_restore: Optional[int] = 5,
    mirroring_state: Optional[str] = 'NONE',
    mode: Optional[str] = None,
    mount_base: Optional[str] = None,
    mount_point: Optional[str] = None,
    mssql_ag_backup_based: Optional[bool] = None,
    mssql_ag_backup_location: Optional[str] = None,
    mssql_backup_uuid: Optional[str] = None,
    mssql_database_password: Optional[str] = None,
    mssql_database_username: Optional[str] = None,
    mssql_failover_drive_letter: Optional[str] = None,
    mssql_incremental_export_backup_frequency_minutes: Optional[int] = None,
    mssql_user_domain_azure_vault_name: Optional[str] = None,
    mssql_user_domain_azure_vault_secret_key: Optional[str] = None,
    mssql_user_domain_azure_vault_username_key: Optional[str] = None,
    mssql_user_domain_cyberark_vault_query_string: Optional[str] = None,
    mssql_user_domain_hashicorp_vault_engine: Optional[str] = None,
    mssql_user_domain_hashicorp_vault_secret_key: Optional[str] = None,
    mssql_user_domain_hashicorp_vault_secret_path: Optional[str] = None,
    mssql_user_domain_hashicorp_vault_username_key: Optional[str] = None,
    mssql_user_domain_password: Optional[str] = None,
    mssql_user_domain_username: Optional[str] = None,
    mssql_user_domain_vault: Optional[str] = None,
    mssql_user_domain_vault_username: Optional[str] = None,
    mssql_user_environment_reference: Optional[str] = None,
    name: Optional[str] = None,
    new_dbid: Optional[bool] = None,
    non_sys_azure_vault_name: Optional[str] = None,
    non_sys_azure_vault_secret_key: Optional[str] = None,
    non_sys_azure_vault_username_key: Optional[str] = None,
    non_sys_cyberark_vault_query_string: Optional[str] = None,
    non_sys_hashicorp_vault_engine: Optional[str] = None,
    non_sys_hashicorp_vault_secret_key: Optional[str] = None,
    non_sys_hashicorp_vault_secret_path: Optional[str] = None,
    non_sys_hashicorp_vault_username_key: Optional[str] = None,
    non_sys_password: Optional[str] = None,
    non_sys_username: Optional[str] = None,
    non_sys_vault: Optional[str] = None,
    non_sys_vault_username: Optional[str] = None,
    number_of_connections: Optional[int] = 1,
    okv_client_id: Optional[str] = None,
    online_log_groups: Optional[int] = None,
    online_log_size: Optional[int] = None,
    open_reset_logs: Optional[bool] = None,
    operations: Optional[list] = None,
    operations_post_v2_p: Optional[bool] = False,
    ops_post_sync: Optional[list] = None,
    ops_pre_log_sync: Optional[list] = None,
    ops_pre_sync: Optional[list] = None,
    oracle_fallback_credentials: Optional[str] = None,
    oracle_fallback_user: Optional[str] = None,
    oracle_instance_name: Optional[str] = None,
    oracle_password: Optional[str] = None,
    oracle_rac_custom_env_files: Optional[list] = None,
    oracle_rac_custom_env_vars: Optional[list] = None,
    oracle_services: Optional[list] = None,
    oracle_username: Optional[str] = None,
    os_password: Optional[str] = None,
    os_username: Optional[str] = None,
    ownership_spec: Optional[str] = None,
    parameters: Optional[dict] = None,
    parent_pdb_tde_keystore_password: Optional[str] = None,
    parent_pdb_tde_keystore_path: Optional[str] = None,
    parent_tde_keystore_password: Optional[str] = None,
    parent_tde_keystore_path: Optional[str] = None,
    pdb_name: Optional[str] = None,
    permission: Optional[str] = None,
    physical_standby: Optional[bool] = False,
    post_refresh: Optional[list] = None,
    post_rollback: Optional[list] = None,
    post_script: Optional[str] = None,
    post_self_refresh: Optional[list] = None,
    post_snapshot: Optional[list] = None,
    post_start: Optional[list] = None,
    post_stop: Optional[list] = None,
    post_validated_sync: Optional[list] = None,
    postgres_port: Optional[int] = None,
    ppt_host_user: Optional[str] = None,
    ppt_repository: Optional[str] = None,
    pre_provisioning_enabled: Optional[bool] = False,
    pre_refresh: Optional[list] = None,
    pre_rollback: Optional[list] = None,
    pre_script: Optional[str] = None,
    pre_self_refresh: Optional[list] = None,
    pre_snapshot: Optional[list] = None,
    pre_start: Optional[list] = None,
    pre_stop: Optional[list] = None,
    pre_validated_sync: Optional[list] = None,
    privileged_os_user: Optional[str] = None,
    provision_parameters: Optional[dict] = None,
    rac_max_instance_lag: Optional[int] = None,
    recover_database: Optional[bool] = True,
    recovery_model: Optional[str] = None,
    redo_diskgroup: Optional[str] = None,
    refresh_immediately: Optional[bool] = False,
    repository: Optional[str] = None,
    repository_id: Optional[str] = None,
    retention_policy_id: Optional[str] = None,
    rman_channels: Optional[int] = 8,
    rman_channels_for_incremental_backup: Optional[int] = 8,
    rman_file_section_size_in_gb: Optional[int] = 0,
    rman_file_section_size_in_gb_for_incremental_backup: Optional[int] = 0,
    rman_files_per_set_for_incremental_backup: Optional[int] = 5,
    rman_rate_in__m_b: Optional[int] = 0,
    script_directory: Optional[str] = None,
    sid: Optional[str] = None,
    skip_space_check: Optional[bool] = False,
    snapshot_id: Optional[str] = None,
    snapshot_policy_id: Optional[str] = None,
    sort: Optional[str] = None,
    source_data_id: Optional[str] = None,
    source_host_user: Optional[str] = None,
    source_id: Optional[str] = None,
    staging_container_database_reference: Optional[str] = None,
    staging_database_config_params: Optional[dict] = None,
    staging_database_name: Optional[str] = None,
    staging_database_templates: Optional[list] = None,
    staging_environment: Optional[str] = None,
    staging_environment_user: Optional[str] = None,
    staging_host_user: Optional[str] = None,
    staging_mount_base: Optional[str] = None,
    staging_post_script: Optional[str] = None,
    staging_pre_script: Optional[str] = None,
    staging_repository: Optional[str] = None,
    sync_parameters: Optional[dict] = None,
    sync_policy_id: Optional[str] = None,
    sync_strategy: Optional[str] = 'new_backup',
    sync_strategy_managed_type: Optional[str] = 'external',
    tags: Optional[list] = None,
    target_directory: Optional[str] = None,
    target_group_id: Optional[str] = None,
    target_pdb_tde_keystore_password: Optional[str] = None,
    target_vcdb_tde_keystore_path: Optional[str] = None,
    tde_exported_key_file_secret: Optional[str] = None,
    tde_exported_keyfile_secret: Optional[str] = None,
    tde_key_identifier: Optional[str] = None,
    tde_keystore_config_type: Optional[str] = None,
    tde_keystore_password: Optional[str] = None,
    temp_directory: Optional[str] = None,
    template_id: Optional[str] = None,
    timeflow_id: Optional[str] = None,
    timestamp: Optional[str] = None,
    timestamp_in_database_timezone: Optional[str] = None,
    truncate_log_on_checkpoint: Optional[bool] = None,
    unique_name: Optional[str] = None,
    use_absolute_path_for_data_files: Optional[bool] = None,
    validate_by_opening_db_in_read_only_mode: Optional[bool] = None,
    validate_db_credentials: Optional[bool] = True,
    validate_snapshot_in_readonly: Optional[bool] = False,
    validated_sync_mode: Optional[str] = 'ENABLED',
    value: Optional[str] = None,
    vcdb_database_name: Optional[str] = None,
    vcdb_name: Optional[str] = None,
    vcdb_restart: Optional[bool] = None,
    vcdb_tde_key_identifier: Optional[str] = None,
    vdb_disable_param_mappings: Optional[list] = None,
    vdb_enable_param_mappings: Optional[list] = None,
    vdb_group_id: Optional[str] = None,
    vdb_id: Optional[str] = None,
    vdb_ids: Optional[list] = None,
    vdb_restart: Optional[bool] = None,
    vdb_snapshot_mappings: Optional[list] = None,
    vdb_start_param_mappings: Optional[list] = None,
    vdb_stop_param_mappings: Optional[list] = None,
    vdb_timestamp_mappings: Optional[list] = None,
    vdbs: Optional[list] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for DATA operations.
    
    This tool supports 122 actions: list_vdbs, search_vdbs, get_vdb, update_vdb, provision_by_timestamp, provision_by_timestamp_defaults, provision_by_snapshot, provision_by_snapshot_defaults, provision_from_bookmark, provision_from_bookmark_defaults, provision_by_location, provision_by_location_defaults, provision_empty_vdb, delete_vdb, start_vdb, stop_vdb, enable_vdb, disable_vdb, refresh_vdb_by_timestamp, refresh_vdb_by_snapshot, refresh_vdb_from_bookmark, refresh_vdb_by_location, undo_vdb_refresh, rollback_vdb_by_timestamp, rollback_vdb_by_snapshot, rollback_vdb_from_bookmark, switch_vdb_timeflow, lock_vdb, unlock_vdb, migrate_vdb, get_migrate_compatible_repositories, upgrade_vdb, upgrade_oracle_vdb, get_upgrade_compatible_repositories, list_vdb_snapshots, snapshot_vdb, list_vdb_bookmarks, search_vdb_bookmarks, get_vdb_deletion_dependencies, verify_vdb_jdbc_connection, get_vdb_tags, add_vdb_tags, export_vdb_in_place, export_vdb_asm_in_place, export_vdb_by_snapshot, export_vdb_by_timestamp, export_vdb_by_location, export_vdb_from_bookmark, export_vdb_to_asm_by_snapshot, export_vdb_to_asm_by_timestamp, export_vdb_to_asm_by_location, export_vdb_to_asm_from_bookmark, export_cleanup, export_finalize, list_vdb_groups, search_vdb_groups, get_vdb_group, create_vdb_group, update_vdb_group, delete_vdb_group, provision_vdb_group_from_bookmark, refresh_vdb_group, refresh_vdb_group_from_bookmark, refresh_vdb_group_by_snapshot, refresh_vdb_group_by_timestamp, rollback_vdb_group, lock_vdb_group, unlock_vdb_group, start_vdb_group, stop_vdb_group, enable_vdb_group, disable_vdb_group, get_vdb_group_latest_snapshots, get_vdb_group_timestamp_summary, list_vdb_group_bookmarks, search_vdb_group_bookmarks, get_vdb_group_tags, add_vdb_group_tags, list_dsources, search_dsources, get_dsource, delete_dsource, enable_dsource, disable_dsource, list_dsource_snapshots, dsource_create_snapshot, upgrade_dsource, get_dsource_upgrade_compatible_repositories, get_dsource_deletion_dependencies, get_dsource_tags, add_dsource_tags, delete_dsource_tags, dsource_link_oracle, dsource_link_oracle_defaults, dsource_link_oracle_staging_push, dsource_link_oracle_staging_push_defaults, update_oracle_dsource, attach_oracle_dsource, detach_oracle_dsource, upgrade_oracle_dsource, dsource_link_ase, dsource_link_ase_defaults, update_ase_dsource, dsource_link_appdata, dsource_link_appdata_defaults, update_appdata_dsource, dsource_link_mssql, dsource_link_mssql_defaults, dsource_link_mssql_staging_push, dsource_link_mssql_staging_push_defaults, attach_mssql_staging_push_dsource, update_mssql_dsource, attach_mssql_dsource, detach_mssql_dsource, export_dsource_by_snapshot, export_dsource_by_timestamp, export_dsource_by_location, export_dsource_from_bookmark, export_dsource_to_asm_by_snapshot, export_dsource_to_asm_by_timestamp, export_dsource_to_asm_by_location, export_dsource_to_asm_from_bookmark
    
    IMPORTANT — Delphix domain terminology:
  • "dSource" is often used as a VERB meaning "create/link a dSource" (i.e. ingest a source database). When a user says "dSource database X", they want to LINK a new dSource for database X, NOT look up an existing dSource named X. Use the appropriate dsource_link_* action (dsource_link_oracle, dsource_link_mssql, dsource_link_ase, dsource_link_appdata) depending on the database type.
  • "provision" or "spin up" a VDB or "create a golden image of a VDB" means creating a virtual database from a dSource or bookmark  — use provision_by_timestamp, provision_by_snapshot, etc.
  • "refresh" a VDB means updating it with newer data from its parent — use refresh_vdb_by_timestamp, refresh_vdb_by_snapshot, etc.
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: list_vdbs
    ----------------------------------------
    Summary: List all vdbs.
    Method: GET
    Endpoint: /vdbs
    Required Parameters: limit, cursor, sort, permission
    
    Example:
        >>> data_tool(action='list_vdbs', limit=..., cursor=..., sort=..., permission=...)
    
    ACTION: search_vdbs
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
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> data_tool(action='search_vdbs', limit=..., cursor=..., sort=..., permission=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get_vdb
    ----------------------------------------
    Summary: Get a VDB by ID.
    Method: GET
    Endpoint: /vdbs/{vdbId}
    Required Parameters: vdb_id
    
    Example:
        >>> data_tool(action='get_vdb', vdb_id='example-vdb-123')
    
    ACTION: update_vdb
    ----------------------------------------
    Summary: Update values of a VDB
    Method: PATCH
    Endpoint: /vdbs/{vdbId}
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): name, description, db_username, db_password, validate_db_credentials, auto_restart, environment_user_id, template_id, listener_ids, new_dbid, cdc_on_provision, pre_script, post_script, hooks, custom_env_vars, custom_env_files, oracle_rac_custom_env_files, oracle_rac_custom_env_vars, parent_tde_keystore_path, parent_tde_keystore_password, tde_key_identifier, target_vcdb_tde_keystore_path, cdb_tde_keystore_password, parent_pdb_tde_keystore_path, parent_pdb_tde_keystore_password, target_pdb_tde_keystore_password, appdata_source_params, additional_mount_points, appdata_config_params, config_params, mount_point, oracle_services, instances, invoke_datapatch, mssql_ag_backup_location, mssql_ag_backup_based, cache_priority, mssql_incremental_export_backup_frequency_minutes, database_name
    
    Example:
        >>> data_tool(action='update_vdb', vdb_id='example-vdb-123', name=..., description=..., db_username=..., db_password=..., validate_db_credentials=..., auto_restart=..., environment_user_id='example-environment_user-123', template_id='example-template-123', listener_ids=..., new_dbid=..., cdc_on_provision=..., pre_script=..., post_script=..., hooks=..., custom_env_vars=..., custom_env_files=..., oracle_rac_custom_env_files=..., oracle_rac_custom_env_vars=..., parent_tde_keystore_path=..., parent_tde_keystore_password=..., tde_key_identifier=..., target_vcdb_tde_keystore_path=..., cdb_tde_keystore_password=..., parent_pdb_tde_keystore_path=..., parent_pdb_tde_keystore_password=..., target_pdb_tde_keystore_password=..., appdata_source_params=..., additional_mount_points=..., appdata_config_params=..., config_params=..., mount_point=..., oracle_services=..., instances=..., invoke_datapatch=..., mssql_ag_backup_location=..., mssql_ag_backup_based=..., cache_priority=..., mssql_incremental_export_backup_frequency_minutes=..., database_name=...)
    
    ACTION: provision_by_timestamp
    ----------------------------------------
    Summary: Provision a new VDB by timestamp.
    Method: POST
    Endpoint: /vdbs/provision_by_timestamp
    Required Parameters: source_data_id
    Key Parameters (provide as applicable): timestamp, timestamp_in_database_timezone, timeflow_id, engine_id, make_current_account_owner
    
    Example:
        >>> data_tool(action='provision_by_timestamp', timestamp=..., timestamp_in_database_timezone=..., timeflow_id='example-timeflow-123', engine_id='example-engine-123', source_data_id='example-source_data-123', make_current_account_owner=...)
    
        IMPORTANT — Toolkit schema for AppData payloads: The 'parameters', 'appdata_source_params', and 'appdata_config_params' fields follow a DraftV4 schema defined by the toolkit. Do NOT call toolkit_tool to fetch the schema — it is already pre-cached as an MCP resource. Use resources/read on toolkit://{toolkit_id}/schema to get the full schema definition. Identify the toolkit_id from the source or environment first, then read the resource.
    
    ACTION: provision_by_timestamp_defaults
    ----------------------------------------
    Summary: Get default provision parameters for provisioning a new VDB by timestamp.
    Method: POST
    Endpoint: /vdbs/provision_by_timestamp/defaults
    Required Parameters: source_data_id
    Key Parameters (provide as applicable): timestamp, timestamp_in_database_timezone, timeflow_id, engine_id
    
    Example:
        >>> data_tool(action='provision_by_timestamp_defaults', timestamp=..., timestamp_in_database_timezone=..., timeflow_id='example-timeflow-123', engine_id='example-engine-123', source_data_id='example-source_data-123')
    
    ACTION: provision_by_snapshot
    ----------------------------------------
    Summary: Provision a new VDB by snapshot.
    Method: POST
    Endpoint: /vdbs/provision_by_snapshot
    Key Parameters (provide as applicable): engine_id, source_data_id, make_current_account_owner, snapshot_id
    
    Example:
        >>> data_tool(action='provision_by_snapshot', engine_id='example-engine-123', source_data_id='example-source_data-123', make_current_account_owner=..., snapshot_id='example-snapshot-123')
    
        IMPORTANT — Toolkit schema for AppData payloads: The 'parameters', 'appdata_source_params', and 'appdata_config_params' fields follow a DraftV4 schema defined by the toolkit. Do NOT call toolkit_tool to fetch the schema — it is already pre-cached as an MCP resource. Use resources/read on toolkit://{toolkit_id}/schema to get the full schema definition. Identify the toolkit_id from the source or environment first, then read the resource.
    
    ACTION: provision_by_snapshot_defaults
    ----------------------------------------
    Summary: Get default provision parameters for provisioning a new VDB by snapshot.
    Method: POST
    Endpoint: /vdbs/provision_by_snapshot/defaults
    Key Parameters (provide as applicable): engine_id, source_data_id, snapshot_id
    
    Example:
        >>> data_tool(action='provision_by_snapshot_defaults', engine_id='example-engine-123', source_data_id='example-source_data-123', snapshot_id='example-snapshot-123')
    
    ACTION: provision_from_bookmark
    ----------------------------------------
    Summary: Provision a new VDB from a bookmark with a single VDB.
    Method: POST
    Endpoint: /vdbs/provision_from_bookmark
    Required Parameters: bookmark_id
    Key Parameters (provide as applicable): make_current_account_owner
    
    Example:
        >>> data_tool(action='provision_from_bookmark', make_current_account_owner=..., bookmark_id='example-bookmark-123')
    
        IMPORTANT — Toolkit schema for AppData payloads: The 'parameters', 'appdata_source_params', and 'appdata_config_params' fields follow a DraftV4 schema defined by the toolkit. Do NOT call toolkit_tool to fetch the schema — it is already pre-cached as an MCP resource. Use resources/read on toolkit://{toolkit_id}/schema to get the full schema definition. Identify the toolkit_id from the source or environment first, then read the resource.
    
    ACTION: provision_from_bookmark_defaults
    ----------------------------------------
    Summary: Get default provision parameters for provisioning a new VDB from a bookmark.
    Method: POST
    Endpoint: /vdbs/provision_from_bookmark/defaults
    Required Parameters: bookmark_id
    
    Example:
        >>> data_tool(action='provision_from_bookmark_defaults', bookmark_id='example-bookmark-123')
    
    ACTION: provision_by_location
    ----------------------------------------
    Summary: Provision a new VDB by location.
    Method: POST
    Endpoint: /vdbs/provision_by_location
    Key Parameters (provide as applicable): timeflow_id, engine_id, source_data_id, make_current_account_owner, location
    
    Example:
        >>> data_tool(action='provision_by_location', timeflow_id='example-timeflow-123', engine_id='example-engine-123', source_data_id='example-source_data-123', make_current_account_owner=..., location=...)
    
        IMPORTANT — Toolkit schema for AppData payloads: The 'parameters', 'appdata_source_params', and 'appdata_config_params' fields follow a DraftV4 schema defined by the toolkit. Do NOT call toolkit_tool to fetch the schema — it is already pre-cached as an MCP resource. Use resources/read on toolkit://{toolkit_id}/schema to get the full schema definition. Identify the toolkit_id from the source or environment first, then read the resource.
    
    ACTION: provision_by_location_defaults
    ----------------------------------------
    Summary: Get default provision parameters for provisioning a new VDB by location.
    Method: POST
    Endpoint: /vdbs/provision_by_location/defaults
    Key Parameters (provide as applicable): timeflow_id, engine_id, source_data_id, location
    
    Example:
        >>> data_tool(action='provision_by_location_defaults', timeflow_id='example-timeflow-123', engine_id='example-engine-123', source_data_id='example-source_data-123', location=...)
    
    ACTION: provision_empty_vdb
    ----------------------------------------
    Summary: Provision an empty VDB.
    Method: POST
    Endpoint: /vdbs/empty_vdb
    Key Parameters (provide as applicable): repository_id, engine_id
    
    Example:
        >>> data_tool(action='provision_empty_vdb', repository_id='example-repository-123', engine_id='example-engine-123')
    
        IMPORTANT — Toolkit schema for AppData payloads: The 'parameters', 'appdata_source_params', and 'appdata_config_params' fields follow a DraftV4 schema defined by the toolkit. Do NOT call toolkit_tool to fetch the schema — it is already pre-cached as an MCP resource. Use resources/read on toolkit://{toolkit_id}/schema to get the full schema definition. Identify the toolkit_id from the source or environment first, then read the resource.
    
    ACTION: delete_vdb
    ----------------------------------------
    Summary: Delete a VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/delete
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): force, delete_all_dependent_vdbs
    
    Example:
        >>> data_tool(action='delete_vdb', vdb_id='example-vdb-123', force=..., delete_all_dependent_vdbs=...)
    
    ACTION: start_vdb
    ----------------------------------------
    Summary: Start a VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/start
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): instances
    
    Example:
        >>> data_tool(action='start_vdb', vdb_id='example-vdb-123', instances=...)
    
    ACTION: stop_vdb
    ----------------------------------------
    Summary: Stop a VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/stop
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): instances, abort
    
    Example:
        >>> data_tool(action='stop_vdb', vdb_id='example-vdb-123', instances=..., abort=...)
    
    ACTION: enable_vdb
    ----------------------------------------
    Summary: Enable a VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/enable
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): container_mode, attempt_start, ownership_spec
    
    Example:
        >>> data_tool(action='enable_vdb', vdb_id='example-vdb-123', container_mode=..., attempt_start=..., ownership_spec=...)
    
    ACTION: disable_vdb
    ----------------------------------------
    Summary: Disable a VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/disable
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): container_mode, attempt_cleanup
    
    Example:
        >>> data_tool(action='disable_vdb', vdb_id='example-vdb-123', container_mode=..., attempt_cleanup=...)
    
    ACTION: refresh_vdb_by_timestamp
    ----------------------------------------
    Summary: Refresh a VDB by timestamp.
    Method: POST
    Endpoint: /vdbs/{vdbId}/refresh_by_timestamp
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): timestamp, timestamp_in_database_timezone, timeflow_id, dataset_id
    
    Example:
        >>> data_tool(action='refresh_vdb_by_timestamp', vdb_id='example-vdb-123', timestamp=..., timestamp_in_database_timezone=..., timeflow_id='example-timeflow-123', dataset_id='example-dataset-123')
    
    ACTION: refresh_vdb_by_snapshot
    ----------------------------------------
    Summary: Refresh a VDB by snapshot.
    Method: POST
    Endpoint: /vdbs/{vdbId}/refresh_by_snapshot
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): snapshot_id
    
    Example:
        >>> data_tool(action='refresh_vdb_by_snapshot', vdb_id='example-vdb-123', snapshot_id='example-snapshot-123')
    
    ACTION: refresh_vdb_from_bookmark
    ----------------------------------------
    Summary: Refresh a VDB from bookmark with a single VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/refresh_from_bookmark
    Required Parameters: vdb_id, bookmark_id
    
    Example:
        >>> data_tool(action='refresh_vdb_from_bookmark', vdb_id='example-vdb-123', bookmark_id='example-bookmark-123')
    
    ACTION: refresh_vdb_by_location
    ----------------------------------------
    Summary: Refresh a VDB by location.
    Method: POST
    Endpoint: /vdbs/{vdbId}/refresh_by_location
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): timeflow_id, location, dataset_id
    
    Example:
        >>> data_tool(action='refresh_vdb_by_location', vdb_id='example-vdb-123', timeflow_id='example-timeflow-123', location=..., dataset_id='example-dataset-123')
    
    ACTION: undo_vdb_refresh
    ----------------------------------------
    Summary: Undo the last refresh operation.
    Method: POST
    Endpoint: /vdbs/{vdbId}/undo_refresh
    Required Parameters: vdb_id
    
    Example:
        >>> data_tool(action='undo_vdb_refresh', vdb_id='example-vdb-123')
    
    ACTION: rollback_vdb_by_timestamp
    ----------------------------------------
    Summary: Rollback a VDB by timestamp.
    Method: POST
    Endpoint: /vdbs/{vdbId}/rollback_by_timestamp
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): timestamp, timestamp_in_database_timezone, timeflow_id
    
    Example:
        >>> data_tool(action='rollback_vdb_by_timestamp', vdb_id='example-vdb-123', timestamp=..., timestamp_in_database_timezone=..., timeflow_id='example-timeflow-123')
    
    ACTION: rollback_vdb_by_snapshot
    ----------------------------------------
    Summary: Rollback a VDB by snapshot.
    Method: POST
    Endpoint: /vdbs/{vdbId}/rollback_by_snapshot
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): snapshot_id
    
    Example:
        >>> data_tool(action='rollback_vdb_by_snapshot', vdb_id='example-vdb-123', snapshot_id='example-snapshot-123')
    
    ACTION: rollback_vdb_from_bookmark
    ----------------------------------------
    Summary: Rollback a VDB from a bookmark with only the same VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/rollback_from_bookmark
    Required Parameters: vdb_id, bookmark_id
    
    Example:
        >>> data_tool(action='rollback_vdb_from_bookmark', vdb_id='example-vdb-123', bookmark_id='example-bookmark-123')
    
    ACTION: switch_vdb_timeflow
    ----------------------------------------
    Summary: Switches the current timeflow of a VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/switch_timeflow
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): timeflow_id
    
    Example:
        >>> data_tool(action='switch_vdb_timeflow', vdb_id='example-vdb-123', timeflow_id='example-timeflow-123')
    
    ACTION: lock_vdb
    ----------------------------------------
    Summary: Lock a VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/lock
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): account_id
    
    Example:
        >>> data_tool(action='lock_vdb', vdb_id='example-vdb-123', account_id='example-account-123')
    
    ACTION: unlock_vdb
    ----------------------------------------
    Summary: Unlock a VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/unlock
    Required Parameters: vdb_id
    
    Example:
        >>> data_tool(action='unlock_vdb', vdb_id='example-vdb-123')
    
    ACTION: migrate_vdb
    ----------------------------------------
    Summary: Migrate a VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/migrate
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): cdb_id, cluster_node_ids, cluster_node_instances, environment_id, repository_id, environment_user_ref
    
    Example:
        >>> data_tool(action='migrate_vdb', vdb_id='example-vdb-123', cdb_id='example-cdb-123', cluster_node_ids=..., cluster_node_instances=..., environment_id='example-environment-123', repository_id='example-repository-123', environment_user_ref=...)
    
    ACTION: get_migrate_compatible_repositories
    ----------------------------------------
    Summary: Returns a list of compatible repositories for vdb migration.
    Method: GET
    Endpoint: /vdbs/{vdbId}/migrate_compatible_repositories
    Required Parameters: vdb_id
    
    Example:
        >>> data_tool(action='get_migrate_compatible_repositories', vdb_id='example-vdb-123')
    
    ACTION: upgrade_vdb
    ----------------------------------------
    Summary: Upgrade VDB
    Method: POST
    Endpoint: /vdbs/{vdbId}/upgrade
    Required Parameters: vdb_id, repository_id
    Key Parameters (provide as applicable): environment_user_id, ppt_repository
    
    Example:
        >>> data_tool(action='upgrade_vdb', vdb_id='example-vdb-123', environment_user_id='example-environment_user-123', repository_id='example-repository-123', ppt_repository=...)
    
    ACTION: upgrade_oracle_vdb
    ----------------------------------------
    Summary: Upgrade Oracle VDB
    Method: POST
    Endpoint: /vdbs/oracle/{vdbId}/upgrade
    Required Parameters: vdb_id, environment_user_id, repository_id
    
    Example:
        >>> data_tool(action='upgrade_oracle_vdb', vdb_id='example-vdb-123', environment_user_id='example-environment_user-123', repository_id='example-repository-123')
    
    ACTION: get_upgrade_compatible_repositories
    ----------------------------------------
    Summary: Returns a list of compatible repositories for vdb upgrade.
    Method: GET
    Endpoint: /vdbs/{vdbId}/upgrade_compatible_repositories
    Required Parameters: vdb_id
    
    Example:
        >>> data_tool(action='get_upgrade_compatible_repositories', vdb_id='example-vdb-123')
    
    ACTION: list_vdb_snapshots
    ----------------------------------------
    Summary: List Snapshots for a VDB.
    Method: GET
    Endpoint: /vdbs/{vdbId}/snapshots
    Required Parameters: limit, cursor, vdb_id
    
    Example:
        >>> data_tool(action='list_vdb_snapshots', limit=..., cursor=..., vdb_id='example-vdb-123')
    
    ACTION: snapshot_vdb
    ----------------------------------------
    Summary: Snapshot a VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/snapshots
    Required Parameters: vdb_id
    
    Example:
        >>> data_tool(action='snapshot_vdb', vdb_id='example-vdb-123')
    
    ACTION: list_vdb_bookmarks
    ----------------------------------------
    Summary: List Bookmarks compatible with this VDB.
    Method: GET
    Endpoint: /vdbs/{vdbId}/bookmarks
    Required Parameters: limit, cursor, sort, vdb_id
    
    Example:
        >>> data_tool(action='list_vdb_bookmarks', limit=..., cursor=..., sort=..., vdb_id='example-vdb-123')
    
    ACTION: search_vdb_bookmarks
    ----------------------------------------
    Summary: Search Bookmarks compatible with this VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/bookmarks/search
    Required Parameters: limit, cursor, sort, vdb_id
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
        >>> data_tool(action='search_vdb_bookmarks', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'", vdb_id='example-vdb-123')
    
    ACTION: get_vdb_deletion_dependencies
    ----------------------------------------
    Summary: Get deletion dependencies of a VDB.
    Method: GET
    Endpoint: /vdbs/{vdbId}/deletion-dependencies
    Required Parameters: vdb_id
    
    Example:
        >>> data_tool(action='get_vdb_deletion_dependencies', vdb_id='example-vdb-123')
    
    ACTION: verify_vdb_jdbc_connection
    ----------------------------------------
    Summary: Verify JDBC connection string for VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/jdbc-check
    Required Parameters: vdb_id, database_username, database_password, jdbc_connection_string
    
    Example:
        >>> data_tool(action='verify_vdb_jdbc_connection', vdb_id='example-vdb-123', database_username=..., database_password=..., jdbc_connection_string=...)
    
    ACTION: get_vdb_tags
    ----------------------------------------
    Summary: Get tags for a VDB.
    Method: GET
    Endpoint: /vdbs/{vdbId}/tags
    Required Parameters: vdb_id
    
    Example:
        >>> data_tool(action='get_vdb_tags', vdb_id='example-vdb-123')
    
    ACTION: add_vdb_tags
    ----------------------------------------
    Summary: Create tags for a VDB.
    Method: POST
    Endpoint: /vdbs/{vdbId}/tags
    Required Parameters: vdb_id, tags
    
    Example:
        >>> data_tool(action='add_vdb_tags', vdb_id='example-vdb-123', tags=...)
    
    ACTION: export_vdb_in_place
    ----------------------------------------
    Summary: Convert a virtual database to a physical database on physical file system.
    Method: POST
    Endpoint: /vdbs/{vdbId}/in-place-export
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): rman_channels, rman_file_section_size_in_gb, db_unique_name, pdb_name, operations_post_v2_p
    
    Example:
        >>> data_tool(action='export_vdb_in_place', vdb_id='example-vdb-123', rman_channels=..., rman_file_section_size_in_gb=..., db_unique_name=..., pdb_name=..., operations_post_v2_p=...)
    
    ACTION: export_vdb_asm_in_place
    ----------------------------------------
    Summary: Convert a virtual database to a physical database on Oracle ASM file system.
    Method: POST
    Endpoint: /vdbs/{vdbId}/asm-in-place-export
    Required Parameters: vdb_id, default_data_diskgroup
    Key Parameters (provide as applicable): rman_channels, rman_file_section_size_in_gb, db_unique_name, pdb_name, operations_post_v2_p, redo_diskgroup
    
    Example:
        >>> data_tool(action='export_vdb_asm_in_place', vdb_id='example-vdb-123', rman_channels=..., rman_file_section_size_in_gb=..., db_unique_name=..., pdb_name=..., operations_post_v2_p=..., default_data_diskgroup=..., redo_diskgroup=...)
    
    ACTION: export_vdb_by_snapshot
    ----------------------------------------
    Summary: Export a vdb using snapshot to a physical file system
    Method: POST
    Endpoint: /vdbs/{vdbId}/export-by-snapshot
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): snapshot_id, rman_channels, rman_file_section_size_in_gb
    
    Example:
        >>> data_tool(action='export_vdb_by_snapshot', vdb_id='example-vdb-123', snapshot_id='example-snapshot-123', rman_channels=..., rman_file_section_size_in_gb=...)
    
    ACTION: export_vdb_by_timestamp
    ----------------------------------------
    Summary: Export a vdb using timestamp to a physical file system
    Method: POST
    Endpoint: /vdbs/{vdbId}/export-by-timestamp
    Required Parameters: vdb_id, timestamp, timeflow_id
    Key Parameters (provide as applicable): rman_channels, rman_file_section_size_in_gb
    
    Example:
        >>> data_tool(action='export_vdb_by_timestamp', vdb_id='example-vdb-123', timestamp=..., timeflow_id='example-timeflow-123', rman_channels=..., rman_file_section_size_in_gb=...)
    
    ACTION: export_vdb_by_location
    ----------------------------------------
    Summary: Export a vdb using timeflow location to a physical file system
    Method: POST
    Endpoint: /vdbs/{vdbId}/export-by-location
    Required Parameters: vdb_id, location
    Key Parameters (provide as applicable): rman_channels, rman_file_section_size_in_gb
    
    Example:
        >>> data_tool(action='export_vdb_by_location', vdb_id='example-vdb-123', location=..., rman_channels=..., rman_file_section_size_in_gb=...)
    
    ACTION: export_vdb_from_bookmark
    ----------------------------------------
    Summary: Export a vdb using bookmark to physical file system
    Method: POST
    Endpoint: /vdbs/{vdbId}/export-from-bookmark
    Required Parameters: vdb_id, bookmark_id
    Key Parameters (provide as applicable): rman_channels, rman_file_section_size_in_gb
    
    Example:
        >>> data_tool(action='export_vdb_from_bookmark', vdb_id='example-vdb-123', bookmark_id='example-bookmark-123', rman_channels=..., rman_file_section_size_in_gb=...)
    
    ACTION: export_vdb_to_asm_by_snapshot
    ----------------------------------------
    Summary: Export a vdb using snapshot to an ASM file system
    Method: POST
    Endpoint: /vdbs/{vdbId}/asm-export-by-snapshot
    Required Parameters: vdb_id, default_data_diskgroup
    Key Parameters (provide as applicable): snapshot_id, rman_channels, rman_file_section_size_in_gb, redo_diskgroup
    
    Example:
        >>> data_tool(action='export_vdb_to_asm_by_snapshot', vdb_id='example-vdb-123', snapshot_id='example-snapshot-123', rman_channels=..., rman_file_section_size_in_gb=..., default_data_diskgroup=..., redo_diskgroup=...)
    
    ACTION: export_vdb_to_asm_by_timestamp
    ----------------------------------------
    Summary: Export a vdb using timestamp to an ASM file system
    Method: POST
    Endpoint: /vdbs/{vdbId}/asm-export-by-timestamp
    Required Parameters: vdb_id, timestamp, timeflow_id, default_data_diskgroup
    Key Parameters (provide as applicable): rman_channels, rman_file_section_size_in_gb, redo_diskgroup
    
    Example:
        >>> data_tool(action='export_vdb_to_asm_by_timestamp', vdb_id='example-vdb-123', timestamp=..., timeflow_id='example-timeflow-123', rman_channels=..., rman_file_section_size_in_gb=..., default_data_diskgroup=..., redo_diskgroup=...)
    
    ACTION: export_vdb_to_asm_by_location
    ----------------------------------------
    Summary: Export a vdb using SCN to an ASM file system
    Method: POST
    Endpoint: /vdbs/{vdbId}/asm-export-by-location
    Required Parameters: vdb_id, location, default_data_diskgroup
    Key Parameters (provide as applicable): rman_channels, rman_file_section_size_in_gb, redo_diskgroup
    
    Example:
        >>> data_tool(action='export_vdb_to_asm_by_location', vdb_id='example-vdb-123', location=..., rman_channels=..., rman_file_section_size_in_gb=..., default_data_diskgroup=..., redo_diskgroup=...)
    
    ACTION: export_vdb_to_asm_from_bookmark
    ----------------------------------------
    Summary: Export a vdb using bookmark to an ASM file system
    Method: POST
    Endpoint: /vdbs/{vdbId}/asm-export-from-bookmark
    Required Parameters: vdb_id, bookmark_id, default_data_diskgroup
    Key Parameters (provide as applicable): rman_channels, rman_file_section_size_in_gb, redo_diskgroup
    
    Example:
        >>> data_tool(action='export_vdb_to_asm_from_bookmark', vdb_id='example-vdb-123', bookmark_id='example-bookmark-123', rman_channels=..., rman_file_section_size_in_gb=..., default_data_diskgroup=..., redo_diskgroup=...)
    
    ACTION: export_cleanup
    ----------------------------------------
    Summary: Export cleanup for incremental V2P operation
    Method: POST
    Endpoint: /vdbs/{vdbId}/export_cleanup
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): cleanup_target_physical_files, cleanup_target_container
    
    Example:
        >>> data_tool(action='export_cleanup', vdb_id='example-vdb-123', cleanup_target_physical_files=..., cleanup_target_container=...)
    
    ACTION: export_finalize
    ----------------------------------------
    Summary: Finalize operation on incremental V2P export
    Method: POST
    Endpoint: /vdbs/{vdbId}/export_finalize
    Required Parameters: vdb_id
    Key Parameters (provide as applicable): force, max_allowed_backups_pending_restore
    
    Example:
        >>> data_tool(action='export_finalize', vdb_id='example-vdb-123', force=..., max_allowed_backups_pending_restore=...)
    
    ACTION: list_vdb_groups
    ----------------------------------------
    Summary: List all VDBGroups.
    Method: GET
    Endpoint: /vdb-groups
    Required Parameters: limit, cursor, sort
    
    Example:
        >>> data_tool(action='list_vdb_groups', limit=..., cursor=..., sort=...)
    
    ACTION: search_vdb_groups
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
        >>> data_tool(action='search_vdb_groups', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get_vdb_group
    ----------------------------------------
    Summary: Get a VDB Group by name.
    Method: GET
    Endpoint: /vdb-groups/{vdbGroupId}
    Required Parameters: vdb_group_id
    
    Example:
        >>> data_tool(action='get_vdb_group', vdb_group_id='example-vdb_group-123')
    
    ACTION: create_vdb_group
    ----------------------------------------
    Summary: Create a new VDB Group.
    Method: POST
    Endpoint: /vdb-groups
    Required Parameters: name
    Key Parameters (provide as applicable): tags, make_current_account_owner, vdb_ids, vdbs, refresh_immediately
    
    Example:
        >>> data_tool(action='create_vdb_group', name=..., tags=..., make_current_account_owner=..., vdb_ids=..., vdbs=..., refresh_immediately=...)
    
    ACTION: update_vdb_group
    ----------------------------------------
    Summary: Update values of a VDB group.
    Method: PATCH
    Endpoint: /vdb-groups/{vdbGroupId}
    Required Parameters: vdb_group_id
    Key Parameters (provide as applicable): name, vdb_ids, vdbs, refresh_immediately
    
    Example:
        >>> data_tool(action='update_vdb_group', name=..., vdb_group_id='example-vdb_group-123', vdb_ids=..., vdbs=..., refresh_immediately=...)
    
    ACTION: delete_vdb_group
    ----------------------------------------
    Summary: Delete a VDBGoup.
    Method: DELETE
    Endpoint: /vdb-groups/{vdbGroupId}
    Required Parameters: vdb_group_id
    
    Example:
        >>> data_tool(action='delete_vdb_group', vdb_group_id='example-vdb_group-123')
    
    ACTION: provision_vdb_group_from_bookmark
    ----------------------------------------
    Summary: Provision a new VDB Group from a Bookmark.
    Method: POST
    Endpoint: /vdb-groups/provision_from_bookmark
    Required Parameters: name, bookmark_id, provision_parameters
    Key Parameters (provide as applicable): tags, make_current_account_owner
    
    Example:
        >>> data_tool(action='provision_vdb_group_from_bookmark', name=..., tags=..., make_current_account_owner=..., bookmark_id='example-bookmark-123', provision_parameters=...)
    
    ACTION: refresh_vdb_group
    ----------------------------------------
    Summary: Refresh a VDB Group from bookmark.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/refresh
    Required Parameters: bookmark_id, vdb_group_id
    
    Example:
        >>> data_tool(action='refresh_vdb_group', bookmark_id='example-bookmark-123', vdb_group_id='example-vdb_group-123')
    
    ACTION: refresh_vdb_group_from_bookmark
    ----------------------------------------
    Summary: Refresh a VDB Group from bookmark.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/refresh_from_bookmark
    Required Parameters: bookmark_id, vdb_group_id
    
    Example:
        >>> data_tool(action='refresh_vdb_group_from_bookmark', bookmark_id='example-bookmark-123', vdb_group_id='example-vdb_group-123')
    
    ACTION: refresh_vdb_group_by_snapshot
    ----------------------------------------
    Summary: Refresh a VDB Group by snapshot.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/refresh_by_snapshot
    Required Parameters: vdb_group_id
    Key Parameters (provide as applicable): vdb_snapshot_mappings
    
    Example:
        >>> data_tool(action='refresh_vdb_group_by_snapshot', vdb_group_id='example-vdb_group-123', vdb_snapshot_mappings=...)
    
    ACTION: refresh_vdb_group_by_timestamp
    ----------------------------------------
    Summary: Refresh a VDB Group by timestamp.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/refresh_by_timestamp
    Required Parameters: vdb_group_id
    Key Parameters (provide as applicable): vdb_timestamp_mappings, is_refresh_to_nearest
    
    Example:
        >>> data_tool(action='refresh_vdb_group_by_timestamp', vdb_group_id='example-vdb_group-123', vdb_timestamp_mappings=..., is_refresh_to_nearest=...)
    
    ACTION: rollback_vdb_group
    ----------------------------------------
    Summary: Rollback a VDB Group from a bookmark.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/rollback
    Required Parameters: bookmark_id, vdb_group_id
    
    Example:
        >>> data_tool(action='rollback_vdb_group', bookmark_id='example-bookmark-123', vdb_group_id='example-vdb_group-123')
    
    ACTION: lock_vdb_group
    ----------------------------------------
    Summary: Lock a VDB Group.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/lock
    Required Parameters: vdb_group_id
    Key Parameters (provide as applicable): account_id
    
    Example:
        >>> data_tool(action='lock_vdb_group', account_id='example-account-123', vdb_group_id='example-vdb_group-123')
    
    ACTION: unlock_vdb_group
    ----------------------------------------
    Summary: Unlock a VDB Group.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/unlock
    Required Parameters: vdb_group_id
    
    Example:
        >>> data_tool(action='unlock_vdb_group', vdb_group_id='example-vdb_group-123')
    
    ACTION: start_vdb_group
    ----------------------------------------
    Summary: Start a VDB Group.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/start
    Required Parameters: vdb_group_id
    Key Parameters (provide as applicable): vdb_start_param_mappings
    
    Example:
        >>> data_tool(action='start_vdb_group', vdb_group_id='example-vdb_group-123', vdb_start_param_mappings=...)
    
    ACTION: stop_vdb_group
    ----------------------------------------
    Summary: Stop a VDB Group.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/stop
    Required Parameters: vdb_group_id
    Key Parameters (provide as applicable): vdb_stop_param_mappings
    
    Example:
        >>> data_tool(action='stop_vdb_group', vdb_group_id='example-vdb_group-123', vdb_stop_param_mappings=...)
    
    ACTION: enable_vdb_group
    ----------------------------------------
    Summary: Enable a VDB Group.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/enable
    Required Parameters: vdb_group_id
    Key Parameters (provide as applicable): vdb_enable_param_mappings
    
    Example:
        >>> data_tool(action='enable_vdb_group', vdb_group_id='example-vdb_group-123', vdb_enable_param_mappings=...)
    
    ACTION: disable_vdb_group
    ----------------------------------------
    Summary: Disable a VDB Group.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/disable
    Required Parameters: vdb_group_id
    Key Parameters (provide as applicable): vdb_disable_param_mappings
    
    Example:
        >>> data_tool(action='disable_vdb_group', vdb_group_id='example-vdb_group-123', vdb_disable_param_mappings=...)
    
    ACTION: get_vdb_group_latest_snapshots
    ----------------------------------------
    Summary: Get latest snapshot of all the vdbs in VDB Group.
    Method: GET
    Endpoint: /vdb-groups/{vdbGroupId}/latest-snapshots
    Required Parameters: vdb_group_id
    
    Example:
        >>> data_tool(action='get_vdb_group_latest_snapshots', vdb_group_id='example-vdb_group-123')
    
    ACTION: get_vdb_group_timestamp_summary
    ----------------------------------------
    Summary: Get timestamp summary of all the vdbs in VDB Group.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/timestamp-summary
    Required Parameters: vdb_group_id
    Key Parameters (provide as applicable): timestamp, vdb_ids, mode
    
    Example:
        >>> data_tool(action='get_vdb_group_timestamp_summary', timestamp=..., vdb_group_id='example-vdb_group-123', vdb_ids=..., mode=...)
    
    ACTION: list_vdb_group_bookmarks
    ----------------------------------------
    Summary: List bookmarks compatible with this VDB Group.
    Method: GET
    Endpoint: /vdb-groups/{vdbGroupId}/bookmarks
    Required Parameters: limit, cursor, sort, vdb_group_id
    
    Example:
        >>> data_tool(action='list_vdb_group_bookmarks', limit=..., cursor=..., sort=..., vdb_group_id='example-vdb_group-123')
    
    ACTION: search_vdb_group_bookmarks
    ----------------------------------------
    Summary: Search for bookmarks compatible with this VDB Group.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/bookmarks/search
    Required Parameters: limit, cursor, sort, vdb_group_id
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
        >>> data_tool(action='search_vdb_group_bookmarks', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'", vdb_group_id='example-vdb_group-123')
    
    ACTION: get_vdb_group_tags
    ----------------------------------------
    Summary: Get tags for a VDB Group.
    Method: GET
    Endpoint: /vdb-groups/{vdbGroupId}/tags
    Required Parameters: vdb_group_id
    
    Example:
        >>> data_tool(action='get_vdb_group_tags', vdb_group_id='example-vdb_group-123')
    
    ACTION: add_vdb_group_tags
    ----------------------------------------
    Summary: Create tags for a VDB Group.
    Method: POST
    Endpoint: /vdb-groups/{vdbGroupId}/tags
    Required Parameters: tags, vdb_group_id
    
    Example:
        >>> data_tool(action='add_vdb_group_tags', tags=..., vdb_group_id='example-vdb_group-123')
    
    ACTION: list_dsources
    ----------------------------------------
    Summary: List all dSources.
    Method: GET
    Endpoint: /dsources
    Required Parameters: limit, cursor, sort, permission
    
    Example:
        >>> data_tool(action='list_dsources', limit=..., cursor=..., sort=..., permission=...)
    
    ACTION: search_dsources
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
        >>> data_tool(action='search_dsources', limit=..., cursor=..., sort=..., permission=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get_dsource
    ----------------------------------------
    Summary: Get a dSource by ID.
    Method: GET
    Endpoint: /dsources/{dsourceId}
    Required Parameters: dsource_id
    
    Example:
        >>> data_tool(action='get_dsource', dsource_id='example-dsource-123')
    
    ACTION: delete_dsource
    ----------------------------------------
    Summary: Delete the specified dSource.
    Method: POST
    Endpoint: /dsources/delete
    Required Parameters: dsource_id
    Key Parameters (provide as applicable): force, delete_all_dependent_vdbs, oracle_username, oracle_password
    
    Example:
        >>> data_tool(action='delete_dsource', force=..., delete_all_dependent_vdbs=..., dsource_id='example-dsource-123', oracle_username=..., oracle_password=...)
    
    ACTION: enable_dsource
    ----------------------------------------
    Summary: Enable a dSource.
    Method: POST
    Endpoint: /dsources/{dsourceId}/enable
    Required Parameters: dsource_id
    Key Parameters (provide as applicable): attempt_start
    
    Example:
        >>> data_tool(action='enable_dsource', attempt_start=..., dsource_id='example-dsource-123')
    
    ACTION: disable_dsource
    ----------------------------------------
    Summary: Disable a dSource.
    Method: POST
    Endpoint: /dsources/{dsourceId}/disable
    Required Parameters: dsource_id
    Key Parameters (provide as applicable): attempt_cleanup
    
    Example:
        >>> data_tool(action='disable_dsource', attempt_cleanup=..., dsource_id='example-dsource-123')
    
    ACTION: list_dsource_snapshots
    ----------------------------------------
    Summary: List Snapshots for a dSource.
    Method: GET
    Endpoint: /dsources/{dsourceId}/snapshots
    Required Parameters: limit, cursor, dsource_id
    
    Example:
        >>> data_tool(action='list_dsource_snapshots', limit=..., cursor=..., dsource_id='example-dsource-123')
    
    ACTION: dsource_create_snapshot
    ----------------------------------------
    Summary: Snapshot a dSource.
    Method: POST
    Endpoint: /dsources/{dsourceId}/snapshots
    Required Parameters: dsource_id
    Key Parameters (provide as applicable): drop_and_recreate_devices, sync_strategy, ase_backup_files, mssql_backup_uuid, compression_enabled, availability_group_backup_policy, do_not_resume, double_sync, force_full_backup, skip_space_check, files_for_partial_full_backup, appdata_parameters, rman_rate_in__m_b
    
    Example:
        >>> data_tool(action='dsource_create_snapshot', dsource_id='example-dsource-123', drop_and_recreate_devices=..., sync_strategy=..., ase_backup_files=..., mssql_backup_uuid=..., compression_enabled=..., availability_group_backup_policy=..., do_not_resume=..., double_sync=..., force_full_backup=..., skip_space_check=..., files_for_partial_full_backup=..., appdata_parameters=..., rman_rate_in__m_b=...)
    
    ACTION: upgrade_dsource
    ----------------------------------------
    Summary: Upgrade dSource
    Method: POST
    Endpoint: /dsources/{dsourceId}/upgrade
    Required Parameters: repository_id, dsource_id
    Key Parameters (provide as applicable): environment_user_id, ppt_repository
    
    Example:
        >>> data_tool(action='upgrade_dsource', environment_user_id='example-environment_user-123', repository_id='example-repository-123', ppt_repository=..., dsource_id='example-dsource-123')
    
    ACTION: get_dsource_upgrade_compatible_repositories
    ----------------------------------------
    Summary: Returns a list of compatible repositories for dSource upgrade.
    Method: GET
    Endpoint: /dsources/{dsourceId}/upgrade_compatible_repositories
    Required Parameters: dsource_id
    
    Example:
        >>> data_tool(action='get_dsource_upgrade_compatible_repositories', dsource_id='example-dsource-123')
    
    ACTION: get_dsource_deletion_dependencies
    ----------------------------------------
    Summary: Get deletion dependencies for a dSource.
    Method: GET
    Endpoint: /dsources/{dsourceId}/deletion-dependencies
    Required Parameters: dsource_id
    
    Example:
        >>> data_tool(action='get_dsource_deletion_dependencies', dsource_id='example-dsource-123')
    
    ACTION: get_dsource_tags
    ----------------------------------------
    Summary: Get tags for a dSource.
    Method: GET
    Endpoint: /dsources/{dsourceId}/tags
    Required Parameters: dsource_id
    
    Example:
        >>> data_tool(action='get_dsource_tags', dsource_id='example-dsource-123')
    
    ACTION: add_dsource_tags
    ----------------------------------------
    Summary: Create tags for a dSource.
    Method: POST
    Endpoint: /dsources/{dsourceId}/tags
    Required Parameters: tags, dsource_id
    
    Example:
        >>> data_tool(action='add_dsource_tags', tags=..., dsource_id='example-dsource-123')
    
    ACTION: delete_dsource_tags
    ----------------------------------------
    Summary: Delete tags for a dSource.
    Method: POST
    Endpoint: /dsources/{dsourceId}/tags/delete
    Required Parameters: dsource_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> data_tool(action='delete_dsource_tags', tags=..., dsource_id='example-dsource-123', key=..., value=...)
    
    ACTION: dsource_link_oracle
    ----------------------------------------
    Summary: Link Oracle database as dSource.
    Method: POST
    Endpoint: /dsources/oracle
    Key Parameters (provide as applicable): environment_user_id, rman_channels, do_not_resume, double_sync, force_full_backup, skip_space_check, rman_rate_in__m_b, external_file_path, backup_level_enabled, files_per_set, check_logical, encrypted_linking_enabled, compressed_linking_enabled, bandwidth_limit, number_of_connections, diagnose_no_logging_faults, pre_provisioning_enabled, link_now, files_for_full_backup, log_sync_mode, log_sync_interval, non_sys_username, non_sys_password, non_sys_vault_username, non_sys_vault, non_sys_hashicorp_vault_engine, non_sys_hashicorp_vault_secret_path, non_sys_hashicorp_vault_username_key, non_sys_hashicorp_vault_secret_key, non_sys_azure_vault_name, non_sys_azure_vault_username_key, non_sys_azure_vault_secret_key, non_sys_cyberark_vault_query_string, fallback_username, fallback_password, fallback_vault_username, fallback_vault, fallback_hashicorp_vault_engine, fallback_hashicorp_vault_secret_path, fallback_hashicorp_vault_username_key, fallback_hashicorp_vault_secret_key, fallback_azure_vault_name, fallback_azure_vault_username_key, fallback_azure_vault_secret_key, fallback_cyberark_vault_query_string, ops_pre_log_sync
    
    Example:
        >>> data_tool(action='dsource_link_oracle', environment_user_id='example-environment_user-123', rman_channels=..., do_not_resume=..., double_sync=..., force_full_backup=..., skip_space_check=..., rman_rate_in__m_b=..., external_file_path=..., backup_level_enabled=..., files_per_set=..., check_logical=..., encrypted_linking_enabled=..., compressed_linking_enabled=..., bandwidth_limit=..., number_of_connections=..., diagnose_no_logging_faults=..., pre_provisioning_enabled=..., link_now=..., files_for_full_backup=..., log_sync_mode=..., log_sync_interval=..., non_sys_username=..., non_sys_password=..., non_sys_vault_username=..., non_sys_vault=..., non_sys_hashicorp_vault_engine=..., non_sys_hashicorp_vault_secret_path=..., non_sys_hashicorp_vault_username_key=..., non_sys_hashicorp_vault_secret_key=..., non_sys_azure_vault_name=..., non_sys_azure_vault_username_key=..., non_sys_azure_vault_secret_key=..., non_sys_cyberark_vault_query_string=..., fallback_username=..., fallback_password=..., fallback_vault_username=..., fallback_vault=..., fallback_hashicorp_vault_engine=..., fallback_hashicorp_vault_secret_path=..., fallback_hashicorp_vault_username_key=..., fallback_hashicorp_vault_secret_key=..., fallback_azure_vault_name=..., fallback_azure_vault_username_key=..., fallback_azure_vault_secret_key=..., fallback_cyberark_vault_query_string=..., ops_pre_log_sync=...)
    
    ACTION: dsource_link_oracle_defaults
    ----------------------------------------
    Summary: Get defaults for dSource linking.
    Method: POST
    Endpoint: /dsources/oracle/defaults
    Required Parameters: source_id
    
    Example:
        >>> data_tool(action='dsource_link_oracle_defaults', source_id='example-source-123')
    
    ACTION: dsource_link_oracle_staging_push
    ----------------------------------------
    Summary: Link an Oracle staging push database as dSource.
    Method: POST
    Endpoint: /dsources/oracle/staging-push
    Key Parameters (provide as applicable): environment_user_id, template_id, database_name, tde_keystore_config_type, engine_id, mount_base, ops_pre_log_sync, container_type, repository, database_unique_name, sid, custom_env_variables_pairs, custom_env_variables_paths, auto_staging_restart, allow_auto_staging_restart_on_host_reboot, physical_standby, validate_snapshot_in_readonly, validate_by_opening_db_in_read_only_mode, staging_database_templates, staging_database_config_params, staging_container_database_reference
    
    Example:
        >>> data_tool(action='dsource_link_oracle_staging_push', environment_user_id='example-environment_user-123', template_id='example-template-123', database_name=..., tde_keystore_config_type=..., engine_id='example-engine-123', mount_base=..., ops_pre_log_sync=..., container_type=..., repository=..., database_unique_name=..., sid=..., custom_env_variables_pairs=..., custom_env_variables_paths=..., auto_staging_restart=..., allow_auto_staging_restart_on_host_reboot=..., physical_standby=..., validate_snapshot_in_readonly=..., validate_by_opening_db_in_read_only_mode=..., staging_database_templates=..., staging_database_config_params=..., staging_container_database_reference=...)
    
    ACTION: dsource_link_oracle_staging_push_defaults
    ----------------------------------------
    Summary: Get defaults for a Oracle staging push dSource linking.
    Method: POST
    Endpoint: /dsources/oracle/staging-push/defaults
    Required Parameters: environment_id
    Key Parameters (provide as applicable): container_type
    
    Example:
        >>> data_tool(action='dsource_link_oracle_staging_push_defaults', environment_id='example-environment-123', container_type=...)
    
    ACTION: update_oracle_dsource
    ----------------------------------------
    Summary: Update values of an Oracle dSource
    Method: PATCH
    Endpoint: /dsources/oracle/{dsourceId}
    Required Parameters: dsource_id
    Key Parameters (provide as applicable): name, description, db_username, db_password, validate_db_credentials, environment_user_id, template_id, hooks, rman_channels, external_file_path, backup_level_enabled, files_per_set, check_logical, encrypted_linking_enabled, compressed_linking_enabled, bandwidth_limit, number_of_connections, diagnose_no_logging_faults, pre_provisioning_enabled, non_sys_username, non_sys_password, repository, custom_env_variables_pairs, custom_env_variables_paths, allow_auto_staging_restart_on_host_reboot, physical_standby, validate_by_opening_db_in_read_only_mode, staging_database_config_params, rac_max_instance_lag, logsync_enabled, logsync_mode, logsync_interval
    
    Example:
        >>> data_tool(action='update_oracle_dsource', name=..., description=..., db_username=..., db_password=..., validate_db_credentials=..., environment_user_id='example-environment_user-123', template_id='example-template-123', hooks=..., rman_channels=..., dsource_id='example-dsource-123', external_file_path=..., backup_level_enabled=..., files_per_set=..., check_logical=..., encrypted_linking_enabled=..., compressed_linking_enabled=..., bandwidth_limit=..., number_of_connections=..., diagnose_no_logging_faults=..., pre_provisioning_enabled=..., non_sys_username=..., non_sys_password=..., repository=..., custom_env_variables_pairs=..., custom_env_variables_paths=..., allow_auto_staging_restart_on_host_reboot=..., physical_standby=..., validate_by_opening_db_in_read_only_mode=..., staging_database_config_params=..., rac_max_instance_lag=..., logsync_enabled=..., logsync_mode=..., logsync_interval=...)
    
    ACTION: attach_oracle_dsource
    ----------------------------------------
    Summary: Attach an Oracle dSource to an Oracle database.
    Method: POST
    Endpoint: /dsources/oracle/{dsourceId}/attachSource
    Required Parameters: dsource_id, source_id
    
    Example:
        >>> data_tool(action='attach_oracle_dsource', dsource_id='example-dsource-123', source_id='example-source-123')
    
    ACTION: detach_oracle_dsource
    ----------------------------------------
    Summary: Detaches an Oracle source from an Oracle database.
    Method: POST
    Endpoint: /dsources/oracle/{dsourceId}/detachSource
    Required Parameters: dsource_id
    
    Example:
        >>> data_tool(action='detach_oracle_dsource', dsource_id='example-dsource-123')
    
    ACTION: upgrade_oracle_dsource
    ----------------------------------------
    Summary: Upgrade the requested Oracle dSource installation and user.
    Method: POST
    Endpoint: /dsources/oracle/{dsourceId}/upgrade
    Required Parameters: environment_user_id, repository_id, dsource_id
    
    Example:
        >>> data_tool(action='upgrade_oracle_dsource', environment_user_id='example-environment_user-123', repository_id='example-repository-123', dsource_id='example-dsource-123')
    
    ACTION: dsource_link_ase
    ----------------------------------------
    Summary: Link an ASE database as dSource.
    Method: POST
    Endpoint: /dsources/ase
    Key Parameters (provide as applicable): db_password, mount_base, drop_and_recreate_devices, sync_strategy, ase_backup_files, external_file_path, load_backup_path, backup_server_name, backup_host_user, backup_host, dump_credentials, source_host_user, db_user, db_vault_username, db_vault, db_hashicorp_vault_engine, db_hashicorp_vault_secret_path, db_hashicorp_vault_username_key, db_hashicorp_vault_secret_key, db_azure_vault_name, db_azure_vault_username_key, db_azure_vault_secret_key, db_cyberark_vault_query_string, staging_repository, staging_host_user, validated_sync_mode, dump_history_file_enabled, pre_validated_sync, post_validated_sync
    
    Example:
        >>> data_tool(action='dsource_link_ase', db_password=..., mount_base=..., drop_and_recreate_devices=..., sync_strategy=..., ase_backup_files=..., external_file_path=..., load_backup_path=..., backup_server_name=..., backup_host_user=..., backup_host=..., dump_credentials=..., source_host_user=..., db_user=..., db_vault_username=..., db_vault=..., db_hashicorp_vault_engine=..., db_hashicorp_vault_secret_path=..., db_hashicorp_vault_username_key=..., db_hashicorp_vault_secret_key=..., db_azure_vault_name=..., db_azure_vault_username_key=..., db_azure_vault_secret_key=..., db_cyberark_vault_query_string=..., staging_repository=..., staging_host_user=..., validated_sync_mode=..., dump_history_file_enabled=..., pre_validated_sync=..., post_validated_sync=...)
    
    ACTION: dsource_link_ase_defaults
    ----------------------------------------
    Summary: Get defaults for an ASE dSource linking.
    Method: POST
    Endpoint: /dsources/ase/defaults
    Required Parameters: source_id
    
    Example:
        >>> data_tool(action='dsource_link_ase_defaults', source_id='example-source-123')
    
    ACTION: update_ase_dsource
    ----------------------------------------
    Summary: Update values of an ASE dSource
    Method: PATCH
    Endpoint: /dsources/ase/{dsourceId}
    Required Parameters: dsource_id
    Key Parameters (provide as applicable): name, description, hooks, retention_policy_id, sync_policy_id
    
    Example:
        >>> data_tool(action='update_ase_dsource', name=..., description=..., hooks=..., retention_policy_id='example-retention_policy-123', dsource_id='example-dsource-123', sync_policy_id='example-sync_policy-123')
    
    ACTION: dsource_link_appdata
    ----------------------------------------
    Summary: Link an AppData database as dSource.
    Method: POST
    Endpoint: /dsources/appdata
    Key Parameters (provide as applicable): environment_user, link_type, staging_mount_base, staging_environment, staging_environment_user, excludes, follow_symlinks, parameters, sync_parameters
    
    Example:
        >>> data_tool(action='dsource_link_appdata', environment_user=..., link_type=..., staging_mount_base=..., staging_environment=..., staging_environment_user=..., excludes=..., follow_symlinks=..., parameters=..., sync_parameters=...)
    
        IMPORTANT — Toolkit schema for AppData payloads: The 'parameters', 'appdata_source_params', and 'appdata_config_params' fields follow a DraftV4 schema defined by the toolkit. Do NOT call toolkit_tool to fetch the schema — it is already pre-cached as an MCP resource. Use resources/read on toolkit://{toolkit_id}/schema to get the full schema definition. Identify the toolkit_id from the source or environment first, then read the resource.
    
    ACTION: dsource_link_appdata_defaults
    ----------------------------------------
    Summary: Get defaults for an AppData dSource linking.
    Method: POST
    Endpoint: /dsources/appdata/defaults
    Required Parameters: source_id
    
    Example:
        >>> data_tool(action='dsource_link_appdata_defaults', source_id='example-source-123')
    
        IMPORTANT — Toolkit schema for AppData payloads: The 'parameters', 'appdata_source_params', and 'appdata_config_params' fields follow a DraftV4 schema defined by the toolkit. Do NOT call toolkit_tool to fetch the schema — it is already pre-cached as an MCP resource. Use resources/read on toolkit://{toolkit_id}/schema to get the full schema definition. Identify the toolkit_id from the source or environment first, then read the resource.
    
    ACTION: update_appdata_dsource
    ----------------------------------------
    Summary: Update values of an AppData dSource
    Method: PATCH
    Endpoint: /dsources/appdata/{dsourceId}
    Required Parameters: dsource_id
    Key Parameters (provide as applicable): name, description, hooks, retention_policy_id, sync_policy_id, ops_pre_sync, ops_post_sync, environment_user, staging_environment, staging_environment_user, parameters
    
    Example:
        >>> data_tool(action='update_appdata_dsource', name=..., description=..., hooks=..., retention_policy_id='example-retention_policy-123', dsource_id='example-dsource-123', sync_policy_id='example-sync_policy-123', ops_pre_sync=..., ops_post_sync=..., environment_user=..., staging_environment=..., staging_environment_user=..., parameters=...)
    
        IMPORTANT — Toolkit schema for AppData payloads: The 'parameters', 'appdata_source_params', and 'appdata_config_params' fields follow a DraftV4 schema defined by the toolkit. Do NOT call toolkit_tool to fetch the schema — it is already pre-cached as an MCP resource. Use resources/read on toolkit://{toolkit_id}/schema to get the full schema definition. Identify the toolkit_id from the source or environment first, then read the resource.
    
    ACTION: dsource_link_mssql
    ----------------------------------------
    Summary: Link a MSSql database as dSource.
    Method: POST
    Endpoint: /dsources/mssql
    Key Parameters (provide as applicable): ppt_repository, sync_strategy, mssql_backup_uuid, compression_enabled, availability_group_backup_policy, source_host_user, encryption_key, ppt_host_user, staging_pre_script, staging_post_script, sync_strategy_managed_type, mssql_user_environment_reference, mssql_user_domain_username, mssql_user_domain_password, mssql_user_domain_vault_username, mssql_user_domain_vault, mssql_user_domain_hashicorp_vault_engine, mssql_user_domain_hashicorp_vault_secret_path, mssql_user_domain_hashicorp_vault_username_key, mssql_user_domain_hashicorp_vault_secret_key, mssql_user_domain_azure_vault_name, mssql_user_domain_azure_vault_username_key, mssql_user_domain_azure_vault_secret_key, mssql_user_domain_cyberark_vault_query_string, mssql_database_username, mssql_database_password, delphix_managed_backup_compression_enabled, delphix_managed_backup_policy, external_managed_validate_sync_mode, external_managed_shared_backup_locations, external_netbackup_config_master_name, external_netbackup_config_source_client_name, external_netbackup_config_params, external_netbackup_config_templates, external_commserve_host_name, external_commvault_config_source_client_name, external_commvault_config_staging_client_name, external_commvault_config_params, external_commvault_config_templates
    
    Example:
        >>> data_tool(action='dsource_link_mssql', ppt_repository=..., sync_strategy=..., mssql_backup_uuid=..., compression_enabled=..., availability_group_backup_policy=..., source_host_user=..., encryption_key=..., ppt_host_user=..., staging_pre_script=..., staging_post_script=..., sync_strategy_managed_type=..., mssql_user_environment_reference=..., mssql_user_domain_username=..., mssql_user_domain_password=..., mssql_user_domain_vault_username=..., mssql_user_domain_vault=..., mssql_user_domain_hashicorp_vault_engine=..., mssql_user_domain_hashicorp_vault_secret_path=..., mssql_user_domain_hashicorp_vault_username_key=..., mssql_user_domain_hashicorp_vault_secret_key=..., mssql_user_domain_azure_vault_name=..., mssql_user_domain_azure_vault_username_key=..., mssql_user_domain_azure_vault_secret_key=..., mssql_user_domain_cyberark_vault_query_string=..., mssql_database_username=..., mssql_database_password=..., delphix_managed_backup_compression_enabled=..., delphix_managed_backup_policy=..., external_managed_validate_sync_mode=..., external_managed_shared_backup_locations=..., external_netbackup_config_master_name=..., external_netbackup_config_source_client_name=..., external_netbackup_config_params=..., external_netbackup_config_templates=..., external_commserve_host_name=..., external_commvault_config_source_client_name=..., external_commvault_config_staging_client_name=..., external_commvault_config_params=..., external_commvault_config_templates=...)
    
    ACTION: dsource_link_mssql_defaults
    ----------------------------------------
    Summary: Get defaults for a MSSql dSource linking.
    Method: POST
    Endpoint: /dsources/mssql/defaults
    Required Parameters: source_id
    
    Example:
        >>> data_tool(action='dsource_link_mssql_defaults', source_id='example-source-123')
    
    ACTION: dsource_link_mssql_staging_push
    ----------------------------------------
    Summary: Link a MSSql staging push database as dSource.
    Method: POST
    Endpoint: /dsources/mssql/staging-push
    Key Parameters (provide as applicable): engine_id, ppt_repository, encryption_key, ppt_host_user, staging_pre_script, staging_post_script, staging_database_name, db_state
    
    Example:
        >>> data_tool(action='dsource_link_mssql_staging_push', engine_id='example-engine-123', ppt_repository=..., encryption_key=..., ppt_host_user=..., staging_pre_script=..., staging_post_script=..., staging_database_name=..., db_state=...)
    
    ACTION: dsource_link_mssql_staging_push_defaults
    ----------------------------------------
    Summary: Get defaults for a MSSql staging push dSource linking.
    Method: POST
    Endpoint: /dsources/mssql/staging-push/defaults
    Required Parameters: environment_id
    
    Example:
        >>> data_tool(action='dsource_link_mssql_staging_push_defaults', environment_id='example-environment-123')
    
    ACTION: attach_mssql_staging_push_dsource
    ----------------------------------------
    Summary: Attaches a MSSql staging push database to a previously detached dsource.
    Method: POST
    Endpoint: /dsources/mssql/staging-push/{dsourceId}/attachSource
    Required Parameters: ppt_repository, dsource_id, staging_database_name
    Key Parameters (provide as applicable): ops_pre_sync, ops_post_sync, encryption_key, ppt_host_user, staging_pre_script, staging_post_script, db_state
    
    Example:
        >>> data_tool(action='attach_mssql_staging_push_dsource', ppt_repository=..., dsource_id='example-dsource-123', ops_pre_sync=..., ops_post_sync=..., encryption_key=..., ppt_host_user=..., staging_pre_script=..., staging_post_script=..., staging_database_name=..., db_state=...)
    
    ACTION: update_mssql_dsource
    ----------------------------------------
    Summary: Update values of an MSSql dSource
    Method: PATCH
    Endpoint: /dsources/mssql/{dsourceId}
    Required Parameters: dsource_id
    Key Parameters (provide as applicable): name, hooks, retention_policy_id, ppt_repository, sync_policy_id, logsync_enabled, source_host_user, encryption_key, ppt_host_user, sync_strategy_managed_type, mssql_user_environment_reference, mssql_user_domain_username, mssql_user_domain_password, mssql_user_domain_vault_username, mssql_user_domain_vault, mssql_user_domain_hashicorp_vault_engine, mssql_user_domain_hashicorp_vault_secret_path, mssql_user_domain_hashicorp_vault_username_key, mssql_user_domain_hashicorp_vault_secret_key, mssql_user_domain_azure_vault_name, mssql_user_domain_azure_vault_username_key, mssql_user_domain_azure_vault_secret_key, mssql_user_domain_cyberark_vault_query_string, mssql_database_username, mssql_database_password, delphix_managed_backup_compression_enabled, delphix_managed_backup_policy, external_managed_validate_sync_mode, external_managed_shared_backup_locations, external_netbackup_config_master_name, external_netbackup_config_source_client_name, external_netbackup_config_params, external_netbackup_config_templates, external_commserve_host_name, external_commvault_config_source_client_name, external_commvault_config_staging_client_name, external_commvault_config_params, external_commvault_config_templates, disable_netbackup_config, disable_commvault_config
    
    Example:
        >>> data_tool(action='update_mssql_dsource', name=..., hooks=..., retention_policy_id='example-retention_policy-123', ppt_repository=..., dsource_id='example-dsource-123', sync_policy_id='example-sync_policy-123', logsync_enabled=..., source_host_user=..., encryption_key=..., ppt_host_user=..., sync_strategy_managed_type=..., mssql_user_environment_reference=..., mssql_user_domain_username=..., mssql_user_domain_password=..., mssql_user_domain_vault_username=..., mssql_user_domain_vault=..., mssql_user_domain_hashicorp_vault_engine=..., mssql_user_domain_hashicorp_vault_secret_path=..., mssql_user_domain_hashicorp_vault_username_key=..., mssql_user_domain_hashicorp_vault_secret_key=..., mssql_user_domain_azure_vault_name=..., mssql_user_domain_azure_vault_username_key=..., mssql_user_domain_azure_vault_secret_key=..., mssql_user_domain_cyberark_vault_query_string=..., mssql_database_username=..., mssql_database_password=..., delphix_managed_backup_compression_enabled=..., delphix_managed_backup_policy=..., external_managed_validate_sync_mode=..., external_managed_shared_backup_locations=..., external_netbackup_config_master_name=..., external_netbackup_config_source_client_name=..., external_netbackup_config_params=..., external_netbackup_config_templates=..., external_commserve_host_name=..., external_commvault_config_source_client_name=..., external_commvault_config_staging_client_name=..., external_commvault_config_params=..., external_commvault_config_templates=..., disable_netbackup_config=..., disable_commvault_config=...)
    
    ACTION: attach_mssql_dsource
    ----------------------------------------
    Summary: Attaches a MSSql source to a previously detached dsource.
    Method: POST
    Endpoint: /dsources/mssql/{dsourceId}/attachSource
    Required Parameters: ppt_repository, dsource_id, source_id
    Key Parameters (provide as applicable): ops_pre_sync, ops_post_sync, source_host_user, encryption_key, ppt_host_user, staging_pre_script, staging_post_script, sync_strategy_managed_type, mssql_user_environment_reference, mssql_user_domain_username, mssql_user_domain_password, mssql_user_domain_vault_username, mssql_user_domain_vault, mssql_user_domain_hashicorp_vault_engine, mssql_user_domain_hashicorp_vault_secret_path, mssql_user_domain_hashicorp_vault_username_key, mssql_user_domain_hashicorp_vault_secret_key, mssql_user_domain_azure_vault_name, mssql_user_domain_azure_vault_username_key, mssql_user_domain_azure_vault_secret_key, mssql_user_domain_cyberark_vault_query_string, mssql_database_username, mssql_database_password, delphix_managed_backup_compression_enabled, delphix_managed_backup_policy, external_managed_validate_sync_mode, external_managed_shared_backup_locations, external_netbackup_config_master_name, external_netbackup_config_source_client_name, external_netbackup_config_params, external_netbackup_config_templates, external_commserve_host_name, external_commvault_config_source_client_name, external_commvault_config_staging_client_name, external_commvault_config_params, external_commvault_config_templates
    
    Example:
        >>> data_tool(action='attach_mssql_dsource', ppt_repository=..., dsource_id='example-dsource-123', source_id='example-source-123', ops_pre_sync=..., ops_post_sync=..., source_host_user=..., encryption_key=..., ppt_host_user=..., staging_pre_script=..., staging_post_script=..., sync_strategy_managed_type=..., mssql_user_environment_reference=..., mssql_user_domain_username=..., mssql_user_domain_password=..., mssql_user_domain_vault_username=..., mssql_user_domain_vault=..., mssql_user_domain_hashicorp_vault_engine=..., mssql_user_domain_hashicorp_vault_secret_path=..., mssql_user_domain_hashicorp_vault_username_key=..., mssql_user_domain_hashicorp_vault_secret_key=..., mssql_user_domain_azure_vault_name=..., mssql_user_domain_azure_vault_username_key=..., mssql_user_domain_azure_vault_secret_key=..., mssql_user_domain_cyberark_vault_query_string=..., mssql_database_username=..., mssql_database_password=..., delphix_managed_backup_compression_enabled=..., delphix_managed_backup_policy=..., external_managed_validate_sync_mode=..., external_managed_shared_backup_locations=..., external_netbackup_config_master_name=..., external_netbackup_config_source_client_name=..., external_netbackup_config_params=..., external_netbackup_config_templates=..., external_commserve_host_name=..., external_commvault_config_source_client_name=..., external_commvault_config_staging_client_name=..., external_commvault_config_params=..., external_commvault_config_templates=...)
    
    ACTION: detach_mssql_dsource
    ----------------------------------------
    Summary: Detaches a linked source from a MSSql database.
    Method: POST
    Endpoint: /dsources/mssql/{dsourceId}/detachSource
    Required Parameters: dsource_id
    
    Example:
        >>> data_tool(action='detach_mssql_dsource', dsource_id='example-dsource-123')
    
    ACTION: export_dsource_by_snapshot
    ----------------------------------------
    Summary: Export a dSource using snapshot to a physical file system
    Method: POST
    Endpoint: /dsources/{dsourceId}/export-by-snapshot
    Required Parameters: dsource_id
    Key Parameters (provide as applicable): snapshot_id, rman_channels, rman_file_section_size_in_gb
    
    Example:
        >>> data_tool(action='export_dsource_by_snapshot', snapshot_id='example-snapshot-123', rman_channels=..., rman_file_section_size_in_gb=..., dsource_id='example-dsource-123')
    
    ACTION: export_dsource_by_timestamp
    ----------------------------------------
    Summary: Export a dSource using timestamp to a physical file system.
    Method: POST
    Endpoint: /dsources/{dsourceId}/export-by-timestamp
    Required Parameters: timestamp, timeflow_id, dsource_id
    Key Parameters (provide as applicable): rman_channels, rman_file_section_size_in_gb
    
    Example:
        >>> data_tool(action='export_dsource_by_timestamp', timestamp=..., timeflow_id='example-timeflow-123', rman_channels=..., rman_file_section_size_in_gb=..., dsource_id='example-dsource-123')
    
    ACTION: export_dsource_by_location
    ----------------------------------------
    Summary: Export a dSource using timeflow location to a physical file system.
    Method: POST
    Endpoint: /dsources/{dsourceId}/export-by-location
    Required Parameters: location, dsource_id
    Key Parameters (provide as applicable): rman_channels, rman_file_section_size_in_gb
    
    Example:
        >>> data_tool(action='export_dsource_by_location', location=..., rman_channels=..., rman_file_section_size_in_gb=..., dsource_id='example-dsource-123')
    
    ACTION: export_dsource_from_bookmark
    ----------------------------------------
    Summary: Export a dSource using bookmark to physical file system
    Method: POST
    Endpoint: /dsources/{dsourceId}/export-from-bookmark
    Required Parameters: bookmark_id, dsource_id
    Key Parameters (provide as applicable): rman_channels, rman_file_section_size_in_gb
    
    Example:
        >>> data_tool(action='export_dsource_from_bookmark', bookmark_id='example-bookmark-123', rman_channels=..., rman_file_section_size_in_gb=..., dsource_id='example-dsource-123')
    
    ACTION: export_dsource_to_asm_by_snapshot
    ----------------------------------------
    Summary: Export a dSource by a snapshot to an ASM file system
    Method: POST
    Endpoint: /dsources/{dsourceId}/asm-export-by-snapshot
    Required Parameters: default_data_diskgroup, dsource_id
    Key Parameters (provide as applicable): snapshot_id, rman_channels, rman_file_section_size_in_gb, redo_diskgroup
    
    Example:
        >>> data_tool(action='export_dsource_to_asm_by_snapshot', snapshot_id='example-snapshot-123', rman_channels=..., rman_file_section_size_in_gb=..., default_data_diskgroup=..., redo_diskgroup=..., dsource_id='example-dsource-123')
    
    ACTION: export_dsource_to_asm_by_timestamp
    ----------------------------------------
    Summary: Export a dSource using timestamp to an ASM file system
    Method: POST
    Endpoint: /dsources/{dsourceId}/asm-export-by-timestamp
    Required Parameters: timestamp, timeflow_id, default_data_diskgroup, dsource_id
    Key Parameters (provide as applicable): rman_channels, rman_file_section_size_in_gb, redo_diskgroup
    
    Example:
        >>> data_tool(action='export_dsource_to_asm_by_timestamp', timestamp=..., timeflow_id='example-timeflow-123', rman_channels=..., rman_file_section_size_in_gb=..., default_data_diskgroup=..., redo_diskgroup=..., dsource_id='example-dsource-123')
    
    ACTION: export_dsource_to_asm_by_location
    ----------------------------------------
    Summary: Export a dSource using SCN to an ASM file system
    Method: POST
    Endpoint: /dsources/{dsourceId}/asm-export-by-location
    Required Parameters: location, default_data_diskgroup, dsource_id
    Key Parameters (provide as applicable): rman_channels, rman_file_section_size_in_gb, redo_diskgroup
    
    Example:
        >>> data_tool(action='export_dsource_to_asm_by_location', location=..., rman_channels=..., rman_file_section_size_in_gb=..., default_data_diskgroup=..., redo_diskgroup=..., dsource_id='example-dsource-123')
    
    ACTION: export_dsource_to_asm_from_bookmark
    ----------------------------------------
    Summary: Export a dSource using bookmark to an ASM file system
    Method: POST
    Endpoint: /dsources/{dsourceId}/asm-export-from-bookmark
    Required Parameters: bookmark_id, default_data_diskgroup, dsource_id
    Key Parameters (provide as applicable): rman_channels, rman_file_section_size_in_gb, redo_diskgroup
    
    Example:
        >>> data_tool(action='export_dsource_to_asm_from_bookmark', bookmark_id='example-bookmark-123', rman_channels=..., rman_file_section_size_in_gb=..., default_data_diskgroup=..., redo_diskgroup=..., dsource_id='example-dsource-123')
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: list_vdbs, search_vdbs, get_vdb, update_vdb, provision_by_timestamp, provision_by_timestamp_defaults, provision_by_snapshot, provision_by_snapshot_defaults, provision_from_bookmark, provision_from_bookmark_defaults, provision_by_location, provision_by_location_defaults, provision_empty_vdb, delete_vdb, start_vdb, stop_vdb, enable_vdb, disable_vdb, refresh_vdb_by_timestamp, refresh_vdb_by_snapshot, refresh_vdb_from_bookmark, refresh_vdb_by_location, undo_vdb_refresh, rollback_vdb_by_timestamp, rollback_vdb_by_snapshot, rollback_vdb_from_bookmark, switch_vdb_timeflow, lock_vdb, unlock_vdb, migrate_vdb, get_migrate_compatible_repositories, upgrade_vdb, upgrade_oracle_vdb, get_upgrade_compatible_repositories, list_vdb_snapshots, snapshot_vdb, list_vdb_bookmarks, search_vdb_bookmarks, get_vdb_deletion_dependencies, verify_vdb_jdbc_connection, get_vdb_tags, add_vdb_tags, export_vdb_in_place, export_vdb_asm_in_place, export_vdb_by_snapshot, export_vdb_by_timestamp, export_vdb_by_location, export_vdb_from_bookmark, export_vdb_to_asm_by_snapshot, export_vdb_to_asm_by_timestamp, export_vdb_to_asm_by_location, export_vdb_to_asm_from_bookmark, export_cleanup, export_finalize, list_vdb_groups, search_vdb_groups, get_vdb_group, create_vdb_group, update_vdb_group, delete_vdb_group, provision_vdb_group_from_bookmark, refresh_vdb_group, refresh_vdb_group_from_bookmark, refresh_vdb_group_by_snapshot, refresh_vdb_group_by_timestamp, rollback_vdb_group, lock_vdb_group, unlock_vdb_group, start_vdb_group, stop_vdb_group, enable_vdb_group, disable_vdb_group, get_vdb_group_latest_snapshots, get_vdb_group_timestamp_summary, list_vdb_group_bookmarks, search_vdb_group_bookmarks, get_vdb_group_tags, add_vdb_group_tags, list_dsources, search_dsources, get_dsource, delete_dsource, enable_dsource, disable_dsource, list_dsource_snapshots, dsource_create_snapshot, upgrade_dsource, get_dsource_upgrade_compatible_repositories, get_dsource_deletion_dependencies, get_dsource_tags, add_dsource_tags, delete_dsource_tags, dsource_link_oracle, dsource_link_oracle_defaults, dsource_link_oracle_staging_push, dsource_link_oracle_staging_push_defaults, update_oracle_dsource, attach_oracle_dsource, detach_oracle_dsource, upgrade_oracle_dsource, dsource_link_ase, dsource_link_ase_defaults, update_ase_dsource, dsource_link_appdata, dsource_link_appdata_defaults, update_appdata_dsource, dsource_link_mssql, dsource_link_mssql_defaults, dsource_link_mssql_staging_push, dsource_link_mssql_staging_push_defaults, attach_mssql_staging_push_dsource, update_mssql_dsource, attach_mssql_dsource, detach_mssql_dsource, export_dsource_by_snapshot, export_dsource_by_timestamp, export_dsource_by_location, export_dsource_from_bookmark, export_dsource_to_asm_by_snapshot, export_dsource_to_asm_by_timestamp, export_dsource_to_asm_by_location, export_dsource_to_asm_from_bookmark
    
      -- General parameters (all database types) --
        abort (bool): Whether to issue 'shutdown abort' to shutdown Oracle Virtual DB instances. (D...
            [Optional for all actions]
        account_id (int): Id of the account on whose behalf this request is being made. Only accounts h...
            [Optional for all actions]
        additional_mount_points (list): Specifies additional locations on which to mount a subdirectory of an AppData...
            [Optional for all actions]
        allow_auto_staging_restart_on_host_reboot (bool): Boolean value indicates whether this staging database should automatically be...
            [Optional for all actions]
        appdata_config_params (dict): The parameters specified by the source config schema in the toolkit (Pass as ...
            [Optional for all actions]
        appdata_parameters (dict): The list of parameters specified by the snapshotParametersDefinition schema i...
            [Optional for all actions]
        appdata_source_params (dict): The JSON payload conforming to the DraftV4 schema based on the type of applic...
            [Optional for all actions]
        archive_directory (str): The directory for archive files.
            [Optional for all actions]
        ase_backup_files (list): When using the `specific_backup` sync_strategy, determines the backup files. ...
            [Optional for all actions]
        attempt_cleanup (bool): Whether to attempt a cleanup of the VDB before the disable. (Default: True)
            [Optional for all actions]
        attempt_start (bool): Whether to attempt a startup of the VDB after the enable. (Default: True)
            [Optional for all actions]
        auto_restart (bool): Whether to enable VDB restart.
            [Optional for all actions]
        auto_select_repository (bool): Option to automatically select a compatible environment and repository. Mutua...
            [Optional for all actions]
        auto_staging_restart (bool): Boolean value indicates whether this staging database should automatically be...
            [Optional for all actions]
        availability_group_backup_policy (str): When using the `new_backup` sync_strategy for an MSSql Availability Group, de...
            [Optional for all actions]
        backup_frequency_minutes (int): The frequency with which the incremental backup will be taken in minutes. (De...
            [Optional for all actions]
        backup_host (str): Host environment where the backup server is located.
            [Optional for all actions]
        backup_host_user (str): OS user for the host where the backup server is located.
            [Optional for all actions]
        backup_level_enabled (bool): Boolean value indicates whether LEVEL-based incremental backups can be used o...
            [Optional for all actions]
        backup_server_name (str): Name of the backup server instance.
            [Optional for all actions]
        bandwidth_limit (int): Bandwidth limit (MB/s) for SnapSync and LogSync network traffic. A value of 0...
            [Optional for all actions]
        bookmark_id (str): The ID of the bookmark from which to execute the operation. The bookmark must...
            [Required for: provision_from_bookmark, provision_from_bookmark_defaults, refresh_vdb_from_bookmark, rollback_vdb_from_bookmark, export_vdb_from_bookmark, export_vdb_to_asm_from_bookmark, provision_vdb_group_from_bookmark, refresh_vdb_group, refresh_vdb_group_from_bookmark, rollback_vdb_group, export_dsource_from_bookmark, export_dsource_to_asm_from_bookmark]
        cache_priority (str): When set to a value other than NORMAL (valid only for object storage engines)...
            [Optional for all actions]
        cdb_tde_keystore_password (str): The password for the Transparent Data Encryption keystore associated with the...
            [Optional for all actions]
        cdc_on_provision (bool): Whether to enable CDC on provision for MSSql
            [Optional for all actions]
        check_logical (bool): True if extended block checking should be used for this linked database. (Def...
            [Optional for all actions]
        cleanup_target_container (bool): Flag indicating whether to delete the temporary virtual source created for ex...
            [Optional for all actions]
        cleanup_target_physical_files (bool): Flag indicating whether to delete the database files already copied to target...
            [Optional for all actions]
        compressed_linking_enabled (bool): True if SnapSync data from the source should be compressed over the network. ...
            [Optional for all actions]
        compression_enabled (bool): When using the `new_backup` sync_strategy, determines if compression must be ...
            [Optional for all actions]
        config_params (dict): Database configuration parameter overrides. (Pass as JSON object)
            [Optional for all actions]
        configure_clone (list): The commands to execute on the target environment when the VDB is created or ...
            [Optional for all actions]
        container_type (str): The container type of this database.If not provided the request would be cons...
            [Optional for all actions]
        crs_database_name (str): The Oracle Clusterware database name.
            [Optional for all actions]
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: list_vdbs, search_vdbs, list_vdb_snapshots, list_vdb_bookmarks, search_vdb_bookmarks, list_vdb_groups, search_vdb_groups, list_vdb_group_bookmarks, search_vdb_group_bookmarks, list_dsources, search_dsources, list_dsource_snapshots]
        custom_env_files (list): Environment files to be sourced when the Engine administers a VDB. This path ...
            [Optional for all actions]
        custom_env_variables_pairs (list): An array of name value pair of environment variables. (Pass as JSON array)
            [Optional for all actions]
        custom_env_variables_paths (list): An array of strings of whitespace-separated parameters to be passed to the so...
            [Optional for all actions]
        custom_env_vars (dict): Environment variable to be set when the engine administers a VDB. See the Eng...
            [Optional for all actions]
        data_directory (str): The directory for data files.
            [Optional for all actions]
        database_name (str): The name of the database in the target environment (update not applicable for...
            [Optional for all actions]
        database_password (str): oracle database password.
            [Required for: verify_vdb_jdbc_connection]
        database_unique_name (str): The unique name of the database.
            [Optional for all actions]
        database_username (str): oracle database username.
            [Required for: verify_vdb_jdbc_connection]
        dataset_id (str): ID of the dataset to refresh to, mutually exclusive with timeflow_id.
            [Optional for all actions]
        db_azure_vault_name (str): Azure key vault name.
            [Optional for all actions]
        db_azure_vault_secret_key (str): Azure vault key for the password in the key-value store.
            [Optional for all actions]
        db_azure_vault_username_key (str): Azure vault key for the username in the key-value store.
            [Optional for all actions]
        db_cyberark_vault_query_string (str): Query to find a credential in the CyberArk vault.
            [Optional for all actions]
        db_hashicorp_vault_engine (str): Vault engine name where the credential is stored.
            [Optional for all actions]
        db_hashicorp_vault_secret_key (str): Hashicorp vault key for the password in the key-value store.
            [Optional for all actions]
        db_hashicorp_vault_secret_path (str): Path in the vault engine where the credential is stored.
            [Optional for all actions]
        db_hashicorp_vault_username_key (str): Hashicorp vault key for the username in the key-value store.
            [Optional for all actions]
        db_password (str): The password of the database user (Oracle, ASE Only).
            [Optional for all actions]
        db_state (str): User provided db state that will be used to create staging push db. Default i...
            [Optional for all actions]
        db_unique_name (str): Unique name to be given to the database after it is converted to physical.
            [Optional for all actions]
        db_user (str): The user name for the source DB user.
            [Optional for all actions]
        db_username (str): The username of the database user (Oracle, ASE Only).
            [Optional for all actions]
        db_vault (str): The name or reference of the vault from which to read the database credentials.
            [Optional for all actions]
        db_vault_username (str): Delphix display name for the vault user.
            [Optional for all actions]
        default_data_diskgroup (str): Default diskgroup for datafiles.
            [Required for: export_vdb_asm_in_place, export_vdb_to_asm_by_snapshot, export_vdb_to_asm_by_timestamp, export_vdb_to_asm_by_location, export_vdb_to_asm_from_bookmark, export_dsource_to_asm_by_snapshot, export_dsource_to_asm_by_timestamp, export_dsource_to_asm_by_location, export_dsource_to_asm_from_bookmark]
        delete_all_dependent_vdbs (bool): Flag indicating whether to delete all dependent VDBs before deleting the VDB....
            [Optional for all actions]
        delphix_managed_backup_compression_enabled (bool): Specify whether the backups taken should be compressed or uncompressed when D...
            [Optional for all actions]
        delphix_managed_backup_policy (str): Specify which node of an availability group to run the copy-only full backup ...
            [Optional for all actions]
        description (str): The container description of this VDB.
            [Optional for all actions]
        diagnose_no_logging_faults (bool): If true, NOLOGGING operations on this container are treated as faults and can...
            [Optional for all actions]
        disable_commvault_config (bool): Disable Commvault configuration.
            [Optional for all actions]
        disable_netbackup_config (bool): Disable NetBackup configuration.
            [Optional for all actions]
        do_not_resume (bool): Indicates whether a fresh SnapSync must be started regardless if it was possi...
            [Optional for all actions]
        double_sync (bool): True if two SnapSyncs should be performed in immediate succession to reduce t...
            [Optional for all actions]
        drop_and_recreate_devices (bool): If this parameter is set to true, it will drop the older devices and create n...
            [Optional for all actions]
        dsource_id (str): The unique identifier for the dsource.
            [Required for: get_dsource, delete_dsource, enable_dsource, disable_dsource, list_dsource_snapshots, dsource_create_snapshot, upgrade_dsource, get_dsource_upgrade_compatible_repositories, get_dsource_deletion_dependencies, get_dsource_tags, add_dsource_tags, delete_dsource_tags, update_oracle_dsource, attach_oracle_dsource, detach_oracle_dsource, upgrade_oracle_dsource, update_ase_dsource, update_appdata_dsource, attach_mssql_staging_push_dsource, update_mssql_dsource, attach_mssql_dsource, detach_mssql_dsource, export_dsource_by_snapshot, export_dsource_by_timestamp, export_dsource_by_location, export_dsource_from_bookmark, export_dsource_to_asm_by_snapshot, export_dsource_to_asm_by_timestamp, export_dsource_to_asm_by_location, export_dsource_to_asm_from_bookmark]
        dump_credentials (str): The password credential for the source DB user.
            [Optional for all actions]
        dump_history_file_enabled (bool): Specifies if Dump History File is enabled for backup history detection. (Defa...
            [Optional for all actions]
        enable_cdc (bool): Indicates whether to enable Change Data Capture (CDC) or not on exported data...
            [Optional for all actions]
        encrypted_linking_enabled (bool): True if SnapSync data from the source should be retrieved through an encrypte...
            [Optional for all actions]
        encryption_key (str): The encryption key to use when restoring encrypted backups.
            [Optional for all actions]
        engine_id (str): The ID of the Engine onto which to provision. If the source ID unambiguously ...
            [Optional for all actions]
        environment_id (str): The ID of the target environment where to provision the VDB. If repository_id...
            [Required for: dsource_link_oracle_staging_push_defaults, dsource_link_mssql_staging_push_defaults]
        environment_user (str): Reference to the user that should be used in the host.
            [Optional for all actions]
        environment_user_id (str): The environment user ID to use to connect to the target environment.
            [Required for: upgrade_oracle_vdb, upgrade_oracle_dsource]
        environment_user_ref (str): Reference of the environment user.
            [Optional for all actions]
        excludes (list): List of subdirectories in the source to exclude when syncing data. These path...
            [Optional for all actions]
        external_commserve_host_name (str): The commserve host name of this Commvault configuration.
            [Optional for all actions]
        external_commvault_config_params (dict): Commvault configuration parameter overrides. (Pass as JSON object)
            [Optional for all actions]
        external_commvault_config_source_client_name (str): The source client name of this Commvault configuration.
            [Optional for all actions]
        external_commvault_config_staging_client_name (str): The staging client name of this Commvault configuration.
            [Optional for all actions]
        external_commvault_config_templates (str): Optional config template selection for Commvault configurations. If set, conf...
            [Optional for all actions]
        external_directory (str): The directory for external files.
            [Optional for all actions]
        external_file_path (str): External file path.
            [Optional for all actions]
        external_managed_shared_backup_locations (list): Shared source database backup locations. (Pass as JSON array)
            [Optional for all actions]
        external_managed_validate_sync_mode (str): Specifies the backup types ValidatedSync will use to synchronize the dSource ...
            [Optional for all actions]
        external_netbackup_config_master_name (str): The master server name of this NetBackup configuration.
            [Optional for all actions]
        external_netbackup_config_params (dict): NetBackup configuration parameter overrides. (Pass as JSON object)
            [Optional for all actions]
        external_netbackup_config_source_client_name (str): The source's client server name of this NetBackup configuration.
            [Optional for all actions]
        external_netbackup_config_templates (str): Optional config template selection for NetBackup configurations. If set, exte...
            [Optional for all actions]
        fallback_azure_vault_name (str): Azure key vault name.
            [Optional for all actions]
        fallback_azure_vault_secret_key (str): Azure vault key for the password in the key-value store.
            [Optional for all actions]
        fallback_azure_vault_username_key (str): Azure vault key for the username in the key-value store.
            [Optional for all actions]
        fallback_cyberark_vault_query_string (str): Query to find a credential in the CyberArk vault.
            [Optional for all actions]
        fallback_hashicorp_vault_engine (str): Vault engine name where the credential is stored.
            [Optional for all actions]
        fallback_hashicorp_vault_secret_key (str): Hashicorp vault key for the password in the key-value store.
            [Optional for all actions]
        fallback_hashicorp_vault_secret_path (str): Path in the vault engine where the credential is stored.
            [Optional for all actions]
        fallback_hashicorp_vault_username_key (str): Hashicorp vault key for the username in the key-value store.
            [Optional for all actions]
        fallback_password (str): Password for fallback username.
            [Optional for all actions]
        fallback_username (str): The database fallback username. Optional if bequeath connections are enabled ...
            [Optional for all actions]
        fallback_vault (str): The name or reference of the vault from which to read the database credentials.
            [Optional for all actions]
        fallback_vault_username (str): Delphix display name for the fallback vault user.
            [Optional for all actions]
        files_for_full_backup (list): List of datafiles to take a full backup of. This would be useful in situation...
            [Optional for all actions]
        files_for_partial_full_backup (list): List of datafiles to take a full backup of. This would be useful in situation...
            [Optional for all actions]
        files_per_set (int): Number of data files to include in each RMAN backup set. (Default: 5)
            [Optional for all actions]
        filter_expression (str): Request body parameter
            [Optional for all actions]
        follow_symlinks (list): List of symlinks in the source to follow when syncing data. These paths are r...
            [Optional for all actions]
        force (bool): Whether to continue the operation upon failures. (Default: False)
            [Optional for all actions]
        force_full_backup (bool): Whether or not to take another full backup of the source database. (Default: ...
            [Optional for all actions]
        group_id (str): Id of the dataset group where this dSource should belong to.
            [Optional for all actions]
        hooks (dict): VDB operation hooks. (Pass as JSON object)
            [Optional for all actions]
        instance_number (int): The number of the instance.
            [Optional for all actions]
        instances (list): The instances of this RAC database. (Pass as JSON array)
            [Optional for all actions]
        invoke_datapatch (bool): Indicates whether datapatch should be invoked.
            [Optional for all actions]
        is_incremental_v2p (bool): Whether to enable incremental V2P (Virtual to Physical) export. When enabled,...
            [Optional for all actions]
        is_refresh_to_nearest (bool): If true, and the provided timestamp is not found for the VDB mapping, the sys...
            [Optional for all actions]
        jdbc_connection_string (str): Oracle jdbc connection string to validate.
            [Required for: verify_vdb_jdbc_connection]
        key (str): Key of the tag
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: list_vdbs, search_vdbs, list_vdb_snapshots, list_vdb_bookmarks, search_vdb_bookmarks, list_vdb_groups, search_vdb_groups, list_vdb_group_bookmarks, search_vdb_group_bookmarks, list_dsources, search_dsources, list_dsource_snapshots]
        link_now (bool): True if initial load should be done immediately. (Default: False)
            [Optional for all actions]
        link_type (str): The type of link to create. Default is AppDataDirect.
* `AppDataDirect` - Rep...
            [Optional for all actions]
        listener_ids (list): The listener IDs for this provision operation (Oracle Only). (Pass as JSON ar...
            [Optional for all actions]
        load_backup_path (str): Source database backup location.
            [Optional for all actions]
        location (str): The location to provision from.
            [Required for: export_vdb_by_location, export_vdb_to_asm_by_location, export_dsource_by_location, export_dsource_to_asm_by_location]
        log_sync_enabled (bool): True if LogSync should run for this database. (Default: False)
            [Optional for all actions]
        log_sync_interval (int): Interval between LogSync requests, in seconds. (Default: 5)
            [Optional for all actions]
        log_sync_mode (str): LogSync operation mode for this database. Valid values: ARCHIVE_ONLY_MODE, AR...
            [Optional for all actions]
        logsync_enabled (bool): True if LogSync is enabled for this dSource.
            [Optional for all actions]
        logsync_interval (int): Interval between LogSync requests, in seconds.
            [Optional for all actions]
        logsync_mode (str): LogSync operation mode for this dSource. Valid values: ARCHIVE_ONLY_MODE, ARC...
            [Optional for all actions]
        make_current_account_owner (bool): Whether the account provisioning this VDB must be configured as owner of the ...
            [Optional for all actions]
        masked (bool): Indicates whether to mark this VDB as a masked VDB.
            [Optional for all actions]
        max_allowed_backups_pending_restore (int): The maximum number of pending backup restores at which export-finalize operat...
            [Optional for all actions]
        mirroring_state (str): Recovery model of the database (MSSql Only). Valid values: SUSPENDED, DISCONN...
            [Optional for all actions]
        mode (str): Refresh Mode either self or parent, if PARENT then VDB Group is refreshed fro...
            [Optional for all actions]
        mount_base (str): The base mount point to use for the NFS mounts for the temporary VDB.
            [Optional for all actions]
        mount_point (str): Mount point for the VDB (AppData only), can only be updated while the VDB is ...
            [Optional for all actions]
        mssql_ag_backup_based (bool): Indicates whether to do fast operations for VDB on AG which will use a health...
            [Optional for all actions]
        mssql_ag_backup_location (str): Shared backup location to be used for VDB provision on AG Cluster.
            [Optional for all actions]
        mssql_backup_uuid (str): When using the `specific_backup` sync_strategy, determines the Backup Set UUI...
            [Optional for all actions]
        mssql_database_password (str): Password for the database user.
            [Optional for all actions]
        mssql_database_username (str): The username for the source DB user.
            [Optional for all actions]
        mssql_incremental_export_backup_frequency_minutes (int): Frequency in minutes for incremental export backups for VDBs.
            [Optional for all actions]
        mssql_user_domain_azure_vault_name (str): Azure key vault name.
            [Optional for all actions]
        mssql_user_domain_azure_vault_secret_key (str): Azure vault key for the password in the key-value store.
            [Optional for all actions]
        mssql_user_domain_azure_vault_username_key (str): Azure vault key for the username in the key-value store.
            [Optional for all actions]
        mssql_user_domain_cyberark_vault_query_string (str): Query to find a credential in the CyberArk vault.
            [Optional for all actions]
        mssql_user_domain_hashicorp_vault_engine (str): Vault engine name where the credential is stored.
            [Optional for all actions]
        mssql_user_domain_hashicorp_vault_secret_key (str): Hashicorp vault key for the password in the key-value store.
            [Optional for all actions]
        mssql_user_domain_hashicorp_vault_secret_path (str): Path in the vault engine where the credential is stored.
            [Optional for all actions]
        mssql_user_domain_hashicorp_vault_username_key (str): Hashicorp vault key for the username in the key-value store.
            [Optional for all actions]
        mssql_user_domain_password (str): Password for the database user.
            [Optional for all actions]
        mssql_user_domain_username (str): The username for the source DB user.
            [Optional for all actions]
        mssql_user_domain_vault (str): The name or reference of the vault from which to read the database credentials.
            [Optional for all actions]
        mssql_user_domain_vault_username (str): Delphix display name for the vault user.
            [Optional for all actions]
        mssql_user_environment_reference (str): Reference to the source environment user to use for linking.
            [Optional for all actions]
        name (str): The unique name of the VDB within a group.
            [Required for: create_vdb_group, provision_vdb_group_from_bookmark]
        new_dbid (bool): Whether to enable new DBID for Oracle
            [Optional for all actions]
        non_sys_azure_vault_name (str): Azure key vault name (Single tenant only).
            [Optional for all actions]
        non_sys_azure_vault_secret_key (str): Azure vault key for the password in the key-value store (Single tenant only).
            [Optional for all actions]
        non_sys_azure_vault_username_key (str): Azure vault key for the username in the key-value store (Single tenant only).
            [Optional for all actions]
        non_sys_cyberark_vault_query_string (str): Query to find a credential in the CyberArk vault (Single tenant only).
            [Optional for all actions]
        non_sys_hashicorp_vault_engine (str): Vault engine name where the credential is stored (Single tenant only).
            [Optional for all actions]
        non_sys_hashicorp_vault_secret_key (str): Hashicorp vault key for the password in the key-value store (Single tenant on...
            [Optional for all actions]
        non_sys_hashicorp_vault_secret_path (str): Path in the vault engine where the credential is stored (Single tenant only).
            [Optional for all actions]
        non_sys_hashicorp_vault_username_key (str): Hashicorp vault key for the username in the key-value store (Single tenant on...
            [Optional for all actions]
        non_sys_password (str): Password for non sys user authentication (Single tenant only).
            [Optional for all actions]
        non_sys_username (str): Non-SYS database user to access this database. Only required for username-pas...
            [Optional for all actions]
        non_sys_vault (str): The name or reference of the vault from which to read the database credential...
            [Optional for all actions]
        non_sys_vault_username (str): Delphix display name for the non sys vault user(Single tenant only).
            [Optional for all actions]
        number_of_connections (int): Total number of transport connections to use during SnapSync. (Default: 1)
            [Optional for all actions]
        operations (list): Operations to perform after syncing a created dSource and before running the ...
            [Optional for all actions]
        operations_post_v2_p (bool): Indicates operations allowed on virtual source post V2P. (Default: False)
            [Optional for all actions]
        ops_post_sync (list): Operations to perform after syncing a created dSource. (Pass as JSON array)
            [Optional for all actions]
        ops_pre_log_sync (list): Operations to perform after syncing a created dSource and before running the ...
            [Optional for all actions]
        ops_pre_sync (list): Operations to perform before syncing the created dSource. These operations ca...
            [Optional for all actions]
        oracle_fallback_credentials (str): Password for fallback username.
            [Optional for all actions]
        oracle_fallback_user (str): The database fallback username. Optional if bequeath connections are enabled ...
            [Optional for all actions]
        oracle_password (str): Password for privileged user (Oracle only).
            [Optional for all actions]
        oracle_rac_custom_env_files (list): Environment files to be sourced when the Engine administers an Oracle RAC VDB...
            [Optional for all actions]
        oracle_rac_custom_env_vars (list): Environment variable to be set when the engine administers an Oracle RAC VDB....
            [Optional for all actions]
        oracle_services (list): List of jdbc connection strings which are used to connect with the database. ...
            [Optional for all actions]
        oracle_username (str): The name of the privileged user to run the delete operation as (Oracle only).
            [Optional for all actions]
        ownership_spec (str): The uid:gid string that NFS mounts should belong to.
            [Optional for all actions]
        parameters (dict): The JSON payload conforming to the DraftV4 schema based on the type of applic...
            [Optional for all actions]
        parent_pdb_tde_keystore_password (str): The password of the parent PDB keystore. (Oracle Multitenant Only)
            [Optional for all actions]
        parent_pdb_tde_keystore_path (str): Path to a copy of the parent PDB's Oracle transparent data encryption keystor...
            [Optional for all actions]
        parent_tde_keystore_password (str): The password of the keystore specified in parentTdeKeystorePath. (Oracle Mult...
            [Optional for all actions]
        parent_tde_keystore_path (str): Path to a copy of the parent's Oracle transparent data encryption keystore on...
            [Optional for all actions]
        pdb_name (str): The name to be given to the PDB after it is exported in-place.
            [Optional for all actions]
        permission (str): Restrict the objects, which are allowed.
            [Required for: list_vdbs, search_vdbs, list_dsources, search_dsources]
        physical_standby (bool): Boolean value indicates whether this staging database will be configured as a...
            [Optional for all actions]
        post_refresh (list): The commands to execute on the target environment after refreshing the VDB. (...
            [Optional for all actions]
        post_rollback (list): The commands to execute on the target environment after rewinding the VDB. (P...
            [Optional for all actions]
        post_script (str): Post script for MSSql.
            [Optional for all actions]
        post_self_refresh (list): The commands to execute on the target environment after refreshing the VDB wi...
            [Optional for all actions]
        post_snapshot (list): The commands to execute on the target environment after snapshotting a virtua...
            [Optional for all actions]
        post_start (list): The commands to execute on the target environment after starting a virtual so...
            [Optional for all actions]
        post_stop (list): The commands to execute on the target environment after stopping a virtual so...
            [Optional for all actions]
        post_validated_sync (list): Operations to perform on the staging source after performing a validated sync...
            [Optional for all actions]
        ppt_host_user (str): Reference of the host OS user on the PPT host to use for linking.
            [Optional for all actions]
        ppt_repository (str): The id of the SQL instance on the PPT environment that we want to use for pre...
            [Required for: attach_mssql_staging_push_dsource, attach_mssql_dsource]
        pre_provisioning_enabled (bool): If true, pre-provisioning will be performed after every sync. (Default: False)
            [Optional for all actions]
        pre_refresh (list): The commands to execute on the target environment before refreshing the VDB. ...
            [Optional for all actions]
        pre_rollback (list): The commands to execute on the target environment before rewinding the VDB. (...
            [Optional for all actions]
        pre_script (str): Pre script for MSSql.
            [Optional for all actions]
        pre_self_refresh (list): The commands to execute on the target environment before refreshing the VDB w...
            [Optional for all actions]
        pre_snapshot (list): The commands to execute on the target environment before snapshotting a virtu...
            [Optional for all actions]
        pre_start (list): The commands to execute on the target environment before starting a virtual s...
            [Optional for all actions]
        pre_stop (list): The commands to execute on the target environment before stopping a virtual s...
            [Optional for all actions]
        pre_validated_sync (list): Operations to perform on the staging source before performing a validated syn...
            [Optional for all actions]
        provision_parameters (dict): Provision parameters for each of the VDBs which will need to be provisioned. ...
            [Required for: provision_vdb_group_from_bookmark]
        rac_max_instance_lag (int): Maximum number of log sequences to allow a RAC instance to lag before conside...
            [Optional for all actions]
        recover_database (bool): If specified, then take the exported database through recovery procedures, if...
            [Optional for all actions]
        redo_diskgroup (str): Diskgroup for archive logs. Optional as it is not required for PDB databases.
            [Optional for all actions]
        refresh_immediately (bool): If true, VDB Group will be refreshed immediately after creation. (Default: Fa...
            [Optional for all actions]
        repository (str): The repository reference to link.
            [Optional for all actions]
        repository_id (str): The ID of the target repository where to provision the VDB. A repository typi...
            [Required for: upgrade_vdb, upgrade_oracle_vdb, upgrade_dsource, upgrade_oracle_dsource]
        retention_policy_id (str): The ID of the retention policy for the VDB.
            [Optional for all actions]
        rman_channels (int): Number of data streams to connect to the database. (Default: 8)
            [Optional for all actions]
        rman_channels_for_incremental_backup (int): Number of data streams to connect to the database for incremental backup. (De...
            [Optional for all actions]
        rman_file_section_size_in_gb (int): Number of GigaBytes in which RMAN will break large files to back them in para...
            [Optional for all actions]
        rman_file_section_size_in_gb_for_incremental_backup (int): Number of GigaBytes in which RMAN will break large files to back them up in p...
            [Optional for all actions]
        rman_files_per_set_for_incremental_backup (int): Number of data files to include in each RMAN backup set for incremental backu...
            [Optional for all actions]
        rman_rate_in__m_b (int): RMAN rate in megabytes to be used. This is the upper limit for bytes read so ...
            [Optional for all actions]
        script_directory (str): The directory for script files.
            [Optional for all actions]
        sid (str): The name (sid) of the instance.
            [Optional for all actions]
        skip_space_check (bool): Skip check that tests if there is enough space available to store the databas...
            [Optional for all actions]
        snapshot_id (str): The ID of the snapshot from which to execute the operation. If the snapshot_i...
            [Optional for all actions]
        snapshot_policy_id (str): The ID of the snapshot policy for the VDB.
            [Optional for all actions]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: list_vdbs, search_vdbs, list_vdb_bookmarks, search_vdb_bookmarks, list_vdb_groups, search_vdb_groups, list_vdb_group_bookmarks, search_vdb_group_bookmarks, list_dsources, search_dsources]
        source_data_id (str): The ID of the source object (dSource or VDB) to provision from. All other obj...
            [Required for: provision_by_timestamp, provision_by_timestamp_defaults]
        source_host_user (str): ID or user reference of the host OS user to use for linking.
            [Optional for all actions]
        source_id (str): Id of the source to link.
            [Required for: dsource_link_oracle_defaults, attach_oracle_dsource, dsource_link_ase_defaults, dsource_link_appdata_defaults, dsource_link_mssql_defaults, attach_mssql_dsource]
        staging_container_database_reference (str): Reference of the CDB source config.
            [Optional for all actions]
        staging_database_config_params (dict): Oracle database configuration parameter overrides. If both staging_database_t...
            [Optional for all actions]
        staging_database_name (str): The name of the database to create on the staging environment. This property ...
            [Required for: attach_mssql_staging_push_dsource]
        staging_database_templates (list): An array of name value pair of Oracle database configuration parameter overri...
            [Optional for all actions]
        staging_environment (str): The environment used as an intermediate stage to pull data into Delphix [AppD...
            [Optional for all actions]
        staging_environment_user (str): The environment user used to access the staging environment [AppDataStaged on...
            [Optional for all actions]
        staging_host_user (str): Information about the host OS user on the staging environment to use for link...
            [Optional for all actions]
        staging_mount_base (str): The base mount point for the NFS mount on the staging environment [AppDataSta...
            [Optional for all actions]
        staging_post_script (str): A user-provided PowerShell script or executable to run after restoring from a...
            [Optional for all actions]
        staging_pre_script (str): A user-provided PowerShell script or executable to run prior to restoring fro...
            [Optional for all actions]
        staging_repository (str): The SAP ASE instance on the staging environment that we want to use for valid...
            [Optional for all actions]
        sync_parameters (dict): The JSON payload conforming to the snapshot parameters definition in a LUA to...
            [Optional for all actions]
        sync_policy_id (str): The ID of the SnapSync policy for the dSource.
            [Optional for all actions]
        sync_strategy (str): Determines how the Delphix Engine will take a backup:
* `latest_backup` - Use...
            [Optional for all actions]
        sync_strategy_managed_type (str): MSSQL specific parameters for source based sync strategy.:
* `external` - MSS...
            [Optional for all actions]
        tags (list): The tags to be created for VDB. (Pass as JSON array)
            [Required for: add_vdb_tags, add_vdb_group_tags, add_dsource_tags]
        target_directory (str): The base directory to use for the exported database.
            [Optional for all actions]
        target_group_id (str): The ID of the group into which the VDB will be provisioned. This field must b...
            [Optional for all actions]
        target_pdb_tde_keystore_password (str): The password for the isolated mode TDE keystore of the target virtual PDB. (O...
            [Optional for all actions]
        target_vcdb_tde_keystore_path (str): Path to the keystore of the target vCDB. (Oracle Multitenant Only)
            [Optional for all actions]
        tde_exported_keyfile_secret (str): Secret to be used while exporting and importing vPDB encryption keys.
            [Optional for all actions]
        tde_key_identifier (str): ID of the key created by Delphix. (Oracle Multitenant Only)
            [Optional for all actions]
        tde_keystore_config_type (str): Oracle TDE keystore configuration type. Valid values: FILE, OKV, HSM, OKV|FIL...
            [Optional for all actions]
        tde_keystore_password (str): The password for the Transparent Data Encryption keystore associated with thi...
            [Optional for all actions]
        temp_directory (str): The directory for temporary files.
            [Optional for all actions]
        template_id (str): The ID of the target VDB Template (Oracle and MSSql Only).
            [Optional for all actions]
        timeflow_id (str): The Timeflow ID.
            [Required for: export_vdb_by_timestamp, export_vdb_to_asm_by_timestamp, export_dsource_by_timestamp, export_dsource_to_asm_by_timestamp]
        timestamp (str): The point in time from which to execute the operation. Mutually exclusive wit...
            [Required for: export_vdb_by_timestamp, export_vdb_to_asm_by_timestamp, export_dsource_by_timestamp, export_dsource_to_asm_by_timestamp]
        timestamp_in_database_timezone (str): The point in time from which to execute the operation, expressed as a date-ti...
            [Optional for all actions]
        use_absolute_path_for_data_files (bool): Whether to use absolute path for data files (Oracle only).
            [Optional for all actions]
        validate_by_opening_db_in_read_only_mode (bool): Boolean value indicates whether this staging database snapshot will be valida...
            [Optional for all actions]
        validate_db_credentials (bool): Whether db_username and db_password must be validated, if present, against th...
            [Optional for all actions]
        validate_snapshot_in_readonly (bool): Boolean value indicates whether this staging database snapshot will be valida...
            [Optional for all actions]
        validated_sync_mode (str): Information about the host OS user on the staging environment to use for link...
            [Optional for all actions]
        value (str): Value of the tag
            [Optional for all actions]
        vdb_disable_param_mappings (list): Request body parameter (Pass as JSON array)
            [Optional for all actions]
        vdb_enable_param_mappings (list): Request body parameter (Pass as JSON array)
            [Optional for all actions]
        vdb_group_id (str): The unique identifier for the vdbGroup.
            [Required for: get_vdb_group, update_vdb_group, delete_vdb_group, refresh_vdb_group, refresh_vdb_group_from_bookmark, refresh_vdb_group_by_snapshot, refresh_vdb_group_by_timestamp, rollback_vdb_group, lock_vdb_group, unlock_vdb_group, start_vdb_group, stop_vdb_group, enable_vdb_group, disable_vdb_group, get_vdb_group_latest_snapshots, get_vdb_group_timestamp_summary, list_vdb_group_bookmarks, search_vdb_group_bookmarks, get_vdb_group_tags, add_vdb_group_tags]
        vdb_id (str): The unique identifier for the vdb.
            [Required for: get_vdb, update_vdb, delete_vdb, start_vdb, stop_vdb, enable_vdb, disable_vdb, refresh_vdb_by_timestamp, refresh_vdb_by_snapshot, refresh_vdb_from_bookmark, refresh_vdb_by_location, undo_vdb_refresh, rollback_vdb_by_timestamp, rollback_vdb_by_snapshot, rollback_vdb_from_bookmark, switch_vdb_timeflow, lock_vdb, unlock_vdb, migrate_vdb, get_migrate_compatible_repositories, upgrade_vdb, upgrade_oracle_vdb, get_upgrade_compatible_repositories, list_vdb_snapshots, snapshot_vdb, list_vdb_bookmarks, search_vdb_bookmarks, get_vdb_deletion_dependencies, verify_vdb_jdbc_connection, get_vdb_tags, add_vdb_tags, export_vdb_in_place, export_vdb_asm_in_place, export_vdb_by_snapshot, export_vdb_by_timestamp, export_vdb_by_location, export_vdb_from_bookmark, export_vdb_to_asm_by_snapshot, export_vdb_to_asm_by_timestamp, export_vdb_to_asm_by_location, export_vdb_to_asm_from_bookmark, export_cleanup, export_finalize]
        vdb_ids (list): Request body parameter (Pass as JSON array)
            [Optional for all actions]
        vdb_restart (bool): Indicates whether the Engine should automatically restart this virtual source...
            [Optional for all actions]
        vdb_snapshot_mappings (list): List of the pair of VDB and snapshot to refresh from. If this is not set, all...
            [Optional for all actions]
        vdb_start_param_mappings (list): Request body parameter (Pass as JSON array)
            [Optional for all actions]
        vdb_stop_param_mappings (list): Request body parameter (Pass as JSON array)
            [Optional for all actions]
        vdb_timestamp_mappings (list): List of the pair of VDB and timestamp to refresh from. If this is not set, al...
            [Optional for all actions]
        vdbs (list): Dictates order of operations on VDBs. Operations can be performed in parallel...
            [Optional for all actions]
    
      -- MSSql-specific parameters (SKIP if not provisioning mssql) --
        mssql_failover_drive_letter (str): [MSSql only] Base drive letter location for mount points. (MSSql Only).
            [Optional for all actions]
        recovery_model (str): Recovery model of the database (MSSql Only). Valid values: FULL, SIMPLE, BULK...
            [Optional for all actions]
    
      -- Oracle-specific parameters (SKIP if not provisioning oracle) --
        archive_log (bool): [Oracle only] Option to create a VDB in archivelog mode (Oracle Only).
            [Optional for all actions]
        auxiliary_template_id (str): [Oracle only] The ID of the configuration template to apply to the auxiliary ...
            [Optional for all actions]
        cdb_id (str): [Oracle only] The ID of the container database (CDB) to provision an Oracle M...
            [Optional for all actions]
        cluster_node_ids (list): [Oracle only] The cluster node ids, name or addresses for this provision oper...
            [Optional for all actions]
        cluster_node_instances (list): [Oracle only] The cluster node instances details for this provision operation...
            [Optional for all actions]
        container_mode (bool): [Oracle only] Whether the virtual database will be provisioned for a containe...
            [Optional for all actions]
        file_mapping_rules (str): [Oracle only] Target VDB file mapping rules (Oracle Only). Rules must be line...
            [Optional for all actions]
        okv_client_id (str): [Oracle only] The id of the OKV client used by the target new vCDB for TDE ke...
            [Optional for all actions]
        online_log_groups (int): [Oracle only] Number of online log groups (Oracle Only).
            [Optional for all actions]
        online_log_size (int): [Oracle only] Online log size in MB (Oracle Only).
            [Optional for all actions]
        open_reset_logs (bool): [Oracle only] Whether to open the database after provision (Oracle Only).
            [Optional for all actions]
        oracle_instance_name (str): [Oracle only] Target VDB SID name (Oracle Only).
            [Optional for all actions]
        os_password (str): [Oracle only] The password of the privileged user to run the provision operat...
            [Optional for all actions]
        os_username (str): [Oracle only] The name of the privileged user to run the provision operation ...
            [Optional for all actions]
        tde_exported_key_file_secret (str): [Oracle only] Secret to be used while exporting and importing vPDB encryption...
            [Optional for all actions]
        unique_name (str): [Oracle only] Target VDB db_unique_name (Oracle Only).
            [Optional for all actions]
        vcdb_database_name (str): [Oracle only] When provisioning an Oracle Multitenant vCDB (when the cdb_id p...
            [Optional for all actions]
        vcdb_name (str): [Oracle only] When provisioning an Oracle Multitenant vCDB (when the cdb_id p...
            [Optional for all actions]
        vcdb_restart (bool): [Oracle only] Indicates whether the Engine should automatically restart this ...
            [Optional for all actions]
        vcdb_tde_key_identifier (str): [Oracle only] ID of the key created by Delphix. (Oracle Multitenant Only)
            [Optional for all actions]
    
      -- Postgres-specific parameters (SKIP if not provisioning postgres) --
        config_settings_stg (list): [Postgres only] Custom Database-Level config settings (postgres only). (Pass ...
            [Optional for all actions]
        postgres_port (int): [Postgres only] Port number for Postgres target database (postgres only).
            [Optional for all actions]
        privileged_os_user (str): [Postgres only] This privileged unix username will be used to create the VDB....
            [Optional for all actions]
    
      -- ASE/Sybase-specific parameters (SKIP if not provisioning sybase) --
        truncate_log_on_checkpoint (bool): [ASE/Sybase only] Whether to truncate log on checkpoint (ASE only).
            [Optional for all actions]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'list_vdbs':
        params = build_params(limit=limit, cursor=cursor, sort=sort, permission=permission)
        conf = check_confirmation('GET', '/vdbs', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', '/vdbs', params=params)
    elif action == 'search_vdbs':
        params = build_params(limit=limit, cursor=cursor, sort=sort, permission=permission)
        conf = check_confirmation('POST', '/vdbs/search', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/vdbs/search', params=params, json_body=body)
    elif action == 'get_vdb':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action get_vdb'}
        endpoint = f'/vdbs/{vdb_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'update_vdb':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action update_vdb'}
        endpoint = f'/vdbs/{vdb_id}'
        params = build_params()
        conf = check_confirmation('PATCH', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name, 'description': description, 'db_username': db_username, 'db_password': db_password, 'validate_db_credentials': validate_db_credentials, 'auto_restart': auto_restart, 'environment_user_id': environment_user_id, 'template_id': template_id, 'listener_ids': listener_ids, 'new_dbid': new_dbid, 'cdc_on_provision': cdc_on_provision, 'pre_script': pre_script, 'post_script': post_script, 'hooks': hooks, 'custom_env_vars': custom_env_vars, 'custom_env_files': custom_env_files, 'oracle_rac_custom_env_files': oracle_rac_custom_env_files, 'oracle_rac_custom_env_vars': oracle_rac_custom_env_vars, 'parent_tde_keystore_path': parent_tde_keystore_path, 'parent_tde_keystore_password': parent_tde_keystore_password, 'tde_key_identifier': tde_key_identifier, 'target_vcdb_tde_keystore_path': target_vcdb_tde_keystore_path, 'cdb_tde_keystore_password': cdb_tde_keystore_password, 'parent_pdb_tde_keystore_path': parent_pdb_tde_keystore_path, 'parent_pdb_tde_keystore_password': parent_pdb_tde_keystore_password, 'target_pdb_tde_keystore_password': target_pdb_tde_keystore_password, 'appdata_source_params': appdata_source_params, 'additional_mount_points': additional_mount_points, 'appdata_config_params': appdata_config_params, 'config_params': config_params, 'mount_point': mount_point, 'oracle_services': oracle_services, 'instances': instances, 'invoke_datapatch': invoke_datapatch, 'mssql_ag_backup_location': mssql_ag_backup_location, 'mssql_ag_backup_based': mssql_ag_backup_based, 'cache_priority': cache_priority, 'mssql_incremental_export_backup_frequency_minutes': mssql_incremental_export_backup_frequency_minutes, 'database_name': database_name}.items() if v is not None}
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'provision_by_timestamp':
        params = build_params()
        conf = check_confirmation('POST', '/vdbs/provision_by_timestamp', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'pre_refresh': pre_refresh, 'post_refresh': post_refresh, 'pre_self_refresh': pre_self_refresh, 'post_self_refresh': post_self_refresh, 'pre_rollback': pre_rollback, 'post_rollback': post_rollback, 'configure_clone': configure_clone, 'pre_snapshot': pre_snapshot, 'post_snapshot': post_snapshot, 'pre_start': pre_start, 'post_start': post_start, 'pre_stop': pre_stop, 'post_stop': post_stop, 'target_group_id': target_group_id, 'name': name, 'database_name': database_name, 'cdb_id': cdb_id, 'cluster_node_ids': cluster_node_ids, 'cluster_node_instances': cluster_node_instances, 'truncate_log_on_checkpoint': truncate_log_on_checkpoint, 'os_username': os_username, 'os_password': os_password, 'environment_id': environment_id, 'environment_user_id': environment_user_id, 'repository_id': repository_id, 'auto_select_repository': auto_select_repository, 'vdb_restart': vdb_restart, 'template_id': template_id, 'auxiliary_template_id': auxiliary_template_id, 'file_mapping_rules': file_mapping_rules, 'oracle_instance_name': oracle_instance_name, 'unique_name': unique_name, 'vcdb_name': vcdb_name, 'vcdb_database_name': vcdb_database_name, 'mount_point': mount_point, 'open_reset_logs': open_reset_logs, 'snapshot_policy_id': snapshot_policy_id, 'retention_policy_id': retention_policy_id, 'recovery_model': recovery_model, 'pre_script': pre_script, 'post_script': post_script, 'cdc_on_provision': cdc_on_provision, 'online_log_size': online_log_size, 'online_log_groups': online_log_groups, 'archive_log': archive_log, 'new_dbid': new_dbid, 'masked': masked, 'listener_ids': listener_ids, 'custom_env_vars': custom_env_vars, 'custom_env_files': custom_env_files, 'oracle_rac_custom_env_files': oracle_rac_custom_env_files, 'oracle_rac_custom_env_vars': oracle_rac_custom_env_vars, 'parentTdeKeystorePath': parent_tde_keystore_path, 'parent_tde_keystore_password': parent_tde_keystore_password, 'parent_pdb_tde_keystore_path': parent_pdb_tde_keystore_path, 'parent_pdb_tde_keystore_password': parent_pdb_tde_keystore_password, 'target_pdb_tde_keystore_password': target_pdb_tde_keystore_password, 'tde_exported_key_file_secret': tde_exported_key_file_secret, 'tde_key_identifier': tde_key_identifier, 'target_vcdb_tde_keystore_path': target_vcdb_tde_keystore_path, 'cdb_tde_keystore_password': cdb_tde_keystore_password, 'vcdb_tde_key_identifier': vcdb_tde_key_identifier, 'tde_keystore_config_type': tde_keystore_config_type, 'okv_client_id': okv_client_id, 'appdata_source_params': appdata_source_params, 'additional_mount_points': additional_mount_points, 'appdata_config_params': appdata_config_params, 'config_params': config_params, 'privileged_os_user': privileged_os_user, 'postgres_port': postgres_port, 'config_settings_stg': config_settings_stg, 'vcdb_restart': vcdb_restart, 'mssql_failover_drive_letter': mssql_failover_drive_letter, 'tags': tags, 'invoke_datapatch': invoke_datapatch, 'container_mode': container_mode, 'mssql_ag_backup_location': mssql_ag_backup_location, 'mssql_ag_backup_based': mssql_ag_backup_based, 'cache_priority': cache_priority, 'mssql_incremental_export_backup_frequency_minutes': mssql_incremental_export_backup_frequency_minutes, 'timestamp': timestamp, 'timestamp_in_database_timezone': timestamp_in_database_timezone, 'timeflow_id': timeflow_id, 'engine_id': engine_id, 'source_data_id': source_data_id, 'make_current_account_owner': make_current_account_owner}.items() if v is not None}
        return make_api_request('POST', '/vdbs/provision_by_timestamp', params=params, json_body=body if body else None)
    elif action == 'provision_by_timestamp_defaults':
        params = build_params()
        conf = check_confirmation('POST', '/vdbs/provision_by_timestamp/defaults', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'timestamp': timestamp, 'timestamp_in_database_timezone': timestamp_in_database_timezone, 'engine_id': engine_id, 'source_data_id': source_data_id, 'timeflow_id': timeflow_id}.items() if v is not None}
        return make_api_request('POST', '/vdbs/provision_by_timestamp/defaults', params=params, json_body=body if body else None)
    elif action == 'provision_by_snapshot':
        params = build_params()
        conf = check_confirmation('POST', '/vdbs/provision_by_snapshot', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'pre_refresh': pre_refresh, 'post_refresh': post_refresh, 'pre_self_refresh': pre_self_refresh, 'post_self_refresh': post_self_refresh, 'pre_rollback': pre_rollback, 'post_rollback': post_rollback, 'configure_clone': configure_clone, 'pre_snapshot': pre_snapshot, 'post_snapshot': post_snapshot, 'pre_start': pre_start, 'post_start': post_start, 'pre_stop': pre_stop, 'post_stop': post_stop, 'target_group_id': target_group_id, 'name': name, 'database_name': database_name, 'cdb_id': cdb_id, 'cluster_node_ids': cluster_node_ids, 'cluster_node_instances': cluster_node_instances, 'truncate_log_on_checkpoint': truncate_log_on_checkpoint, 'os_username': os_username, 'os_password': os_password, 'environment_id': environment_id, 'environment_user_id': environment_user_id, 'repository_id': repository_id, 'auto_select_repository': auto_select_repository, 'vdb_restart': vdb_restart, 'template_id': template_id, 'auxiliary_template_id': auxiliary_template_id, 'file_mapping_rules': file_mapping_rules, 'oracle_instance_name': oracle_instance_name, 'unique_name': unique_name, 'vcdb_name': vcdb_name, 'vcdb_database_name': vcdb_database_name, 'mount_point': mount_point, 'open_reset_logs': open_reset_logs, 'snapshot_policy_id': snapshot_policy_id, 'retention_policy_id': retention_policy_id, 'recovery_model': recovery_model, 'pre_script': pre_script, 'post_script': post_script, 'cdc_on_provision': cdc_on_provision, 'online_log_size': online_log_size, 'online_log_groups': online_log_groups, 'archive_log': archive_log, 'new_dbid': new_dbid, 'masked': masked, 'listener_ids': listener_ids, 'custom_env_vars': custom_env_vars, 'custom_env_files': custom_env_files, 'oracle_rac_custom_env_files': oracle_rac_custom_env_files, 'oracle_rac_custom_env_vars': oracle_rac_custom_env_vars, 'parentTdeKeystorePath': parent_tde_keystore_path, 'parent_tde_keystore_password': parent_tde_keystore_password, 'parent_pdb_tde_keystore_path': parent_pdb_tde_keystore_path, 'parent_pdb_tde_keystore_password': parent_pdb_tde_keystore_password, 'target_pdb_tde_keystore_password': target_pdb_tde_keystore_password, 'tde_exported_key_file_secret': tde_exported_key_file_secret, 'tde_key_identifier': tde_key_identifier, 'target_vcdb_tde_keystore_path': target_vcdb_tde_keystore_path, 'cdb_tde_keystore_password': cdb_tde_keystore_password, 'vcdb_tde_key_identifier': vcdb_tde_key_identifier, 'tde_keystore_config_type': tde_keystore_config_type, 'okv_client_id': okv_client_id, 'appdata_source_params': appdata_source_params, 'additional_mount_points': additional_mount_points, 'appdata_config_params': appdata_config_params, 'config_params': config_params, 'privileged_os_user': privileged_os_user, 'postgres_port': postgres_port, 'config_settings_stg': config_settings_stg, 'vcdb_restart': vcdb_restart, 'mssql_failover_drive_letter': mssql_failover_drive_letter, 'tags': tags, 'invoke_datapatch': invoke_datapatch, 'container_mode': container_mode, 'mssql_ag_backup_location': mssql_ag_backup_location, 'mssql_ag_backup_based': mssql_ag_backup_based, 'cache_priority': cache_priority, 'mssql_incremental_export_backup_frequency_minutes': mssql_incremental_export_backup_frequency_minutes, 'snapshot_id': snapshot_id, 'engine_id': engine_id, 'source_data_id': source_data_id, 'make_current_account_owner': make_current_account_owner}.items() if v is not None}
        return make_api_request('POST', '/vdbs/provision_by_snapshot', params=params, json_body=body if body else None)
    elif action == 'provision_by_snapshot_defaults':
        params = build_params()
        conf = check_confirmation('POST', '/vdbs/provision_by_snapshot/defaults', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'snapshot_id': snapshot_id, 'engine_id': engine_id, 'source_data_id': source_data_id}.items() if v is not None}
        return make_api_request('POST', '/vdbs/provision_by_snapshot/defaults', params=params, json_body=body if body else None)
    elif action == 'provision_from_bookmark':
        params = build_params()
        conf = check_confirmation('POST', '/vdbs/provision_from_bookmark', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'pre_refresh': pre_refresh, 'post_refresh': post_refresh, 'pre_self_refresh': pre_self_refresh, 'post_self_refresh': post_self_refresh, 'pre_rollback': pre_rollback, 'post_rollback': post_rollback, 'configure_clone': configure_clone, 'pre_snapshot': pre_snapshot, 'post_snapshot': post_snapshot, 'pre_start': pre_start, 'post_start': post_start, 'pre_stop': pre_stop, 'post_stop': post_stop, 'target_group_id': target_group_id, 'name': name, 'database_name': database_name, 'cdb_id': cdb_id, 'cluster_node_ids': cluster_node_ids, 'cluster_node_instances': cluster_node_instances, 'truncate_log_on_checkpoint': truncate_log_on_checkpoint, 'os_username': os_username, 'os_password': os_password, 'environment_id': environment_id, 'environment_user_id': environment_user_id, 'repository_id': repository_id, 'auto_select_repository': auto_select_repository, 'vdb_restart': vdb_restart, 'template_id': template_id, 'auxiliary_template_id': auxiliary_template_id, 'file_mapping_rules': file_mapping_rules, 'oracle_instance_name': oracle_instance_name, 'unique_name': unique_name, 'vcdb_name': vcdb_name, 'vcdb_database_name': vcdb_database_name, 'mount_point': mount_point, 'open_reset_logs': open_reset_logs, 'snapshot_policy_id': snapshot_policy_id, 'retention_policy_id': retention_policy_id, 'recovery_model': recovery_model, 'pre_script': pre_script, 'post_script': post_script, 'cdc_on_provision': cdc_on_provision, 'online_log_size': online_log_size, 'online_log_groups': online_log_groups, 'archive_log': archive_log, 'new_dbid': new_dbid, 'masked': masked, 'listener_ids': listener_ids, 'custom_env_vars': custom_env_vars, 'custom_env_files': custom_env_files, 'oracle_rac_custom_env_files': oracle_rac_custom_env_files, 'oracle_rac_custom_env_vars': oracle_rac_custom_env_vars, 'parentTdeKeystorePath': parent_tde_keystore_path, 'parent_tde_keystore_password': parent_tde_keystore_password, 'parent_pdb_tde_keystore_path': parent_pdb_tde_keystore_path, 'parent_pdb_tde_keystore_password': parent_pdb_tde_keystore_password, 'target_pdb_tde_keystore_password': target_pdb_tde_keystore_password, 'tde_exported_key_file_secret': tde_exported_key_file_secret, 'tde_key_identifier': tde_key_identifier, 'target_vcdb_tde_keystore_path': target_vcdb_tde_keystore_path, 'cdb_tde_keystore_password': cdb_tde_keystore_password, 'vcdb_tde_key_identifier': vcdb_tde_key_identifier, 'tde_keystore_config_type': tde_keystore_config_type, 'okv_client_id': okv_client_id, 'appdata_source_params': appdata_source_params, 'additional_mount_points': additional_mount_points, 'appdata_config_params': appdata_config_params, 'config_params': config_params, 'privileged_os_user': privileged_os_user, 'postgres_port': postgres_port, 'config_settings_stg': config_settings_stg, 'vcdb_restart': vcdb_restart, 'mssql_failover_drive_letter': mssql_failover_drive_letter, 'tags': tags, 'invoke_datapatch': invoke_datapatch, 'container_mode': container_mode, 'mssql_ag_backup_location': mssql_ag_backup_location, 'mssql_ag_backup_based': mssql_ag_backup_based, 'cache_priority': cache_priority, 'mssql_incremental_export_backup_frequency_minutes': mssql_incremental_export_backup_frequency_minutes, 'bookmark_id': bookmark_id, 'make_current_account_owner': make_current_account_owner}.items() if v is not None}
        return make_api_request('POST', '/vdbs/provision_from_bookmark', params=params, json_body=body if body else None)
    elif action == 'provision_from_bookmark_defaults':
        params = build_params()
        conf = check_confirmation('POST', '/vdbs/provision_from_bookmark/defaults', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'bookmark_id': bookmark_id}.items() if v is not None}
        return make_api_request('POST', '/vdbs/provision_from_bookmark/defaults', params=params, json_body=body if body else None)
    elif action == 'provision_by_location':
        params = build_params()
        conf = check_confirmation('POST', '/vdbs/provision_by_location', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'pre_refresh': pre_refresh, 'post_refresh': post_refresh, 'pre_self_refresh': pre_self_refresh, 'post_self_refresh': post_self_refresh, 'pre_rollback': pre_rollback, 'post_rollback': post_rollback, 'configure_clone': configure_clone, 'pre_snapshot': pre_snapshot, 'post_snapshot': post_snapshot, 'pre_start': pre_start, 'post_start': post_start, 'pre_stop': pre_stop, 'post_stop': post_stop, 'target_group_id': target_group_id, 'name': name, 'database_name': database_name, 'cdb_id': cdb_id, 'cluster_node_ids': cluster_node_ids, 'cluster_node_instances': cluster_node_instances, 'truncate_log_on_checkpoint': truncate_log_on_checkpoint, 'os_username': os_username, 'os_password': os_password, 'environment_id': environment_id, 'environment_user_id': environment_user_id, 'repository_id': repository_id, 'auto_select_repository': auto_select_repository, 'vdb_restart': vdb_restart, 'template_id': template_id, 'auxiliary_template_id': auxiliary_template_id, 'file_mapping_rules': file_mapping_rules, 'oracle_instance_name': oracle_instance_name, 'unique_name': unique_name, 'vcdb_name': vcdb_name, 'vcdb_database_name': vcdb_database_name, 'mount_point': mount_point, 'open_reset_logs': open_reset_logs, 'snapshot_policy_id': snapshot_policy_id, 'retention_policy_id': retention_policy_id, 'recovery_model': recovery_model, 'pre_script': pre_script, 'post_script': post_script, 'cdc_on_provision': cdc_on_provision, 'online_log_size': online_log_size, 'online_log_groups': online_log_groups, 'archive_log': archive_log, 'new_dbid': new_dbid, 'masked': masked, 'listener_ids': listener_ids, 'custom_env_vars': custom_env_vars, 'custom_env_files': custom_env_files, 'oracle_rac_custom_env_files': oracle_rac_custom_env_files, 'oracle_rac_custom_env_vars': oracle_rac_custom_env_vars, 'parentTdeKeystorePath': parent_tde_keystore_path, 'parent_tde_keystore_password': parent_tde_keystore_password, 'parent_pdb_tde_keystore_path': parent_pdb_tde_keystore_path, 'parent_pdb_tde_keystore_password': parent_pdb_tde_keystore_password, 'target_pdb_tde_keystore_password': target_pdb_tde_keystore_password, 'tde_exported_key_file_secret': tde_exported_key_file_secret, 'tde_key_identifier': tde_key_identifier, 'target_vcdb_tde_keystore_path': target_vcdb_tde_keystore_path, 'cdb_tde_keystore_password': cdb_tde_keystore_password, 'vcdb_tde_key_identifier': vcdb_tde_key_identifier, 'tde_keystore_config_type': tde_keystore_config_type, 'okv_client_id': okv_client_id, 'appdata_source_params': appdata_source_params, 'additional_mount_points': additional_mount_points, 'appdata_config_params': appdata_config_params, 'config_params': config_params, 'privileged_os_user': privileged_os_user, 'postgres_port': postgres_port, 'config_settings_stg': config_settings_stg, 'vcdb_restart': vcdb_restart, 'mssql_failover_drive_letter': mssql_failover_drive_letter, 'tags': tags, 'invoke_datapatch': invoke_datapatch, 'container_mode': container_mode, 'mssql_ag_backup_location': mssql_ag_backup_location, 'mssql_ag_backup_based': mssql_ag_backup_based, 'cache_priority': cache_priority, 'mssql_incremental_export_backup_frequency_minutes': mssql_incremental_export_backup_frequency_minutes, 'location': location, 'timeflow_id': timeflow_id, 'engine_id': engine_id, 'source_data_id': source_data_id, 'make_current_account_owner': make_current_account_owner}.items() if v is not None}
        return make_api_request('POST', '/vdbs/provision_by_location', params=params, json_body=body if body else None)
    elif action == 'provision_by_location_defaults':
        params = build_params()
        conf = check_confirmation('POST', '/vdbs/provision_by_location/defaults', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'source_data_id': source_data_id, 'engine_id': engine_id, 'location': location, 'timeflow_id': timeflow_id}.items() if v is not None}
        return make_api_request('POST', '/vdbs/provision_by_location/defaults', params=params, json_body=body if body else None)
    elif action == 'provision_empty_vdb':
        params = build_params()
        conf = check_confirmation('POST', '/vdbs/empty_vdb', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'pre_refresh': pre_refresh, 'post_refresh': post_refresh, 'pre_self_refresh': pre_self_refresh, 'post_self_refresh': post_self_refresh, 'pre_rollback': pre_rollback, 'post_rollback': post_rollback, 'configure_clone': configure_clone, 'pre_snapshot': pre_snapshot, 'post_snapshot': post_snapshot, 'pre_start': pre_start, 'post_start': post_start, 'pre_stop': pre_stop, 'post_stop': post_stop, 'target_group_id': target_group_id, 'name': name, 'database_name': database_name, 'cdb_id': cdb_id, 'cluster_node_ids': cluster_node_ids, 'cluster_node_instances': cluster_node_instances, 'truncate_log_on_checkpoint': truncate_log_on_checkpoint, 'os_username': os_username, 'os_password': os_password, 'environment_id': environment_id, 'environment_user_id': environment_user_id, 'repository_id': repository_id, 'auto_select_repository': auto_select_repository, 'vdb_restart': vdb_restart, 'template_id': template_id, 'auxiliary_template_id': auxiliary_template_id, 'file_mapping_rules': file_mapping_rules, 'oracle_instance_name': oracle_instance_name, 'unique_name': unique_name, 'vcdb_name': vcdb_name, 'vcdb_database_name': vcdb_database_name, 'mount_point': mount_point, 'open_reset_logs': open_reset_logs, 'snapshot_policy_id': snapshot_policy_id, 'retention_policy_id': retention_policy_id, 'recovery_model': recovery_model, 'pre_script': pre_script, 'post_script': post_script, 'cdc_on_provision': cdc_on_provision, 'online_log_size': online_log_size, 'online_log_groups': online_log_groups, 'archive_log': archive_log, 'new_dbid': new_dbid, 'masked': masked, 'listener_ids': listener_ids, 'custom_env_vars': custom_env_vars, 'custom_env_files': custom_env_files, 'oracle_rac_custom_env_files': oracle_rac_custom_env_files, 'oracle_rac_custom_env_vars': oracle_rac_custom_env_vars, 'parentTdeKeystorePath': parent_tde_keystore_path, 'parent_tde_keystore_password': parent_tde_keystore_password, 'parent_pdb_tde_keystore_path': parent_pdb_tde_keystore_path, 'parent_pdb_tde_keystore_password': parent_pdb_tde_keystore_password, 'target_pdb_tde_keystore_password': target_pdb_tde_keystore_password, 'tde_exported_key_file_secret': tde_exported_key_file_secret, 'tde_key_identifier': tde_key_identifier, 'target_vcdb_tde_keystore_path': target_vcdb_tde_keystore_path, 'cdb_tde_keystore_password': cdb_tde_keystore_password, 'vcdb_tde_key_identifier': vcdb_tde_key_identifier, 'tde_keystore_config_type': tde_keystore_config_type, 'okv_client_id': okv_client_id, 'appdata_source_params': appdata_source_params, 'additional_mount_points': additional_mount_points, 'appdata_config_params': appdata_config_params, 'config_params': config_params, 'privileged_os_user': privileged_os_user, 'postgres_port': postgres_port, 'config_settings_stg': config_settings_stg, 'vcdb_restart': vcdb_restart, 'mssql_failover_drive_letter': mssql_failover_drive_letter, 'tags': tags, 'invoke_datapatch': invoke_datapatch, 'container_mode': container_mode, 'mssql_ag_backup_location': mssql_ag_backup_location, 'mssql_ag_backup_based': mssql_ag_backup_based, 'cache_priority': cache_priority, 'mssql_incremental_export_backup_frequency_minutes': mssql_incremental_export_backup_frequency_minutes, 'engine_id': engine_id}.items() if v is not None}
        return make_api_request('POST', '/vdbs/empty_vdb', params=params, json_body=body if body else None)
    elif action == 'delete_vdb':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action delete_vdb'}
        endpoint = f'/vdbs/{vdb_id}/delete'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'force': force, 'delete_all_dependent_vdbs': delete_all_dependent_vdbs}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'start_vdb':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action start_vdb'}
        endpoint = f'/vdbs/{vdb_id}/start'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'instances': instances}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'stop_vdb':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action stop_vdb'}
        endpoint = f'/vdbs/{vdb_id}/stop'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'instances': instances, 'abort': abort}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'enable_vdb':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action enable_vdb'}
        endpoint = f'/vdbs/{vdb_id}/enable'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'attempt_start': attempt_start, 'container_mode': container_mode, 'ownership_spec': ownership_spec}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'disable_vdb':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action disable_vdb'}
        endpoint = f'/vdbs/{vdb_id}/disable'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'attempt_cleanup': attempt_cleanup, 'container_mode': container_mode}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'refresh_vdb_by_timestamp':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action refresh_vdb_by_timestamp'}
        endpoint = f'/vdbs/{vdb_id}/refresh_by_timestamp'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'timestamp': timestamp, 'timestamp_in_database_timezone': timestamp_in_database_timezone, 'timeflow_id': timeflow_id, 'dataset_id': dataset_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'refresh_vdb_by_snapshot':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action refresh_vdb_by_snapshot'}
        endpoint = f'/vdbs/{vdb_id}/refresh_by_snapshot'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'snapshot_id': snapshot_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'refresh_vdb_from_bookmark':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action refresh_vdb_from_bookmark'}
        endpoint = f'/vdbs/{vdb_id}/refresh_from_bookmark'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'bookmark_id': bookmark_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'refresh_vdb_by_location':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action refresh_vdb_by_location'}
        endpoint = f'/vdbs/{vdb_id}/refresh_by_location'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'location': location, 'dataset_id': dataset_id, 'timeflow_id': timeflow_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'undo_vdb_refresh':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action undo_vdb_refresh'}
        endpoint = f'/vdbs/{vdb_id}/undo_refresh'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'rollback_vdb_by_timestamp':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action rollback_vdb_by_timestamp'}
        endpoint = f'/vdbs/{vdb_id}/rollback_by_timestamp'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'timestamp': timestamp, 'timestamp_in_database_timezone': timestamp_in_database_timezone, 'timeflow_id': timeflow_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'rollback_vdb_by_snapshot':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action rollback_vdb_by_snapshot'}
        endpoint = f'/vdbs/{vdb_id}/rollback_by_snapshot'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'snapshot_id': snapshot_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'rollback_vdb_from_bookmark':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action rollback_vdb_from_bookmark'}
        endpoint = f'/vdbs/{vdb_id}/rollback_from_bookmark'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'bookmark_id': bookmark_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'switch_vdb_timeflow':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action switch_vdb_timeflow'}
        endpoint = f'/vdbs/{vdb_id}/switch_timeflow'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'timeflow_id': timeflow_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'lock_vdb':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action lock_vdb'}
        endpoint = f'/vdbs/{vdb_id}/lock'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'account_id': account_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'unlock_vdb':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action unlock_vdb'}
        endpoint = f'/vdbs/{vdb_id}/unlock'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'migrate_vdb':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action migrate_vdb'}
        endpoint = f'/vdbs/{vdb_id}/migrate'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'environment_id': environment_id, 'environment_user_ref': environment_user_ref, 'repository_id': repository_id, 'cdb_id': cdb_id, 'cluster_node_ids': cluster_node_ids, 'cluster_node_instances': cluster_node_instances}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'get_migrate_compatible_repositories':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action get_migrate_compatible_repositories'}
        endpoint = f'/vdbs/{vdb_id}/migrate_compatible_repositories'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'upgrade_vdb':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action upgrade_vdb'}
        endpoint = f'/vdbs/{vdb_id}/upgrade'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'repository_id': repository_id, 'environment_user_id': environment_user_id, 'ppt_repository': ppt_repository}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'upgrade_oracle_vdb':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action upgrade_oracle_vdb'}
        endpoint = f'/vdbs/oracle/{vdb_id}/upgrade'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'repository_id': repository_id, 'environment_user_id': environment_user_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'get_upgrade_compatible_repositories':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action get_upgrade_compatible_repositories'}
        endpoint = f'/vdbs/{vdb_id}/upgrade_compatible_repositories'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'list_vdb_snapshots':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action list_vdb_snapshots'}
        endpoint = f'/vdbs/{vdb_id}/snapshots'
        params = build_params(limit=limit, cursor=cursor)
        conf = check_confirmation('GET', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'snapshot_vdb':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action snapshot_vdb'}
        endpoint = f'/vdbs/{vdb_id}/snapshots'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'list_vdb_bookmarks':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action list_vdb_bookmarks'}
        endpoint = f'/vdbs/{vdb_id}/bookmarks'
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('GET', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'search_vdb_bookmarks':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action search_vdb_bookmarks'}
        endpoint = f'/vdbs/{vdb_id}/bookmarks/search'
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', endpoint, params=params, json_body=body)
    elif action == 'get_vdb_deletion_dependencies':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action get_vdb_deletion_dependencies'}
        endpoint = f'/vdbs/{vdb_id}/deletion-dependencies'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'verify_vdb_jdbc_connection':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action verify_vdb_jdbc_connection'}
        endpoint = f'/vdbs/{vdb_id}/jdbc-check'
        params = build_params(database_username=database_username, database_password=database_password, jdbc_connection_string=jdbc_connection_string)
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'database_username': database_username, 'database_password': database_password, 'jdbc_connection_string': jdbc_connection_string}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'get_vdb_tags':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action get_vdb_tags'}
        endpoint = f'/vdbs/{vdb_id}/tags'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_vdb_tags':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action add_vdb_tags'}
        endpoint = f'/vdbs/{vdb_id}/tags'
        params = build_params(tags=tags)
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'export_vdb_in_place':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action export_vdb_in_place'}
        endpoint = f'/vdbs/{vdb_id}/in-place-export'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'targetDirectory': target_directory, 'dataDirectory': data_directory, 'archiveDirectory': archive_directory, 'externalDirectory': external_directory, 'tempDirectory': temp_directory, 'scriptDirectory': script_directory, 'useAbsolutePathForDataFiles': use_absolute_path_for_data_files, 'rman_channels': rman_channels, 'rman_file_section_size_in_gb': rman_file_section_size_in_gb, 'db_unique_name': db_unique_name, 'pdb_name': pdb_name, 'operations_postV2P': operations_post_v2_p}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'export_vdb_asm_in_place':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action export_vdb_asm_in_place'}
        endpoint = f'/vdbs/{vdb_id}/asm-in-place-export'
        params = build_params(default_data_diskgroup=default_data_diskgroup)
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'default_data_diskgroup': default_data_diskgroup, 'redo_diskgroup': redo_diskgroup, 'rman_channels': rman_channels, 'rman_file_section_size_in_gb': rman_file_section_size_in_gb, 'db_unique_name': db_unique_name, 'pdb_name': pdb_name, 'operations_postV2P': operations_post_v2_p}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'export_vdb_by_snapshot':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action export_vdb_by_snapshot'}
        endpoint = f'/vdbs/{vdb_id}/export-by-snapshot'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'unique_name': unique_name, 'database_name': database_name, 'repository_id': repository_id, 'environment_user_ref': environment_user_ref, 'tde_keystore_password': tde_keystore_password, 'tde_keystore_config_type': tde_keystore_config_type, 'oracle_instance_name': oracle_instance_name, 'instance_number': instance_number, 'instances': instances, 'mount_base': mount_base, 'config_params': config_params, 'cdb_id': cdb_id, 'parent_tde_keystore_path': parent_tde_keystore_path, 'parent_tde_keystore_password': parent_tde_keystore_password, 'tde_exported_keyfile_secret': tde_exported_keyfile_secret, 'tde_key_identifier': tde_key_identifier, 'parent_pdb_tde_keystore_path': parent_pdb_tde_keystore_path, 'parent_pdb_tde_keystore_password': parent_pdb_tde_keystore_password, 'target_pdb_tde_keystore_password': target_pdb_tde_keystore_password, 'crs_database_name': crs_database_name, 'recover_database': recover_database, 'file_mapping_rules': file_mapping_rules, 'enable_cdc': enable_cdc, 'recovery_model': recovery_model, 'mirroring_state': mirroring_state, 'is_incremental_v2p': is_incremental_v2p, 'backup_frequency_minutes': backup_frequency_minutes, 'rman_channels_for_incremental_backup': rman_channels_for_incremental_backup, 'rman_files_per_set_for_incremental_backup': rman_files_per_set_for_incremental_backup, 'rman_file_section_size_in_gb_for_incremental_backup': rman_file_section_size_in_gb_for_incremental_backup, 'targetDirectory': target_directory, 'dataDirectory': data_directory, 'archiveDirectory': archive_directory, 'externalDirectory': external_directory, 'tempDirectory': temp_directory, 'scriptDirectory': script_directory, 'useAbsolutePathForDataFiles': use_absolute_path_for_data_files, 'rman_channels': rman_channels, 'rman_file_section_size_in_gb': rman_file_section_size_in_gb, 'snapshot_id': snapshot_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'export_vdb_by_timestamp':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action export_vdb_by_timestamp'}
        endpoint = f'/vdbs/{vdb_id}/export-by-timestamp'
        params = build_params(timestamp=timestamp)
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'unique_name': unique_name, 'database_name': database_name, 'repository_id': repository_id, 'environment_user_ref': environment_user_ref, 'tde_keystore_password': tde_keystore_password, 'tde_keystore_config_type': tde_keystore_config_type, 'oracle_instance_name': oracle_instance_name, 'instance_number': instance_number, 'instances': instances, 'mount_base': mount_base, 'config_params': config_params, 'cdb_id': cdb_id, 'parent_tde_keystore_path': parent_tde_keystore_path, 'parent_tde_keystore_password': parent_tde_keystore_password, 'tde_exported_keyfile_secret': tde_exported_keyfile_secret, 'tde_key_identifier': tde_key_identifier, 'parent_pdb_tde_keystore_path': parent_pdb_tde_keystore_path, 'parent_pdb_tde_keystore_password': parent_pdb_tde_keystore_password, 'target_pdb_tde_keystore_password': target_pdb_tde_keystore_password, 'crs_database_name': crs_database_name, 'recover_database': recover_database, 'file_mapping_rules': file_mapping_rules, 'enable_cdc': enable_cdc, 'recovery_model': recovery_model, 'mirroring_state': mirroring_state, 'is_incremental_v2p': is_incremental_v2p, 'backup_frequency_minutes': backup_frequency_minutes, 'rman_channels_for_incremental_backup': rman_channels_for_incremental_backup, 'rman_files_per_set_for_incremental_backup': rman_files_per_set_for_incremental_backup, 'rman_file_section_size_in_gb_for_incremental_backup': rman_file_section_size_in_gb_for_incremental_backup, 'targetDirectory': target_directory, 'dataDirectory': data_directory, 'archiveDirectory': archive_directory, 'externalDirectory': external_directory, 'tempDirectory': temp_directory, 'scriptDirectory': script_directory, 'useAbsolutePathForDataFiles': use_absolute_path_for_data_files, 'rman_channels': rman_channels, 'rman_file_section_size_in_gb': rman_file_section_size_in_gb, 'timeflow_id': timeflow_id, 'timestamp': timestamp}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'export_vdb_by_location':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action export_vdb_by_location'}
        endpoint = f'/vdbs/{vdb_id}/export-by-location'
        params = build_params(location=location)
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'unique_name': unique_name, 'database_name': database_name, 'repository_id': repository_id, 'environment_user_ref': environment_user_ref, 'tde_keystore_password': tde_keystore_password, 'tde_keystore_config_type': tde_keystore_config_type, 'oracle_instance_name': oracle_instance_name, 'instance_number': instance_number, 'instances': instances, 'mount_base': mount_base, 'config_params': config_params, 'cdb_id': cdb_id, 'parent_tde_keystore_path': parent_tde_keystore_path, 'parent_tde_keystore_password': parent_tde_keystore_password, 'tde_exported_keyfile_secret': tde_exported_keyfile_secret, 'tde_key_identifier': tde_key_identifier, 'parent_pdb_tde_keystore_path': parent_pdb_tde_keystore_path, 'parent_pdb_tde_keystore_password': parent_pdb_tde_keystore_password, 'target_pdb_tde_keystore_password': target_pdb_tde_keystore_password, 'crs_database_name': crs_database_name, 'recover_database': recover_database, 'file_mapping_rules': file_mapping_rules, 'enable_cdc': enable_cdc, 'recovery_model': recovery_model, 'mirroring_state': mirroring_state, 'is_incremental_v2p': is_incremental_v2p, 'backup_frequency_minutes': backup_frequency_minutes, 'rman_channels_for_incremental_backup': rman_channels_for_incremental_backup, 'rman_files_per_set_for_incremental_backup': rman_files_per_set_for_incremental_backup, 'rman_file_section_size_in_gb_for_incremental_backup': rman_file_section_size_in_gb_for_incremental_backup, 'targetDirectory': target_directory, 'dataDirectory': data_directory, 'archiveDirectory': archive_directory, 'externalDirectory': external_directory, 'tempDirectory': temp_directory, 'scriptDirectory': script_directory, 'useAbsolutePathForDataFiles': use_absolute_path_for_data_files, 'rman_channels': rman_channels, 'rman_file_section_size_in_gb': rman_file_section_size_in_gb, 'location': location}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'export_vdb_from_bookmark':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action export_vdb_from_bookmark'}
        endpoint = f'/vdbs/{vdb_id}/export-from-bookmark'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'unique_name': unique_name, 'database_name': database_name, 'repository_id': repository_id, 'environment_user_ref': environment_user_ref, 'tde_keystore_password': tde_keystore_password, 'tde_keystore_config_type': tde_keystore_config_type, 'oracle_instance_name': oracle_instance_name, 'instance_number': instance_number, 'instances': instances, 'mount_base': mount_base, 'config_params': config_params, 'cdb_id': cdb_id, 'parent_tde_keystore_path': parent_tde_keystore_path, 'parent_tde_keystore_password': parent_tde_keystore_password, 'tde_exported_keyfile_secret': tde_exported_keyfile_secret, 'tde_key_identifier': tde_key_identifier, 'parent_pdb_tde_keystore_path': parent_pdb_tde_keystore_path, 'parent_pdb_tde_keystore_password': parent_pdb_tde_keystore_password, 'target_pdb_tde_keystore_password': target_pdb_tde_keystore_password, 'crs_database_name': crs_database_name, 'recover_database': recover_database, 'file_mapping_rules': file_mapping_rules, 'enable_cdc': enable_cdc, 'recovery_model': recovery_model, 'mirroring_state': mirroring_state, 'is_incremental_v2p': is_incremental_v2p, 'backup_frequency_minutes': backup_frequency_minutes, 'rman_channels_for_incremental_backup': rman_channels_for_incremental_backup, 'rman_files_per_set_for_incremental_backup': rman_files_per_set_for_incremental_backup, 'rman_file_section_size_in_gb_for_incremental_backup': rman_file_section_size_in_gb_for_incremental_backup, 'targetDirectory': target_directory, 'dataDirectory': data_directory, 'archiveDirectory': archive_directory, 'externalDirectory': external_directory, 'tempDirectory': temp_directory, 'scriptDirectory': script_directory, 'useAbsolutePathForDataFiles': use_absolute_path_for_data_files, 'rman_channels': rman_channels, 'rman_file_section_size_in_gb': rman_file_section_size_in_gb, 'bookmark_id': bookmark_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'export_vdb_to_asm_by_snapshot':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action export_vdb_to_asm_by_snapshot'}
        endpoint = f'/vdbs/{vdb_id}/asm-export-by-snapshot'
        params = build_params(default_data_diskgroup=default_data_diskgroup)
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'unique_name': unique_name, 'database_name': database_name, 'repository_id': repository_id, 'environment_user_ref': environment_user_ref, 'tde_keystore_password': tde_keystore_password, 'tde_keystore_config_type': tde_keystore_config_type, 'oracle_instance_name': oracle_instance_name, 'instance_number': instance_number, 'instances': instances, 'mount_base': mount_base, 'config_params': config_params, 'cdb_id': cdb_id, 'parent_tde_keystore_path': parent_tde_keystore_path, 'parent_tde_keystore_password': parent_tde_keystore_password, 'tde_exported_keyfile_secret': tde_exported_keyfile_secret, 'tde_key_identifier': tde_key_identifier, 'parent_pdb_tde_keystore_path': parent_pdb_tde_keystore_path, 'parent_pdb_tde_keystore_password': parent_pdb_tde_keystore_password, 'target_pdb_tde_keystore_password': target_pdb_tde_keystore_password, 'crs_database_name': crs_database_name, 'recover_database': recover_database, 'file_mapping_rules': file_mapping_rules, 'enable_cdc': enable_cdc, 'recovery_model': recovery_model, 'mirroring_state': mirroring_state, 'is_incremental_v2p': is_incremental_v2p, 'backup_frequency_minutes': backup_frequency_minutes, 'rman_channels_for_incremental_backup': rman_channels_for_incremental_backup, 'rman_files_per_set_for_incremental_backup': rman_files_per_set_for_incremental_backup, 'rman_file_section_size_in_gb_for_incremental_backup': rman_file_section_size_in_gb_for_incremental_backup, 'default_data_diskgroup': default_data_diskgroup, 'redo_diskgroup': redo_diskgroup, 'rman_channels': rman_channels, 'rman_file_section_size_in_gb': rman_file_section_size_in_gb, 'snapshot_id': snapshot_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'export_vdb_to_asm_by_timestamp':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action export_vdb_to_asm_by_timestamp'}
        endpoint = f'/vdbs/{vdb_id}/asm-export-by-timestamp'
        params = build_params(timestamp=timestamp, default_data_diskgroup=default_data_diskgroup)
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'unique_name': unique_name, 'database_name': database_name, 'repository_id': repository_id, 'environment_user_ref': environment_user_ref, 'tde_keystore_password': tde_keystore_password, 'tde_keystore_config_type': tde_keystore_config_type, 'oracle_instance_name': oracle_instance_name, 'instance_number': instance_number, 'instances': instances, 'mount_base': mount_base, 'config_params': config_params, 'cdb_id': cdb_id, 'parent_tde_keystore_path': parent_tde_keystore_path, 'parent_tde_keystore_password': parent_tde_keystore_password, 'tde_exported_keyfile_secret': tde_exported_keyfile_secret, 'tde_key_identifier': tde_key_identifier, 'parent_pdb_tde_keystore_path': parent_pdb_tde_keystore_path, 'parent_pdb_tde_keystore_password': parent_pdb_tde_keystore_password, 'target_pdb_tde_keystore_password': target_pdb_tde_keystore_password, 'crs_database_name': crs_database_name, 'recover_database': recover_database, 'file_mapping_rules': file_mapping_rules, 'enable_cdc': enable_cdc, 'recovery_model': recovery_model, 'mirroring_state': mirroring_state, 'is_incremental_v2p': is_incremental_v2p, 'backup_frequency_minutes': backup_frequency_minutes, 'rman_channels_for_incremental_backup': rman_channels_for_incremental_backup, 'rman_files_per_set_for_incremental_backup': rman_files_per_set_for_incremental_backup, 'rman_file_section_size_in_gb_for_incremental_backup': rman_file_section_size_in_gb_for_incremental_backup, 'default_data_diskgroup': default_data_diskgroup, 'redo_diskgroup': redo_diskgroup, 'rman_channels': rman_channels, 'rman_file_section_size_in_gb': rman_file_section_size_in_gb, 'timeflow_id': timeflow_id, 'timestamp': timestamp}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'export_vdb_to_asm_by_location':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action export_vdb_to_asm_by_location'}
        endpoint = f'/vdbs/{vdb_id}/asm-export-by-location'
        params = build_params(location=location, default_data_diskgroup=default_data_diskgroup)
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'unique_name': unique_name, 'database_name': database_name, 'repository_id': repository_id, 'environment_user_ref': environment_user_ref, 'tde_keystore_password': tde_keystore_password, 'tde_keystore_config_type': tde_keystore_config_type, 'oracle_instance_name': oracle_instance_name, 'instance_number': instance_number, 'instances': instances, 'mount_base': mount_base, 'config_params': config_params, 'cdb_id': cdb_id, 'parent_tde_keystore_path': parent_tde_keystore_path, 'parent_tde_keystore_password': parent_tde_keystore_password, 'tde_exported_keyfile_secret': tde_exported_keyfile_secret, 'tde_key_identifier': tde_key_identifier, 'parent_pdb_tde_keystore_path': parent_pdb_tde_keystore_path, 'parent_pdb_tde_keystore_password': parent_pdb_tde_keystore_password, 'target_pdb_tde_keystore_password': target_pdb_tde_keystore_password, 'crs_database_name': crs_database_name, 'recover_database': recover_database, 'file_mapping_rules': file_mapping_rules, 'enable_cdc': enable_cdc, 'recovery_model': recovery_model, 'mirroring_state': mirroring_state, 'is_incremental_v2p': is_incremental_v2p, 'backup_frequency_minutes': backup_frequency_minutes, 'rman_channels_for_incremental_backup': rman_channels_for_incremental_backup, 'rman_files_per_set_for_incremental_backup': rman_files_per_set_for_incremental_backup, 'rman_file_section_size_in_gb_for_incremental_backup': rman_file_section_size_in_gb_for_incremental_backup, 'default_data_diskgroup': default_data_diskgroup, 'redo_diskgroup': redo_diskgroup, 'rman_channels': rman_channels, 'rman_file_section_size_in_gb': rman_file_section_size_in_gb, 'location': location}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'export_vdb_to_asm_from_bookmark':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action export_vdb_to_asm_from_bookmark'}
        endpoint = f'/vdbs/{vdb_id}/asm-export-from-bookmark'
        params = build_params(default_data_diskgroup=default_data_diskgroup)
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'unique_name': unique_name, 'database_name': database_name, 'repository_id': repository_id, 'environment_user_ref': environment_user_ref, 'tde_keystore_password': tde_keystore_password, 'tde_keystore_config_type': tde_keystore_config_type, 'oracle_instance_name': oracle_instance_name, 'instance_number': instance_number, 'instances': instances, 'mount_base': mount_base, 'config_params': config_params, 'cdb_id': cdb_id, 'parent_tde_keystore_path': parent_tde_keystore_path, 'parent_tde_keystore_password': parent_tde_keystore_password, 'tde_exported_keyfile_secret': tde_exported_keyfile_secret, 'tde_key_identifier': tde_key_identifier, 'parent_pdb_tde_keystore_path': parent_pdb_tde_keystore_path, 'parent_pdb_tde_keystore_password': parent_pdb_tde_keystore_password, 'target_pdb_tde_keystore_password': target_pdb_tde_keystore_password, 'crs_database_name': crs_database_name, 'recover_database': recover_database, 'file_mapping_rules': file_mapping_rules, 'enable_cdc': enable_cdc, 'recovery_model': recovery_model, 'mirroring_state': mirroring_state, 'is_incremental_v2p': is_incremental_v2p, 'backup_frequency_minutes': backup_frequency_minutes, 'rman_channels_for_incremental_backup': rman_channels_for_incremental_backup, 'rman_files_per_set_for_incremental_backup': rman_files_per_set_for_incremental_backup, 'rman_file_section_size_in_gb_for_incremental_backup': rman_file_section_size_in_gb_for_incremental_backup, 'default_data_diskgroup': default_data_diskgroup, 'redo_diskgroup': redo_diskgroup, 'rman_channels': rman_channels, 'rman_file_section_size_in_gb': rman_file_section_size_in_gb, 'bookmark_id': bookmark_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'export_cleanup':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action export_cleanup'}
        endpoint = f'/vdbs/{vdb_id}/export_cleanup'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'cleanup_target_physical_files': cleanup_target_physical_files, 'cleanup_target_container': cleanup_target_container}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'export_finalize':
        if vdb_id is None:
            return {'error': 'Missing required parameter: vdb_id for action export_finalize'}
        endpoint = f'/vdbs/{vdb_id}/export_finalize'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'force': force, 'max_allowed_backups_pending_restore': max_allowed_backups_pending_restore}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'list_vdb_groups':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('GET', '/vdb-groups', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', '/vdb-groups', params=params)
    elif action == 'search_vdb_groups':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('POST', '/vdb-groups/search', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/vdb-groups/search', params=params, json_body=body)
    elif action == 'get_vdb_group':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action get_vdb_group'}
        endpoint = f'/vdb-groups/{vdb_group_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'create_vdb_group':
        params = build_params(name=name)
        conf = check_confirmation('POST', '/vdb-groups', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name, 'vdb_ids': vdb_ids, 'vdbs': vdbs, 'tags': tags, 'make_current_account_owner': make_current_account_owner, 'refresh_immediately': refresh_immediately}.items() if v is not None}
        return make_api_request('POST', '/vdb-groups', params=params, json_body=body if body else None)
    elif action == 'update_vdb_group':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action update_vdb_group'}
        endpoint = f'/vdb-groups/{vdb_group_id}'
        params = build_params()
        conf = check_confirmation('PATCH', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name, 'vdb_ids': vdb_ids, 'vdbs': vdbs, 'refresh_immediately': refresh_immediately}.items() if v is not None}
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_vdb_group':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action delete_vdb_group'}
        endpoint = f'/vdb-groups/{vdb_group_id}'
        params = build_params()
        conf = check_confirmation('DELETE', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'provision_vdb_group_from_bookmark':
        params = build_params(name=name, provision_parameters=provision_parameters)
        conf = check_confirmation('POST', '/vdb-groups/provision_from_bookmark', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name, 'bookmark_id': bookmark_id, 'provision_parameters': provision_parameters, 'tags': tags, 'make_current_account_owner': make_current_account_owner}.items() if v is not None}
        return make_api_request('POST', '/vdb-groups/provision_from_bookmark', params=params, json_body=body if body else None)
    elif action == 'refresh_vdb_group':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action refresh_vdb_group'}
        endpoint = f'/vdb-groups/{vdb_group_id}/refresh'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'bookmark_id': bookmark_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'refresh_vdb_group_from_bookmark':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action refresh_vdb_group_from_bookmark'}
        endpoint = f'/vdb-groups/{vdb_group_id}/refresh_from_bookmark'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'bookmark_id': bookmark_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'refresh_vdb_group_by_snapshot':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action refresh_vdb_group_by_snapshot'}
        endpoint = f'/vdb-groups/{vdb_group_id}/refresh_by_snapshot'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'vdb_snapshot_mappings': vdb_snapshot_mappings}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'refresh_vdb_group_by_timestamp':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action refresh_vdb_group_by_timestamp'}
        endpoint = f'/vdb-groups/{vdb_group_id}/refresh_by_timestamp'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'vdb_timestamp_mappings': vdb_timestamp_mappings, 'is_refresh_to_nearest': is_refresh_to_nearest}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'rollback_vdb_group':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action rollback_vdb_group'}
        endpoint = f'/vdb-groups/{vdb_group_id}/rollback'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'bookmark_id': bookmark_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'lock_vdb_group':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action lock_vdb_group'}
        endpoint = f'/vdb-groups/{vdb_group_id}/lock'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'account_id': account_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'unlock_vdb_group':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action unlock_vdb_group'}
        endpoint = f'/vdb-groups/{vdb_group_id}/unlock'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'start_vdb_group':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action start_vdb_group'}
        endpoint = f'/vdb-groups/{vdb_group_id}/start'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'vdb_start_param_mappings': vdb_start_param_mappings}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'stop_vdb_group':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action stop_vdb_group'}
        endpoint = f'/vdb-groups/{vdb_group_id}/stop'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'vdb_stop_param_mappings': vdb_stop_param_mappings}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'enable_vdb_group':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action enable_vdb_group'}
        endpoint = f'/vdb-groups/{vdb_group_id}/enable'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'vdb_enable_param_mappings': vdb_enable_param_mappings}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'disable_vdb_group':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action disable_vdb_group'}
        endpoint = f'/vdb-groups/{vdb_group_id}/disable'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'vdb_disable_param_mappings': vdb_disable_param_mappings}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'get_vdb_group_latest_snapshots':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action get_vdb_group_latest_snapshots'}
        endpoint = f'/vdb-groups/{vdb_group_id}/latest-snapshots'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'get_vdb_group_timestamp_summary':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action get_vdb_group_timestamp_summary'}
        endpoint = f'/vdb-groups/{vdb_group_id}/timestamp-summary'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'timestamp': timestamp, 'vdb_ids': vdb_ids, 'mode': mode}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'list_vdb_group_bookmarks':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action list_vdb_group_bookmarks'}
        endpoint = f'/vdb-groups/{vdb_group_id}/bookmarks'
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('GET', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'search_vdb_group_bookmarks':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action search_vdb_group_bookmarks'}
        endpoint = f'/vdb-groups/{vdb_group_id}/bookmarks/search'
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', endpoint, params=params, json_body=body)
    elif action == 'get_vdb_group_tags':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action get_vdb_group_tags'}
        endpoint = f'/vdb-groups/{vdb_group_id}/tags'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_vdb_group_tags':
        if vdb_group_id is None:
            return {'error': 'Missing required parameter: vdb_group_id for action add_vdb_group_tags'}
        endpoint = f'/vdb-groups/{vdb_group_id}/tags'
        params = build_params(tags=tags)
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'list_dsources':
        params = build_params(limit=limit, cursor=cursor, sort=sort, permission=permission)
        conf = check_confirmation('GET', '/dsources', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', '/dsources', params=params)
    elif action == 'search_dsources':
        params = build_params(limit=limit, cursor=cursor, sort=sort, permission=permission)
        conf = check_confirmation('POST', '/dsources/search', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/dsources/search', params=params, json_body=body)
    elif action == 'get_dsource':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action get_dsource'}
        endpoint = f'/dsources/{dsource_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'delete_dsource':
        params = build_params()
        conf = check_confirmation('POST', '/dsources/delete', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'dsource_id': dsource_id, 'force': force, 'oracle_username': oracle_username, 'oracle_password': oracle_password, 'delete_all_dependent_vdbs': delete_all_dependent_vdbs}.items() if v is not None}
        return make_api_request('POST', '/dsources/delete', params=params, json_body=body if body else None)
    elif action == 'enable_dsource':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action enable_dsource'}
        endpoint = f'/dsources/{dsource_id}/enable'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'attempt_start': attempt_start}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'disable_dsource':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action disable_dsource'}
        endpoint = f'/dsources/{dsource_id}/disable'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'attempt_cleanup': attempt_cleanup}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'list_dsource_snapshots':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action list_dsource_snapshots'}
        endpoint = f'/dsources/{dsource_id}/snapshots'
        params = build_params(limit=limit, cursor=cursor)
        conf = check_confirmation('GET', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'dsource_create_snapshot':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action dsource_create_snapshot'}
        endpoint = f'/dsources/{dsource_id}/snapshots'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'drop_and_recreate_devices': drop_and_recreate_devices, 'sync_strategy': sync_strategy, 'ase_backup_files': ase_backup_files, 'mssql_backup_uuid': mssql_backup_uuid, 'compression_enabled': compression_enabled, 'availability_group_backup_policy': availability_group_backup_policy, 'do_not_resume': do_not_resume, 'double_sync': double_sync, 'force_full_backup': force_full_backup, 'skip_space_check': skip_space_check, 'files_for_partial_full_backup': files_for_partial_full_backup, 'appdata_parameters': appdata_parameters, 'rman_rate_in_MB': rman_rate_in__m_b}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'upgrade_dsource':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action upgrade_dsource'}
        endpoint = f'/dsources/{dsource_id}/upgrade'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'repository_id': repository_id, 'environment_user_id': environment_user_id, 'ppt_repository': ppt_repository}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'get_dsource_upgrade_compatible_repositories':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action get_dsource_upgrade_compatible_repositories'}
        endpoint = f'/dsources/{dsource_id}/upgrade_compatible_repositories'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'get_dsource_deletion_dependencies':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action get_dsource_deletion_dependencies'}
        endpoint = f'/dsources/{dsource_id}/deletion-dependencies'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'get_dsource_tags':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action get_dsource_tags'}
        endpoint = f'/dsources/{dsource_id}/tags'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_dsource_tags':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action add_dsource_tags'}
        endpoint = f'/dsources/{dsource_id}/tags'
        params = build_params(tags=tags)
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_dsource_tags':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action delete_dsource_tags'}
        endpoint = f'/dsources/{dsource_id}/tags/delete'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'dsource_link_oracle':
        params = build_params()
        conf = check_confirmation('POST', '/dsources/oracle', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name, 'source_id': source_id, 'group_id': group_id, 'description': description, 'log_sync_enabled': log_sync_enabled, 'sync_policy_id': sync_policy_id, 'retention_policy_id': retention_policy_id, 'make_current_account_owner': make_current_account_owner, 'tags': tags, 'ops_pre_sync': ops_pre_sync, 'ops_post_sync': ops_post_sync, 'external_file_path': external_file_path, 'environment_user_id': environment_user_id, 'backup_level_enabled': backup_level_enabled, 'rman_channels': rman_channels, 'files_per_set': files_per_set, 'check_logical': check_logical, 'encrypted_linking_enabled': encrypted_linking_enabled, 'compressed_linking_enabled': compressed_linking_enabled, 'bandwidth_limit': bandwidth_limit, 'number_of_connections': number_of_connections, 'diagnose_no_logging_faults': diagnose_no_logging_faults, 'pre_provisioning_enabled': pre_provisioning_enabled, 'link_now': link_now, 'force_full_backup': force_full_backup, 'double_sync': double_sync, 'rman_rate_in_MB': rman_rate_in__m_b, 'skip_space_check': skip_space_check, 'do_not_resume': do_not_resume, 'files_for_full_backup': files_for_full_backup, 'log_sync_mode': log_sync_mode, 'log_sync_interval': log_sync_interval, 'non_sys_username': non_sys_username, 'non_sys_password': non_sys_password, 'non_sys_vault_username': non_sys_vault_username, 'non_sys_vault': non_sys_vault, 'non_sys_hashicorp_vault_engine': non_sys_hashicorp_vault_engine, 'non_sys_hashicorp_vault_secret_path': non_sys_hashicorp_vault_secret_path, 'non_sys_hashicorp_vault_username_key': non_sys_hashicorp_vault_username_key, 'non_sys_hashicorp_vault_secret_key': non_sys_hashicorp_vault_secret_key, 'non_sys_azure_vault_name': non_sys_azure_vault_name, 'non_sys_azure_vault_username_key': non_sys_azure_vault_username_key, 'non_sys_azure_vault_secret_key': non_sys_azure_vault_secret_key, 'non_sys_cyberark_vault_query_string': non_sys_cyberark_vault_query_string, 'fallback_username': fallback_username, 'fallback_password': fallback_password, 'fallback_vault_username': fallback_vault_username, 'fallback_vault': fallback_vault, 'fallback_hashicorp_vault_engine': fallback_hashicorp_vault_engine, 'fallback_hashicorp_vault_secret_path': fallback_hashicorp_vault_secret_path, 'fallback_hashicorp_vault_username_key': fallback_hashicorp_vault_username_key, 'fallback_hashicorp_vault_secret_key': fallback_hashicorp_vault_secret_key, 'fallback_azure_vault_name': fallback_azure_vault_name, 'fallback_azure_vault_username_key': fallback_azure_vault_username_key, 'fallback_azure_vault_secret_key': fallback_azure_vault_secret_key, 'fallback_cyberark_vault_query_string': fallback_cyberark_vault_query_string, 'ops_pre_log_sync': ops_pre_log_sync}.items() if v is not None}
        return make_api_request('POST', '/dsources/oracle', params=params, json_body=body if body else None)
    elif action == 'dsource_link_oracle_defaults':
        params = build_params()
        conf = check_confirmation('POST', '/dsources/oracle/defaults', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'source_id': source_id}.items() if v is not None}
        return make_api_request('POST', '/dsources/oracle/defaults', params=params, json_body=body if body else None)
    elif action == 'dsource_link_oracle_staging_push':
        params = build_params()
        conf = check_confirmation('POST', '/dsources/oracle/staging-push', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name, 'source_id': source_id, 'group_id': group_id, 'description': description, 'log_sync_enabled': log_sync_enabled, 'sync_policy_id': sync_policy_id, 'retention_policy_id': retention_policy_id, 'make_current_account_owner': make_current_account_owner, 'tags': tags, 'ops_pre_sync': ops_pre_sync, 'ops_post_sync': ops_post_sync, 'engine_id': engine_id, 'container_type': container_type, 'environment_user_id': environment_user_id, 'repository': repository, 'database_name': database_name, 'database_unique_name': database_unique_name, 'sid': sid, 'mount_base': mount_base, 'custom_env_variables_pairs': custom_env_variables_pairs, 'custom_env_variables_paths': custom_env_variables_paths, 'auto_staging_restart': auto_staging_restart, 'allow_auto_staging_restart_on_host_reboot': allow_auto_staging_restart_on_host_reboot, 'physical_standby': physical_standby, 'validate_snapshot_in_readonly': validate_snapshot_in_readonly, 'validate_by_opening_db_in_read_only_mode': validate_by_opening_db_in_read_only_mode, 'staging_database_templates': staging_database_templates, 'staging_database_config_params': staging_database_config_params, 'staging_container_database_reference': staging_container_database_reference, 'ops_pre_log_sync': ops_pre_log_sync, 'tde_keystore_config_type': tde_keystore_config_type, 'template_id': template_id}.items() if v is not None}
        return make_api_request('POST', '/dsources/oracle/staging-push', params=params, json_body=body if body else None)
    elif action == 'dsource_link_oracle_staging_push_defaults':
        params = build_params()
        conf = check_confirmation('POST', '/dsources/oracle/staging-push/defaults', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'environment_id': environment_id, 'container_type': container_type}.items() if v is not None}
        return make_api_request('POST', '/dsources/oracle/staging-push/defaults', params=params, json_body=body if body else None)
    elif action == 'update_oracle_dsource':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action update_oracle_dsource'}
        endpoint = f'/dsources/oracle/{dsource_id}'
        params = build_params()
        conf = check_confirmation('PATCH', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name, 'description': description, 'db_username': db_username, 'db_password': db_password, 'non_sys_username': non_sys_username, 'non_sys_password': non_sys_password, 'validate_db_credentials': validate_db_credentials, 'environment_user_id': environment_user_id, 'backup_level_enabled': backup_level_enabled, 'rman_channels': rman_channels, 'files_per_set': files_per_set, 'check_logical': check_logical, 'encrypted_linking_enabled': encrypted_linking_enabled, 'compressed_linking_enabled': compressed_linking_enabled, 'bandwidth_limit': bandwidth_limit, 'number_of_connections': number_of_connections, 'validate_by_opening_db_in_read_only_mode': validate_by_opening_db_in_read_only_mode, 'pre_provisioning_enabled': pre_provisioning_enabled, 'diagnose_no_logging_faults': diagnose_no_logging_faults, 'rac_max_instance_lag': rac_max_instance_lag, 'allow_auto_staging_restart_on_host_reboot': allow_auto_staging_restart_on_host_reboot, 'physical_standby': physical_standby, 'external_file_path': external_file_path, 'hooks': hooks, 'custom_env_variables_pairs': custom_env_variables_pairs, 'custom_env_variables_paths': custom_env_variables_paths, 'staging_database_config_params': staging_database_config_params, 'template_id': template_id, 'logsync_enabled': logsync_enabled, 'logsync_mode': logsync_mode, 'logsync_interval': logsync_interval, 'repository': repository}.items() if v is not None}
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'attach_oracle_dsource':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action attach_oracle_dsource'}
        endpoint = f'/dsources/oracle/{dsource_id}/attachSource'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'backup_level_enabled': backup_level_enabled, 'bandwidth_limit': bandwidth_limit, 'check_logical': check_logical, 'compressed_linking_enabled': compressed_linking_enabled, 'double_sync': double_sync, 'encrypted_linking_enabled': encrypted_linking_enabled, 'environment_user': environment_user, 'external_file_path': external_file_path, 'files_per_set': files_per_set, 'force': force, 'link_now': link_now, 'number_of_connections': number_of_connections, 'operations': operations, 'oracle_fallback_user': oracle_fallback_user, 'oracle_fallback_credentials': oracle_fallback_credentials, 'rman_channels': rman_channels, 'source_id': source_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'detach_oracle_dsource':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action detach_oracle_dsource'}
        endpoint = f'/dsources/oracle/{dsource_id}/detachSource'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'upgrade_oracle_dsource':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action upgrade_oracle_dsource'}
        endpoint = f'/dsources/oracle/{dsource_id}/upgrade'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'repository_id': repository_id, 'environment_user_id': environment_user_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'dsource_link_ase':
        params = build_params()
        conf = check_confirmation('POST', '/dsources/ase', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name, 'source_id': source_id, 'group_id': group_id, 'description': description, 'log_sync_enabled': log_sync_enabled, 'sync_policy_id': sync_policy_id, 'retention_policy_id': retention_policy_id, 'make_current_account_owner': make_current_account_owner, 'tags': tags, 'ops_pre_sync': ops_pre_sync, 'ops_post_sync': ops_post_sync, 'external_file_path': external_file_path, 'mount_base': mount_base, 'load_backup_path': load_backup_path, 'backup_server_name': backup_server_name, 'backup_host_user': backup_host_user, 'backup_host': backup_host, 'dump_credentials': dump_credentials, 'source_host_user': source_host_user, 'db_user': db_user, 'db_password': db_password, 'db_vault_username': db_vault_username, 'db_vault': db_vault, 'db_hashicorp_vault_engine': db_hashicorp_vault_engine, 'db_hashicorp_vault_secret_path': db_hashicorp_vault_secret_path, 'db_hashicorp_vault_username_key': db_hashicorp_vault_username_key, 'db_hashicorp_vault_secret_key': db_hashicorp_vault_secret_key, 'db_azure_vault_name': db_azure_vault_name, 'db_azure_vault_username_key': db_azure_vault_username_key, 'db_azure_vault_secret_key': db_azure_vault_secret_key, 'db_cyberark_vault_query_string': db_cyberark_vault_query_string, 'staging_repository': staging_repository, 'staging_host_user': staging_host_user, 'validated_sync_mode': validated_sync_mode, 'dump_history_file_enabled': dump_history_file_enabled, 'drop_and_recreate_devices': drop_and_recreate_devices, 'sync_strategy': sync_strategy, 'ase_backup_files': ase_backup_files, 'pre_validated_sync': pre_validated_sync, 'post_validated_sync': post_validated_sync}.items() if v is not None}
        return make_api_request('POST', '/dsources/ase', params=params, json_body=body if body else None)
    elif action == 'dsource_link_ase_defaults':
        params = build_params()
        conf = check_confirmation('POST', '/dsources/ase/defaults', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'source_id': source_id}.items() if v is not None}
        return make_api_request('POST', '/dsources/ase/defaults', params=params, json_body=body if body else None)
    elif action == 'update_ase_dsource':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action update_ase_dsource'}
        endpoint = f'/dsources/ase/{dsource_id}'
        params = build_params()
        conf = check_confirmation('PATCH', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name, 'description': description, 'sync_policy_id': sync_policy_id, 'retention_policy_id': retention_policy_id, 'hooks': hooks}.items() if v is not None}
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'dsource_link_appdata':
        params = build_params()
        conf = check_confirmation('POST', '/dsources/appdata', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name, 'source_id': source_id, 'group_id': group_id, 'description': description, 'log_sync_enabled': log_sync_enabled, 'sync_policy_id': sync_policy_id, 'retention_policy_id': retention_policy_id, 'make_current_account_owner': make_current_account_owner, 'tags': tags, 'ops_pre_sync': ops_pre_sync, 'ops_post_sync': ops_post_sync, 'link_type': link_type, 'staging_mount_base': staging_mount_base, 'staging_environment': staging_environment, 'staging_environment_user': staging_environment_user, 'environment_user': environment_user, 'excludes': excludes, 'follow_symlinks': follow_symlinks, 'parameters': parameters, 'sync_parameters': sync_parameters}.items() if v is not None}
        return make_api_request('POST', '/dsources/appdata', params=params, json_body=body if body else None)
    elif action == 'dsource_link_appdata_defaults':
        params = build_params()
        conf = check_confirmation('POST', '/dsources/appdata/defaults', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'source_id': source_id}.items() if v is not None}
        return make_api_request('POST', '/dsources/appdata/defaults', params=params, json_body=body if body else None)
    elif action == 'update_appdata_dsource':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action update_appdata_dsource'}
        endpoint = f'/dsources/appdata/{dsource_id}'
        params = build_params()
        conf = check_confirmation('PATCH', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name, 'description': description, 'staging_environment': staging_environment, 'staging_environment_user': staging_environment_user, 'environment_user': environment_user, 'parameters': parameters, 'sync_policy_id': sync_policy_id, 'retention_policy_id': retention_policy_id, 'ops_pre_sync': ops_pre_sync, 'ops_post_sync': ops_post_sync, 'hooks': hooks}.items() if v is not None}
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'dsource_link_mssql':
        params = build_params()
        conf = check_confirmation('POST', '/dsources/mssql', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name, 'source_id': source_id, 'group_id': group_id, 'description': description, 'log_sync_enabled': log_sync_enabled, 'sync_policy_id': sync_policy_id, 'retention_policy_id': retention_policy_id, 'make_current_account_owner': make_current_account_owner, 'tags': tags, 'ops_pre_sync': ops_pre_sync, 'ops_post_sync': ops_post_sync, 'encryption_key': encryption_key, 'sync_strategy': sync_strategy, 'mssql_backup_uuid': mssql_backup_uuid, 'compression_enabled': compression_enabled, 'availability_group_backup_policy': availability_group_backup_policy, 'source_host_user': source_host_user, 'ppt_repository': ppt_repository, 'ppt_host_user': ppt_host_user, 'staging_pre_script': staging_pre_script, 'staging_post_script': staging_post_script, 'sync_strategy_managed_type': sync_strategy_managed_type, 'mssql_user_environment_reference': mssql_user_environment_reference, 'mssql_user_domain_username': mssql_user_domain_username, 'mssql_user_domain_password': mssql_user_domain_password, 'mssql_user_domain_vault_username': mssql_user_domain_vault_username, 'mssql_user_domain_vault': mssql_user_domain_vault, 'mssql_user_domain_hashicorp_vault_engine': mssql_user_domain_hashicorp_vault_engine, 'mssql_user_domain_hashicorp_vault_secret_path': mssql_user_domain_hashicorp_vault_secret_path, 'mssql_user_domain_hashicorp_vault_username_key': mssql_user_domain_hashicorp_vault_username_key, 'mssql_user_domain_hashicorp_vault_secret_key': mssql_user_domain_hashicorp_vault_secret_key, 'mssql_user_domain_azure_vault_name': mssql_user_domain_azure_vault_name, 'mssql_user_domain_azure_vault_username_key': mssql_user_domain_azure_vault_username_key, 'mssql_user_domain_azure_vault_secret_key': mssql_user_domain_azure_vault_secret_key, 'mssql_user_domain_cyberark_vault_query_string': mssql_user_domain_cyberark_vault_query_string, 'mssql_database_username': mssql_database_username, 'mssql_database_password': mssql_database_password, 'delphix_managed_backup_compression_enabled': delphix_managed_backup_compression_enabled, 'delphix_managed_backup_policy': delphix_managed_backup_policy, 'external_managed_validate_sync_mode': external_managed_validate_sync_mode, 'external_managed_shared_backup_locations': external_managed_shared_backup_locations, 'external_netbackup_config_master_name': external_netbackup_config_master_name, 'external_netbackup_config_source_client_name': external_netbackup_config_source_client_name, 'external_netbackup_config_params': external_netbackup_config_params, 'external_netbackup_config_templates': external_netbackup_config_templates, 'external_commserve_host_name': external_commserve_host_name, 'external_commvault_config_source_client_name': external_commvault_config_source_client_name, 'external_commvault_config_staging_client_name': external_commvault_config_staging_client_name, 'external_commvault_config_params': external_commvault_config_params, 'external_commvault_config_templates': external_commvault_config_templates}.items() if v is not None}
        return make_api_request('POST', '/dsources/mssql', params=params, json_body=body if body else None)
    elif action == 'dsource_link_mssql_defaults':
        params = build_params()
        conf = check_confirmation('POST', '/dsources/mssql/defaults', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'source_id': source_id}.items() if v is not None}
        return make_api_request('POST', '/dsources/mssql/defaults', params=params, json_body=body if body else None)
    elif action == 'dsource_link_mssql_staging_push':
        params = build_params()
        conf = check_confirmation('POST', '/dsources/mssql/staging-push', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name, 'source_id': source_id, 'group_id': group_id, 'description': description, 'log_sync_enabled': log_sync_enabled, 'sync_policy_id': sync_policy_id, 'retention_policy_id': retention_policy_id, 'make_current_account_owner': make_current_account_owner, 'tags': tags, 'ops_pre_sync': ops_pre_sync, 'ops_post_sync': ops_post_sync, 'engine_id': engine_id, 'encryption_key': encryption_key, 'ppt_repository': ppt_repository, 'ppt_host_user': ppt_host_user, 'staging_pre_script': staging_pre_script, 'staging_post_script': staging_post_script, 'staging_database_name': staging_database_name, 'db_state': db_state}.items() if v is not None}
        return make_api_request('POST', '/dsources/mssql/staging-push', params=params, json_body=body if body else None)
    elif action == 'dsource_link_mssql_staging_push_defaults':
        params = build_params()
        conf = check_confirmation('POST', '/dsources/mssql/staging-push/defaults', action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'environment_id': environment_id}.items() if v is not None}
        return make_api_request('POST', '/dsources/mssql/staging-push/defaults', params=params, json_body=body if body else None)
    elif action == 'attach_mssql_staging_push_dsource':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action attach_mssql_staging_push_dsource'}
        endpoint = f'/dsources/mssql/staging-push/{dsource_id}/attachSource'
        params = build_params(ppt_repository=ppt_repository, staging_database_name=staging_database_name)
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'encryption_key': encryption_key, 'ppt_repository': ppt_repository, 'ppt_host_user': ppt_host_user, 'staging_pre_script': staging_pre_script, 'staging_post_script': staging_post_script, 'staging_database_name': staging_database_name, 'db_state': db_state, 'ops_pre_sync': ops_pre_sync, 'ops_post_sync': ops_post_sync}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'update_mssql_dsource':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action update_mssql_dsource'}
        endpoint = f'/dsources/mssql/{dsource_id}'
        params = build_params()
        conf = check_confirmation('PATCH', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name, 'logsync_enabled': logsync_enabled, 'encryption_key': encryption_key, 'ppt_repository': ppt_repository, 'ppt_host_user': ppt_host_user, 'sync_strategy_managed_type': sync_strategy_managed_type, 'source_host_user': source_host_user, 'mssql_user_environment_reference': mssql_user_environment_reference, 'mssql_user_domain_username': mssql_user_domain_username, 'mssql_user_domain_password': mssql_user_domain_password, 'mssql_user_domain_vault_username': mssql_user_domain_vault_username, 'mssql_user_domain_vault': mssql_user_domain_vault, 'mssql_user_domain_hashicorp_vault_engine': mssql_user_domain_hashicorp_vault_engine, 'mssql_user_domain_hashicorp_vault_secret_path': mssql_user_domain_hashicorp_vault_secret_path, 'mssql_user_domain_hashicorp_vault_username_key': mssql_user_domain_hashicorp_vault_username_key, 'mssql_user_domain_hashicorp_vault_secret_key': mssql_user_domain_hashicorp_vault_secret_key, 'mssql_user_domain_azure_vault_name': mssql_user_domain_azure_vault_name, 'mssql_user_domain_azure_vault_username_key': mssql_user_domain_azure_vault_username_key, 'mssql_user_domain_azure_vault_secret_key': mssql_user_domain_azure_vault_secret_key, 'mssql_user_domain_cyberark_vault_query_string': mssql_user_domain_cyberark_vault_query_string, 'mssql_database_username': mssql_database_username, 'mssql_database_password': mssql_database_password, 'delphix_managed_backup_compression_enabled': delphix_managed_backup_compression_enabled, 'delphix_managed_backup_policy': delphix_managed_backup_policy, 'external_managed_validate_sync_mode': external_managed_validate_sync_mode, 'external_managed_shared_backup_locations': external_managed_shared_backup_locations, 'disable_netbackup_config': disable_netbackup_config, 'external_netbackup_config_master_name': external_netbackup_config_master_name, 'external_netbackup_config_source_client_name': external_netbackup_config_source_client_name, 'external_netbackup_config_params': external_netbackup_config_params, 'external_netbackup_config_templates': external_netbackup_config_templates, 'disable_commvault_config': disable_commvault_config, 'external_commserve_host_name': external_commserve_host_name, 'external_commvault_config_source_client_name': external_commvault_config_source_client_name, 'external_commvault_config_staging_client_name': external_commvault_config_staging_client_name, 'external_commvault_config_params': external_commvault_config_params, 'external_commvault_config_templates': external_commvault_config_templates, 'hooks': hooks, 'sync_policy_id': sync_policy_id, 'retention_policy_id': retention_policy_id}.items() if v is not None}
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'attach_mssql_dsource':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action attach_mssql_dsource'}
        endpoint = f'/dsources/mssql/{dsource_id}/attachSource'
        params = build_params(ppt_repository=ppt_repository)
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'source_id': source_id, 'ppt_repository': ppt_repository, 'sync_strategy_managed_type': sync_strategy_managed_type, 'mssql_user_environment_reference': mssql_user_environment_reference, 'mssql_user_domain_username': mssql_user_domain_username, 'mssql_user_domain_password': mssql_user_domain_password, 'mssql_user_domain_vault_username': mssql_user_domain_vault_username, 'mssql_user_domain_vault': mssql_user_domain_vault, 'mssql_user_domain_hashicorp_vault_engine': mssql_user_domain_hashicorp_vault_engine, 'mssql_user_domain_hashicorp_vault_secret_path': mssql_user_domain_hashicorp_vault_secret_path, 'mssql_user_domain_hashicorp_vault_username_key': mssql_user_domain_hashicorp_vault_username_key, 'mssql_user_domain_hashicorp_vault_secret_key': mssql_user_domain_hashicorp_vault_secret_key, 'mssql_user_domain_azure_vault_name': mssql_user_domain_azure_vault_name, 'mssql_user_domain_azure_vault_username_key': mssql_user_domain_azure_vault_username_key, 'mssql_user_domain_azure_vault_secret_key': mssql_user_domain_azure_vault_secret_key, 'mssql_user_domain_cyberark_vault_query_string': mssql_user_domain_cyberark_vault_query_string, 'mssql_database_username': mssql_database_username, 'mssql_database_password': mssql_database_password, 'delphix_managed_backup_compression_enabled': delphix_managed_backup_compression_enabled, 'delphix_managed_backup_policy': delphix_managed_backup_policy, 'external_managed_validate_sync_mode': external_managed_validate_sync_mode, 'external_managed_shared_backup_locations': external_managed_shared_backup_locations, 'external_netbackup_config_master_name': external_netbackup_config_master_name, 'external_netbackup_config_source_client_name': external_netbackup_config_source_client_name, 'external_netbackup_config_params': external_netbackup_config_params, 'external_netbackup_config_templates': external_netbackup_config_templates, 'external_commserve_host_name': external_commserve_host_name, 'external_commvault_config_source_client_name': external_commvault_config_source_client_name, 'external_commvault_config_staging_client_name': external_commvault_config_staging_client_name, 'external_commvault_config_params': external_commvault_config_params, 'external_commvault_config_templates': external_commvault_config_templates, 'encryption_key': encryption_key, 'source_host_user': source_host_user, 'ppt_host_user': ppt_host_user, 'staging_pre_script': staging_pre_script, 'staging_post_script': staging_post_script, 'ops_pre_sync': ops_pre_sync, 'ops_post_sync': ops_post_sync}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'detach_mssql_dsource':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action detach_mssql_dsource'}
        endpoint = f'/dsources/mssql/{dsource_id}/detachSource'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'export_dsource_by_snapshot':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action export_dsource_by_snapshot'}
        endpoint = f'/dsources/{dsource_id}/export-by-snapshot'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'unique_name': unique_name, 'database_name': database_name, 'repository_id': repository_id, 'environment_user_ref': environment_user_ref, 'tde_keystore_password': tde_keystore_password, 'tde_keystore_config_type': tde_keystore_config_type, 'oracle_instance_name': oracle_instance_name, 'instance_number': instance_number, 'instances': instances, 'mount_base': mount_base, 'config_params': config_params, 'cdb_id': cdb_id, 'parent_tde_keystore_path': parent_tde_keystore_path, 'parent_tde_keystore_password': parent_tde_keystore_password, 'tde_exported_keyfile_secret': tde_exported_keyfile_secret, 'tde_key_identifier': tde_key_identifier, 'parent_pdb_tde_keystore_path': parent_pdb_tde_keystore_path, 'parent_pdb_tde_keystore_password': parent_pdb_tde_keystore_password, 'target_pdb_tde_keystore_password': target_pdb_tde_keystore_password, 'crs_database_name': crs_database_name, 'recover_database': recover_database, 'file_mapping_rules': file_mapping_rules, 'enable_cdc': enable_cdc, 'recovery_model': recovery_model, 'mirroring_state': mirroring_state, 'is_incremental_v2p': is_incremental_v2p, 'backup_frequency_minutes': backup_frequency_minutes, 'rman_channels_for_incremental_backup': rman_channels_for_incremental_backup, 'rman_files_per_set_for_incremental_backup': rman_files_per_set_for_incremental_backup, 'rman_file_section_size_in_gb_for_incremental_backup': rman_file_section_size_in_gb_for_incremental_backup, 'targetDirectory': target_directory, 'dataDirectory': data_directory, 'archiveDirectory': archive_directory, 'externalDirectory': external_directory, 'tempDirectory': temp_directory, 'scriptDirectory': script_directory, 'useAbsolutePathForDataFiles': use_absolute_path_for_data_files, 'rman_channels': rman_channels, 'rman_file_section_size_in_gb': rman_file_section_size_in_gb, 'snapshot_id': snapshot_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'export_dsource_by_timestamp':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action export_dsource_by_timestamp'}
        endpoint = f'/dsources/{dsource_id}/export-by-timestamp'
        params = build_params(timestamp=timestamp)
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'unique_name': unique_name, 'database_name': database_name, 'repository_id': repository_id, 'environment_user_ref': environment_user_ref, 'tde_keystore_password': tde_keystore_password, 'tde_keystore_config_type': tde_keystore_config_type, 'oracle_instance_name': oracle_instance_name, 'instance_number': instance_number, 'instances': instances, 'mount_base': mount_base, 'config_params': config_params, 'cdb_id': cdb_id, 'parent_tde_keystore_path': parent_tde_keystore_path, 'parent_tde_keystore_password': parent_tde_keystore_password, 'tde_exported_keyfile_secret': tde_exported_keyfile_secret, 'tde_key_identifier': tde_key_identifier, 'parent_pdb_tde_keystore_path': parent_pdb_tde_keystore_path, 'parent_pdb_tde_keystore_password': parent_pdb_tde_keystore_password, 'target_pdb_tde_keystore_password': target_pdb_tde_keystore_password, 'crs_database_name': crs_database_name, 'recover_database': recover_database, 'file_mapping_rules': file_mapping_rules, 'enable_cdc': enable_cdc, 'recovery_model': recovery_model, 'mirroring_state': mirroring_state, 'is_incremental_v2p': is_incremental_v2p, 'backup_frequency_minutes': backup_frequency_minutes, 'rman_channels_for_incremental_backup': rman_channels_for_incremental_backup, 'rman_files_per_set_for_incremental_backup': rman_files_per_set_for_incremental_backup, 'rman_file_section_size_in_gb_for_incremental_backup': rman_file_section_size_in_gb_for_incremental_backup, 'targetDirectory': target_directory, 'dataDirectory': data_directory, 'archiveDirectory': archive_directory, 'externalDirectory': external_directory, 'tempDirectory': temp_directory, 'scriptDirectory': script_directory, 'useAbsolutePathForDataFiles': use_absolute_path_for_data_files, 'rman_channels': rman_channels, 'rman_file_section_size_in_gb': rman_file_section_size_in_gb, 'timeflow_id': timeflow_id, 'timestamp': timestamp}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'export_dsource_by_location':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action export_dsource_by_location'}
        endpoint = f'/dsources/{dsource_id}/export-by-location'
        params = build_params(location=location)
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'unique_name': unique_name, 'database_name': database_name, 'repository_id': repository_id, 'environment_user_ref': environment_user_ref, 'tde_keystore_password': tde_keystore_password, 'tde_keystore_config_type': tde_keystore_config_type, 'oracle_instance_name': oracle_instance_name, 'instance_number': instance_number, 'instances': instances, 'mount_base': mount_base, 'config_params': config_params, 'cdb_id': cdb_id, 'parent_tde_keystore_path': parent_tde_keystore_path, 'parent_tde_keystore_password': parent_tde_keystore_password, 'tde_exported_keyfile_secret': tde_exported_keyfile_secret, 'tde_key_identifier': tde_key_identifier, 'parent_pdb_tde_keystore_path': parent_pdb_tde_keystore_path, 'parent_pdb_tde_keystore_password': parent_pdb_tde_keystore_password, 'target_pdb_tde_keystore_password': target_pdb_tde_keystore_password, 'crs_database_name': crs_database_name, 'recover_database': recover_database, 'file_mapping_rules': file_mapping_rules, 'enable_cdc': enable_cdc, 'recovery_model': recovery_model, 'mirroring_state': mirroring_state, 'is_incremental_v2p': is_incremental_v2p, 'backup_frequency_minutes': backup_frequency_minutes, 'rman_channels_for_incremental_backup': rman_channels_for_incremental_backup, 'rman_files_per_set_for_incremental_backup': rman_files_per_set_for_incremental_backup, 'rman_file_section_size_in_gb_for_incremental_backup': rman_file_section_size_in_gb_for_incremental_backup, 'targetDirectory': target_directory, 'dataDirectory': data_directory, 'archiveDirectory': archive_directory, 'externalDirectory': external_directory, 'tempDirectory': temp_directory, 'scriptDirectory': script_directory, 'useAbsolutePathForDataFiles': use_absolute_path_for_data_files, 'rman_channels': rman_channels, 'rman_file_section_size_in_gb': rman_file_section_size_in_gb, 'location': location}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'export_dsource_from_bookmark':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action export_dsource_from_bookmark'}
        endpoint = f'/dsources/{dsource_id}/export-from-bookmark'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'unique_name': unique_name, 'database_name': database_name, 'repository_id': repository_id, 'environment_user_ref': environment_user_ref, 'tde_keystore_password': tde_keystore_password, 'tde_keystore_config_type': tde_keystore_config_type, 'oracle_instance_name': oracle_instance_name, 'instance_number': instance_number, 'instances': instances, 'mount_base': mount_base, 'config_params': config_params, 'cdb_id': cdb_id, 'parent_tde_keystore_path': parent_tde_keystore_path, 'parent_tde_keystore_password': parent_tde_keystore_password, 'tde_exported_keyfile_secret': tde_exported_keyfile_secret, 'tde_key_identifier': tde_key_identifier, 'parent_pdb_tde_keystore_path': parent_pdb_tde_keystore_path, 'parent_pdb_tde_keystore_password': parent_pdb_tde_keystore_password, 'target_pdb_tde_keystore_password': target_pdb_tde_keystore_password, 'crs_database_name': crs_database_name, 'recover_database': recover_database, 'file_mapping_rules': file_mapping_rules, 'enable_cdc': enable_cdc, 'recovery_model': recovery_model, 'mirroring_state': mirroring_state, 'is_incremental_v2p': is_incremental_v2p, 'backup_frequency_minutes': backup_frequency_minutes, 'rman_channels_for_incremental_backup': rman_channels_for_incremental_backup, 'rman_files_per_set_for_incremental_backup': rman_files_per_set_for_incremental_backup, 'rman_file_section_size_in_gb_for_incremental_backup': rman_file_section_size_in_gb_for_incremental_backup, 'targetDirectory': target_directory, 'dataDirectory': data_directory, 'archiveDirectory': archive_directory, 'externalDirectory': external_directory, 'tempDirectory': temp_directory, 'scriptDirectory': script_directory, 'useAbsolutePathForDataFiles': use_absolute_path_for_data_files, 'rman_channels': rman_channels, 'rman_file_section_size_in_gb': rman_file_section_size_in_gb, 'bookmark_id': bookmark_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'export_dsource_to_asm_by_snapshot':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action export_dsource_to_asm_by_snapshot'}
        endpoint = f'/dsources/{dsource_id}/asm-export-by-snapshot'
        params = build_params(default_data_diskgroup=default_data_diskgroup)
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'unique_name': unique_name, 'database_name': database_name, 'repository_id': repository_id, 'environment_user_ref': environment_user_ref, 'tde_keystore_password': tde_keystore_password, 'tde_keystore_config_type': tde_keystore_config_type, 'oracle_instance_name': oracle_instance_name, 'instance_number': instance_number, 'instances': instances, 'mount_base': mount_base, 'config_params': config_params, 'cdb_id': cdb_id, 'parent_tde_keystore_path': parent_tde_keystore_path, 'parent_tde_keystore_password': parent_tde_keystore_password, 'tde_exported_keyfile_secret': tde_exported_keyfile_secret, 'tde_key_identifier': tde_key_identifier, 'parent_pdb_tde_keystore_path': parent_pdb_tde_keystore_path, 'parent_pdb_tde_keystore_password': parent_pdb_tde_keystore_password, 'target_pdb_tde_keystore_password': target_pdb_tde_keystore_password, 'crs_database_name': crs_database_name, 'recover_database': recover_database, 'file_mapping_rules': file_mapping_rules, 'enable_cdc': enable_cdc, 'recovery_model': recovery_model, 'mirroring_state': mirroring_state, 'is_incremental_v2p': is_incremental_v2p, 'backup_frequency_minutes': backup_frequency_minutes, 'rman_channels_for_incremental_backup': rman_channels_for_incremental_backup, 'rman_files_per_set_for_incremental_backup': rman_files_per_set_for_incremental_backup, 'rman_file_section_size_in_gb_for_incremental_backup': rman_file_section_size_in_gb_for_incremental_backup, 'default_data_diskgroup': default_data_diskgroup, 'redo_diskgroup': redo_diskgroup, 'rman_channels': rman_channels, 'rman_file_section_size_in_gb': rman_file_section_size_in_gb, 'snapshot_id': snapshot_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'export_dsource_to_asm_by_timestamp':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action export_dsource_to_asm_by_timestamp'}
        endpoint = f'/dsources/{dsource_id}/asm-export-by-timestamp'
        params = build_params(timestamp=timestamp, default_data_diskgroup=default_data_diskgroup)
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'unique_name': unique_name, 'database_name': database_name, 'repository_id': repository_id, 'environment_user_ref': environment_user_ref, 'tde_keystore_password': tde_keystore_password, 'tde_keystore_config_type': tde_keystore_config_type, 'oracle_instance_name': oracle_instance_name, 'instance_number': instance_number, 'instances': instances, 'mount_base': mount_base, 'config_params': config_params, 'cdb_id': cdb_id, 'parent_tde_keystore_path': parent_tde_keystore_path, 'parent_tde_keystore_password': parent_tde_keystore_password, 'tde_exported_keyfile_secret': tde_exported_keyfile_secret, 'tde_key_identifier': tde_key_identifier, 'parent_pdb_tde_keystore_path': parent_pdb_tde_keystore_path, 'parent_pdb_tde_keystore_password': parent_pdb_tde_keystore_password, 'target_pdb_tde_keystore_password': target_pdb_tde_keystore_password, 'crs_database_name': crs_database_name, 'recover_database': recover_database, 'file_mapping_rules': file_mapping_rules, 'enable_cdc': enable_cdc, 'recovery_model': recovery_model, 'mirroring_state': mirroring_state, 'is_incremental_v2p': is_incremental_v2p, 'backup_frequency_minutes': backup_frequency_minutes, 'rman_channels_for_incremental_backup': rman_channels_for_incremental_backup, 'rman_files_per_set_for_incremental_backup': rman_files_per_set_for_incremental_backup, 'rman_file_section_size_in_gb_for_incremental_backup': rman_file_section_size_in_gb_for_incremental_backup, 'default_data_diskgroup': default_data_diskgroup, 'redo_diskgroup': redo_diskgroup, 'rman_channels': rman_channels, 'rman_file_section_size_in_gb': rman_file_section_size_in_gb, 'timeflow_id': timeflow_id, 'timestamp': timestamp}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'export_dsource_to_asm_by_location':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action export_dsource_to_asm_by_location'}
        endpoint = f'/dsources/{dsource_id}/asm-export-by-location'
        params = build_params(location=location, default_data_diskgroup=default_data_diskgroup)
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'unique_name': unique_name, 'database_name': database_name, 'repository_id': repository_id, 'environment_user_ref': environment_user_ref, 'tde_keystore_password': tde_keystore_password, 'tde_keystore_config_type': tde_keystore_config_type, 'oracle_instance_name': oracle_instance_name, 'instance_number': instance_number, 'instances': instances, 'mount_base': mount_base, 'config_params': config_params, 'cdb_id': cdb_id, 'parent_tde_keystore_path': parent_tde_keystore_path, 'parent_tde_keystore_password': parent_tde_keystore_password, 'tde_exported_keyfile_secret': tde_exported_keyfile_secret, 'tde_key_identifier': tde_key_identifier, 'parent_pdb_tde_keystore_path': parent_pdb_tde_keystore_path, 'parent_pdb_tde_keystore_password': parent_pdb_tde_keystore_password, 'target_pdb_tde_keystore_password': target_pdb_tde_keystore_password, 'crs_database_name': crs_database_name, 'recover_database': recover_database, 'file_mapping_rules': file_mapping_rules, 'enable_cdc': enable_cdc, 'recovery_model': recovery_model, 'mirroring_state': mirroring_state, 'is_incremental_v2p': is_incremental_v2p, 'backup_frequency_minutes': backup_frequency_minutes, 'rman_channels_for_incremental_backup': rman_channels_for_incremental_backup, 'rman_files_per_set_for_incremental_backup': rman_files_per_set_for_incremental_backup, 'rman_file_section_size_in_gb_for_incremental_backup': rman_file_section_size_in_gb_for_incremental_backup, 'default_data_diskgroup': default_data_diskgroup, 'redo_diskgroup': redo_diskgroup, 'rman_channels': rman_channels, 'rman_file_section_size_in_gb': rman_file_section_size_in_gb, 'location': location}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'export_dsource_to_asm_from_bookmark':
        if dsource_id is None:
            return {'error': 'Missing required parameter: dsource_id for action export_dsource_to_asm_from_bookmark'}
        endpoint = f'/dsources/{dsource_id}/asm-export-from-bookmark'
        params = build_params(default_data_diskgroup=default_data_diskgroup)
        conf = check_confirmation('POST', endpoint, action, 'data_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'unique_name': unique_name, 'database_name': database_name, 'repository_id': repository_id, 'environment_user_ref': environment_user_ref, 'tde_keystore_password': tde_keystore_password, 'tde_keystore_config_type': tde_keystore_config_type, 'oracle_instance_name': oracle_instance_name, 'instance_number': instance_number, 'instances': instances, 'mount_base': mount_base, 'config_params': config_params, 'cdb_id': cdb_id, 'parent_tde_keystore_path': parent_tde_keystore_path, 'parent_tde_keystore_password': parent_tde_keystore_password, 'tde_exported_keyfile_secret': tde_exported_keyfile_secret, 'tde_key_identifier': tde_key_identifier, 'parent_pdb_tde_keystore_path': parent_pdb_tde_keystore_path, 'parent_pdb_tde_keystore_password': parent_pdb_tde_keystore_password, 'target_pdb_tde_keystore_password': target_pdb_tde_keystore_password, 'crs_database_name': crs_database_name, 'recover_database': recover_database, 'file_mapping_rules': file_mapping_rules, 'enable_cdc': enable_cdc, 'recovery_model': recovery_model, 'mirroring_state': mirroring_state, 'is_incremental_v2p': is_incremental_v2p, 'backup_frequency_minutes': backup_frequency_minutes, 'rman_channels_for_incremental_backup': rman_channels_for_incremental_backup, 'rman_files_per_set_for_incremental_backup': rman_files_per_set_for_incremental_backup, 'rman_file_section_size_in_gb_for_incremental_backup': rman_file_section_size_in_gb_for_incremental_backup, 'default_data_diskgroup': default_data_diskgroup, 'redo_diskgroup': redo_diskgroup, 'rman_channels': rman_channels, 'rman_file_section_size_in_gb': rman_file_section_size_in_gb, 'bookmark_id': bookmark_id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: list_vdbs, search_vdbs, get_vdb, update_vdb, provision_by_timestamp, provision_by_timestamp_defaults, provision_by_snapshot, provision_by_snapshot_defaults, provision_from_bookmark, provision_from_bookmark_defaults, provision_by_location, provision_by_location_defaults, provision_empty_vdb, delete_vdb, start_vdb, stop_vdb, enable_vdb, disable_vdb, refresh_vdb_by_timestamp, refresh_vdb_by_snapshot, refresh_vdb_from_bookmark, refresh_vdb_by_location, undo_vdb_refresh, rollback_vdb_by_timestamp, rollback_vdb_by_snapshot, rollback_vdb_from_bookmark, switch_vdb_timeflow, lock_vdb, unlock_vdb, migrate_vdb, get_migrate_compatible_repositories, upgrade_vdb, upgrade_oracle_vdb, get_upgrade_compatible_repositories, list_vdb_snapshots, snapshot_vdb, list_vdb_bookmarks, search_vdb_bookmarks, get_vdb_deletion_dependencies, verify_vdb_jdbc_connection, get_vdb_tags, add_vdb_tags, export_vdb_in_place, export_vdb_asm_in_place, export_vdb_by_snapshot, export_vdb_by_timestamp, export_vdb_by_location, export_vdb_from_bookmark, export_vdb_to_asm_by_snapshot, export_vdb_to_asm_by_timestamp, export_vdb_to_asm_by_location, export_vdb_to_asm_from_bookmark, export_cleanup, export_finalize, list_vdb_groups, search_vdb_groups, get_vdb_group, create_vdb_group, update_vdb_group, delete_vdb_group, provision_vdb_group_from_bookmark, refresh_vdb_group, refresh_vdb_group_from_bookmark, refresh_vdb_group_by_snapshot, refresh_vdb_group_by_timestamp, rollback_vdb_group, lock_vdb_group, unlock_vdb_group, start_vdb_group, stop_vdb_group, enable_vdb_group, disable_vdb_group, get_vdb_group_latest_snapshots, get_vdb_group_timestamp_summary, list_vdb_group_bookmarks, search_vdb_group_bookmarks, get_vdb_group_tags, add_vdb_group_tags, list_dsources, search_dsources, get_dsource, delete_dsource, enable_dsource, disable_dsource, list_dsource_snapshots, dsource_create_snapshot, upgrade_dsource, get_dsource_upgrade_compatible_repositories, get_dsource_deletion_dependencies, get_dsource_tags, add_dsource_tags, delete_dsource_tags, dsource_link_oracle, dsource_link_oracle_defaults, dsource_link_oracle_staging_push, dsource_link_oracle_staging_push_defaults, update_oracle_dsource, attach_oracle_dsource, detach_oracle_dsource, upgrade_oracle_dsource, dsource_link_ase, dsource_link_ase_defaults, update_ase_dsource, dsource_link_appdata, dsource_link_appdata_defaults, update_appdata_dsource, dsource_link_mssql, dsource_link_mssql_defaults, dsource_link_mssql_staging_push, dsource_link_mssql_staging_push_defaults, attach_mssql_staging_push_dsource, update_mssql_dsource, attach_mssql_dsource, detach_mssql_dsource, export_dsource_by_snapshot, export_dsource_by_timestamp, export_dsource_by_location, export_dsource_from_bookmark, export_dsource_to_asm_by_snapshot, export_dsource_to_asm_by_timestamp, export_dsource_to_asm_by_location, export_dsource_to_asm_from_bookmark'}

@log_tool_execution
def snapshot_bookmark_tool(
    action: str,  # One of: search_snapshots, get_snapshot, update_snapshot, delete_snapshot, unset_snapshot_expiration, get_snapshot_timeflow_range, get_runtime, get_snapshot_tags, add_snapshot_tags, delete_snapshot_tags, search_bookmarks, get_bookmark, create_bookmark, update_bookmark, delete_bookmark, get_bookmark_vdb_groups, get_bookmark_tags, add_bookmark_tags, delete_bookmark_tags
    bookmark_id: Optional[str] = None,
    bookmark_type: Optional[str] = 'PRIVATE',
    cursor: Optional[str] = None,
    delete_all_dependencies: Optional[bool] = False,
    expiration: Optional[str] = None,
    filter_expression: Optional[str] = None,
    inherit_parent_tags: Optional[bool] = False,
    inherit_parent_vdb_tags: Optional[bool] = False,
    key: Optional[str] = None,
    limit: Optional[int] = 100,
    location: Optional[str] = None,
    make_current_account_owner: Optional[bool] = True,
    name: Optional[str] = None,
    paas_database_ids: Optional[list] = None,
    paas_instance_ids: Optional[list] = None,
    paas_snapshot_ids: Optional[list] = None,
    retain_forever: Optional[bool] = None,
    retention: Optional[int] = None,
    snapshot_id: Optional[str] = None,
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
    Unified tool for SNAPSHOT BOOKMARK operations.
    
    This tool supports 19 actions: search_snapshots, get_snapshot, update_snapshot, delete_snapshot, unset_snapshot_expiration, get_snapshot_timeflow_range, get_runtime, get_snapshot_tags, add_snapshot_tags, delete_snapshot_tags, search_bookmarks, get_bookmark, create_bookmark, update_bookmark, delete_bookmark, get_bookmark_vdb_groups, get_bookmark_tags, add_bookmark_tags, delete_bookmark_tags
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search_snapshots
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
        >>> snapshot_bookmark_tool(action='search_snapshots', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get_snapshot
    ----------------------------------------
    Summary: Get a Snapshot by ID.
    Method: GET
    Endpoint: /snapshots/{snapshotId}
    Required Parameters: snapshot_id
    
    Example:
        >>> snapshot_bookmark_tool(action='get_snapshot', snapshot_id='example-snapshot-123')
    
    ACTION: update_snapshot
    ----------------------------------------
    Summary: Update values of a Snapshot.
    Method: PATCH
    Endpoint: /snapshots/{snapshotId}
    Required Parameters: snapshot_id
    Key Parameters (provide as applicable): expiration, retain_forever
    
    Example:
        >>> snapshot_bookmark_tool(action='update_snapshot', snapshot_id='example-snapshot-123', expiration=..., retain_forever=...)
    
    ACTION: delete_snapshot
    ----------------------------------------
    Summary: Delete a Snapshot.
    Method: POST
    Endpoint: /snapshots/{snapshotId}/delete
    Required Parameters: snapshot_id
    Key Parameters (provide as applicable): delete_all_dependencies
    
    Example:
        >>> snapshot_bookmark_tool(action='delete_snapshot', snapshot_id='example-snapshot-123', delete_all_dependencies=...)
    
    ACTION: unset_snapshot_expiration
    ----------------------------------------
    Summary: Unset a Snapshot's expiration, removing expiration and retain_forever values for the snapshot.
    Method: POST
    Endpoint: /snapshots/{snapshotId}/unset_expiration
    Required Parameters: snapshot_id
    
    Example:
        >>> snapshot_bookmark_tool(action='unset_snapshot_expiration', snapshot_id='example-snapshot-123')
    
    ACTION: get_snapshot_timeflow_range
    ----------------------------------------
    Summary: Return the provisionable timeflow range based on a specific snapshot.
    Method: GET
    Endpoint: /snapshots/{snapshotId}/timeflow_range
    Required Parameters: snapshot_id
    
    Example:
        >>> snapshot_bookmark_tool(action='get_snapshot_timeflow_range', snapshot_id='example-snapshot-123')
    
    ACTION: get_runtime
    ----------------------------------------
    Summary: Get a runtime object of a snapshot by id
    Method: GET
    Endpoint: /snapshots/{snapshotId}/runtime
    Required Parameters: snapshot_id
    
    Example:
        >>> snapshot_bookmark_tool(action='get_runtime', snapshot_id='example-snapshot-123')
    
    ACTION: get_snapshot_tags
    ----------------------------------------
    Summary: Get tags for a Snapshot.
    Method: GET
    Endpoint: /snapshots/{snapshotId}/tags
    Required Parameters: snapshot_id
    
    Example:
        >>> snapshot_bookmark_tool(action='get_snapshot_tags', snapshot_id='example-snapshot-123')
    
    ACTION: add_snapshot_tags
    ----------------------------------------
    Summary: Create tags for a Snapshot.
    Method: POST
    Endpoint: /snapshots/{snapshotId}/tags
    Required Parameters: snapshot_id, tags
    
    Example:
        >>> snapshot_bookmark_tool(action='add_snapshot_tags', snapshot_id='example-snapshot-123', tags=...)
    
    ACTION: delete_snapshot_tags
    ----------------------------------------
    Summary: Delete tags for a Snapshot.
    Method: POST
    Endpoint: /snapshots/{snapshotId}/tags/delete
    Required Parameters: snapshot_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> snapshot_bookmark_tool(action='delete_snapshot_tags', snapshot_id='example-snapshot-123', tags=..., key=..., value=...)
    
    ACTION: search_bookmarks
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
        >>> snapshot_bookmark_tool(action='search_bookmarks', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get_bookmark
    ----------------------------------------
    Summary: Get a bookmark by ID.
    Method: GET
    Endpoint: /bookmarks/{bookmarkId}
    Required Parameters: bookmark_id
    
    Example:
        >>> snapshot_bookmark_tool(action='get_bookmark', bookmark_id='example-bookmark-123')
    
    ACTION: create_bookmark
    ----------------------------------------
    Summary: Create a bookmark at the current time.
    Method: POST
    Endpoint: /bookmarks
    Required Parameters: name
    Key Parameters (provide as applicable): expiration, retain_forever, tags, vdb_ids, vdb_group_id, snapshot_ids, timeflow_ids, timestamp, timestamp_in_database_timezone, location, paas_snapshot_ids, paas_database_ids, paas_instance_ids, retention, bookmark_type, make_current_account_owner, inherit_parent_vdb_tags, inherit_parent_tags
    
    Example:
        >>> snapshot_bookmark_tool(action='create_bookmark', expiration=..., retain_forever=..., tags=..., name=..., vdb_ids=..., vdb_group_id='example-vdb_group-123', snapshot_ids=..., timeflow_ids=..., timestamp=..., timestamp_in_database_timezone=..., location=..., paas_snapshot_ids=..., paas_database_ids=..., paas_instance_ids=..., retention=..., bookmark_type=..., make_current_account_owner=..., inherit_parent_vdb_tags=..., inherit_parent_tags=...)
    
    ACTION: update_bookmark
    ----------------------------------------
    Summary: Update a bookmark
    Method: PATCH
    Endpoint: /bookmarks/{bookmarkId}
    Required Parameters: bookmark_id
    Key Parameters (provide as applicable): expiration, retain_forever, name, bookmark_type
    
    Example:
        >>> snapshot_bookmark_tool(action='update_bookmark', expiration=..., retain_forever=..., bookmark_id='example-bookmark-123', name=..., bookmark_type=...)
    
    ACTION: delete_bookmark
    ----------------------------------------
    Summary: Delete a bookmark.
    Method: DELETE
    Endpoint: /bookmarks/{bookmarkId}
    Required Parameters: bookmark_id
    
    Example:
        >>> snapshot_bookmark_tool(action='delete_bookmark', bookmark_id='example-bookmark-123')
    
    ACTION: get_bookmark_vdb_groups
    ----------------------------------------
    Summary: List VDB Groups compatible with this bookmark.
    Method: GET
    Endpoint: /bookmarks/{bookmarkId}/vdb-groups
    Required Parameters: limit, cursor, sort, bookmark_id
    
    Example:
        >>> snapshot_bookmark_tool(action='get_bookmark_vdb_groups', limit=..., cursor=..., sort=..., bookmark_id='example-bookmark-123')
    
    ACTION: get_bookmark_tags
    ----------------------------------------
    Summary: Get tags for a Bookmark.
    Method: GET
    Endpoint: /bookmarks/{bookmarkId}/tags
    Required Parameters: bookmark_id
    
    Example:
        >>> snapshot_bookmark_tool(action='get_bookmark_tags', bookmark_id='example-bookmark-123')
    
    ACTION: add_bookmark_tags
    ----------------------------------------
    Summary: Create tags for a Bookmark.
    Method: POST
    Endpoint: /bookmarks/{bookmarkId}/tags
    Required Parameters: tags, bookmark_id
    
    Example:
        >>> snapshot_bookmark_tool(action='add_bookmark_tags', tags=..., bookmark_id='example-bookmark-123')
    
    ACTION: delete_bookmark_tags
    ----------------------------------------
    Summary: Delete tags for a Bookmark.
    Method: POST
    Endpoint: /bookmarks/{bookmarkId}/tags/delete
    Required Parameters: bookmark_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> snapshot_bookmark_tool(action='delete_bookmark_tags', tags=..., key=..., value=..., bookmark_id='example-bookmark-123')
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search_snapshots, get_snapshot, update_snapshot, delete_snapshot, unset_snapshot_expiration, get_snapshot_timeflow_range, get_runtime, get_snapshot_tags, add_snapshot_tags, delete_snapshot_tags, search_bookmarks, get_bookmark, create_bookmark, update_bookmark, delete_bookmark, get_bookmark_vdb_groups, get_bookmark_tags, add_bookmark_tags, delete_bookmark_tags
    
      -- General parameters (all database types) --
        bookmark_id (str): The unique identifier for the bookmark.
            [Required for: get_bookmark, update_bookmark, delete_bookmark, get_bookmark_vdb_groups, get_bookmark_tags, add_bookmark_tags, delete_bookmark_tags]
        bookmark_type (str): Type of the bookmark, either PUBLIC or PRIVATE. Valid values: PUBLIC, PRIVATE...
            [Optional for all actions]
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search_snapshots, search_bookmarks, get_bookmark_vdb_groups]
        delete_all_dependencies (bool): Whether to delete the snapshot along with all of its dependencies. (Default: ...
            [Optional for all actions]
        expiration (str): The expiration for this snapshot. Mutually exclusive with retain_forever.
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
            [Required for: search_snapshots, search_bookmarks, get_bookmark_vdb_groups]
        location (str): The location to create bookmark from. Mutually exclusive with snapshot_ids, t...
            [Optional for all actions]
        make_current_account_owner (bool): Whether the account creating this bookmark must be configured as owner of the...
            [Optional for all actions]
        name (str): The user-defined name of this bookmark.
            [Required for: create_bookmark]
        paas_database_ids (list): The IDs of the PaaS Database associated with the PaaS snapshot. This paramete...
            [Optional for all actions]
        paas_instance_ids (list): The IDs of the PaaS Instance associated with the PaaS Database. This paramete...
            [Optional for all actions]
        paas_snapshot_ids (list): The IDs of the PaaS snapshot to create the Bookmark on. This parameter is mut...
            [Optional for all actions]
        retain_forever (bool): Indicates that the snapshot should be retained forever.
            [Optional for all actions]
        retention (int): The retention policy for this bookmark, in days. A value of -1 indicates the ...
            [Optional for all actions]
        snapshot_id (str): The unique identifier for the snapshot.
            [Required for: get_snapshot, update_snapshot, delete_snapshot, unset_snapshot_expiration, get_snapshot_timeflow_range, get_runtime, get_snapshot_tags, add_snapshot_tags, delete_snapshot_tags]
        snapshot_ids (list): The IDs of the snapshots that will be part of the Bookmark. This parameter is...
            [Optional for all actions]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search_snapshots, search_bookmarks, get_bookmark_vdb_groups]
        tags (list): Array of tags with key value pairs (Pass as JSON array)
            [Required for: add_snapshot_tags, add_bookmark_tags]
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
    if action == 'search_snapshots':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('POST', '/snapshots/search', action, 'snapshot_bookmark_tool', confirmed or False)
        if conf:
            return conf
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/snapshots/search', params=params, json_body=body)
    elif action == 'get_snapshot':
        if snapshot_id is None:
            return {'error': 'Missing required parameter: snapshot_id for action get_snapshot'}
        endpoint = f'/snapshots/{snapshot_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'snapshot_bookmark_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'update_snapshot':
        if snapshot_id is None:
            return {'error': 'Missing required parameter: snapshot_id for action update_snapshot'}
        endpoint = f'/snapshots/{snapshot_id}'
        params = build_params()
        conf = check_confirmation('PATCH', endpoint, action, 'snapshot_bookmark_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'expiration': expiration, 'retain_forever': retain_forever}.items() if v is not None}
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_snapshot':
        if snapshot_id is None:
            return {'error': 'Missing required parameter: snapshot_id for action delete_snapshot'}
        endpoint = f'/snapshots/{snapshot_id}/delete'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'snapshot_bookmark_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'delete_all_dependencies': delete_all_dependencies}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'unset_snapshot_expiration':
        if snapshot_id is None:
            return {'error': 'Missing required parameter: snapshot_id for action unset_snapshot_expiration'}
        endpoint = f'/snapshots/{snapshot_id}/unset_expiration'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'snapshot_bookmark_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'get_snapshot_timeflow_range':
        if snapshot_id is None:
            return {'error': 'Missing required parameter: snapshot_id for action get_snapshot_timeflow_range'}
        endpoint = f'/snapshots/{snapshot_id}/timeflow_range'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'snapshot_bookmark_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'get_runtime':
        if snapshot_id is None:
            return {'error': 'Missing required parameter: snapshot_id for action get_runtime'}
        endpoint = f'/snapshots/{snapshot_id}/runtime'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'snapshot_bookmark_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'get_snapshot_tags':
        if snapshot_id is None:
            return {'error': 'Missing required parameter: snapshot_id for action get_snapshot_tags'}
        endpoint = f'/snapshots/{snapshot_id}/tags'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'snapshot_bookmark_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_snapshot_tags':
        if snapshot_id is None:
            return {'error': 'Missing required parameter: snapshot_id for action add_snapshot_tags'}
        endpoint = f'/snapshots/{snapshot_id}/tags'
        params = build_params(tags=tags)
        conf = check_confirmation('POST', endpoint, action, 'snapshot_bookmark_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_snapshot_tags':
        if snapshot_id is None:
            return {'error': 'Missing required parameter: snapshot_id for action delete_snapshot_tags'}
        endpoint = f'/snapshots/{snapshot_id}/tags/delete'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'snapshot_bookmark_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'search_bookmarks':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('POST', '/bookmarks/search', action, 'snapshot_bookmark_tool', confirmed or False)
        if conf:
            return conf
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/bookmarks/search', params=params, json_body=body)
    elif action == 'get_bookmark':
        if bookmark_id is None:
            return {'error': 'Missing required parameter: bookmark_id for action get_bookmark'}
        endpoint = f'/bookmarks/{bookmark_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'snapshot_bookmark_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'create_bookmark':
        params = build_params(name=name)
        conf = check_confirmation('POST', '/bookmarks', action, 'snapshot_bookmark_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name, 'vdb_ids': vdb_ids, 'vdb_group_id': vdb_group_id, 'snapshot_ids': snapshot_ids, 'timeflow_ids': timeflow_ids, 'timestamp': timestamp, 'timestamp_in_database_timezone': timestamp_in_database_timezone, 'location': location, 'paas_snapshot_ids': paas_snapshot_ids, 'paas_database_ids': paas_database_ids, 'paas_instance_ids': paas_instance_ids, 'retention': retention, 'expiration': expiration, 'retain_forever': retain_forever, 'tags': tags, 'bookmark_type': bookmark_type, 'make_current_account_owner': make_current_account_owner, 'inherit_parent_vdb_tags': inherit_parent_vdb_tags, 'inherit_parent_tags': inherit_parent_tags}.items() if v is not None}
        return make_api_request('POST', '/bookmarks', params=params, json_body=body if body else None)
    elif action == 'update_bookmark':
        if bookmark_id is None:
            return {'error': 'Missing required parameter: bookmark_id for action update_bookmark'}
        endpoint = f'/bookmarks/{bookmark_id}'
        params = build_params()
        conf = check_confirmation('PATCH', endpoint, action, 'snapshot_bookmark_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name, 'expiration': expiration, 'retain_forever': retain_forever, 'bookmark_type': bookmark_type}.items() if v is not None}
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_bookmark':
        if bookmark_id is None:
            return {'error': 'Missing required parameter: bookmark_id for action delete_bookmark'}
        endpoint = f'/bookmarks/{bookmark_id}'
        params = build_params()
        conf = check_confirmation('DELETE', endpoint, action, 'snapshot_bookmark_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'get_bookmark_vdb_groups':
        if bookmark_id is None:
            return {'error': 'Missing required parameter: bookmark_id for action get_bookmark_vdb_groups'}
        endpoint = f'/bookmarks/{bookmark_id}/vdb-groups'
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('GET', endpoint, action, 'snapshot_bookmark_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'get_bookmark_tags':
        if bookmark_id is None:
            return {'error': 'Missing required parameter: bookmark_id for action get_bookmark_tags'}
        endpoint = f'/bookmarks/{bookmark_id}/tags'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'snapshot_bookmark_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_bookmark_tags':
        if bookmark_id is None:
            return {'error': 'Missing required parameter: bookmark_id for action add_bookmark_tags'}
        endpoint = f'/bookmarks/{bookmark_id}/tags'
        params = build_params(tags=tags)
        conf = check_confirmation('POST', endpoint, action, 'snapshot_bookmark_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_bookmark_tags':
        if bookmark_id is None:
            return {'error': 'Missing required parameter: bookmark_id for action delete_bookmark_tags'}
        endpoint = f'/bookmarks/{bookmark_id}/tags/delete'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'snapshot_bookmark_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search_snapshots, get_snapshot, update_snapshot, delete_snapshot, unset_snapshot_expiration, get_snapshot_timeflow_range, get_runtime, get_snapshot_tags, add_snapshot_tags, delete_snapshot_tags, search_bookmarks, get_bookmark, create_bookmark, update_bookmark, delete_bookmark, get_bookmark_vdb_groups, get_bookmark_tags, add_bookmark_tags, delete_bookmark_tags'}

@log_tool_execution
def data_connection_tool(
    action: str,  # One of: search, get, update, get_tags, add_tags, delete_tags
    cursor: Optional[str] = None,
    data_connection_id: Optional[str] = None,
    filter_expression: Optional[str] = None,
    key: Optional[str] = None,
    limit: Optional[int] = 100,
    name: Optional[str] = None,
    sort: Optional[str] = None,
    tags: Optional[list] = None,
    value: Optional[str] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for DATA CONNECTION operations.
    
    This tool supports 6 actions: search, get, update, get_tags, add_tags, delete_tags
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search for data connections.
    Method: POST
    Endpoint: /data-connections/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
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
        >>> data_connection_tool(action='search', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
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
    Key Parameters (provide as applicable): name
    
    Example:
        >>> data_connection_tool(action='update', data_connection_id='example-data_connection-123', name=...)
    
    ACTION: get_tags
    ----------------------------------------
    Summary: Get tags for a data connection.
    Method: GET
    Endpoint: /data-connections/{dataConnectionId}/tags
    Required Parameters: data_connection_id
    
    Example:
        >>> data_connection_tool(action='get_tags', data_connection_id='example-data_connection-123')
    
    ACTION: add_tags
    ----------------------------------------
    Summary: Create tags for a data connection.
    Method: POST
    Endpoint: /data-connections/{dataConnectionId}/tags
    Required Parameters: data_connection_id, tags
    
    Example:
        >>> data_connection_tool(action='add_tags', data_connection_id='example-data_connection-123', tags=...)
    
    ACTION: delete_tags
    ----------------------------------------
    Summary: Delete tags for a data connection.
    Method: POST
    Endpoint: /data-connections/{dataConnectionId}/tags/delete
    Required Parameters: data_connection_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> data_connection_tool(action='delete_tags', data_connection_id='example-data_connection-123', tags=..., key=..., value=...)
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, update, get_tags, add_tags, delete_tags
    
      -- General parameters (all database types) --
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search]
        data_connection_id (str): The unique identifier for the dataConnection.
            [Required for: get, update, get_tags, add_tags, delete_tags]
        filter_expression (str): Request body parameter
            [Optional for all actions]
        key (str): Key of the tag
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search]
        name (str): The data connection name
            [Optional for all actions]
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
        conf = check_confirmation('POST', '/data-connections/search', action, 'data_connection_tool', confirmed or False)
        if conf:
            return conf
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/data-connections/search', params=params, json_body=body)
    elif action == 'get':
        if data_connection_id is None:
            return {'error': 'Missing required parameter: data_connection_id for action get'}
        endpoint = f'/data-connections/{data_connection_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'data_connection_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'update':
        if data_connection_id is None:
            return {'error': 'Missing required parameter: data_connection_id for action update'}
        endpoint = f'/data-connections/{data_connection_id}'
        params = build_params()
        conf = check_confirmation('PATCH', endpoint, action, 'data_connection_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name}.items() if v is not None}
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'get_tags':
        if data_connection_id is None:
            return {'error': 'Missing required parameter: data_connection_id for action get_tags'}
        endpoint = f'/data-connections/{data_connection_id}/tags'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'data_connection_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_tags':
        if data_connection_id is None:
            return {'error': 'Missing required parameter: data_connection_id for action add_tags'}
        endpoint = f'/data-connections/{data_connection_id}/tags'
        params = build_params(tags=tags)
        conf = check_confirmation('POST', endpoint, action, 'data_connection_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_tags':
        if data_connection_id is None:
            return {'error': 'Missing required parameter: data_connection_id for action delete_tags'}
        endpoint = f'/data-connections/{data_connection_id}/tags/delete'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'data_connection_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, update, get_tags, add_tags, delete_tags'}

@log_tool_execution
def timeflow_tool(
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
    port: Optional[int] = 22,
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
        conf = check_confirmation('GET', '/timeflows', action, 'timeflow_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', '/timeflows', params=params)
    elif action == 'search':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('POST', '/timeflows/search', action, 'timeflow_tool', confirmed or False)
        if conf:
            return conf
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/timeflows/search', params=params, json_body=body)
    elif action == 'get':
        if timeflow_id is None:
            return {'error': 'Missing required parameter: timeflow_id for action get'}
        endpoint = f'/timeflows/{timeflow_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'timeflow_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'update':
        if timeflow_id is None:
            return {'error': 'Missing required parameter: timeflow_id for action update'}
        endpoint = f'/timeflows/{timeflow_id}'
        params = build_params()
        conf = check_confirmation('PATCH', endpoint, action, 'timeflow_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name}.items() if v is not None}
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete':
        if timeflow_id is None:
            return {'error': 'Missing required parameter: timeflow_id for action delete'}
        endpoint = f'/timeflows/{timeflow_id}'
        params = build_params()
        conf = check_confirmation('DELETE', endpoint, action, 'timeflow_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'get_snapshot_day_range':
        if timeflow_id is None:
            return {'error': 'Missing required parameter: timeflow_id for action get_snapshot_day_range'}
        endpoint = f'/timeflows/{timeflow_id}/timeflowSnapshotDayRange'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'timeflow_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'repair':
        if timeflow_id is None:
            return {'error': 'Missing required parameter: timeflow_id for action repair'}
        endpoint = f'/timeflows/{timeflow_id}/repair'
        params = build_params(host=host, username=username, directory=directory, start_location=start_location, end_location=end_location)
        conf = check_confirmation('POST', endpoint, action, 'timeflow_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'host': host, 'port': port, 'username': username, 'directory': directory, 'start_location': start_location, 'end_location': end_location, 'use_engine_public_key': use_engine_public_key, 'password': password, 'key_pair_private_key': key_pair_private_key, 'key_pair_public_key': key_pair_public_key, 'vault_id': vault_id, 'hashicorp_vault_engine': hashicorp_vault_engine, 'hashicorp_vault_secret_path': hashicorp_vault_secret_path, 'hashicorp_vault_username_key': hashicorp_vault_username_key, 'hashicorp_vault_secret_key': hashicorp_vault_secret_key, 'azure_vault_name': azure_vault_name, 'azure_vault_username_key': azure_vault_username_key, 'azure_vault_secret_key': azure_vault_secret_key, 'cyberark_vault_query_string': cyberark_vault_query_string, 'use_kerberos_authentication': use_kerberos_authentication, 'sshVerificationStrategy': ssh_verification_strategy}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'get_tags':
        if timeflow_id is None:
            return {'error': 'Missing required parameter: timeflow_id for action get_tags'}
        endpoint = f'/timeflows/{timeflow_id}/tags'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'timeflow_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_tags':
        if timeflow_id is None:
            return {'error': 'Missing required parameter: timeflow_id for action add_tags'}
        endpoint = f'/timeflows/{timeflow_id}/tags'
        params = build_params(tags=tags)
        conf = check_confirmation('POST', endpoint, action, 'timeflow_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_tags':
        if timeflow_id is None:
            return {'error': 'Missing required parameter: timeflow_id for action delete_tags'}
        endpoint = f'/timeflows/{timeflow_id}/tags/delete'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'timeflow_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: list, search, get, update, delete, get_snapshot_day_range, repair, get_tags, add_tags, delete_tags'}


def register_tools(app, dct_client):
    global client
    client = dct_client
    logger.info(f'Registering tools for dataset_endpoints...')
    try:
        logger.info(f'  Registering tool function: data_tool')
        app.add_tool(data_tool, name="data_tool")
        logger.info(f'  Registering tool function: snapshot_bookmark_tool')
        app.add_tool(snapshot_bookmark_tool, name="snapshot_bookmark_tool")
        logger.info(f'  Registering tool function: data_connection_tool')
        app.add_tool(data_connection_tool, name="data_connection_tool")
        logger.info(f'  Registering tool function: timeflow_tool')
        app.add_tool(timeflow_tool, name="timeflow_tool")
    except Exception as e:
        logger.error(f'Error registering tools for dataset_endpoints: {e}')
    logger.info(f'Tools registration finished for dataset_endpoints.')
