from mcp.server.fastmcp import FastMCP
from typing import Dict,Any,Optional
from dct_mcp_server.core.decorators import log_tool_execution
import asyncio
import logging
import threading
from functools import wraps

client = None
logger = logging.getLogger(__name__)

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
def search_connectors(limit: Optional[int] = None, cursor: Optional[str] = None, sort: Optional[str] = None, filter_expression: Optional[str] = None) -> Dict[str, Any]:
    """
    Search for masking Connectors.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.(optional)
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.(optional)
    :param sort: The field to sort results by. A property name with a prepended '-' signifies a descending order.
    :param sort: The field to sort results by. A property name with a prepended '-' signifies a descending order.(optional)
    :param filter_expression: Filter expression string (optional)
    Filter expression can include the following fields:
     - id: The Connector entity ID.
     - name: The Connector name.
     - engine_id: The id of the Compliance Engine that this Connector belongs to.
     - engine_name: The name of the Compliance Engine that this Connector belongs to.
     - type: No description
     - hostname: The network hostname or IP address of the database server.
     - port: The TCP port of the server.
     - username: The username this Connector will use to connect to the database.
     - password: The password this Connector will use to connect to the database.
     - auth_present: Whether this connector has authentication credentials set
     - database_type: The database variant, such as Oracle or MSSQL Server
     - custom_driver_name: The name of the custom JDBC driver for this connector
     - database_name: The database name for this connector
     - instance_name: The instance name for this connector
     - jdbc: The jdbc URL for this connector
     - schema_name: The schema name for this connector
     - sid: The SID value for this connector. This field is specific to Oracle database connectors
     - kerberos_auth: Whether kerberos authentication is enabled for this connector
     - service_principal: The service principal to use for kerberos authentication
     - enable_logger: Whether the logger is enable for this connector
     - file_type: The type of file this connector is configured to access
     - connection_mode: The connection mode for file connectors
     - path: The path on the remote server for file connections
     - ssh_key: The name of the ssh key for SFTP mode file connectors
     - user_dir_is_root: For FTP and SFTP connections, whether the user dir is set to root
     - platform: This database or file connection type associated with the connector
     - data_connection_id: The ID of the associated DataConnection.
     - account_id: The ID of the account who created this connector.
     - account_name: The account name of the DCT user who created this connector.
     - dct_managed: Whether this connector is managed by DCT or not.
     - tags: No description

    How to use filter_expresssion: 
    A request body containing a filter expression. This enables searching
    for items matching arbitrarily complex conditions. The list of
    attributes which can be used in filter expressions is available
    in the x-filterable vendor extension.
    
    # Filter Expression Overview
    **Note: All keywords are case-insensitive**
    
    ## Comparison Operators
    | Operator | Description | Example |
    | --- | --- | --- |
    | CONTAINS | Substring or membership testing for string and list attributes respectively. | field3 CONTAINS 'foobar', field4 CONTAINS TRUE  |
    | IN | Tests if field is a member of a list literal. List can contain a maximum of 100 values | field2 IN ['Goku', 'Vegeta'] |
    | GE | Tests if a field is greater than or equal to a literal value | field1 GE 1.2e-2 |
    | GT | Tests if a field is greater than a literal value | field1 GT 1.2e-2 |
    | LE | Tests if a field is less than or equal to a literal value | field1 LE 9000 |
    | LT | Tests if a field is less than a literal value | field1 LT 9.02 |
    | NE | Tests if a field is not equal to a literal value | field1 NE 42 |
    | EQ | Tests if a field is equal to a literal value | field1 EQ 42 |
    
    ## Search Operator
    The SEARCH operator filters for items which have any filterable
    attribute that contains the input string as a substring, comparison
    is done case-insensitively. This is not restricted to attributes with
    string values. Specifically `SEARCH '12'` would match an item with an
    attribute with an integer value of `123`.
    
    ## Logical Operators
    Ordered by precedence.
    | Operator | Description | Example |
    | --- | --- | --- |
    | NOT | Logical NOT (Right associative) | NOT field1 LE 9000 |
    | AND | Logical AND (Left Associative) | field1 GT 9000 AND field2 EQ 'Goku' |
    | OR | Logical OR (Left Associative) | field1 GT 9000 OR field2 EQ 'Goku' |
    
    ## Grouping
    Parenthesis `()` can be used to override operator precedence.
    
    For example:
    NOT (field1 LT 1234 AND field2 CONTAINS 'foo')
    
    ## Literal Values
    | Literal      | Description | Examples |
    | --- | --- | --- |
    | Nil | Represents the absence of a value | nil, Nil, nIl, NIL |
    | Boolean | true/false boolean | true, false, True, False, TRUE, FALSE |
    | Number | Signed integer and floating point numbers. Also supports scientific notation. | 0, 1, -1, 1.2, 0.35, 1.2e-2, -1.2e+2 |
    | String | Single or double quoted | "foo", "bar", "foo bar", 'foo', 'bar', 'foo bar' |
    | Datetime | Formatted according to [RFC3339](https://datatracker.ietf.org/doc/html/rfc3339) | 2018-04-27T18:39:26.397237+00:00 |
    | List | Comma-separated literals wrapped in square brackets | [0], [0, 1], ['foo', "bar"] |
    
    ## Limitations
    - A maximum of 8 unique identifiers may be used inside a filter expression.
    
    """
    # Build parameters excluding None values
    params = build_params(limit=limit, cursor=cursor, sort=sort)
    search_body = {'filter_expression': filter_expression}
    return make_api_request('POST', '/connectors/search', params=params, json_body=search_body)

