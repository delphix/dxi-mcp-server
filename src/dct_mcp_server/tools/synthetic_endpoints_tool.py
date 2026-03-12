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
def search_synthetic_connectors(limit: Optional[int] = None, cursor: Optional[str] = None, sort: Optional[str] = None, filter_expression: Optional[str] = None) -> Dict[str, Any]:
    """
    Search for Synthetic data connectors
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.(optional)
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.(optional)
    :param sort: The field to sort results by. A property name with a prepended '-' signifies a descending order.
    :param sort: The field to sort results by. A property name with a prepended '-' signifies a descending order.(optional)
    :param filter_expression: Filter expression string (optional)
    Filter expression can include the following fields:
     - id: The id of the connector
     - name: The name of this connector. This value must be unique among all synthetic data connectors.
     - description: An optional description for this connector.
     - application_id: An Application associated with the connector.
     - is_reference: Indicates if its reference connector
     - is_target: Indicates if its target connector
     - reference_connector_id: The ID of the reference connector in case its target connector
     - connector_type: No description
     - connector_subtype: No description
     - connector_sync_status: No description
     - last_sync_date: The date this connector was last synced. This will be only present for reference connector.
     - database_config: No description
     - account_id: The ID of the account who created this connector.
     - creation_date: The date this connector was created.
     - updated_date: The date this connector was last updated.

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
    return make_api_request('POST', '/synthetic/connectors/search', params=params, json_body=search_body)

@log_tool_execution
def search_synthetic_applications(limit: Optional[int] = None, cursor: Optional[str] = None, sort: Optional[str] = None, filter_expression: Optional[str] = None) -> Dict[str, Any]:
    """
    Search for Synthetic data applications
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.(optional)
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.(optional)
    :param sort: The field to sort results by. A property name with a prepended '-' signifies a descending order.
    :param sort: The field to sort results by. A property name with a prepended '-' signifies a descending order.(optional)
    :param filter_expression: Filter expression string (optional)
    Filter expression can include the following fields:
     - id: The id of the synthetic data application.
     - name: The name of this Application. This value must be unique among all synthetic data applications.
     - description: An optional description for this synthetic data application.
     - sync_status: No description
     - reference_connector_count: The count of reference connectors associated with this synthetic data application.
     - target_connector_count: The count of target connectors associated with this synthetic data application.
     - connector_count: The count of connectors associated with this synthetic data application.
     - structure_count: The count of structures associated with this synthetic data application.
     - account_id: The ID of the account who created this synthetic data application.
     - creation_date: The date this synthetic data application was created.
     - updated_date: The date this synthetic data application was updated.
     - tags: The tags of this synthetic data application.

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
    return make_api_request('POST', '/synthetic/applications/search', params=params, json_body=search_body)

