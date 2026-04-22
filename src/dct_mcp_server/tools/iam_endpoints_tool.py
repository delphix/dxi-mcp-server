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
def iam_tool(
    action: str,  # One of: search_accounts, get_account, create_account, delete_account, enable_account, disable_account, reset_password, get_account_tags, add_account_tags, delete_account_tags, get_account_ui_profiles, get_password_policies, update_password_policies, search_roles, get_role, create_role, update_role, delete_role, add_role_permissions, delete_role_permissions, get_role_tags, add_role_tags, delete_role_tags, add_role_ui_profiles, delete_role_ui_profiles, search_access_groups, get_access_group, create_access_group, update_access_group, delete_access_group, add_access_group_tags, delete_access_group_tags, add_access_group_scopes, get_access_group_scope, update_access_group_scope, delete_access_group_scope, add_scope_object_tags, delete_scope_object_tags, add_scope_objects, delete_scope_objects, add_scope_always_allowed_permissions, delete_scope_always_allowed_permissions
    access_group_id: Optional[str] = None,
    account_ids: Optional[list] = None,
    account_tags: Optional[list] = None,
    always_allowed_permissions: Optional[list] = None,
    api_client_id: Optional[str] = None,
    cursor: Optional[str] = None,
    description: Optional[str] = None,
    digit: Optional[bool] = None,
    disallow_username_as_password: Optional[bool] = None,
    email: Optional[str] = None,
    enabled: Optional[bool] = None,
    filter_expression: Optional[str] = None,
    first_name: Optional[str] = None,
    generate_api_key: Optional[bool] = None,
    id: Optional[str] = None,
    immutable: Optional[bool] = None,
    is_admin: Optional[bool] = None,
    key: Optional[str] = None,
    last_name: Optional[str] = None,
    ldap_principal: Optional[str] = None,
    limit: Optional[int] = 100,
    lowercase_letter: Optional[bool] = None,
    maximum_password_attempts: Optional[int] = None,
    min_length: Optional[int] = None,
    name: Optional[str] = None,
    new_password: Optional[str] = None,
    objects: Optional[list] = None,
    password: Optional[str] = None,
    permission_objects: Optional[list] = None,
    reuse_disallow_limit: Optional[int] = None,
    role_id: Optional[str] = None,
    scope_id: Optional[str] = None,
    scope_type: Optional[str] = None,
    scopes: Optional[list] = None,
    single_account: Optional[bool] = None,
    sort: Optional[str] = None,
    special_character: Optional[bool] = None,
    tagged_account_ids: Optional[list] = None,
    tags: Optional[list] = None,
    ui_profiles: Optional[list] = None,
    uppercase_letter: Optional[bool] = None,
    username: Optional[str] = None,
    value: Optional[str] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for IAM operations.
    
    This tool supports 42 actions: search_accounts, get_account, create_account, delete_account, enable_account, disable_account, reset_password, get_account_tags, add_account_tags, delete_account_tags, get_account_ui_profiles, get_password_policies, update_password_policies, search_roles, get_role, create_role, update_role, delete_role, add_role_permissions, delete_role_permissions, get_role_tags, add_role_tags, delete_role_tags, add_role_ui_profiles, delete_role_ui_profiles, search_access_groups, get_access_group, create_access_group, update_access_group, delete_access_group, add_access_group_tags, delete_access_group_tags, add_access_group_scopes, get_access_group_scope, update_access_group_scope, delete_access_group_scope, add_scope_object_tags, delete_scope_object_tags, add_scope_objects, delete_scope_objects, add_scope_always_allowed_permissions, delete_scope_always_allowed_permissions
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search_accounts
    ----------------------------------------
    Summary: Search for Accounts.
    Method: POST
    Endpoint: /management/accounts/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
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
        >>> iam_tool(action='search_accounts', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
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
    Key Parameters (provide as applicable): is_admin, generate_api_key, api_client_id, first_name, last_name, email, username, password, ldap_principal, tags
    
    Example:
        >>> iam_tool(action='create_account', is_admin=..., generate_api_key=..., api_client_id='example-api_client-123', first_name=..., last_name=..., email=..., username=..., password=..., ldap_principal=..., tags=...)
    
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
    Key Parameters (provide as applicable): new_password
    
    Example:
        >>> iam_tool(action='reset_password', id=..., new_password=...)
    
    ACTION: get_account_tags
    ----------------------------------------
    Summary: Get tags for an Account.
    Method: GET
    Endpoint: /management/accounts/{id}/tags
    Required Parameters: id
    
    Example:
        >>> iam_tool(action='get_account_tags', id=...)
    
    ACTION: add_account_tags
    ----------------------------------------
    Summary: Create tags for an Account.
    Method: POST
    Endpoint: /management/accounts/{id}/tags
    Required Parameters: id, tags
    
    Example:
        >>> iam_tool(action='add_account_tags', id=..., tags=...)
    
    ACTION: delete_account_tags
    ----------------------------------------
    Summary: Delete tags for an Account.
    Method: POST
    Endpoint: /management/accounts/{id}/tags/delete
    Required Parameters: id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> iam_tool(action='delete_account_tags', id=..., tags=..., key=..., value=...)
    
    ACTION: get_account_ui_profiles
    ----------------------------------------
    Summary: Returns the list of effective UI profiles for an account. This can only be called for one's own account.
    Method: GET
    Endpoint: /management/accounts/{id}/ui-profiles
    Required Parameters: id
    
    Example:
        >>> iam_tool(action='get_account_ui_profiles', id=...)
    
    ACTION: get_password_policies
    ----------------------------------------
    Summary: Returns the password policies
    Method: GET
    Endpoint: /management/accounts/password-policies
    
    Example:
        >>> iam_tool(action='get_password_policies')
    
    ACTION: update_password_policies
    ----------------------------------------
    Summary: Update password policies.
    Method: PATCH
    Endpoint: /management/accounts/password-policies
    Key Parameters (provide as applicable): enabled, min_length, reuse_disallow_limit, digit, uppercase_letter, lowercase_letter, special_character, disallow_username_as_password, maximum_password_attempts
    
    Example:
        >>> iam_tool(action='update_password_policies', enabled=..., min_length=..., reuse_disallow_limit=..., digit=..., uppercase_letter=..., lowercase_letter=..., special_character=..., disallow_username_as_password=..., maximum_password_attempts=...)
    
    ACTION: search_roles
    ----------------------------------------
    Summary: Search for roles.
    Method: POST
    Endpoint: /roles/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> iam_tool(action='search_roles', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
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
    Required Parameters: name, permission_objects
    Key Parameters (provide as applicable): tags, description, immutable, ui_profiles
    
    Example:
        >>> iam_tool(action='create_role', tags=..., name=..., description=..., permission_objects=..., immutable=..., ui_profiles=...)
    
    ACTION: update_role
    ----------------------------------------
    Summary: Update a Role.
    Method: PATCH
    Endpoint: /roles/{roleId}
    Required Parameters: role_id
    Key Parameters (provide as applicable): name, description
    
    Example:
        >>> iam_tool(action='update_role', role_id='example-role-123', name=..., description=...)
    
    ACTION: delete_role
    ----------------------------------------
    Summary: Delete role by ID.
    Method: DELETE
    Endpoint: /roles/{roleId}
    Required Parameters: role_id
    
    Example:
        >>> iam_tool(action='delete_role', role_id='example-role-123')
    
    ACTION: add_role_permissions
    ----------------------------------------
    Summary: Add permissions to a role.
    Method: POST
    Endpoint: /roles/{roleId}/permissions
    Required Parameters: role_id, permission_objects
    
    Example:
        >>> iam_tool(action='add_role_permissions', role_id='example-role-123', permission_objects=...)
    
    ACTION: delete_role_permissions
    ----------------------------------------
    Summary: Remove permissions from a role.
    Method: POST
    Endpoint: /roles/{roleId}/permissions/delete
    Required Parameters: role_id, permission_objects
    
    Example:
        >>> iam_tool(action='delete_role_permissions', role_id='example-role-123', permission_objects=...)
    
    ACTION: get_role_tags
    ----------------------------------------
    Summary: Get tags for a Role.
    Method: GET
    Endpoint: /roles/{roleId}/tags
    Required Parameters: role_id
    
    Example:
        >>> iam_tool(action='get_role_tags', role_id='example-role-123')
    
    ACTION: add_role_tags
    ----------------------------------------
    Summary: Create tags for a role.
    Method: POST
    Endpoint: /roles/{roleId}/tags
    Required Parameters: tags, role_id
    
    Example:
        >>> iam_tool(action='add_role_tags', tags=..., role_id='example-role-123')
    
    ACTION: delete_role_tags
    ----------------------------------------
    Summary: Delete tags for a Role.
    Method: POST
    Endpoint: /roles/{roleId}/tags/delete
    Required Parameters: role_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> iam_tool(action='delete_role_tags', tags=..., key=..., value=..., role_id='example-role-123')
    
    ACTION: add_role_ui_profiles
    ----------------------------------------
    Summary: Add UI profiles to a role.
    Method: POST
    Endpoint: /roles/{roleId}/ui-profiles
    Required Parameters: role_id, ui_profiles
    
    Example:
        >>> iam_tool(action='add_role_ui_profiles', role_id='example-role-123', ui_profiles=...)
    
    ACTION: delete_role_ui_profiles
    ----------------------------------------
    Summary: Delete UI profiles from a Role.
    Method: POST
    Endpoint: /roles/{roleId}/ui-profiles/delete
    Required Parameters: role_id, ui_profiles
    
    Example:
        >>> iam_tool(action='delete_role_ui_profiles', role_id='example-role-123', ui_profiles=...)
    
    ACTION: search_access_groups
    ----------------------------------------
    Summary: Search for access groups.
    Method: POST
    Endpoint: /access-groups/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
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
        >>> iam_tool(action='search_access_groups', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
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
    Key Parameters (provide as applicable): id, single_account, account_ids, tagged_account_ids, account_tags, scopes
    
    Example:
        >>> iam_tool(action='create_access_group', id=..., name=..., single_account=..., account_ids=..., tagged_account_ids=..., account_tags=..., scopes=...)
    
    ACTION: update_access_group
    ----------------------------------------
    Summary: Update an Access group.
    Method: PATCH
    Endpoint: /access-groups/{accessGroupId}
    Required Parameters: access_group_id
    Key Parameters (provide as applicable): name
    
    Example:
        >>> iam_tool(action='update_access_group', name=..., access_group_id='example-access_group-123')
    
    ACTION: delete_access_group
    ----------------------------------------
    Summary: Delete an Access group.
    Method: DELETE
    Endpoint: /access-groups/{accessGroupId}
    Required Parameters: access_group_id
    
    Example:
        >>> iam_tool(action='delete_access_group', access_group_id='example-access_group-123')
    
    ACTION: add_access_group_tags
    ----------------------------------------
    Summary: Add account tags to an Access group
    Method: POST
    Endpoint: /access-groups/{accessGroupId}/tags
    Required Parameters: tags, access_group_id
    
    Example:
        >>> iam_tool(action='add_access_group_tags', tags=..., access_group_id='example-access_group-123')
    
    ACTION: delete_access_group_tags
    ----------------------------------------
    Summary: Remove account tags from an access group.
    Method: POST
    Endpoint: /access-groups/{accessGroupId}/tags/delete
    Required Parameters: access_group_id
    Key Parameters (provide as applicable): tags, key, value
    
    Example:
        >>> iam_tool(action='delete_access_group_tags', tags=..., key=..., value=..., access_group_id='example-access_group-123')
    
    ACTION: add_access_group_scopes
    ----------------------------------------
    Summary: Add scopes to an Access group
    Method: POST
    Endpoint: /access-groups/{accessGroupId}/scopes
    Required Parameters: access_group_id, scopes
    
    Example:
        >>> iam_tool(action='add_access_group_scopes', access_group_id='example-access_group-123', scopes=...)
    
    ACTION: get_access_group_scope
    ----------------------------------------
    Summary: Get access group scope.
    Method: GET
    Endpoint: /access-groups/{accessGroupId}/scopes/{scopeId}
    Required Parameters: access_group_id, scope_id
    
    Example:
        >>> iam_tool(action='get_access_group_scope', access_group_id='example-access_group-123', scope_id='example-scope-123')
    
    ACTION: update_access_group_scope
    ----------------------------------------
    Summary: Update access group scope.
    Method: PATCH
    Endpoint: /access-groups/{accessGroupId}/scopes/{scopeId}
    Required Parameters: access_group_id, scope_id
    Key Parameters (provide as applicable): name, scope_type
    
    Example:
        >>> iam_tool(action='update_access_group_scope', name=..., access_group_id='example-access_group-123', scope_id='example-scope-123', scope_type=...)
    
    ACTION: delete_access_group_scope
    ----------------------------------------
    Summary: Remove the scope from the Access group.
    Method: DELETE
    Endpoint: /access-groups/{accessGroupId}/scopes/{scopeId}
    Required Parameters: access_group_id, scope_id
    
    Example:
        >>> iam_tool(action='delete_access_group_scope', access_group_id='example-access_group-123', scope_id='example-scope-123')
    
    ACTION: add_scope_object_tags
    ----------------------------------------
    Summary: Add object tags to the access group scope.
    Method: POST
    Endpoint: /access-groups/{accessGroupId}/scopes/{scopeId}/object-tags
    Required Parameters: tags, access_group_id, scope_id
    
    Example:
        >>> iam_tool(action='add_scope_object_tags', tags=..., access_group_id='example-access_group-123', scope_id='example-scope-123')
    
    ACTION: delete_scope_object_tags
    ----------------------------------------
    Summary: Remove tags from the access group scope.
    Method: POST
    Endpoint: /access-groups/{accessGroupId}/scopes/{scopeId}/object-tags/delete
    Required Parameters: access_group_id, scope_id
    Key Parameters (provide as applicable): tags
    
    Example:
        >>> iam_tool(action='delete_scope_object_tags', tags=..., access_group_id='example-access_group-123', scope_id='example-scope-123')
    
    ACTION: add_scope_objects
    ----------------------------------------
    Summary: Add objects to the access group scope.
    Method: POST
    Endpoint: /access-groups/{accessGroupId}/scopes/{scopeId}/objects
    Required Parameters: access_group_id, scope_id, objects
    
    Example:
        >>> iam_tool(action='add_scope_objects', access_group_id='example-access_group-123', scope_id='example-scope-123', objects=...)
    
    ACTION: delete_scope_objects
    ----------------------------------------
    Summary: Remove objects from the access group scope.
    Method: POST
    Endpoint: /access-groups/{accessGroupId}/scopes/{scopeId}/objects/delete
    Required Parameters: access_group_id, scope_id, objects
    
    Example:
        >>> iam_tool(action='delete_scope_objects', access_group_id='example-access_group-123', scope_id='example-scope-123', objects=...)
    
    ACTION: add_scope_always_allowed_permissions
    ----------------------------------------
    Summary: Add always allowed permissions for given object type.
    Method: POST
    Endpoint: /access-groups/{accessGroupId}/scopes/{scopeId}/always_allowed_permissions
    Required Parameters: access_group_id, scope_id, always_allowed_permissions
    
    Example:
        >>> iam_tool(action='add_scope_always_allowed_permissions', access_group_id='example-access_group-123', scope_id='example-scope-123', always_allowed_permissions=...)
    
    ACTION: delete_scope_always_allowed_permissions
    ----------------------------------------
    Summary: Remove always allowed permissions for given object type.
    Method: POST
    Endpoint: /access-groups/{accessGroupId}/scopes/{scopeId}/always_allowed_permissions/delete
    Required Parameters: access_group_id, scope_id, always_allowed_permissions
    
    Example:
        >>> iam_tool(action='delete_scope_always_allowed_permissions', access_group_id='example-access_group-123', scope_id='example-scope-123', always_allowed_permissions=...)
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search_accounts, get_account, create_account, delete_account, enable_account, disable_account, reset_password, get_account_tags, add_account_tags, delete_account_tags, get_account_ui_profiles, get_password_policies, update_password_policies, search_roles, get_role, create_role, update_role, delete_role, add_role_permissions, delete_role_permissions, get_role_tags, add_role_tags, delete_role_tags, add_role_ui_profiles, delete_role_ui_profiles, search_access_groups, get_access_group, create_access_group, update_access_group, delete_access_group, add_access_group_tags, delete_access_group_tags, add_access_group_scopes, get_access_group_scope, update_access_group_scope, delete_access_group_scope, add_scope_object_tags, delete_scope_object_tags, add_scope_objects, delete_scope_objects, add_scope_always_allowed_permissions, delete_scope_always_allowed_permissions
    
      -- General parameters (all database types) --
        access_group_id (str): The unique identifier for the accessGroup.
            [Required for: get_access_group, update_access_group, delete_access_group, add_access_group_tags, delete_access_group_tags, add_access_group_scopes, get_access_group_scope, update_access_group_scope, delete_access_group_scope, add_scope_object_tags, delete_scope_object_tags, add_scope_objects, delete_scope_objects, add_scope_always_allowed_permissions, delete_scope_always_allowed_permissions]
        account_ids (list): List of accounts ids included individually (as opposed to added by tags) in t...
            [Optional for all actions]
        account_tags (list): List of account tags. Accounts matching any of these tags will be automatical...
            [Optional for all actions]
        always_allowed_permissions (list): An array of always allowed permissions (Pass as JSON array)
            [Required for: add_scope_always_allowed_permissions, delete_scope_always_allowed_permissions]
        api_client_id (str): The unique ID which is used to identify the identity of an API request. The w...
            [Optional for all actions]
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search_accounts, search_roles, search_access_groups]
        description (str): Role description.
            [Optional for all actions]
        digit (bool): Mandate at least one digit in password. (Default: True)
            [Optional for all actions]
        disallow_username_as_password (bool): Disallows password containing case-insensitive user name or reversed user nam...
            [Optional for all actions]
        email (str): An optional email for the Account.
            [Optional for all actions]
        enabled (bool): True if password policies are enforced/enabled. (Default: True)
            [Optional for all actions]
        filter_expression (str): Request body parameter
            [Optional for all actions]
        first_name (str): An optional first name for the Account.
            [Optional for all actions]
        generate_api_key (bool): Whether an API key must be generated for this Account. This must be set if th...
            [Optional for all actions]
        id (str): The unique identifier for the id.
            [Required for: get_account, delete_account, enable_account, disable_account, reset_password, get_account_tags, add_account_tags, delete_account_tags, get_account_ui_profiles]
        immutable (bool): If set to true, adding or removing permission is not allowed. (Default: False)
            [Optional for all actions]
        is_admin (bool): Whether the created account must be granted to admin role. (Default: False)
            [Optional for all actions]
        key (str): Key of the tag
            [Optional for all actions]
        last_name (str): An optional last name for the Account.
            [Optional for all actions]
        ldap_principal (str): This value will be used for linking this account to an LDAP user when authent...
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search_accounts, search_roles, search_access_groups]
        lowercase_letter (bool): Mandate at least one lower letter in password. (Default: True)
            [Optional for all actions]
        maximum_password_attempts (int): The number of allowed attempts for incorrect password, after which the accoun...
            [Optional for all actions]
        min_length (int): Minimum length for password. (Default: 15)
            [Optional for all actions]
        name (str): The Role name.
            [Required for: create_role, create_access_group]
        new_password (str): New password that needs to be set for the Account. Set this to null for unset...
            [Optional for all actions]
        objects (list): An array of scoped objects (Pass as JSON array)
            [Required for: add_scope_objects, delete_scope_objects]
        password (str): The password for username/password authentication.
            [Optional for all actions]
        permission_objects (list): The list of permissions granted by this role. (Pass as JSON array)
            [Required for: create_role, add_role_permissions, delete_role_permissions]
        reuse_disallow_limit (int): The password can not be the same as any of the previous n passwords. (Default...
            [Optional for all actions]
        role_id (str): The unique identifier for the role.
            [Required for: get_role, update_role, delete_role, add_role_permissions, delete_role_permissions, get_role_tags, add_role_tags, delete_role_tags, add_role_ui_profiles, delete_role_ui_profiles]
        scope_id (str): The unique identifier for the scope.
            [Required for: get_access_group_scope, update_access_group_scope, delete_access_group_scope, add_scope_object_tags, delete_scope_object_tags, add_scope_objects, delete_scope_objects, add_scope_always_allowed_permissions, delete_scope_always_allowed_permissions]
        scope_type (str): Specifies the type of the scope. Scope of type SIMPLE would grant access to a...
            [Optional for all actions]
        scopes (list): The Access group scopes. (Pass as JSON array)
            [Required for: add_access_group_scopes]
        single_account (bool): Indicates that this Access group defines the permissions of a single account,...
            [Optional for all actions]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search_accounts, search_roles, search_access_groups]
        special_character (bool): Mandate at least one special character in password. (Default: True)
            [Optional for all actions]
        tagged_account_ids (list): List of accounts ids included by tags in the Access group. (Pass as JSON array)
            [Optional for all actions]
        tags (list): The tags to be created for this Account. (Pass as JSON array)
            [Required for: add_account_tags, add_role_tags, add_access_group_tags, add_scope_object_tags]
        ui_profiles (list): The list of profiles that influence the navigation menus shown in the UI. (Pa...
            [Required for: add_role_ui_profiles, delete_role_ui_profiles]
        uppercase_letter (bool): Mandate at least one uppercase letter in password. (Default: True)
            [Optional for all actions]
        username (str): The username for username/password authentication. This can also be used to p...
            [Optional for all actions]
        value (str): Value of the tag
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
        conf = check_confirmation('POST', '/management/accounts/search', action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/management/accounts/search', params=params, json_body=body)
    elif action == 'get_account':
        if id is None:
            return {'error': 'Missing required parameter: id for action get_account'}
        endpoint = f'/management/accounts/{id}'
        params = build_params(id=id)
        conf = check_confirmation('GET', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'create_account':
        params = build_params()
        body = {k: v for k, v in {'is_admin': is_admin, 'generate_api_key': generate_api_key, 'api_client_id': api_client_id, 'first_name': first_name, 'last_name': last_name, 'email': email, 'username': username, 'password': password, 'ldap_principal': ldap_principal, 'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', '/management/accounts', action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/management/accounts', params=params, json_body=body if body else None)
    elif action == 'delete_account':
        if id is None:
            return {'error': 'Missing required parameter: id for action delete_account'}
        endpoint = f'/management/accounts/{id}'
        params = build_params(id=id)
        conf = check_confirmation('DELETE', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'enable_account':
        if id is None:
            return {'error': 'Missing required parameter: id for action enable_account'}
        endpoint = f'/management/accounts/{id}/enable'
        params = build_params(id=id)
        conf = check_confirmation('POST', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'disable_account':
        if id is None:
            return {'error': 'Missing required parameter: id for action disable_account'}
        endpoint = f'/management/accounts/{id}/disable'
        params = build_params(id=id)
        conf = check_confirmation('POST', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params)
    elif action == 'reset_password':
        if id is None:
            return {'error': 'Missing required parameter: id for action reset_password'}
        endpoint = f'/management/accounts/{id}/reset_password'
        params = build_params(id=id)
        body = {k: v for k, v in {'new_password': new_password}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'get_account_tags':
        if id is None:
            return {'error': 'Missing required parameter: id for action get_account_tags'}
        endpoint = f'/management/accounts/{id}/tags'
        params = build_params(id=id)
        conf = check_confirmation('GET', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_account_tags':
        if id is None:
            return {'error': 'Missing required parameter: id for action add_account_tags'}
        endpoint = f'/management/accounts/{id}/tags'
        params = build_params(id=id, tags=tags)
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_account_tags':
        if id is None:
            return {'error': 'Missing required parameter: id for action delete_account_tags'}
        endpoint = f'/management/accounts/{id}/tags/delete'
        params = build_params(id=id)
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'get_account_ui_profiles':
        if id is None:
            return {'error': 'Missing required parameter: id for action get_account_ui_profiles'}
        endpoint = f'/management/accounts/{id}/ui-profiles'
        params = build_params(id=id)
        conf = check_confirmation('GET', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'get_password_policies':
        params = build_params()
        conf = check_confirmation('GET', '/management/accounts/password-policies', action, 'iam_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', '/management/accounts/password-policies', params=params)
    elif action == 'update_password_policies':
        params = build_params()
        body = {k: v for k, v in {'enabled': enabled, 'min_length': min_length, 'reuse_disallow_limit': reuse_disallow_limit, 'digit': digit, 'uppercase_letter': uppercase_letter, 'lowercase_letter': lowercase_letter, 'special_character': special_character, 'disallow_username_as_password': disallow_username_as_password, 'maximum_password_attempts': maximum_password_attempts}.items() if v is not None}
        conf = check_confirmation('PATCH', '/management/accounts/password-policies', action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('PATCH', '/management/accounts/password-policies', params=params, json_body=body if body else None)
    elif action == 'search_roles':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', '/roles/search', action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/roles/search', params=params, json_body=body)
    elif action == 'get_role':
        if role_id is None:
            return {'error': 'Missing required parameter: role_id for action get_role'}
        endpoint = f'/roles/{role_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'create_role':
        params = build_params(name=name, permission_objects=permission_objects)
        body = {k: v for k, v in {'name': name, 'description': description, 'permission_objects': permission_objects, 'immutable': immutable, 'tags': tags, 'ui_profiles': ui_profiles}.items() if v is not None}
        conf = check_confirmation('POST', '/roles', action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/roles', params=params, json_body=body if body else None)
    elif action == 'update_role':
        if role_id is None:
            return {'error': 'Missing required parameter: role_id for action update_role'}
        endpoint = f'/roles/{role_id}'
        params = build_params()
        body = {k: v for k, v in {'name': name, 'description': description}.items() if v is not None}
        conf = check_confirmation('PATCH', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_role':
        if role_id is None:
            return {'error': 'Missing required parameter: role_id for action delete_role'}
        endpoint = f'/roles/{role_id}'
        params = build_params()
        conf = check_confirmation('DELETE', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'add_role_permissions':
        if role_id is None:
            return {'error': 'Missing required parameter: role_id for action add_role_permissions'}
        endpoint = f'/roles/{role_id}/permissions'
        params = build_params(permission_objects=permission_objects)
        body = {k: v for k, v in {'permission_objects': permission_objects}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_role_permissions':
        if role_id is None:
            return {'error': 'Missing required parameter: role_id for action delete_role_permissions'}
        endpoint = f'/roles/{role_id}/permissions/delete'
        params = build_params(permission_objects=permission_objects)
        body = {k: v for k, v in {'permission_objects': permission_objects}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'get_role_tags':
        if role_id is None:
            return {'error': 'Missing required parameter: role_id for action get_role_tags'}
        endpoint = f'/roles/{role_id}/tags'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'add_role_tags':
        if role_id is None:
            return {'error': 'Missing required parameter: role_id for action add_role_tags'}
        endpoint = f'/roles/{role_id}/tags'
        params = build_params(tags=tags)
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_role_tags':
        if role_id is None:
            return {'error': 'Missing required parameter: role_id for action delete_role_tags'}
        endpoint = f'/roles/{role_id}/tags/delete'
        params = build_params()
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'add_role_ui_profiles':
        if role_id is None:
            return {'error': 'Missing required parameter: role_id for action add_role_ui_profiles'}
        endpoint = f'/roles/{role_id}/ui-profiles'
        params = build_params(ui_profiles=ui_profiles)
        body = {k: v for k, v in {'ui_profiles': ui_profiles}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_role_ui_profiles':
        if role_id is None:
            return {'error': 'Missing required parameter: role_id for action delete_role_ui_profiles'}
        endpoint = f'/roles/{role_id}/ui-profiles/delete'
        params = build_params(ui_profiles=ui_profiles)
        body = {k: v for k, v in {'ui_profiles': ui_profiles}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'search_access_groups':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', '/access-groups/search', action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/access-groups/search', params=params, json_body=body)
    elif action == 'get_access_group':
        if access_group_id is None:
            return {'error': 'Missing required parameter: access_group_id for action get_access_group'}
        endpoint = f'/access-groups/{access_group_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'create_access_group':
        params = build_params(name=name)
        body = {k: v for k, v in {'id': id, 'name': name, 'single_account': single_account, 'account_ids': account_ids, 'tagged_account_ids': tagged_account_ids, 'account_tags': account_tags, 'scopes': scopes}.items() if v is not None}
        conf = check_confirmation('POST', '/access-groups', action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/access-groups', params=params, json_body=body if body else None)
    elif action == 'update_access_group':
        if access_group_id is None:
            return {'error': 'Missing required parameter: access_group_id for action update_access_group'}
        endpoint = f'/access-groups/{access_group_id}'
        params = build_params()
        body = {k: v for k, v in {'name': name}.items() if v is not None}
        conf = check_confirmation('PATCH', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_access_group':
        if access_group_id is None:
            return {'error': 'Missing required parameter: access_group_id for action delete_access_group'}
        endpoint = f'/access-groups/{access_group_id}'
        params = build_params()
        conf = check_confirmation('DELETE', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'add_access_group_tags':
        if access_group_id is None:
            return {'error': 'Missing required parameter: access_group_id for action add_access_group_tags'}
        endpoint = f'/access-groups/{access_group_id}/tags'
        params = build_params(tags=tags)
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_access_group_tags':
        if access_group_id is None:
            return {'error': 'Missing required parameter: access_group_id for action delete_access_group_tags'}
        endpoint = f'/access-groups/{access_group_id}/tags/delete'
        params = build_params()
        body = {k: v for k, v in {'key': key, 'value': value, 'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'add_access_group_scopes':
        if access_group_id is None:
            return {'error': 'Missing required parameter: access_group_id for action add_access_group_scopes'}
        endpoint = f'/access-groups/{access_group_id}/scopes'
        params = build_params(scopes=scopes)
        body = {k: v for k, v in {'scopes': scopes}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'get_access_group_scope':
        if access_group_id is None:
            return {'error': 'Missing required parameter: access_group_id for action get_access_group_scope'}
        if scope_id is None:
            return {'error': 'Missing required parameter: scope_id for action get_access_group_scope'}
        endpoint = f'/access-groups/{access_group_id}/scopes/{scope_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'update_access_group_scope':
        if access_group_id is None:
            return {'error': 'Missing required parameter: access_group_id for action update_access_group_scope'}
        if scope_id is None:
            return {'error': 'Missing required parameter: scope_id for action update_access_group_scope'}
        endpoint = f'/access-groups/{access_group_id}/scopes/{scope_id}'
        params = build_params()
        body = {k: v for k, v in {'name': name, 'scope_type': scope_type}.items() if v is not None}
        conf = check_confirmation('PATCH', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('PATCH', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_access_group_scope':
        if access_group_id is None:
            return {'error': 'Missing required parameter: access_group_id for action delete_access_group_scope'}
        if scope_id is None:
            return {'error': 'Missing required parameter: scope_id for action delete_access_group_scope'}
        endpoint = f'/access-groups/{access_group_id}/scopes/{scope_id}'
        params = build_params()
        conf = check_confirmation('DELETE', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('DELETE', endpoint, params=params)
    elif action == 'add_scope_object_tags':
        if access_group_id is None:
            return {'error': 'Missing required parameter: access_group_id for action add_scope_object_tags'}
        if scope_id is None:
            return {'error': 'Missing required parameter: scope_id for action add_scope_object_tags'}
        endpoint = f'/access-groups/{access_group_id}/scopes/{scope_id}/object-tags'
        params = build_params(tags=tags)
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_scope_object_tags':
        if access_group_id is None:
            return {'error': 'Missing required parameter: access_group_id for action delete_scope_object_tags'}
        if scope_id is None:
            return {'error': 'Missing required parameter: scope_id for action delete_scope_object_tags'}
        endpoint = f'/access-groups/{access_group_id}/scopes/{scope_id}/object-tags/delete'
        params = build_params()
        body = {k: v for k, v in {'tags': tags}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'add_scope_objects':
        if access_group_id is None:
            return {'error': 'Missing required parameter: access_group_id for action add_scope_objects'}
        if scope_id is None:
            return {'error': 'Missing required parameter: scope_id for action add_scope_objects'}
        endpoint = f'/access-groups/{access_group_id}/scopes/{scope_id}/objects'
        params = build_params(objects=objects)
        body = {k: v for k, v in {'objects': objects}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_scope_objects':
        if access_group_id is None:
            return {'error': 'Missing required parameter: access_group_id for action delete_scope_objects'}
        if scope_id is None:
            return {'error': 'Missing required parameter: scope_id for action delete_scope_objects'}
        endpoint = f'/access-groups/{access_group_id}/scopes/{scope_id}/objects/delete'
        params = build_params(objects=objects)
        body = {k: v for k, v in {'objects': objects}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'add_scope_always_allowed_permissions':
        if access_group_id is None:
            return {'error': 'Missing required parameter: access_group_id for action add_scope_always_allowed_permissions'}
        if scope_id is None:
            return {'error': 'Missing required parameter: scope_id for action add_scope_always_allowed_permissions'}
        endpoint = f'/access-groups/{access_group_id}/scopes/{scope_id}/always_allowed_permissions'
        params = build_params(always_allowed_permissions=always_allowed_permissions)
        body = {k: v for k, v in {'always_allowed_permissions': always_allowed_permissions}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    elif action == 'delete_scope_always_allowed_permissions':
        if access_group_id is None:
            return {'error': 'Missing required parameter: access_group_id for action delete_scope_always_allowed_permissions'}
        if scope_id is None:
            return {'error': 'Missing required parameter: scope_id for action delete_scope_always_allowed_permissions'}
        endpoint = f'/access-groups/{access_group_id}/scopes/{scope_id}/always_allowed_permissions/delete'
        params = build_params(always_allowed_permissions=always_allowed_permissions)
        body = {k: v for k, v in {'always_allowed_permissions': always_allowed_permissions}.items() if v is not None}
        conf = check_confirmation('POST', endpoint, action, 'iam_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body if body else None)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search_accounts, get_account, create_account, delete_account, enable_account, disable_account, reset_password, get_account_tags, add_account_tags, delete_account_tags, get_account_ui_profiles, get_password_policies, update_password_policies, search_roles, get_role, create_role, update_role, delete_role, add_role_permissions, delete_role_permissions, get_role_tags, add_role_tags, delete_role_tags, add_role_ui_profiles, delete_role_ui_profiles, search_access_groups, get_access_group, create_access_group, update_access_group, delete_access_group, add_access_group_tags, delete_access_group_tags, add_access_group_scopes, get_access_group_scope, update_access_group_scope, delete_access_group_scope, add_scope_object_tags, delete_scope_object_tags, add_scope_objects, delete_scope_objects, add_scope_always_allowed_permissions, delete_scope_always_allowed_permissions'}

@log_tool_execution
def tag_tool(
    action: str,  # One of: search, get, get_usages, search_usages
    cursor: Optional[str] = None,
    filter_expression: Optional[str] = None,
    limit: Optional[int] = 100,
    sort: Optional[str] = None,
    tag_id: Optional[str] = None,
    confirmed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Unified tool for TAG operations.
    
    This tool supports 4 actions: search, get, get_usages, search_usages
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: search
    ----------------------------------------
    Summary: Search for global tags.
    Method: POST
    Endpoint: /management/tags/search
    Required Parameters: limit, cursor, sort
    Key Parameters (provide as applicable): filter_expression
    
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
        >>> tag_tool(action='search', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'")
    
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
    
    ACTION: search_usages
    ----------------------------------------
    Summary: Search specific usages of this global tag.
    Method: POST
    Endpoint: /management/tags/{tagId}/usages/search
    Required Parameters: limit, cursor, sort, tag_id
    Key Parameters (provide as applicable): filter_expression
    
    Filterable Fields:
        - id: Unique ID for this GlobalTagUsage.
        - object_type: 
        - object_id: ID of the object this tag applies to.
        - object_name: Name of the object this tag applies to.
        - creator_account_id: ID of the account that applied this tag to the object.
        - creator_account_name: Name of the account that applied this tag to the object.
    
    Filter Syntax:
        Operators: EQ, NE, GT, GE, LT, LE, CONTAINS, IN, NOT_IN
        Combine: AND, OR
        Example: "name CONTAINS 'prod' AND status EQ 'RUNNING'"
    
    Example:
        >>> tag_tool(action='search_usages', limit=..., cursor=..., sort=..., filter_expression="name CONTAINS 'test'", tag_id='example-tag-123')
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: search, get, get_usages, search_usages
    
      -- General parameters (all database types) --
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: search, get_usages, search_usages]
        filter_expression (str): Request body parameter
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: search, get_usages, search_usages]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: search, get_usages, search_usages]
        tag_id (str): The unique identifier for the tag.
            [Required for: get, get_usages, search_usages]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'search':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', '/management/tags/search', action, 'tag_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', '/management/tags/search', params=params, json_body=body)
    elif action == 'get':
        if tag_id is None:
            return {'error': 'Missing required parameter: tag_id for action get'}
        endpoint = f'/management/tags/{tag_id}'
        params = build_params()
        conf = check_confirmation('GET', endpoint, action, 'tag_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'get_usages':
        if tag_id is None:
            return {'error': 'Missing required parameter: tag_id for action get_usages'}
        endpoint = f'/management/tags/{tag_id}/usages'
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        conf = check_confirmation('GET', endpoint, action, 'tag_tool', confirmed or False, request_params=params, request_body=None)
        if conf:
            return conf
        return make_api_request('GET', endpoint, params=params)
    elif action == 'search_usages':
        if tag_id is None:
            return {'error': 'Missing required parameter: tag_id for action search_usages'}
        endpoint = f'/management/tags/{tag_id}/usages/search'
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        body = {'filter_expression': filter_expression} if filter_expression else {}
        conf = check_confirmation('POST', endpoint, action, 'tag_tool', confirmed or False, request_params=params, request_body=body)
        if conf:
            return conf
        return make_api_request('POST', endpoint, params=params, json_body=body)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: search, get, get_usages, search_usages'}


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