@log_tool_execution
def search_executions(limit: Optional[int] = None, cursor: Optional[str] = None, sort: Optional[str] = None, filter_expression: Optional[str] = None) -> Dict[str, Any]:
    """
    Search masking executions.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.(optional)
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.(optional)
    :param sort: The field to sort results by. A property name with a prepended '-' signifies a descending order.
    :param sort: The field to sort results by. A property name with a prepended '-' signifies a descending order.(optional)
    :param filter_expression: Filter expression string (optional)
    Filter expression can include the following fields:
     - id: The Execution entity ID.
     - engine_id: The ID of the engine where this execution ran.
     - hyperscale_instance_id: No description
     - engine_name: The name of the engine where this execution ran.
     - job_orchestrator_id: The ID of the job orchestrator that is associated with this execution.
     - job_orchestrator_name: The name of the job orchestrator that is associated with this execution.
     - masking_job_id: The ID of the masking job that is being executed.
     - masking_job_name: The name of the masking job that is being executed.
     - dct_managed: Indicates whether this execution is for a DCT-managed masking job.
     - source_connector_id: The ID of the source connector. This field is only used for multi-tenant jobs that are also on-the-fly.
     - target_connector_id: The ID of the target connector. This field is only used for multi-tenant jobs.
     - status: No description
     - rows_masked: The number of rows masked or profiled so far by this execution. This is not applicable for JSON file type.
     - rows_total: The total number of rows that this execution should mask. This value is set to -1 while the total row count is being calculated. This is not applicable for JSON file type.
     - bytes_processed: The number of bytes masked so far by this execution. This is only applicable for JSON file type.
     - bytes_total: The total number of bytes that this execution should mask. This value is set to -1 while the total byte count is being calculated. This is only applicable for JSON file type.
     - start_time: The date and time that this execution was started.
     - submit_time: The date and time that this execution was submitted.
     - end_time: The date and time that this execution completed.
     - run_duration: The time this execution spent running, in milliseconds.
     - queue_duration: The time this execution spent in the queue, in milliseconds.
     - total_duration: The total time this execution took, in milliseconds.
     - account_id: The account id of the DCT user who started this execution.
     - account_name: The account name of the DCT user who started this execution.
     - task_events: The progression of steps or events performed by this execution. Only available for executions on masking engines that are version 6.0.14.0 and higher.
     - hyperscale_task_events: No description
     - progress: Progress of the task (value between 0 and 1, Hyperscale executions only)
     - execution_components_total: The total number of execution components in this execution.
     - execution_components_processed: The number of execution components processed so far in this execution.
     - collection_execution_id: The id of the compliance job collection execution this execution is part of, if any
     - data_collection_complete: Indicates whether all peripheral information associated with the execution, including execution components, execution events, logs and discovery results, has been fully collected and finalized.

    How to use filter_expresssion: 
    A request body containing a filter expression. This enables searching
    for items matching arbitrarily complex conditions. The list of
    attributes which can be used in filter expressions is available
    in the x-filterable vendor extension.
    
    # Filter Expression Overview
    **Note: All keywords are case-insensitive**
    
    ## Comparison Operators
    | Operator | Description | Example |
    | --- | --- | --- |
    | CONTAINS | Substring or membership testing for string and list attributes respectively. | field3 CONTAINS 'foobar', field4 CONTAINS TRUE  |
    | IN | Tests if field is a member of a list literal. List can contain a maximum of 100 values | field2 IN ['Goku', 'Vegeta'] |
    | GE | Tests if a field is greater than or equal to a literal value | field1 GE 1.2e-2 |
    | GT | Tests if a field is greater than a literal value | field1 GT 1.2e-2 |
    | LE | Tests if a field is less than or equal to a literal value | field1 LE 9000 |
    | LT | Tests if a field is less than a literal value | field1 LT 9.02 |
    | NE | Tests if a field is not equal to a literal value | field1 NE 42 |
    | EQ | Tests if a field is equal to a literal value | field1 EQ 42 |
    
    ## Search Operator
    The SEARCH operator filters for items which have any filterable
    attribute that contains the input string as a substring, comparison
    is done case-insensitively. This is not restricted to attributes with
    string values. Specifically `SEARCH '12'` would match an item with an
    attribute with an integer value of `123`.
    
    ## Logical Operators
    Ordered by precedence.
    | Operator | Description | Example |
    | --- | --- | --- |
    | NOT | Logical NOT (Right associative) | NOT field1 LE 9000 |
    | AND | Logical AND (Left Associative) | field1 GT 9000 AND field2 EQ 'Goku' |
    | OR | Logical OR (Left Associative) | field1 GT 9000 OR field2 EQ 'Goku' |
    
    ## Grouping
    Parenthesis `()` can be used to override operator precedence.
    
    For example:
    NOT (field1 LT 1234 AND field2 CONTAINS 'foo')
    
    ## Literal Values
    | Literal      | Description | Examples |
    | --- | --- | --- |
    | Nil | Represents the absence of a value | nil, Nil, nIl, NIL |
    | Boolean | true/false boolean | true, false, True, False, TRUE, FALSE |
    | Number | Signed integer and floating point numbers. Also supports scientific notation. | 0, 1, -1, 1.2, 0.35, 1.2e-2, -1.2e+2 |
    | String | Single or double quoted | "foo", "bar", "foo bar", 'foo', 'bar', 'foo bar' |
    | Datetime | Formatted according to [RFC3339](https://datatracker.ietf.org/doc/html/rfc3339) | 2018-04-27T18:39:26.397237+00:00 |
    | List | Comma-separated literals wrapped in square brackets | [0], [0, 1], ['foo', "bar"] |
    
    ## Limitations
    - A maximum of 8 unique identifiers may be used inside a filter expression.
    
    """
    # Build parameters excluding None values
    params = build_params(limit=limit, cursor=cursor, sort=sort)
    search_body = {'filter_expression': filter_expression}
    return make_api_request('POST', '/executions/search', params=params, json_body=search_body)


def register_tools(app, dct_client):
    global client
    client = dct_client
    logger.info(f'Registering tools for compliance_endpoints...')
    try:
        logger.info(f'  Registering tool function: search_connectors')
        app.add_tool(search_connectors, name="search_connectors")
        logger.info(f'  Registering tool function: search_executions')
        app.add_tool(search_executions, name="search_executions")
    except Exception as e:
        logger.error(f'Error registering tools for compliance_endpoints: {e}')
    logger.info(f'Tools registration finished for compliance_endpoints.')
