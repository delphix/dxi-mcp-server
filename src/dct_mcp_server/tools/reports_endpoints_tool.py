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
def reporting_tool(
    action: str,  # One of: search_storage_savings_report, search_vdb_inventory_report, get_dataset_performance_analytics, search_scheduled_reports, get_scheduled_report, create_scheduled_report, delete_scheduled_report, get_license, get_virtualization_jobs_history, search_virtualization_jobs_history, get_virtualization_actions_history, search_virtualization_actions_history, get_virtualization_faults_history, search_virtualization_faults_history, resolve_or_ignore_faults, resolve_all_engine_faults, resolve_fault, get_virtualization_alerts_history, search_virtualization_alerts_history
    cron_expression: Optional[str] = None,
    cursor: Optional[str] = None,
    dataset_ids: Optional[list] = None,
    enabled: Optional[bool] = None,
    end: Optional[str] = None,
    engine_id: Optional[str] = None,
    fault_id: Optional[str] = None,
    fault_ids: Optional[list] = None,
    file_format: Optional[str] = None,
    filter_expression: Optional[str] = None,
    ignore: Optional[bool] = None,
    interval: Optional[int] = None,
    limit: Optional[int] = 10000,
    make_current_account_owner: Optional[bool] = None,
    message: Optional[str] = None,
    object_id: Optional[str] = None,
    recipients: Optional[list] = None,
    report_id: Optional[str] = None,
    report_type: Optional[str] = None,
    resolution_comments: Optional[str] = None,
    row_count: Optional[int] = None,
    sort: Optional[str] = None,
    sort_column: Optional[str] = None,
    start: Optional[str] = None,
    time_zone: Optional[str] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for REPORTING operations.
    
    This tool supports 19 actions: search_storage_savings_report, search_vdb_inventory_report, get_dataset_performance_analytics, search_scheduled_reports, get_scheduled_report, create_scheduled_report, delete_scheduled_report, get_license, get_virtualization_jobs_history, search_virtualization_jobs_history, get_virtualization_actions_history, search_virtualization_actions_history, get_virtualization_faults_history, search_virtualization_faults_history, resolve_or_ignore_faults, resolve_all_engine_faults, resolve_fault, get_virtualization_alerts_history, search_virtualization_alerts_history
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search_storage_savings_report
    ----------------------------------------
    Summary: Search the saving storage summary report for virtualization engines.
    Method: POST
    Endpoint: /reporting/storage-savings-report/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - dsource_id: Id of the dSource.
        - dependant_vdbs: The number of VDBs that are dependant on this dSource. Th...
        - engine_name: The engine name.
        - unvirtualized_space: The disk space, in bytes, that it would take to store the...
        - current_timeflows_unvirtualized_space: The disk space, in bytes, that it would take to store the...
        - virtualized_space: The actual space used by the dSource and its dependant VD...
        - name: The name of the database on the target environment.
        - estimated_savings: The disk space that has been saved by using Delphix virtu...
        - estimated_savings_perc: The disk space that has been saved by using Delphix virtu...
        - estimated_current_timeflows_savings: The disk space that has been saved by using Delphix virtu...
        - estimated_current_timeflows_savings_perc: The disk space that has been saved by using Delphix virtu...
        - is_replica: Indicates if the dSource is a replica
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> reporting_tool(action='search_storage_savings_report', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: search_vdb_inventory_report
    ----------------------------------------
    Summary: Search the inventory report for virtualization engine VDBs.
    Method: POST
    Endpoint: /reporting/vdb-inventory-report/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - vdb_id: The VDB id.
        - engine_name: The name of the engine the VDB belongs to.
        - name: The name of the VDB.
        - type: The database type of the VDB.
        - version: The database version of the VDB.
        - parent_name: The name of the VDB's parent dataset.
        - parent_id: A reference to the parent dataset of the VDB.
        - creation_date: The date the VDB was created.
        - last_refreshed_date: The date the VDB was last refreshed.
        - parent_timeflow_location: The location for the VDB's parent timeflow.
        - parent_timeflow_timestamp: The timestamp for the VDB's parent timeflow.
        - parent_timeflow_timezone: The timezone for the VDB's parent timeflow.
        - enabled: Whether the VDB is enabled
        - status: The runtime status of the VDB. 'Unknown' if all attempts ...
        - storage_size: The actual space used by the VDB, in bytes.
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> reporting_tool(action='search_vdb_inventory_report', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get_dataset_performance_analytics
    ----------------------------------------
    Summary: Get Dataset Performance analytics
    Method: POST
    Endpoint: /reporting/dataset-performance-analytics
    Required Parameters: dataset_ids, start, end, interval
    
    Example:
        >>> reporting_tool(action='get_dataset_performance_analytics', dataset_ids=..., start=..., end=..., interval=...)
    
    ACTION: search_scheduled_reports
    ----------------------------------------
    Summary: Search for report schedules.
    Method: POST
    Endpoint: /reporting/schedule/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - report_id: 
        - report_type: 
        - cron_expression: Standard cron expressions are supported e.g. 0 15 10 L * ...
        - time_zone: Timezones are specified according to the Olson tzinfo dat...
        - message: 
        - file_format: 
        - enabled: 
        - recipients: 
        - tags: 
        - sort_column: 
        - row_count: 
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> reporting_tool(action='search_scheduled_reports', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get_scheduled_report
    ----------------------------------------
    Summary: Returns a report schedule by ID.
    Method: GET
    Endpoint: /reporting/schedule/{reportId}
    Required Parameters: report_id
    
    Example:
        >>> reporting_tool(action='get_scheduled_report', report_id='example-report-123')
    
    ACTION: create_scheduled_report
    ----------------------------------------
    Summary: Create a new report schedule.
    Method: POST
    Endpoint: /reporting/schedule
    Required Parameters: report_type, cron_expression, message, file_format, enabled, recipients
    Key Parameters (provide as applicable): time_zone, sort_column, row_count, make_current_account_owner
    
    Example:
        >>> reporting_tool(action='create_scheduled_report', report_type=..., cron_expression=..., time_zone=..., message=..., file_format=..., enabled=..., recipients=..., sort_column=..., row_count=..., make_current_account_owner=...)
    
    ACTION: delete_scheduled_report
    ----------------------------------------
    Summary: Delete report schedule by ID.
    Method: DELETE
    Endpoint: /reporting/schedule/{reportId}
    Required Parameters: report_id
    
    Example:
        >>> reporting_tool(action='delete_scheduled_report', report_id='example-report-123')
    
    ACTION: get_license
    ----------------------------------------
    Summary: Returns the DCT license information.
    Method: GET
    Endpoint: /management/license
    
    Example:
        >>> reporting_tool(action='get_license')
    
    ACTION: get_virtualization_jobs_history
    ----------------------------------------
    Summary: Fetch a list of all virtualization jobs
    Method: GET
    Endpoint: /virtualization-jobs/history
    Required Parameters: limit, cursor, sort, object_id
    
    Example:
        >>> reporting_tool(action='get_virtualization_jobs_history', limit=..., cursor=..., sort=..., object_id='example-object-123')
    
    ACTION: search_virtualization_jobs_history
    ----------------------------------------
    Summary: Search virtualization jobs
    Method: POST
    Endpoint: /virtualization-jobs/history/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - engine_job_id: ID of the virtualization engine job.
        - engine_id: ID of the RegisteredEngine.
        - legacy_job_type: Legacy type of the job.
        - job_type: 
        - target_object_id: ID of the target object.
        - legacy_target_object_type: Legacy type of the target object.
        - target_object_type: 
        - job_state: 
        - start_time: The time the job started.
        - update_time: The time the job was last updated.
        - suspendable: Indicates whether the job can be suspended.
        - cancelable: Indicates whether the job can be canceled.
        - queued: Indicates whether the job is queued.
        - title: The title of the job.
        - cancel_reason: The reason the job was canceled.
        - percent_complete: The percentage of the job that is complete.
        - run_duration: The time this job took to complete in milliseconds.
        - events: The events associated with this job.
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> reporting_tool(action='search_virtualization_jobs_history', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get_virtualization_actions_history
    ----------------------------------------
    Summary: Fetch a list of all virtualization actions
    Method: GET
    Endpoint: /virtualization-actions/history
    Required Parameters: limit, cursor, sort
    
    Example:
        >>> reporting_tool(action='get_virtualization_actions_history', limit=..., cursor=..., sort=...)
    
    ACTION: search_virtualization_actions_history
    ----------------------------------------
    Summary: Search virtualization actions
    Method: POST
    Endpoint: /virtualization-actions/history/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - id: ID of the virtualization engine action.
        - engine_id: ID of the RegisteredEngine.
        - action_type: Type of the action.
        - title: The title of the action.
        - details: Plain text description of the action.
        - start_time: The time the action occurred. For long running processes,...
        - end_time: The time the action completed.
        - user: The user who initiated the action.
        - user_agent: Name of client software used to initiate the action.
        - origin_ip: Network address used to initiate the action.
        - parent_action: The parent action of this action.
        - state: The state of the action.
        - work_source: Origin of the work that caused the action.
        - work_source_name: Name of user or policy that initiated the action.
        - work_source_principal: Principal of user that initiated the action.
        - failure_description: Details of the action failure.
        - failure_action: Action to be taken to resolve the failure.
        - failure_message_code: Message ID associated with the event.
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> reporting_tool(action='search_virtualization_actions_history', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get_virtualization_faults_history
    ----------------------------------------
    Summary: Fetch a list of all virtualization faults
    Method: GET
    Endpoint: /virtualization-faults/history
    Required Parameters: limit, cursor, sort
    
    Example:
        >>> reporting_tool(action='get_virtualization_faults_history', limit=..., cursor=..., sort=...)
    
    ACTION: search_virtualization_faults_history
    ----------------------------------------
    Summary: Search virtualization faults
    Method: POST
    Endpoint: /virtualization-faults/history/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - id: ID of the virtualization engine fault.
        - engine_id: ID of the RegisteredEngine.
        - bundle_id: A unique dot delimited identifier associated with the fault.
        - target_name: The name of the faulted object at the time the fault was ...
        - target_object_type: The type of the object that is faulted.
        - target_object_id: The ID of the object that is faulted.
        - title: The summary of the fault.
        - description: The full description of the fault.
        - fault_action: The suggested action to be taken.
        - response: The automated response taken by the Delphix engine.
        - severity: The severity of the fault event.
        - status: The status of the fault.
        - date_diagnosed: The date when the fault was diagnosed.
        - date_resolved: The date when the fault was resolved.
        - resolution_comments: A comment that describes the fault resolution.
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> reporting_tool(action='search_virtualization_faults_history', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: resolve_or_ignore_faults
    ----------------------------------------
    Summary: Marks selected faults as resolved or ignored.
    Method: POST
    Endpoint: /virtualization-faults/resolveOrIgnore
    Key Parameters (provide as applicable): engine_id, ignore, fault_ids
    
    Example:
        >>> reporting_tool(action='resolve_or_ignore_faults', engine_id='example-engine-123', ignore=..., fault_ids=...)
    
    ACTION: resolve_all_engine_faults
    ----------------------------------------
    Summary: Marks all active faults of an engine that the user has permissions over as resolved.
    Method: POST
    Endpoint: /virtualization-faults/{engineId}/resolveAll
    Required Parameters: engine_id
    
    Example:
        >>> reporting_tool(action='resolve_all_engine_faults', engine_id='example-engine-123')
    
    ACTION: resolve_fault
    ----------------------------------------
    Summary: Marks the fault as resolved. The Delphix engine will attempt to automatically detect cases where the fault has been resolved; but this is not always possible and may only occur on periodic intervals. In these cases, the user can proactively mark the fault resolved. This does not change the underlying disposition of the fault - if the problem is still present the system may immediately diagnose the same problem again. This should only be used to notify the system of resolution after the underlying problem has been resolved.
    Method: POST
    Endpoint: /virtualization-fault/{faultId}/resolve
    Required Parameters: fault_id
    Key Parameters (provide as applicable): ignore, resolution_comments
    
    Example:
        >>> reporting_tool(action='resolve_fault', ignore=..., fault_id='example-fault-123', resolution_comments=...)
    
    ACTION: get_virtualization_alerts_history
    ----------------------------------------
    Summary: Fetch a list of all virtualization alerts
    Method: GET
    Endpoint: /virtualization-alerts/history
    Required Parameters: limit, cursor, sort
    
    Example:
        >>> reporting_tool(action='get_virtualization_alerts_history', limit=..., cursor=..., sort=...)
    
    ACTION: search_virtualization_alerts_history
    ----------------------------------------
    Summary: Search virtualization alerts
    Method: POST
    Endpoint: /virtualization-alerts/history/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - id: ID of the virtualization engine alert.
        - engine_id: ID of the RegisteredEngine.
        - alert_timestamp: The time the alert occurred.
        - event: The event that caused the alert.
        - event_severity: The severity of the alert.
        - event_title: The title of the event.
        - event_response: The response needed to address the event.
        - event_action: Action(s) to be taken to address the event.
        - event_command_output: Command output associated with the event.
        - event_description: Description of the event.
        - target_object_type: The type of the target object for the event.
        - target_object_id: The ID of the target object.
        - target_name: The name of the target object.
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> reporting_tool(action='search_virtualization_alerts_history', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search_storage_savings_report, search_vdb_inventory_report, get_dataset_performance_analytics, search_scheduled_reports, get_scheduled_report, create_scheduled_report, delete_scheduled_report, get_license, get_virtualization_jobs_history, search_virtualization_jobs_history, get_virtualization_actions_history, search_virtualization_actions_history, get_virtualization_faults_history, search_virtualization_faults_history, resolve_or_ignore_faults, resolve_all_engine_faults, resolve_fault, get_virtualization_alerts_history, search_virtualization_alerts_history
    
      -- General parameters (all database types) --
        cron_expression (str): Standard cron expressions are supported e.g. 0 15 10 L * ?  - Schedule at 10:...
            [Required for: create_scheduled_report]
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search_storage_savings_report, search_vdb_inventory_report, search_scheduled_reports, get_virtualization_jobs_history, search_virtualization_jobs_history, get_virtualization_actions_history, search_virtualization_actions_history, get_virtualization_faults_history, search_virtualization_faults_history, get_virtualization_alerts_history, search_virtualization_alerts_history]
        dataset_ids (list): List of dataset ids for which dataset performance analytics should be fetched...
            [Required for: get_dataset_performance_analytics]
        enabled (bool): Request body parameter (Default: True)
            [Required for: create_scheduled_report]
        end (str): End time in UTC up to which analytics data will be fetched.
            [Required for: get_dataset_performance_analytics]
        engine_id (str): The ID of the engine that the faults belong to.
            [Required for: resolve_all_engine_faults]
        fault_id (str): The unique identifier for the fault.
            [Required for: resolve_fault]
        fault_ids (list): The IDs of the faults to resolve or ignore. (Pass as JSON array)
            [Optional for all actions]
        file_format (str): Request body parameter Valid values: CSV.
            [Required for: create_scheduled_report]
        filter_expression (str): Request body parameter
            [Optional for all actions]
        ignore (bool): Flag indicating whether to ignore the selected faults if they are detected on...
            [Optional for all actions]
        interval (int): Desired time interval in timestamp format.
            [Required for: get_dataset_performance_analytics]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search_storage_savings_report, search_vdb_inventory_report, search_scheduled_reports, get_virtualization_jobs_history, search_virtualization_jobs_history, get_virtualization_actions_history, search_virtualization_actions_history, get_virtualization_faults_history, search_virtualization_faults_history, get_virtualization_alerts_history, search_virtualization_alerts_history]
        make_current_account_owner (bool): Whether the account creating this reporting schedule must be configured as ow...
            [Optional for all actions]
        message (str): Request body parameter
            [Required for: create_scheduled_report]
        object_id (str): The object id to filter by.
            [Required for: get_virtualization_jobs_history]
        recipients (list): Request body parameter (Pass as JSON array)
            [Required for: create_scheduled_report]
        report_id (str): The unique identifier for the report.
            [Required for: get_scheduled_report, delete_scheduled_report]
        report_type (str): Request body parameter Valid values: VIRTUALIZATION_STORAGE_SUMMARY, ENGINE_P...
            [Required for: create_scheduled_report]
        resolution_comments (str): The comments describing the steps taken to resolve a fault.
            [Optional for all actions]
        row_count (int): Request body parameter
            [Optional for all actions]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search_storage_savings_report, search_vdb_inventory_report, search_scheduled_reports, get_virtualization_jobs_history, search_virtualization_jobs_history, get_virtualization_actions_history, search_virtualization_actions_history, get_virtualization_faults_history, search_virtualization_faults_history, get_virtualization_alerts_history, search_virtualization_alerts_history]
        sort_column (str): Request body parameter Valid values: engine_id, engine_name, engine_hostname,...
            [Optional for all actions]
        start (str): Start time in UTC from which to fetch analytics data.
            [Required for: get_dataset_performance_analytics]
        time_zone (str): Timezones are specified according to the Olson tzinfo database - "https://en....
            [Optional for all actions]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'search_storage_savings_report':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', '/reporting/storage-savings-report/search', action, 'reporting_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/reporting/storage-savings-report/search', params=params, json_body=body)
    elif action == 'search_vdb_inventory_report':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', '/reporting/vdb-inventory-report/search', action, 'reporting_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/reporting/vdb-inventory-report/search', params=params, json_body=body)
    elif action == 'get_dataset_performance_analytics':
        params = build_params(dataset_ids=dataset_ids, start=start, end=end, interval=interval)
        body = {k: v for k, v in {'dataset_ids': dataset_ids, 'start': start, 'end': end, 'interval': interval}.items() if v is not None}
        conf = check_confirmation('POST', '/reporting/dataset-performance-analytics', action, 'reporting_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/reporting/dataset-performance-analytics', params=params, json_body=body if body else None)
    elif action == 'search_scheduled_reports':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', '/reporting/schedule/search', action, 'reporting_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/reporting/schedule/search', params=params, json_body=body)
    elif action == 'get_scheduled_report':
        if report_id is None:
            return {'error': 'Missing required parameter: report_id for action get_scheduled_report'}
        endpoint = f'/reporting/schedule/{report_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'reporting_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'create_scheduled_report':
        params = build_params(report_type=report_type, cron_expression=cron_expression, message=message, file_format=file_format, enabled=enabled, recipients=recipients)
        body = {k: v for k, v in {'report_type': report_type, 'cron_expression': cron_expression, 'time_zone': time_zone, 'message': message, 'file_format': file_format, 'enabled': enabled, 'recipients': recipients, 'sort_column': sort_column, 'row_count': row_count, 'make_current_account_owner': make_current_account_owner}.items() if v is not None}
        conf = check_confirmation('POST', '/reporting/schedule', action, 'reporting_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/reporting/schedule', params=params, json_body=body if body else None)
    elif action == 'delete_scheduled_report':
        if report_id is None:
            return {'error': 'Missing required parameter: report_id for action delete_scheduled_report'}
        endpoint = f'/reporting/schedule/{report_id}'
        params = build_params()
        conf = check_confirmation('DELETE', endpoint, action, 'reporting_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'get_license':
        params = build_params()
        conf = check_confirmation('GET', '/management/license', action, 'reporting_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', '/management/license', params=params)
    elif action == 'get_virtualization_jobs_history':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('GET', '/virtualization-jobs/history', action, 'reporting_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', '/virtualization-jobs/history', params=params)
    elif action == 'search_virtualization_jobs_history':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', '/virtualization-jobs/history/search', action, 'reporting_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/virtualization-jobs/history/search', params=params, json_body=body)
    elif action == 'get_virtualization_actions_history':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('GET', '/virtualization-actions/history', action, 'reporting_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', '/virtualization-actions/history', params=params)
    elif action == 'search_virtualization_actions_history':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', '/virtualization-actions/history/search', action, 'reporting_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/virtualization-actions/history/search', params=params, json_body=body)
    elif action == 'get_virtualization_faults_history':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('GET', '/virtualization-faults/history', action, 'reporting_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', '/virtualization-faults/history', params=params)
    elif action == 'search_virtualization_faults_history':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', '/virtualization-faults/history/search', action, 'reporting_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/virtualization-faults/history/search', params=params, json_body=body)
    elif action == 'resolve_or_ignore_faults':
        params = build_params()
        body = {k: v for k, v in {'engine_id': engine_id, 'ignore': ignore, 'fault_ids': fault_ids}.items() if v is not None}
        conf = check_confirmation('POST', '/virtualization-faults/resolveOrIgnore', action, 'reporting_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/virtualization-faults/resolveOrIgnore', params=params, json_body=body if body else None)
    elif action == 'resolve_all_engine_faults':
        if engine_id is None:
            return {'error': 'Missing required parameter: engine_id for action resolve_all_engine_faults'}
        endpoint = f'/virtualization-faults/{engine_id}/resolveAll'
        params = build_params()
        conf = check_confirmation('POST', endpoint, action, 'reporting_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'resolve_fault':
        if fault_id is None:
            return {'error': 'Missing required parameter: fault_id for action resolve_fault'}
        endpoint = f'/virtualization-fault/{fault_id}/resolve'
        params = build_params()
        body = {k: v for k, v in {'ignore': ignore, 'resolution_comments': resolution_comments}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'reporting_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'get_virtualization_alerts_history':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('GET', '/virtualization-alerts/history', action, 'reporting_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', '/virtualization-alerts/history', params=params)
    elif action == 'search_virtualization_alerts_history':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', '/virtualization-alerts/history/search', action, 'reporting_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/virtualization-alerts/history/search', params=params, json_body=body)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search_storage_savings_report, search_vdb_inventory_report, get_dataset_performance_analytics, search_scheduled_reports, get_scheduled_report, create_scheduled_report, delete_scheduled_report, get_license, get_virtualization_jobs_history, search_virtualization_jobs_history, get_virtualization_actions_history, search_virtualization_actions_history, get_virtualization_faults_history, search_virtualization_faults_history, resolve_or_ignore_faults, resolve_all_engine_faults, resolve_fault, get_virtualization_alerts_history, search_virtualization_alerts_history'}


def register_tools(app, dct_client):
    global client
    client = dct_client
    logger.info(f'Registering tools for reports_endpoints...')
    try:
        logger.info(f'  Registering tool function: reporting_tool')
        app.add_tool(reporting_tool, name="reporting_tool")
    except Exception as e:
        logger.error(f'Error registering tools for reports_endpoints: {e}')
    logger.info(f'Tools registration finished for reports_endpoints.')
