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
def iam_tool(
    action: str,  # One of: search_accounts, get_account, create_account, delete_account, enable_account, disable_account, reset_password, search_roles, get_role, create_role, update_role, delete_role, search_access_groups, get_access_group, create_access_group, update_access_group, delete_access_group
    access_group_id: Optional[str] = None,
    api_client_id: Optional[str] = None,
    cursor: Optional[str] = None,
    description: Optional[str] = None,
    email: Optional[str] = None,
    filter_expression: Optional[str] = None,
    first_name: Optional[str] = None,
    generate_api_key: Optional[bool] = None,
    id: Optional[str] = None,
    immutable: Optional[bool] = None,
    is_admin: Optional[bool] = None,
    last_name: Optional[str] = None,
    ldap_principal: Optional[str] = None,
    limit: Optional[int] = None,
    name: Optional[str] = None,
    new_password: Optional[str] = None,
    password: Optional[str] = None,
    role_id: Optional[str] = None,
    single_account: Optional[bool] = None,
    sort: Optional[str] = None,
    username: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Unified tool for IAM operations.
    
    This tool supports 17 actions: search_accounts, get_account, create_account, delete_account, enable_account, disable_account, reset_password, search_roles, get_role, create_role, update_role, delete_role, search_access_groups, get_access_group, create_access_group, update_access_group, delete_access_group
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search_accounts
    ----------------------------------------
    Summary: Search for Accounts.
    Method: POST
    Endpoint: /management/accounts/search
    Required Parameters: limit, cursor, sort
    
    Filterable Fields:
        - id: Numeric ID of the Account.
        - api_client_id: The unique ID which is used to identify the identity of a...
        - first_name: An optional first name for the Account.
        - last_name: An optional last name for the Account.
        - email: An optional email for the Account.
        - username: The username for username/password authentication. This c...
        - ldap_principal: This value will be used for linking this account to an LD...
        - last_access_time: last time this account made a (successful or failed) API ...
        - creation_time: Creation time of this Account. This value is null for acc...
        - api_key_expiry_time: Expiration time of the API key, if null then API key will...
        - effective_scopes: Access group scopes associated with this account.
        - tags: The tags to be created for this Account.
        - enabled: Whether this account can be used to make API calls.
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> iam_tool(action='search_accounts', limit=..., cursor=..., sort=...)
    
    ACTION: get_account
    ----------------------------------------
    Summary: Get an Account by id
    Method: GET
    Endpoint: /management/accounts/{id}
    Required Parameters: id
    
    Example:
        >>> iam_tool(action='get_account', id=...)
    
    ACTION: create_account
    ----------------------------------------
    Summary: Create a new Account

    Method: POST
    Endpoint: /management/accounts
    
    Example:
        >>> iam_tool(action='create_account')
    
    ACTION: delete_account
    ----------------------------------------
    Summary: Delete an Account
    Method: DELETE
    Endpoint: /management/accounts/{id}
    Required Parameters: id
    
    Example:
        >>> iam_tool(action='delete_account', id=...)
    
    ACTION: enable_account
    ----------------------------------------
    Summary: Enable an Account.
    Method: POST
    Endpoint: /management/accounts/{id}/enable
    Required Parameters: id
    
    Example:
        >>> iam_tool(action='enable_account', id=...)
    
    ACTION: disable_account
    ----------------------------------------
    Summary: Disable an Account.
    Method: POST
    Endpoint: /management/accounts/{id}/disable
    Required Parameters: id
    
    Example:
        >>> iam_tool(action='disable_account', id=...)
    
    ACTION: reset_password
    ----------------------------------------
    Summary: Reset Account Password.

    Method: POST
    Endpoint: /management/accounts/{id}/reset_password
    Required Parameters: id
    
    Example:
        >>> iam_tool(action='reset_password', id=...)
    
    ACTION: search_roles
    ----------------------------------------
    Summary: Search for roles.
    Method: POST
    Endpoint: /roles/search
    Required Parameters: limit, cursor, sort
    
    Filterable Fields:
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> iam_tool(action='search_roles', limit=..., cursor=..., sort=...)
    
    ACTION: get_role
    ----------------------------------------
    Summary: Returns role by ID.
    Method: GET
    Endpoint: /roles/{roleId}
    Required Parameters: role_id
    
    Example:
        >>> iam_tool(action='get_role', role_id='example-role-123')
    
    ACTION: create_role
    ----------------------------------------
    Summary: Create custom role
    Method: POST
    Endpoint: /roles
    Required Parameters: name
    
    Example:
        >>> iam_tool(action='create_role', name=...)
    
    ACTION: update_role
    ----------------------------------------
    Summary: Update a Role.
    Method: PATCH
    Endpoint: /roles/{roleId}
    Required Parameters: role_id
    
    Example:
        >>> iam_tool(action='update_role', role_id='example-role-123')
    
    ACTION: delete_role
    ----------------------------------------
    Summary: Delete role by ID.
    Method: DELETE
    Endpoint: /roles/{roleId}
    Required Parameters: role_id
    
    Example:
        >>> iam_tool(action='delete_role', role_id='example-role-123')
    
    ACTION: search_access_groups
    ----------------------------------------
    Summary: Search for access groups.
    Method: POST
    Endpoint: /access-groups/search
    Required Parameters: limit, cursor, sort
    
    Filterable Fields:
        - id: The Access group ID.
        - name: The Access group name
        - single_account: Indicates that this Access group defines the permissions ...
        - account_ids: List of accounts ids included individually (as opposed to...
        - tagged_account_ids: List of accounts ids included by tags in the Access group.
        - account_tags: List of account tags. Accounts matching any of these tags...
        - scopes: The Access group scopes.
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> iam_tool(action='search_access_groups', limit=..., cursor=..., sort=...)
    
    ACTION: get_access_group
    ----------------------------------------
    Summary: Returns an Access group by ID.
    Method: GET
    Endpoint: /access-groups/{accessGroupId}
    Required Parameters: access_group_id
    
    Example:
        >>> iam_tool(action='get_access_group', access_group_id='example-access_group-123')
    
    ACTION: create_access_group
    ----------------------------------------
    Summary: Create a new access group.
    Method: POST
    Endpoint: /access-groups
    Required Parameters: name
    
    Example:
        >>> iam_tool(action='create_access_group', name=...)
    
    ACTION: update_access_group
    ----------------------------------------
    Summary: Update an Access group.
    Method: PATCH
    Endpoint: /access-groups/{accessGroupId}
    Required Parameters: access_group_id
    
    Example:
        >>> iam_tool(action='update_access_group', access_group_id='example-access_group-123')
    
    ACTION: delete_access_group
    ----------------------------------------
    Summary: Delete an Access group.
    Method: DELETE
    Endpoint: /access-groups/{accessGroupId}
    Required Parameters: access_group_id
    
    Example:
        >>> iam_tool(action='delete_access_group', access_group_id='example-access_group-123')
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search_accounts, get_account, create_account, delete_account, enable_account, disable_account, reset_password, search_roles, get_role, create_role, update_role, delete_role, search_access_groups, get_access_group, create_access_group, update_access_group, delete_access_group
        access_group_id (str): The unique identifier for the accessGroup.
            [Required for: get_access_group, update_access_group, delete_access_group]
        api_client_id (str): The unique ID which is used to identify the identity of an API request. The w...
            [Optional for all actions]
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search_accounts, search_roles, search_access_groups]
        description (str): Role description.
            [Optional for all actions]
        email (str): An optional email for the Account.
            [Optional for all actions]
        filter_expression (str): Filter expression to narrow results (e.g., "name CONTAINS 'prod'")
            [Optional for all actions]
        first_name (str): An optional first name for the Account.
            [Optional for all actions]
        generate_api_key (bool): Whether an API key must be generated for this Account. This must be set if th...
            [Optional for all actions]
        id (str): The unique identifier for the id.
            [Required for: get_account, delete_account, enable_account, disable_account, reset_password]
        immutable (bool): If set to true, adding or removing permission is not allowed.
            [Optional for all actions]
        is_admin (bool): Whether the created account must be granted to admin role.
            [Optional for all actions]
        last_name (str): An optional last name for the Account.
            [Optional for all actions]
        ldap_principal (str): This value will be used for linking this account to an LDAP user when authent...
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search_accounts, search_roles, search_access_groups]
        name (str): The Role name.
            [Required for: create_role, create_access_group]
        new_password (str): New password that needs to be set for the Account. Set this to null for unset...
            [Optional for all actions]
        password (str): The password for username/password authentication.
            [Optional for all actions]
        role_id (str): The unique identifier for the role.
            [Required for: get_role, update_role, delete_role]
        single_account (bool): Indicates that this Access group defines the permissions of a single account,...
            [Optional for all actions]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search_accounts, search_roles, search_access_groups]
        username (str): The username for username/password authentication. This can also be used to p...
            [Optional for all actions]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'search_accounts':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/management/accounts/search', params=params, json_body=body)
    elif action == 'get_account':
        if id is None:
            return {'error': 'Missing required parameter: id for action get_account'}
        endpoint = f'/management/accounts/{id}'
        params = build_params(id=id)
        return make_api_request('GET', endpoint, params=params)
    elif action == 'create_account':
        params = build_params()
        return make_api_request('POST', '/management/accounts', params=params)
    elif action == 'delete_account':
        if id is None:
            return {'error': 'Missing required parameter: id for action delete_account'}
        endpoint = f'/management/accounts/{id}'
        params = build_params(id=id)
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'enable_account':
        if id is None:
            return {'error': 'Missing required parameter: id for action enable_account'}
        endpoint = f'/management/accounts/{id}/enable'
        params = build_params(id=id)
        body = {k: v for k, v in {'id': id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'disable_account':
        if id is None:
            return {'error': 'Missing required parameter: id for action disable_account'}
        endpoint = f'/management/accounts/{id}/disable'
        params = build_params(id=id)
        body = {k: v for k, v in {'id': id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'reset_password':
        if id is None:
            return {'error': 'Missing required parameter: id for action reset_password'}
        endpoint = f'/management/accounts/{id}/reset_password'
        params = build_params(id=id)
        body = {k: v for k, v in {'id': id}.items() if v is not None}
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'search_roles':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/roles/search', params=params, json_body=body)
    elif action == 'get_role':
        if role_id is None:
            return {'error': 'Missing required parameter: role_id for action get_role'}
        endpoint = f'/roles/{role_id}'
        params = build_params()
        return make_api_request('GET', endpoint, params=params)
    elif action == 'create_role':
        params = build_params(name=name)
        body = {k: v for k, v in {'name': name}.items() if v is not None}
        return make_api_request('POST', '/roles', params=params, json_body=body if body else None)
    elif action == 'update_role':
        if role_id is None:
            return {'error': 'Missing required parameter: role_id for action update_role'}
        endpoint = f'/roles/{role_id}'
        params = build_params()
        return make_api_request('PATCH', endpoint, params=params)
    elif action == 'delete_role':
        if role_id is None:
            return {'error': 'Missing required parameter: role_id for action delete_role'}
        endpoint = f'/roles/{role_id}'
        params = build_params()
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'search_access_groups':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/access-groups/search', params=params, json_body=body)
    elif action == 'get_access_group':
        if access_group_id is None:
            return {'error': 'Missing required parameter: access_group_id for action get_access_group'}
        endpoint = f'/access-groups/{access_group_id}'
        params = build_params()
        return make_api_request('GET', endpoint, params=params)
    elif action == 'create_access_group':
        params = build_params(name=name)
        body = {k: v for k, v in {'name': name}.items() if v is not None}
        return make_api_request('POST', '/access-groups', params=params, json_body=body if body else None)
    elif action == 'update_access_group':
        if access_group_id is None:
            return {'error': 'Missing required parameter: access_group_id for action update_access_group'}
        endpoint = f'/access-groups/{access_group_id}'
        params = build_params()
        return make_api_request('PATCH', endpoint, params=params)
    elif action == 'delete_access_group':
        if access_group_id is None:
            return {'error': 'Missing required parameter: access_group_id for action delete_access_group'}
        endpoint = f'/access-groups/{access_group_id}'
        params = build_params()
        return make_api_request('DELETE', endpoint, params=params)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search_accounts, get_account, create_account, delete_account, enable_account, disable_account, reset_password, search_roles, get_role, create_role, update_role, delete_role, search_access_groups, get_access_group, create_access_group, update_access_group, delete_access_group'}

@log_tool_execution
def tag_tool(
    action: str,  # One of: search, get, get_usages
    cursor: Optional[str] = None,
    filter_expression: Optional[str] = None,
    limit: Optional[int] = None,
    sort: Optional[str] = None,
    tag_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Unified tool for TAG operations.
    
    This tool supports 3 actions: search, get, get_usages
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search for global tags.
    Method: POST
    Endpoint: /management/tags/search
    Required Parameters: limit, cursor, sort
    
    Filterable Fields:
        - id: ID of the tag.
        - key: Key of the tag
        - value: Value of the tag
        - used_for_access: True if this tag is used in any access group scopes.
        - usage_count: The number of objects this tag applies to.
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> tag_tool(action='search', limit=..., cursor=..., sort=...)
    
    ACTION: get
    ----------------------------------------
    Summary: Get a global tag by id
    Method: GET
    Endpoint: /management/tags/{tagId}
    Required Parameters: tag_id
    
    Example:
        >>> tag_tool(action='get', tag_id='example-tag-123')
    
    ACTION: get_usages
    ----------------------------------------
    Summary: List specific usages of this global tag.
    Method: GET
    Endpoint: /management/tags/{tagId}/usages
    Required Parameters: limit, cursor, sort, tag_id
    
    Example:
        >>> tag_tool(action='get_usages', limit=..., cursor=..., sort=..., tag_id='example-tag-123')
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, get_usages
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search, get_usages]
        filter_expression (str): Filter expression to narrow results (e.g., "name CONTAINS 'prod'")
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search, get_usages]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search, get_usages]
        tag_id (str): The unique identifier for the tag.
            [Required for: get, get_usages]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'search':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        return make_api_request('POST', '/management/tags/search', params=params, json_body=body)
    elif action == 'get':
        if tag_id is None:
            return {'error': 'Missing required parameter: tag_id for action get'}
        endpoint = f'/management/tags/{tag_id}'
        params = build_params()
        return make_api_request('GET', endpoint, params=params)
    elif action == 'get_usages':
        if tag_id is None:
            return {'error': 'Missing required parameter: tag_id for action get_usages'}
        endpoint = f'/management/tags/{tag_id}/usages'
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        return make_api_request('GET', endpoint, params=params)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, get_usages'}


def register_tools(app, dct_client):
    global client
    client = dct_client
    logger.info(f'Registering tools for iam_endpoints...')
    try:
        logger.info(f'  Registering tool function: iam_tool')
        app.add_tool(iam_tool, name="iam_tool")
        logger.info(f'  Registering tool function: tag_tool')
        app.add_tool(tag_tool, name="tag_tool")
    except Exception as e:
        logger.error(f'Error registering tools for iam_endpoints: {e}')
    logger.info(f'Tools registration finished for iam_endpoints.')