@log_tool_execution
def search_synthetic_datasets(limit: Optional[int] = None, cursor: Optional[str] = None, sort: Optional[str] = None, filter_expression: Optional[str] = None) -> Dict[str, Any]:
    """
    Search for synthetic data datasets
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.(optional)
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.(optional)
    :param sort: The field to sort results by. A property name with a prepended '-' signifies a descending order.
    :param sort: The field to sort results by. A property name with a prepended '-' signifies a descending order.(optional)
    :param filter_expression: Filter expression string (optional)
    Filter expression can include the following fields:
     - id: The id of the synthetic data dataset
     - name: The name of this Dataset. This value must be unique among all synthetic data datasets.
     - description: An optional description for this synthetic data ruleset
     - sync_status: No description
     - application_id: The ID of the Synthetic data application associated with this dataset
     - application_name: The name of the Synthetic data application associated with this dataset
     - reference_connectors: The list of reference connectors associated with this synthetic data dataset.
     - account_id: The ID of the account who created this synthetic data dataset.
     - creation_date: The date this synthetic data dataset was created.
     - tags: The tags of this synthetic data dataset.

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
    return make_api_request('POST', '/synthetic/datasets/search', params=params, json_body=search_body)

@log_tool_execution
def search_synthetic_generators(limit: Optional[int] = None, cursor: Optional[str] = None, syntheticGeneratorsSortParam: Optional[str] = None, filter_expression: Optional[str] = None) -> Dict[str, Any]:
    """
    Search for generator instance.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.(optional)
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.(optional)
    :param syntheticGeneratorsSortParam: The field to sort results by. A property name with a prepended '-' signifies a descending order.
    :param syntheticGeneratorsSortParam: The field to sort results by. A property name with a prepended '-' signifies a descending order.(optional)
    :param filter_expression: Filter expression string (optional)
    Filter expression can include the following fields:
     - id: The id of the generator instance
     - name: The name of this generator instance. This value must be unique among all synthetic data generator instances.
     - description: An optional description for this generator instance
     - framework_id: The id of the generator framework this generator instance is part of
     - locale_id: Specifies the id of locale for this generator instance.
     - industry_id: Specifies the id of industry for this generator instance.
     - config: The JSON payload that contains configurations for generator instance.
     - seed: A seed string for the generator instance.
     - seed_list_file_id: The ID of the seed list file associated with this generator instance, if applicable.
     - preview_data: A sample of the data generated by this generator instance based on the current configuration.
     - creation_date: The date this connector was created.
     - created_by: The ID of the account who created this generator.

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
    params = build_params(limit=limit, cursor=cursor, syntheticGeneratorsSortParam=syntheticGeneratorsSortParam)
    search_body = {'filter_expression': filter_expression}
    return make_api_request('POST', '/synthetic/generators/search', params=params, json_body=search_body)

@log_tool_execution
def get_synthetic_generator_frameworks(limit: Optional[int] = None, cursor: Optional[str] = None, syntheticGeneratorFrameworkSortParam: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieve the list of generator frameworks.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.(optional)
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.(optional)
    :param syntheticGeneratorFrameworkSortParam: The field to sort results by. A property name with a prepended '-' signifies a descending order.
    :param syntheticGeneratorFrameworkSortParam: The field to sort results by. A property name with a prepended '-' signifies a descending order.(optional)
    Filter expression can include the following fields:
     - id: The id of the generator framework
     - name: The name of this generator framework.
     - plugin_name: The name of plugin for this generator framework.
     - user_friendly_name: The user friendly name of this generator framework.
     - description: An optional description for this generator framework
     - creation_date: The date this generator framework was created.
    """
    # Build parameters excluding None values
    params = build_params(limit=limit, cursor=cursor, syntheticGeneratorFrameworkSortParam=syntheticGeneratorFrameworkSortParam)
    return make_api_request('GET', '/synthetic/generator-frameworks', params=params)


def register_tools(app, dct_client):
    global client
    client = dct_client
    logger.info(f'Registering tools for synthetic_endpoints...')
    try:
        logger.info(f'  Registering tool function: search_synthetic_connectors')
        app.add_tool(search_synthetic_connectors, name="search_synthetic_connectors")
        logger.info(f'  Registering tool function: search_synthetic_applications')
        app.add_tool(search_synthetic_applications, name="search_synthetic_applications")
        logger.info(f'  Registering tool function: search_synthetic_datasets')
        app.add_tool(search_synthetic_datasets, name="search_synthetic_datasets")
        logger.info(f'  Registering tool function: search_synthetic_generators')
        app.add_tool(search_synthetic_generators, name="search_synthetic_generators")
        logger.info(f'  Registering tool function: get_synthetic_generator_frameworks')
        app.add_tool(get_synthetic_generator_frameworks, name="get_synthetic_generator_frameworks")
    except Exception as e:
        logger.error(f'Error registering tools for synthetic_endpoints: {e}')
    logger.info(f'Tools registration finished for synthetic_endpoints.')
