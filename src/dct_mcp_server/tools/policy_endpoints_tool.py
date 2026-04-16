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
def virtualization_policy_tool(
    action: str,  # One of: search, get, create, update, delete, apply, unapply, search_targets, get_tags, add_tags, delete_tags
    cursor: Optional[str] = None,
    data_duration: Optional[int] = None,
    data_unit: Optional[str] = None,
    day_of_month: Optional[int] = None,
    day_of_week: Optional[str] = None,
    day_of_year: Optional[str] = None,
    filter_expression: Optional[str] = None,
    key: Optional[str] = None,
    limit: Optional[int] = 100,
    log_duration: Optional[int] = None,
    log_unit: Optional[str] = None,
    name: Optional[str] = None,
    num_of_daily: Optional[int] = None,
    num_of_monthly: Optional[int] = None,
    num_of_weekly: Optional[int] = None,
    num_of_yearly: Optional[int] = None,
    policy_id: Optional[str] = None,
    policy_targets: Optional[list] = None,
    policy_type: Optional[str] = None,
    provision_source: Optional[str] = None,
    schedules: Optional[list] = None,
    size: Optional[int] = None,
    sort: Optional[str] = None,
    tags: Optional[list] = None,
    timezone_id: Optional[str] = None,
    value: Optional[str] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for VIRTUALIZATION POLICY operations.
    
    This tool supports 11 actions: search, get, create, update, delete, apply, unapply, search_targets, get_tags, add_tags, delete_tags
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search Virtualization Policies.
    Method: POST
    Endpoint: /virtualization-policies/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - id: 
        - name: 
        - dct_managed: Whether this virtualization policy is managed by DCT or b...
        - create_user: The user who created this virtualization policy.
        - create_timestamp: The time this virtualization policy was created.
        - namespace: 
        - namespace_id: The namespace id of this virtualization policy.
        - namespace_name: The namespace name of this virtualization policy.
        - is_replica: Is this a replicated object.
        - engine_id: 
        - engine_name: The name of the engine the policy belongs to.
        - policy_type: 
        - timezone_id: 
        - default_policy: True if this is the default policy created when the syste...
        - effective_type: Whether this policy has been directly applied or inherite...
        - data_duration: Amount of time to keep source data [Retention Policy].
        - data_unit: Time unit for data_duration [Retention Policy].
        - log_duration: Amount of time to keep log data [Retention Policy].
        - log_unit: Time unit for log_duration [Retention Policy].
        - num_of_daily: Number of daily snapshots to keep [Retention Policy].
        - num_of_weekly: Number of weekly snapshots to keep [Retention Policy].
        - day_of_week: Day of week upon which to enforce weekly snapshot retenti...
        - num_of_monthly: Number of monthly snapshots to keep [Retention Policy].
        - day_of_month: Day of month upon which to enforce monthly snapshot reten...
        - num_of_yearly: Number of yearly snapshots to keep [Retention Policy].
        - day_of_year: Day of year upon which to enforce yearly snapshot retenti...
        - schedules: 
        - provision_source: 
        - size: Size of the quota, in bytes. (QUOTA_POLICY only).
        - tags: The tags that are applied to this VirtualizationPolicy.
        - num_targets: The number of target dSources or VDBs to which this polic...
        - customized: True if this policy is customized specifically for one ob...
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> virtualization_policy_tool(action='search', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get
    ----------------------------------------
    Summary: Fetch a virtualization policy by Id.
    Method: GET
    Endpoint: /virtualization-policies/{policyId}
    Required Parameters: policy_id
    
    Example:
        >>> virtualization_policy_tool(action='get', policy_id='example-policy-123')
    
    ACTION: create
    ----------------------------------------
    Summary: Create a VirtualizationPolicy.
    Method: POST
    Endpoint: /virtualization-policies
    Required Parameters: name, policy_type
    Key Parameters (provide as applicable): policy_targets, provision_source, timezone_id, data_duration, data_unit, log_duration, log_unit, num_of_daily, num_of_weekly, day_of_week, num_of_monthly, day_of_month, num_of_yearly, day_of_year, schedules, size, tags
    
    Example:
        >>> virtualization_policy_tool(action='create', name=..., policy_type=..., policy_targets=..., provision_source=..., timezone_id='example-timezone-123', data_duration=..., data_unit=..., log_duration=..., log_unit=..., num_of_daily=..., num_of_weekly=..., day_of_week=..., num_of_monthly=..., day_of_month=..., num_of_yearly=..., day_of_year=..., schedules=..., size=..., tags=...)
    
    ACTION: update
    ----------------------------------------
    Summary: Update a VirtualizationPolicy.
    Method: PATCH
    Endpoint: /virtualization-policies/{policyId}
    Required Parameters: policy_id
    Key Parameters (provide as applicable): name, provision_source, timezone_id, data_duration, data_unit, log_duration, log_unit, num_of_daily, num_of_weekly, day_of_week, num_of_monthly, day_of_month, num_of_yearly, day_of_year, schedules, size
    
    Example:
        >>> virtualization_policy_tool(action='update', policy_id='example-policy-123', name=..., provision_source=..., timezone_id='example-timezone-123', data_duration=..., data_unit=..., log_duration=..., log_unit=..., num_of_daily=..., num_of_weekly=..., day_of_week=..., num_of_monthly=..., day_of_month=..., num_of_yearly=..., day_of_year=..., schedules=..., size=...)
    
    ACTION: delete
    ----------------------------------------
    Summary: Delete a VirtualizationPolicy.
    Method: DELETE
    Endpoint: /virtualization-policies/{policyId}
    Required Parameters: policy_id
    
    Example:
        >>> virtualization_policy_tool(action='delete', policy_id='example-policy-123')
    
    ACTION: apply
    ----------------------------------------
    Summary: Apply a virtualization policy to the given list of objects.
    Method: POST
    Endpoint: /virtualization-policies/{policyId}/apply
    Required Parameters: policy_id
    
    Example:
        >>> virtualization_policy_tool(action='apply', policy_id='example-policy-123')
    
    ACTION: unapply
    ----------------------------------------
    Summary: Unapply a virtualization policy to the given list of objects.
    Method: POST
    Endpoint: /virtualization-policies/{policyId}/unapply
    Required Parameters: policy_id
    
    Example:
        >>> virtualization_policy_tool(action='unapply', policy_id='example-policy-123')
    
    ACTION: search_targets
    ----------------------------------------
    Summary: Search Virtualization Policy Target Objects.
    Method: POST
    Endpoint: /virtualization-policies/targets/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - id: A unique ID for this VirtualizationPolicyTarget.
        - policy_id: The DCT ID of the policy.
        - target_id: The DCT ID of the target the policy is applied to.
        - engine_id: The ID of the engine hosting the policy and target.
        - policy_type: 
        - target_type: 
        - target_name: The name of the target object.
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> virtualization_policy_tool(action='search_targets', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get_tags
    ----------------------------------------
    Summary: Get tags for a VirtualizationPolicy.
    Method: GET
    Endpoint: /virtualization-policies/{policyId}/tags
    Required Parameters: policy_id
    
    Example:
        >>> virtualization_policy_tool(action='get_tags', policy_id='example-policy-123')
    
    ACTION: add_tags
    ----------------------------------------
    Summary: Create tags for a VirtualizationPolicy.
    Method: POST
    Endpoint: /virtualization-policies/{policyId}/tags
    Required Parameters: policy_id, tags
    
    Example:
        >>> virtualization_policy_tool(action='add_tags', policy_id='example-policy-123', tags=...)
    
    ACTION: delete_tags
    ----------------------------------------
    Summary: Delete tags for a VirtualizationPolicy.
    Method: POST
    Endpoint: /virtualization-policies/{policyId}/tags/delete
    Required Parameters: policy_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> virtualization_policy_tool(action='delete_tags', policy_id='example-policy-123', tags=..., key=..., value=...)
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, create, update, delete, apply, unapply, search_targets, get_tags, add_tags, delete_tags
    
      -- General parameters (all database types) --
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search, search_targets]
        data_duration (int): Amount of time to keep source data [Retention Policy].
            [Optional for all actions]
        data_unit (str): Time unit for data_duration [Retention Policy]. Valid values: DAY, WEEK, MONT...
            [Optional for all actions]
        day_of_month (int): Day of month upon which to enforce monthly snapshot retention [Retention Poli...
            [Optional for all actions]
        day_of_week (str): Day of week upon which to enforce weekly snapshot retention [Retention Policy...
            [Optional for all actions]
        day_of_year (str): Day of year upon which to enforce yearly snapshot retention, expressed a mont...
            [Optional for all actions]
        filter_expression (str): Request body parameter
            [Optional for all actions]
        key (str): Key of the tag
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search, search_targets]
        log_duration (int): Amount of time to keep log data [Retention Policy].
            [Optional for all actions]
        log_unit (str): Time unit for log_duration [Retention Policy]. Valid values: DAY, WEEK, MONTH...
            [Optional for all actions]
        name (str): The name of the virtualization policy.
            [Required for: create]
        num_of_daily (int): Number of daily snapshots to keep [Retention Policy].
            [Optional for all actions]
        num_of_monthly (int): Number of monthly snapshots to keep [Retention Policy].
            [Optional for all actions]
        num_of_weekly (int): Number of weekly snapshots to keep [Retention Policy].
            [Optional for all actions]
        num_of_yearly (int): Number of yearly snapshots to keep [Retention Policy].
            [Optional for all actions]
        policy_id (str): The unique identifier for the policy.
            [Required for: get, update, delete, apply, unapply, get_tags, add_tags, delete_tags]
        policy_targets (list): The target objects that will have this policy applied to them upon creation o...
            [Optional for all actions]
        policy_type (str): The type of a virtualization policy. Valid values: REFRESH_POLICY, SNAPSHOT_P...
            [Required for: create]
        provision_source (str): The source of the data to provision from [Refresh Policy]. Valid values: LATE...
            [Optional for all actions]
        schedules (list): The schedules for this policy. (Pass as JSON array)
            [Optional for all actions]
        size (int): Size of the quota, in bytes. [Quota Policy].
            [Optional for all actions]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search, search_targets]
        tags (list): The tags to be created for the policy. (Pass as JSON array)
            [Required for: add_tags]
        timezone_id (str): The timezone to use for scheduling.
            [Optional for all actions]
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
        conf = check_confirmation('POST', '/virtualization-policies/search', action, 'virtualization_policy_tool', confirmed or False)
        if conf:
            return conf
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/virtualization-policies/search', params=params, json_body=body)
    elif action == 'get':
        if policy_id is None:
            return {'error': 'Missing required parameter: policy_id for action get'}
        endpoint = f'/virtualization-policies/{policy_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'virtualization_policy_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'create':
        params = build_params(name=name, policy_type=policy_type)
        conf = check_confirmation('POST', '/virtualization-policies', action, 'virtualization_policy_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name, 'policy_type': policy_type, 'policy_targets': policy_targets, 'provision_source': provision_source, 'timezone_id': timezone_id, 'data_duration': data_duration, 'data_unit': data_unit, 'log_duration': log_duration, 'log_unit': log_unit, 'num_of_daily': num_of_daily, 'num_of_weekly': num_of_weekly, 'day_of_week': day_of_week, 'num_of_monthly': num_of_monthly, 'day_of_month': day_of_month, 'num_of_yearly': num_of_yearly, 'day_of_year': day_of_year, 'schedules': schedules, 'size': size, 'tags': tags}.items() if v is not None}
        return make_api_request('POST', '/virtualization-policies', params=params, json_body=body if body else None)
    elif action == 'update':
        if policy_id is None:
            return {'error': 'Missing required parameter: policy_id for action update'}
        endpoint = f'/virtualization-policies/{policy_id}'
        params = build_params()
        conf = check_confirmation('PATCH', endpoint, action, 'virtualization_policy_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name, 'timezone_id': timezone_id, 'data_duration': data_duration, 'data_unit': data_unit, 'log_duration': log_duration, 'log_unit': log_unit, 'num_of_daily': num_of_daily, 'num_of_weekly': num_of_weekly, 'day_of_week': day_of_week, 'num_of_monthly': num_of_monthly, 'day_of_month': day_of_month, 'num_of_yearly': num_of_yearly, 'day_of_year': day_of_year, 'schedules': schedules, 'size': size, 'provision_source': provision_source}.items() if v is not None}
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete':
        if policy_id is None:
            return {'error': 'Missing required parameter: policy_id for action delete'}
        endpoint = f'/virtualization-policies/{policy_id}'
        params = build_params()
        conf = check_confirmation('DELETE', endpoint, action, 'virtualization_policy_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'apply':
        if policy_id is None:
            return {'error': 'Missing required parameter: policy_id for action apply'}
        endpoint = f'/virtualization-policies/{policy_id}/apply'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'virtualization_policy_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'unapply':
        if policy_id is None:
            return {'error': 'Missing required parameter: policy_id for action unapply'}
        endpoint = f'/virtualization-policies/{policy_id}/unapply'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'virtualization_policy_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'search_targets':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('POST', '/virtualization-policies/targets/search', action, 'virtualization_policy_tool', confirmed or False)
        if conf:
            return conf
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/virtualization-policies/targets/search', params=params, json_body=body)
    elif action == 'get_tags':
        if policy_id is None:
            return {'error': 'Missing required parameter: policy_id for action get_tags'}
        endpoint = f'/virtualization-policies/{policy_id}/tags'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'virtualization_policy_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_tags':
        if policy_id is None:
            return {'error': 'Missing required parameter: policy_id for action add_tags'}
        endpoint = f'/virtualization-policies/{policy_id}/tags'
        params = build_params(tags=tags)
        conf = check_confirmation('POST', endpoint, action, 'virtualization_policy_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_tags':
        if policy_id is None:
            return {'error': 'Missing required parameter: policy_id for action delete_tags'}
        endpoint = f'/virtualization-policies/{policy_id}/tags/delete'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'virtualization_policy_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, create, update, delete, apply, unapply, search_targets, get_tags, add_tags, delete_tags'}

@log_tool_execution
def replication_tool(
    action: str,  # One of: search, get, create, update, delete, execute, enable_tag_replication, disable_tag_replication, get_tags, add_tags, delete_tags, list_namespaces, search_namespaces, get_namespace, update_namespace, delete_namespace, failover_namespace, commit_failover_namespace, failback_namespace, discard_namespace, get_heldspace_deletion_dependencies, delete_heldspace
    automatic_replication: Optional[bool] = False,
    bandwidth_limit: Optional[int] = 0,
    cdb_ids: Optional[list] = None,
    cursor: Optional[str] = None,
    description: Optional[str] = None,
    dsource_ids: Optional[list] = None,
    enable_failback: Optional[bool] = False,
    enable_tag_replication: Optional[bool] = None,
    encrypted: Optional[bool] = False,
    engine_id: Optional[str] = None,
    filter_expression: Optional[str] = None,
    group_ids: Optional[list] = None,
    heldspace_id: Optional[str] = None,
    key: Optional[str] = None,
    limit: Optional[int] = 100,
    name: Optional[str] = None,
    namespace_id: Optional[str] = None,
    nfs_share: Optional[str] = None,
    number_of_connections: Optional[int] = 1,
    offline_send_profile_tag: Optional[str] = None,
    replicate_entire_engine: Optional[bool] = None,
    replication_mode: Optional[str] = None,
    replication_profile_id: Optional[str] = None,
    schedule: Optional[str] = None,
    sort: Optional[str] = None,
    tags: Optional[list] = None,
    target_engine_id: Optional[str] = None,
    target_host: Optional[str] = None,
    target_port: Optional[int] = 8415,
    use_system_socks_setting: Optional[bool] = False,
    value: Optional[str] = None,
    vcdb_ids: Optional[list] = None,
    vdb_ids: Optional[list] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for REPLICATION operations.
    
    This tool supports 22 actions: search, get, create, update, delete, execute, enable_tag_replication, disable_tag_replication, get_tags, add_tags, delete_tags, list_namespaces, search_namespaces, get_namespace, update_namespace, delete_namespace, failover_namespace, commit_failover_namespace, failback_namespace, discard_namespace, get_heldspace_deletion_dependencies, delete_heldspace
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search for ReplicationProfiles.
    Method: POST
    Endpoint: /replication-profiles/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
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
        >>> replication_tool(action='search', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
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
    Required Parameters: replication_mode, engine_id
    Key Parameters (provide as applicable): name, target_engine_id, target_host, target_port, nfs_share, offline_send_profile_tag, description, schedule, tags, enable_tag_replication, bandwidth_limit, number_of_connections, encrypted, automatic_replication, use_system_socks_setting, vdb_ids, dsource_ids, cdb_ids, vcdb_ids, group_ids, replicate_entire_engine
    
    Example:
        >>> replication_tool(action='create', name=..., replication_mode=..., engine_id='example-engine-123', target_engine_id='example-target_engine-123', target_host=..., target_port=..., nfs_share=..., offline_send_profile_tag=..., description=..., schedule=..., tags=..., enable_tag_replication=..., bandwidth_limit=..., number_of_connections=..., encrypted=..., automatic_replication=..., use_system_socks_setting=..., vdb_ids=..., dsource_ids=..., cdb_ids=..., vcdb_ids=..., group_ids=..., replicate_entire_engine=...)
    
    ACTION: update
    ----------------------------------------
    Summary: Update a ReplicationProfile.
    Method: PATCH
    Endpoint: /replication-profiles/{replicationProfileId}
    Required Parameters: replication_profile_id
    Key Parameters (provide as applicable): name, replication_mode, target_engine_id, target_host, target_port, nfs_share, description, schedule, enable_tag_replication, bandwidth_limit, number_of_connections, encrypted, automatic_replication, use_system_socks_setting, vdb_ids, dsource_ids, cdb_ids, vcdb_ids, group_ids, replicate_entire_engine
    
    Example:
        >>> replication_tool(action='update', replication_profile_id='example-replication_profile-123', name=..., replication_mode=..., target_engine_id='example-target_engine-123', target_host=..., target_port=..., nfs_share=..., description=..., schedule=..., enable_tag_replication=..., bandwidth_limit=..., number_of_connections=..., encrypted=..., automatic_replication=..., use_system_socks_setting=..., vdb_ids=..., dsource_ids=..., cdb_ids=..., vcdb_ids=..., group_ids=..., replicate_entire_engine=...)
    
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
    
    ACTION: enable_tag_replication
    ----------------------------------------
    Summary: Enable tag replication for given ReplicationProfile.
    Method: POST
    Endpoint: /replication-profiles/{replicationProfileId}/enable-tag-replication
    Required Parameters: replication_profile_id
    
    Example:
        >>> replication_tool(action='enable_tag_replication', replication_profile_id='example-replication_profile-123')
    
    ACTION: disable_tag_replication
    ----------------------------------------
    Summary: Disable tag replication for given ReplicationProfile.
    Method: POST
    Endpoint: /replication-profiles/{replicationProfileId}/disable-tag-replication
    Required Parameters: replication_profile_id
    
    Example:
        >>> replication_tool(action='disable_tag_replication', replication_profile_id='example-replication_profile-123')
    
    ACTION: get_tags
    ----------------------------------------
    Summary: Get tags for a ReplicationProfile.
    Method: GET
    Endpoint: /replication-profiles/{replicationProfileId}/tags
    Required Parameters: replication_profile_id
    
    Example:
        >>> replication_tool(action='get_tags', replication_profile_id='example-replication_profile-123')
    
    ACTION: add_tags
    ----------------------------------------
    Summary: Create tags for a ReplicationProfile.
    Method: POST
    Endpoint: /replication-profiles/{replicationProfileId}/tags
    Required Parameters: replication_profile_id, tags
    
    Example:
        >>> replication_tool(action='add_tags', replication_profile_id='example-replication_profile-123', tags=...)
    
    ACTION: delete_tags
    ----------------------------------------
    Summary: Delete tags for a ReplicationProfile.
    Method: POST
    Endpoint: /replication-profiles/{replicationProfileId}/tags/delete
    Required Parameters: replication_profile_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> replication_tool(action='delete_tags', replication_profile_id='example-replication_profile-123', tags=..., key=..., value=...)
    
    ACTION: list_namespaces
    ----------------------------------------
    Summary: List all namespaces.
    Method: GET
    Endpoint: /namespaces
    Required Parameters: limit, cursor, sort
    
    Example:
        >>> replication_tool(action='list_namespaces', limit=..., cursor=..., sort=...)
    
    ACTION: search_namespaces
    ----------------------------------------
    Summary: Search Namespaces.
    Method: POST
    Endpoint: /namespaces/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - id: The Namespace ID.
        - name: The Namespace name.
        - tag: This is the tag of the Replication profile that created t...
        - engine_id: The ID of the engine that the Namespace belongs to.
        - description: A description of the namespace.
        - secure_namespace: True if the source data stream was generated from a Repli...
        - failed_over: True if the namespace has been failed over into the live ...
        - failover_report: If the namespace has been failed over, this contains a re...
        - locked: True if the namespace is locked.
        - failback_possible: True if the namespace can be failed back.
        - failback_capability: Whether the namespace is capable of failback
        - failback_incapability_reason: When incapable, the reason why the namespace is incompati...
        - replication_mode: The replication mode of the associated ReplicationProfile...
        - last_execution_status: The status of the last execution of the ReplicationProfil...
        - last_execution_status_timestamp: The timestamp of the last execution status of the Replica...
        - source_engine_id: The ID of the source engine that the ReplicationProfile t...
        - source_engine_name: The name of the source engine that the ReplicationProfile...
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> replication_tool(action='search_namespaces', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get_namespace
    ----------------------------------------
    Summary: Get a namespace.
    Method: GET
    Endpoint: /namespace/{namespaceId}
    Required Parameters: namespace_id
    
    Example:
        >>> replication_tool(action='get_namespace', namespace_id='example-namespace-123')
    
    ACTION: update_namespace
    ----------------------------------------
    Summary: Update a Namespace.
    Method: PATCH
    Endpoint: /namespace/{namespaceId}
    Required Parameters: namespace_id
    Key Parameters (provide as applicable): name, description
    
    Example:
        >>> replication_tool(action='update_namespace', name=..., description=..., namespace_id='example-namespace-123')
    
    ACTION: delete_namespace
    ----------------------------------------
    Summary: Delete a Namespace.
    Method: DELETE
    Endpoint: /namespace/{namespaceId}
    Required Parameters: namespace_id
    
    Example:
        >>> replication_tool(action='delete_namespace', namespace_id='example-namespace-123')
    
    ACTION: failover_namespace
    ----------------------------------------
    Summary: Initiates failover for the given namespace.
    Method: POST
    Endpoint: /namespace/{namespaceId}/failover
    Required Parameters: namespace_id
    Key Parameters (provide as applicable): enable_failback
    
    Example:
        >>> replication_tool(action='failover_namespace', namespace_id='example-namespace-123', enable_failback=...)
    
    ACTION: commit_failover_namespace
    ----------------------------------------
    Summary: Commits the failover of a given namespace and discards the failback state.
    Method: POST
    Endpoint: /namespace/{namespaceId}/commitFailover
    Required Parameters: namespace_id
    
    Example:
        >>> replication_tool(action='commit_failover_namespace', namespace_id='example-namespace-123')
    
    ACTION: failback_namespace
    ----------------------------------------
    Summary: Initiates failback for the given namespace.
    Method: POST
    Endpoint: /namespace/{namespaceId}/failback
    Required Parameters: namespace_id
    
    Example:
        >>> replication_tool(action='failback_namespace', namespace_id='example-namespace-123')
    
    ACTION: discard_namespace
    ----------------------------------------
    Summary: Discards any partial receive state for the given namespace.
    Method: POST
    Endpoint: /namespace/{namespaceId}/discard
    Required Parameters: namespace_id
    
    Example:
        >>> replication_tool(action='discard_namespace', namespace_id='example-namespace-123')
    
    ACTION: get_heldspace_deletion_dependencies
    ----------------------------------------
    Summary: Get heldspace deletion dependencies.
    Method: GET
    Endpoint: /heldspace/{heldspaceId}/deletion-dependencies
    Required Parameters: heldspace_id
    
    Example:
        >>> replication_tool(action='get_heldspace_deletion_dependencies', heldspace_id='example-heldspace-123')
    
    ACTION: delete_heldspace
    ----------------------------------------
    Summary: Delete a HeldSpace.
    Method: POST
    Endpoint: /heldspace/{heldspaceId}/delete
    Required Parameters: heldspace_id
    
    Example:
        >>> replication_tool(action='delete_heldspace', heldspace_id='example-heldspace-123')
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, create, update, delete, execute, enable_tag_replication, disable_tag_replication, get_tags, add_tags, delete_tags, list_namespaces, search_namespaces, get_namespace, update_namespace, delete_namespace, failover_namespace, commit_failover_namespace, failback_namespace, discard_namespace, get_heldspace_deletion_dependencies, delete_heldspace
    
      -- General parameters (all database types) --
        automatic_replication (bool): Indication whether the replication spec schedule is enabled or not. (Default:...
            [Optional for all actions]
        bandwidth_limit (int): Bandwidth limit (MB/s) for replication network traffic. A value of 0 means no...
            [Optional for all actions]
        cdb_ids (list): The CDBs that are replicated by this ReplicationProfile. (Pass as JSON array)
            [Optional for all actions]
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search, list_namespaces, search_namespaces]
        description (str): The ReplicationProfile description.
            [Optional for all actions]
        dsource_ids (list): The dSources that are replicated by this ReplicationProfile. (Pass as JSON ar...
            [Optional for all actions]
        enable_failback (bool): Whether to enable failback for the datasets being failed over. (Default: False)
            [Optional for all actions]
        enable_tag_replication (bool): Indicates whether tag replication from primary object to replica object is en...
            [Optional for all actions]
        encrypted (bool): Encrypt replication network traffic. This field is specific to network replic...
            [Optional for all actions]
        engine_id (str): The ID of the engine that the ReplicationProfile belongs to.
            [Required for: create]
        filter_expression (str): Request body parameter
            [Optional for all actions]
        group_ids (list): The groups that are replicated by this ReplicationProfile. (Pass as JSON array)
            [Optional for all actions]
        heldspace_id (str): The unique identifier for the heldspace.
            [Required for: get_heldspace_deletion_dependencies, delete_heldspace]
        key (str): Key of the tag
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search, list_namespaces, search_namespaces]
        name (str): The ReplicationProfile name.
            [Optional for all actions]
        namespace_id (str): The unique identifier for the namespace.
            [Required for: get_namespace, update_namespace, delete_namespace, failover_namespace, commit_failover_namespace, failback_namespace, discard_namespace]
        nfs_share (str): The NFS share path for the replication target. This field is specific to offl...
            [Optional for all actions]
        number_of_connections (int): Total number of transport connections to use. This field is specific to netwo...
            [Optional for all actions]
        offline_send_profile_tag (str): The unique tag identifier for the offline send profile. This field is specifi...
            [Optional for all actions]
        replicate_entire_engine (bool): Whether to replicate the entire engine. This is mutually exclusive with the v...
            [Optional for all actions]
        replication_mode (str): The ReplicationProfile mode. Valid values: ENGINE_DATA_REPLICATION, MASKED_DA...
            [Required for: create]
        replication_profile_id (str): The unique identifier for the replicationProfile.
            [Required for: get, update, delete, execute, enable_tag_replication, disable_tag_replication, get_tags, add_tags, delete_tags]
        schedule (str): Replication schedule in the form of a quartz-formatted string.
            [Optional for all actions]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search, list_namespaces, search_namespaces]
        tags (list): The tags that are applied to this ReplicationProfile. (Pass as JSON array)
            [Required for: add_tags]
        target_engine_id (str): The ID of the replication target engine. This field is specific to network re...
            [Optional for all actions]
        target_host (str): Hostname of the replication target engine. If none is provided, the hostname ...
            [Optional for all actions]
        target_port (int): Target TCP port number for the Delphix Session Protocol. This field is specif...
            [Optional for all actions]
        use_system_socks_setting (bool): Connect to the replication target host via the system-wide SOCKS proxy. This ...
            [Optional for all actions]
        value (str): Value of the tag
            [Optional for all actions]
        vcdb_ids (list): The vCDBs that are replicated by this ReplicationProfile. (Pass as JSON array)
            [Optional for all actions]
        vdb_ids (list): The VDBs that are replicated by this ReplicationProfile. (Pass as JSON array)
            [Optional for all actions]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'search':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('POST', '/replication-profiles/search', action, 'replication_tool', confirmed or False)
        if conf:
            return conf
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/replication-profiles/search', params=params, json_body=body)
    elif action == 'get':
        if replication_profile_id is None:
            return {'error': 'Missing required parameter: replication_profile_id for action get'}
        endpoint = f'/replication-profiles/{replication_profile_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'replication_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'create':
        params = build_params(replication_mode=replication_mode)
        conf = check_confirmation('POST', '/replication-profiles', action, 'replication_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name, 'replication_mode': replication_mode, 'engine_id': engine_id, 'target_engine_id': target_engine_id, 'target_host': target_host, 'target_port': target_port, 'nfs_share': nfs_share, 'offline_send_profile_tag': offline_send_profile_tag, 'description': description, 'schedule': schedule, 'tags': tags, 'enable_tag_replication': enable_tag_replication, 'bandwidth_limit': bandwidth_limit, 'number_of_connections': number_of_connections, 'encrypted': encrypted, 'automatic_replication': automatic_replication, 'use_system_socks_setting': use_system_socks_setting, 'vdb_ids': vdb_ids, 'dsource_ids': dsource_ids, 'cdb_ids': cdb_ids, 'vcdb_ids': vcdb_ids, 'group_ids': group_ids, 'replicate_entire_engine': replicate_entire_engine}.items() if v is not None}
        return make_api_request('POST', '/replication-profiles', params=params, json_body=body if body else None)
    elif action == 'update':
        if replication_profile_id is None:
            return {'error': 'Missing required parameter: replication_profile_id for action update'}
        endpoint = f'/replication-profiles/{replication_profile_id}'
        params = build_params()
        conf = check_confirmation('PATCH', endpoint, action, 'replication_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name, 'description': description, 'target_engine_id': target_engine_id, 'target_host': target_host, 'target_port': target_port, 'nfs_share': nfs_share, 'replication_mode': replication_mode, 'schedule': schedule, 'vdb_ids': vdb_ids, 'dsource_ids': dsource_ids, 'cdb_ids': cdb_ids, 'vcdb_ids': vcdb_ids, 'group_ids': group_ids, 'enable_tag_replication': enable_tag_replication, 'replicate_entire_engine': replicate_entire_engine, 'bandwidth_limit': bandwidth_limit, 'number_of_connections': number_of_connections, 'encrypted': encrypted, 'automatic_replication': automatic_replication, 'use_system_socks_setting': use_system_socks_setting}.items() if v is not None}
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete':
        if replication_profile_id is None:
            return {'error': 'Missing required parameter: replication_profile_id for action delete'}
        endpoint = f'/replication-profiles/{replication_profile_id}'
        params = build_params()
        conf = check_confirmation('DELETE', endpoint, action, 'replication_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'execute':
        if replication_profile_id is None:
            return {'error': 'Missing required parameter: replication_profile_id for action execute'}
        endpoint = f'/replication-profiles/{replication_profile_id}/execute'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'replication_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'enable_tag_replication':
        if replication_profile_id is None:
            return {'error': 'Missing required parameter: replication_profile_id for action enable_tag_replication'}
        endpoint = f'/replication-profiles/{replication_profile_id}/enable-tag-replication'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'replication_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'disable_tag_replication':
        if replication_profile_id is None:
            return {'error': 'Missing required parameter: replication_profile_id for action disable_tag_replication'}
        endpoint = f'/replication-profiles/{replication_profile_id}/disable-tag-replication'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'replication_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'get_tags':
        if replication_profile_id is None:
            return {'error': 'Missing required parameter: replication_profile_id for action get_tags'}
        endpoint = f'/replication-profiles/{replication_profile_id}/tags'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'replication_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_tags':
        if replication_profile_id is None:
            return {'error': 'Missing required parameter: replication_profile_id for action add_tags'}
        endpoint = f'/replication-profiles/{replication_profile_id}/tags'
        params = build_params(tags=tags)
        conf = check_confirmation('POST', endpoint, action, 'replication_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_tags':
        if replication_profile_id is None:
            return {'error': 'Missing required parameter: replication_profile_id for action delete_tags'}
        endpoint = f'/replication-profiles/{replication_profile_id}/tags/delete'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'replication_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'list_namespaces':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('GET', '/namespaces', action, 'replication_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', '/namespaces', params=params)
    elif action == 'search_namespaces':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('POST', '/namespaces/search', action, 'replication_tool', confirmed or False)
        if conf:
            return conf
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/namespaces/search', params=params, json_body=body)
    elif action == 'get_namespace':
        if namespace_id is None:
            return {'error': 'Missing required parameter: namespace_id for action get_namespace'}
        endpoint = f'/namespace/{namespace_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'replication_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'update_namespace':
        if namespace_id is None:
            return {'error': 'Missing required parameter: namespace_id for action update_namespace'}
        endpoint = f'/namespace/{namespace_id}'
        params = build_params()
        conf = check_confirmation('PATCH', endpoint, action, 'replication_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'name': name, 'description': description}.items() if v is not None}
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_namespace':
        if namespace_id is None:
            return {'error': 'Missing required parameter: namespace_id for action delete_namespace'}
        endpoint = f'/namespace/{namespace_id}'
        params = build_params()
        conf = check_confirmation('DELETE', endpoint, action, 'replication_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'failover_namespace':
        if namespace_id is None:
            return {'error': 'Missing required parameter: namespace_id for action failover_namespace'}
        endpoint = f'/namespace/{namespace_id}/failover'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'replication_tool', confirmed or False)
        if conf:
            return conf
        body = {k: v for k, v in {'enable_failback': enable_failback}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'commit_failover_namespace':
        if namespace_id is None:
            return {'error': 'Missing required parameter: namespace_id for action commit_failover_namespace'}
        endpoint = f'/namespace/{namespace_id}/commitFailover'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'replication_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'failback_namespace':
        if namespace_id is None:
            return {'error': 'Missing required parameter: namespace_id for action failback_namespace'}
        endpoint = f'/namespace/{namespace_id}/failback'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'replication_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'discard_namespace':
        if namespace_id is None:
            return {'error': 'Missing required parameter: namespace_id for action discard_namespace'}
        endpoint = f'/namespace/{namespace_id}/discard'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'replication_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'get_heldspace_deletion_dependencies':
        if heldspace_id is None:
            return {'error': 'Missing required parameter: heldspace_id for action get_heldspace_deletion_dependencies'}
        endpoint = f'/heldspace/{heldspace_id}/deletion-dependencies'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'replication_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'delete_heldspace':
        if heldspace_id is None:
            return {'error': 'Missing required parameter: heldspace_id for action delete_heldspace'}
        endpoint = f'/heldspace/{heldspace_id}/delete'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'replication_tool', confirmed or False)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, create, update, delete, execute, enable_tag_replication, disable_tag_replication, get_tags, add_tags, delete_tags, list_namespaces, search_namespaces, get_namespace, update_namespace, delete_namespace, failover_namespace, commit_failover_namespace, failback_namespace, discard_namespace, get_heldspace_deletion_dependencies, delete_heldspace'}


def register_tools(app, dct_client):
    global client
    client = dct_client
    logger.info(f'Registering tools for policy_endpoints...')
    try:
        logger.info(f'  Registering tool function: virtualization_policy_tool')
        app.add_tool(virtualization_policy_tool, name="virtualization_policy_tool")
        logger.info(f'  Registering tool function: replication_tool')
        app.add_tool(replication_tool, name="replication_tool")
    except Exception as e:
        logger.error(f'Error registering tools for policy_endpoints: {e}')
    logger.info(f'Tools registration finished for policy_endpoints.')
