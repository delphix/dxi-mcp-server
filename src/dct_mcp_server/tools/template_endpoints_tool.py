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
def database_template_tool(
    action: str,  # One of: search, get, create, update, delete, get_tags, add_tags, delete_tags
    cursor: Optional[str] = None,
    database_template_id: Optional[str] = None,
    description: Optional[str] = None,
    filter_expression: Optional[str] = None,
    key: Optional[str] = None,
    limit: Optional[int] = 100,
    make_current_account_owner: Optional[bool] = None,
    name: Optional[str] = None,
    parameters: Optional[dict] = None,
    sort: Optional[str] = None,
    source_type: Optional[str] = None,
    tags: Optional[list] = None,
    value: Optional[str] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for DATABASE TEMPLATE operations.
    
    This tool supports 8 actions: search, get, create, update, delete, get_tags, add_tags, delete_tags
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search DatabaseTemplates.
    Method: POST
    Endpoint: /database-templates/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - id: The DatabaseTemplate entity ID.
        - name: The DatabaseTemplate name.
        - description: User provided description for this template.
        - source_type: The type of the source associated with the template.
        - parameters: A name/value map of string configuration parameters.
        - tags: 
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> database_template_tool(action='search', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get
    ----------------------------------------
    Summary: Retrieve a DatabaseTemplate by ID.
    Method: GET
    Endpoint: /database-templates/{databaseTemplateId}
    Required Parameters: database_template_id
    
    Example:
        >>> database_template_tool(action='get', database_template_id='example-database_template-123')
    
    ACTION: create
    ----------------------------------------
    Summary: Create a database template.
    Method: POST
    Endpoint: /database-templates
    Required Parameters: name, source_type
    Key Parameters (provide as applicable): description, parameters, make_current_account_owner, tags
    
    Example:
        >>> database_template_tool(action='create', name=..., description=..., source_type=..., parameters=..., make_current_account_owner=..., tags=...)
    
    ACTION: update
    ----------------------------------------
    Summary: Updates a DatabaseTemplate by ID
    Method: PATCH
    Endpoint: /database-templates/{databaseTemplateId}
    Required Parameters: database_template_id
    Key Parameters (provide as applicable): name, description, source_type, parameters
    
    Example:
        >>> database_template_tool(action='update', database_template_id='example-database_template-123', name=..., description=..., source_type=..., parameters=...)
    
    ACTION: delete
    ----------------------------------------
    Summary: Delete a DatabaseTemplate by ID.
    Method: DELETE
    Endpoint: /database-templates/{databaseTemplateId}
    Required Parameters: database_template_id
    
    Example:
        >>> database_template_tool(action='delete', database_template_id='example-database_template-123')
    
    ACTION: get_tags
    ----------------------------------------
    Summary: Get tags for a DatabaseTemplate.
    Method: GET
    Endpoint: /database-templates/{databaseTemplateId}/tags
    Required Parameters: database_template_id
    
    Example:
        >>> database_template_tool(action='get_tags', database_template_id='example-database_template-123')
    
    ACTION: add_tags
    ----------------------------------------
    Summary: Create tags for a DatabaseTemplate.
    Method: POST
    Endpoint: /database-templates/{databaseTemplateId}/tags
    Required Parameters: database_template_id, tags
    
    Example:
        >>> database_template_tool(action='add_tags', database_template_id='example-database_template-123', tags=...)
    
    ACTION: delete_tags
    ----------------------------------------
    Summary: Delete tags for a DatabaseTemplate.
    Method: POST
    Endpoint: /database-templates/{databaseTemplateId}/tags/delete
    Required Parameters: database_template_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> database_template_tool(action='delete_tags', database_template_id='example-database_template-123', tags=..., key=..., value=...)
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, create, update, delete, get_tags, add_tags, delete_tags
    
      -- General parameters (all database types) --
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search]
        database_template_id (str): The unique identifier for the databaseTemplate.
            [Required for: get, update, delete, get_tags, add_tags, delete_tags]
        description (str): User provided description for this template.
            [Optional for all actions]
        filter_expression (str): Request body parameter
            [Optional for all actions]
        key (str): Key of the tag
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search]
        make_current_account_owner (bool): Whether the account creating this database template must be configured as own...
            [Optional for all actions]
        name (str): The DatabaseTemplate name.
            [Required for: create]
        parameters (dict): A name/value map of string configuration parameters. (Pass as JSON object)
            [Optional for all actions]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search]
        source_type (str): The type of the source associated with the template. Valid values: OracleVirt...
            [Required for: create]
        tags (list): Request body parameter (Pass as JSON array)
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
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', '/database-templates/search', action, 'database_template_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/database-templates/search', params=params, json_body=body)
    elif action == 'get':
        if database_template_id is None:
            return {'error': 'Missing required parameter: database_template_id for action get'}
        endpoint = f'/database-templates/{database_template_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'database_template_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'create':
        params = build_params(name=name, source_type=source_type)
        body = {k: v for k, v in {'name': name, 'description': description, 'source_type': source_type, 'parameters': parameters, 'make_current_account_owner': make_current_account_owner, 'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', '/database-templates', action, 'database_template_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/database-templates', params=params, json_body=body if body else None)
    elif action == 'update':
        if database_template_id is None:
            return {'error': 'Missing required parameter: database_template_id for action update'}
        endpoint = f'/database-templates/{database_template_id}'
        params = build_params()
        body = {k: v for k, v in {'name': name, 'description': description, 'source_type': source_type, 'parameters': parameters}.items() if v is not None}
        conf = check_confirmation('PATCH', endpoint, action, 'database_template_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete':
        if database_template_id is None:
            return {'error': 'Missing required parameter: database_template_id for action delete'}
        endpoint = f'/database-templates/{database_template_id}'
        params = build_params()
        conf = check_confirmation('DELETE', endpoint, action, 'database_template_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'get_tags':
        if database_template_id is None:
            return {'error': 'Missing required parameter: database_template_id for action get_tags'}
        endpoint = f'/database-templates/{database_template_id}/tags'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'database_template_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_tags':
        if database_template_id is None:
            return {'error': 'Missing required parameter: database_template_id for action add_tags'}
        endpoint = f'/database-templates/{database_template_id}/tags'
        params = build_params(tags=tags)
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'database_template_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_tags':
        if database_template_id is None:
            return {'error': 'Missing required parameter: database_template_id for action delete_tags'}
        endpoint = f'/database-templates/{database_template_id}/tags/delete'
        params = build_params()
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'database_template_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, create, update, delete, get_tags, add_tags, delete_tags'}

@log_tool_execution
def hook_template_tool(
    action: str,  # One of: search, get, create, update, delete, get_tags, add_tags, delete_tags
    command: Optional[str] = None,
    credentials_env_vars: Optional[list] = None,
    cursor: Optional[str] = None,
    description: Optional[str] = None,
    filter_expression: Optional[str] = None,
    hook_template_id: Optional[str] = None,
    key: Optional[str] = None,
    limit: Optional[int] = 100,
    name: Optional[str] = None,
    shell: Optional[str] = None,
    sort: Optional[str] = None,
    tags: Optional[list] = None,
    value: Optional[str] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for HOOK TEMPLATE operations.
    
    This tool supports 8 actions: search, get, create, update, delete, get_tags, add_tags, delete_tags
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search Hook Templates.
    Method: POST
    Endpoint: /hook-templates/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - id: 
        - name: 
        - dct_managed: Whether this hook template is managed by DCT or by an ind...
        - description: 
        - shell: 
        - command: 
        - credentials_env_vars: List of environment variables that will contain credentia...
        - engine_id: 
        - compatible_engine_id: 
        - tags: The tags that are applied to this hook template.
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> hook_template_tool(action='search', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
    ACTION: get
    ----------------------------------------
    Summary: Fetch Hook Template by ID
    Method: GET
    Endpoint: /hook-templates/{hookTemplateId}
    Required Parameters: hook_template_id
    
    Example:
        >>> hook_template_tool(action='get', hook_template_id='example-hook_template-123')
    
    ACTION: create
    ----------------------------------------
    Summary: Create a Hook Template.
    Method: POST
    Endpoint: /hook-templates
    Required Parameters: name, command
    Key Parameters (provide as applicable): description, shell, credentials_env_vars, tags
    
    Example:
        >>> hook_template_tool(action='create', name=..., description=..., shell=..., command=..., credentials_env_vars=..., tags=...)
    
    ACTION: update
    ----------------------------------------
    Summary: Update a Hook Template.
    Method: PATCH
    Endpoint: /hook-templates/{hookTemplateId}
    Required Parameters: hook_template_id
    Key Parameters (provide as applicable): name, description, shell, command, credentials_env_vars
    
    Example:
        >>> hook_template_tool(action='update', hook_template_id='example-hook_template-123', name=..., description=..., shell=..., command=..., credentials_env_vars=...)
    
    ACTION: delete
    ----------------------------------------
    Summary: Delete a Hook Template.
    Method: DELETE
    Endpoint: /hook-templates/{hookTemplateId}
    Required Parameters: hook_template_id
    
    Example:
        >>> hook_template_tool(action='delete', hook_template_id='example-hook_template-123')
    
    ACTION: get_tags
    ----------------------------------------
    Summary: Get tags for a Hook Template.
    Method: GET
    Endpoint: /hook-templates/{hookTemplateId}/tags
    Required Parameters: hook_template_id
    
    Example:
        >>> hook_template_tool(action='get_tags', hook_template_id='example-hook_template-123')
    
    ACTION: add_tags
    ----------------------------------------
    Summary: Create tags for a Hook Template.
    Method: POST
    Endpoint: /hook-templates/{hookTemplateId}/tags
    Required Parameters: hook_template_id, tags
    
    Example:
        >>> hook_template_tool(action='add_tags', hook_template_id='example-hook_template-123', tags=...)
    
    ACTION: delete_tags
    ----------------------------------------
    Summary: Delete tags for a Hook Template.
    Method: POST
    Endpoint: /hook-templates/{hookTemplateId}/tags/delete
    Required Parameters: hook_template_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> hook_template_tool(action='delete_tags', hook_template_id='example-hook_template-123', tags=..., key=..., value=...)
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, create, update, delete, get_tags, add_tags, delete_tags
    
      -- General parameters (all database types) --
        command (str): Request body parameter
            [Required for: create]
        credentials_env_vars (list): List of environment variables that will contain credentials for this operatio...
            [Optional for all actions]
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search]
        description (str): Description of the hook template.
            [Optional for all actions]
        filter_expression (str): Request body parameter
            [Optional for all actions]
        hook_template_id (str): The unique identifier for the hookTemplate.
            [Required for: get, update, delete, get_tags, add_tags, delete_tags]
        key (str): Key of the tag
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search]
        name (str): Name of the hook template.
            [Required for: create]
        shell (str): Request body parameter Valid values: bash, shell, expect, ps, psd. (Default: ...
            [Optional for all actions]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search]
        tags (list): The tags to be created for the hook template. (Pass as JSON array)
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
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', '/hook-templates/search', action, 'hook_template_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/hook-templates/search', params=params, json_body=body)
    elif action == 'get':
        if hook_template_id is None:
            return {'error': 'Missing required parameter: hook_template_id for action get'}
        endpoint = f'/hook-templates/{hook_template_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'hook_template_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'create':
        params = build_params(name=name, command=command)
        body = {k: v for k, v in {'name': name, 'description': description, 'shell': shell, 'command': command, 'credentials_env_vars': credentials_env_vars, 'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', '/hook-templates', action, 'hook_template_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/hook-templates', params=params, json_body=body if body else None)
    elif action == 'update':
        if hook_template_id is None:
            return {'error': 'Missing required parameter: hook_template_id for action update'}
        endpoint = f'/hook-templates/{hook_template_id}'
        params = build_params()
        body = {k: v for k, v in {'name': name, 'description': description, 'shell': shell, 'command': command, 'credentials_env_vars': credentials_env_vars}.items() if v is not None}
        conf = check_confirmation('PATCH', endpoint, action, 'hook_template_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete':
        if hook_template_id is None:
            return {'error': 'Missing required parameter: hook_template_id for action delete'}
        endpoint = f'/hook-templates/{hook_template_id}'
        params = build_params()
        conf = check_confirmation('DELETE', endpoint, action, 'hook_template_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'get_tags':
        if hook_template_id is None:
            return {'error': 'Missing required parameter: hook_template_id for action get_tags'}
        endpoint = f'/hook-templates/{hook_template_id}/tags'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'hook_template_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_tags':
        if hook_template_id is None:
            return {'error': 'Missing required parameter: hook_template_id for action add_tags'}
        endpoint = f'/hook-templates/{hook_template_id}/tags'
        params = build_params(tags=tags)
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'hook_template_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_tags':
        if hook_template_id is None:
            return {'error': 'Missing required parameter: hook_template_id for action delete_tags'}
        endpoint = f'/hook-templates/{hook_template_id}/tags/delete'
        params = build_params()
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'hook_template_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, create, update, delete, get_tags, add_tags, delete_tags'}


def register_tools(app, dct_client):
    global client
    client = dct_client
    logger.info(f'Registering tools for template_endpoints...')
    try:
        logger.info(f'  Registering tool function: database_template_tool')
        app.add_tool(database_template_tool, name="database_template_tool")
        logger.info(f'  Registering tool function: hook_template_tool')
        app.add_tool(hook_template_tool, name="hook_template_tool")
    except Exception as e:
        logger.error(f'Error registering tools for template_endpoints: {e}')
    logger.info(f'Tools registration finished for template_endpoints.')
