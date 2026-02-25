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
def reporting_tool(
    action: str,  # One of: search_storage_savings_report, search_vdb_inventory_report, get_dataset_performance_analytics, search_scheduled_reports, get_scheduled_report, create_scheduled_report, delete_scheduled_report, get_license, change_license
    cursor: Optional[str] = None,
    end: Optional[str] = None,
    filter_expression: Optional[str] = None,
    interval: Optional[int] = None,
    limit: Optional[int] = None,
    report_id: Optional[str] = None,
    sort: Optional[str] = None,
    start: Optional[str] = None,
    tier: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Unified tool for REPORTING operations.
    
    This tool supports 9 actions: search_storage_savings_report, search_vdb_inventory_report, get_dataset_performance_analytics, search_scheduled_reports, get_scheduled_report, create_scheduled_report, delete_scheduled_report, get_license, change_license
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search_storage_savings_report
    ----------------------------------------
    Summary: Search the saving storage summary report for virtualization engines.
    Method: POST
    Endpoint: /reporting/storage-savings-report/search
    Required Parameters: limit, cursor, sort
    
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
        >>> reporting_tool(action='search_storage_savings_report', limit=..., cursor=..., sort=...)
    
    ACTION: search_vdb_inventory_report
    ----------------------------------------
    Summary: Search the inventory report for virtualization engine VDBs.
    Method: POST
    Endpoint: /reporting/vdb-inventory-report/search
    Required Parameters: limit, cursor, sort
    
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
        >>> reporting_tool(action='search_vdb_inventory_report', limit=..., cursor=..., sort=...)
    
    ACTION: get_dataset_performance_analytics
    ----------------------------------------
    Summary: Get Dataset Performance analytics
    Method: POST
    Endpoint: /reporting/dataset-performance-analytics
    Required Parameters: start, end, interval
    
    Example:
        >>> reporting_tool(action='get_dataset_performance_analytics', start=..., end=..., interval=...)
    
    ACTION: search_scheduled_reports
    ----------------------------------------
    Summary: Search for report schedules.
    Method: POST
    Endpoint: /reporting/schedule/search
    Required Parameters: limit, cursor, sort
    
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
        >>> reporting_tool(action='search_scheduled_reports', limit=..., cursor=..., sort=...)
    
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
    
    Example:
        >>> reporting_tool(action='create_scheduled_report')
    
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
    
    ACTION: change_license
    ----------------------------------------
    Summary: Change the current DCT license.
    Method: POST
    Endpoint: /management/license/change-license
    Required Parameters: tier
    
    Example:
        >>> reporting_tool(action='change_license', tier=...)
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search_storage_savings_report, search_vdb_inventory_report, get_dataset_performance_analytics, search_scheduled_reports, get_scheduled_report, create_scheduled_report, delete_scheduled_report, get_license, change_license
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search_storage_savings_report, search_vdb_inventory_report, search_scheduled_reports]
        end (str): End time in UTC up to which analytics data will be fetched.
            [Required for: get_dataset_performance_analytics]
        filter_expression (str): Filter expression to narrow results (e.g., "name CONTAINS 'prod'")
            [Optional for all actions]
        interval (int): Desired time interval in timestamp format.
            [Required for: get_dataset_performance_analytics]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search_storage_savings_report, search_vdb_inventory_report, search_scheduled_reports]
        report_id (str): The unique identifier for the report.
            [Required for: get_scheduled_report, delete_scheduled_report]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search_storage_savings_report, search_vdb_inventory_report, search_scheduled_reports]
        start (str): Start time in UTC from which to fetch analytics data.
            [Required for: get_dataset_performance_analytics]
        tier (str): Request body parameter
            [Required for: change_license]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'search_storage_savings_report':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/reporting/storage-savings-report/search', params=params, json_body=body)
    elif action == 'search_vdb_inventory_report':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/reporting/vdb-inventory-report/search', params=params, json_body=body)
    elif action == 'get_dataset_performance_analytics':
        params = build_params(start=start, end=end, interval=interval)
        body = {k: v for k, v in {'start': start, 'end': end, 'interval': interval}.items() if v is not None}
        return make_api_request('POST', '/reporting/dataset-performance-analytics', params=params, json_body=body if body else None)
    elif action == 'search_scheduled_reports':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/reporting/schedule/search', params=params, json_body=body)
    elif action == 'get_scheduled_report':
        if report_id is None:
            return {'error': 'Missing required parameter: report_id for action get_scheduled_report'}
        endpoint = f'/reporting/schedule/{report_id}'
        params = build_params()
        return make_api_request('GET', endpoint, params=params)
    elif action == 'create_scheduled_report':
        params = build_params()
        return make_api_request('POST', '/reporting/schedule', params=params)
    elif action == 'delete_scheduled_report':
        if report_id is None:
            return {'error': 'Missing required parameter: report_id for action delete_scheduled_report'}
        endpoint = f'/reporting/schedule/{report_id}'
        params = build_params()
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'get_license':
        params = build_params()
        return make_api_request('GET', '/management/license', params=params)
    elif action == 'change_license':
        params = build_params(tier=tier)
        body = {k: v for k, v in {'tier': tier}.items() if v is not None}
        return make_api_request('POST', '/management/license/change-license', params=params, json_body=body if body else None)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search_storage_savings_report, search_vdb_inventory_report, get_dataset_performance_analytics, search_scheduled_reports, get_scheduled_report, create_scheduled_report, delete_scheduled_report, get_license, change_license'}


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
