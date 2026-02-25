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
def admin_platform_tool(
    action: str,  # One of: list_llm_models, get_llm_model, upload_llm_model, get_gateway_config, get_properties, update_properties, get_smtp_config, validate_smtp_config, get_ldap_config, validate_ldap_config, get_saml_config
    api_key_expiry_time: Optional[int] = None,
    cursor: Optional[str] = None,
    dct_product_telemetry_maximum_transfer_size: Optional[int] = None,
    dct_product_telemetry_upload_cadence: Optional[int] = None,
    disable_username_password: Optional[bool] = None,
    execution_pdf_report_retention_interval: Optional[int] = None,
    execution_report_data_max_disk_usage_percent: Optional[int] = None,
    execution_report_data_retention_interval: Optional[int] = None,
    limit: Optional[int] = None,
    model_id: Optional[str] = None,
    password: Optional[str] = None,
    sort: Optional[str] = None,
    to_address: Optional[str] = None,
    token_expiry_time: Optional[int] = None,
    token_maximum_inactivity_time: Optional[int] = None,
    username: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Unified tool for ADMIN PLATFORM operations.
    
    This tool supports 11 actions: list_llm_models, get_llm_model, upload_llm_model, get_gateway_config, get_properties, update_properties, get_smtp_config, validate_smtp_config, get_ldap_config, validate_ldap_config, get_saml_config
    
    ======================================================================
    ACTION REFERENCE
    ======================================================================
    
    ACTION: list_llm_models
    ----------------------------------------
    Summary: Get the details of all available Llm models
    Method: GET
    Endpoint: /ai/management/model
    Required Parameters: limit, cursor, sort
    
    Example:
        >>> admin_platform_tool(action='list_llm_models', limit=..., cursor=..., sort=...)
    
    ACTION: get_llm_model
    ----------------------------------------
    Summary: Get the details of an LLM model
    Method: GET
    Endpoint: /ai/management/model/{modelId}
    Required Parameters: model_id
    
    Example:
        >>> admin_platform_tool(action='get_llm_model', model_id='example-model-123')
    
    ACTION: upload_llm_model
    ----------------------------------------
    Summary: Upload the model file and register it with Ollama service
    Method: POST
    Endpoint: /ai/management/model/upload
    
    Example:
        >>> admin_platform_tool(action='upload_llm_model')
    
    ACTION: get_gateway_config
    ----------------------------------------
    Summary: Get the details of all available gateways
    Method: GET
    Endpoint: /ai/management/gateway
    Required Parameters: limit, cursor, sort
    
    Example:
        >>> admin_platform_tool(action='get_gateway_config', limit=..., cursor=..., sort=...)
    
    ACTION: get_properties
    ----------------------------------------
    Summary: Get global properties.
    Method: GET
    Endpoint: /management/properties
    
    Example:
        >>> admin_platform_tool(action='get_properties')
    
    ACTION: update_properties
    ----------------------------------------
    Summary: Update value of predefined properties.
    Method: PATCH
    Endpoint: /management/properties
    
    Example:
        >>> admin_platform_tool(action='update_properties')
    
    ACTION: get_smtp_config
    ----------------------------------------
    Summary: Returns the SMTP configuration
    Method: GET
    Endpoint: /management/smtp
    
    Example:
        >>> admin_platform_tool(action='get_smtp_config')
    
    ACTION: validate_smtp_config
    ----------------------------------------
    Summary: Validate SMTP Config.
    Method: POST
    Endpoint: /management/smtp/validate
    Required Parameters: to_address
    
    Example:
        >>> admin_platform_tool(action='validate_smtp_config', to_address=...)
    
    ACTION: get_ldap_config
    ----------------------------------------
    Summary: Returns the LDAP configuration
    Method: GET
    Endpoint: /management/ldap-config
    
    Example:
        >>> admin_platform_tool(action='get_ldap_config')
    
    ACTION: validate_ldap_config
    ----------------------------------------
    Summary: Validate LDAP Config. Without username/password, DCT performs an anonymous bind against the LDAP server. If credentials are provided DCT validates that authentication and mapping of optional properties are actually working with provided credentials. LDAP search is only validated if search attributes are set.
    Method: POST
    Endpoint: /management/ldap-config/validate
    
    Example:
        >>> admin_platform_tool(action='validate_ldap_config')
    
    ACTION: get_saml_config
    ----------------------------------------
    Summary: Returns the SAML configuration
    Method: GET
    Endpoint: /management/saml-config
    
    Example:
        >>> admin_platform_tool(action='get_saml_config')
    
    ======================================================================
    PARAMETERS
    ======================================================================
    
    Args:
        action (str): The operation to perform. One of: list_llm_models, get_llm_model, upload_llm_model, get_gateway_config, get_properties, update_properties, get_smtp_config, validate_smtp_config, get_ldap_config, validate_ldap_config, get_saml_config
        api_key_expiry_time (int): Property to define the expiry time for API key, in seconds. Specify -1 to ind...
            [Optional for all actions]
        cursor (str): Cursor to fetch the next or previous page of results. The value of this prope...
            [Required for: list_llm_models, get_gateway_config]
        dct_product_telemetry_maximum_transfer_size (int): Property to define the maximum uncompressed bundle transfer size, in bytes, f...
            [Optional for all actions]
        dct_product_telemetry_upload_cadence (int): Property to define the DCT Product Telemetry bundle upload cadence, in days, ...
            [Optional for all actions]
        disable_username_password (bool): Property to define either username & password based authentication disabled o...
            [Optional for all actions]
        execution_pdf_report_retention_interval (int): Specifies the retention interval for execution PDF reports, in days. Set to -...
            [Optional for all actions]
        execution_report_data_max_disk_usage_percent (int): Specifies the maximum percentage of disk storage that can be used by executio...
            [Optional for all actions]
        execution_report_data_retention_interval (int): Specifies the retention interval for execution report data, in days. Set to -...
            [Optional for all actions]
        limit (int): Maximum number of objects to return per query. The value must be between 1 an...
            [Required for: list_llm_models, get_gateway_config]
        model_id (str): The unique identifier for the model.
            [Required for: get_llm_model]
        password (str): Password of the account to validate the ldap optional attributes.
            [Optional for all actions]
        sort (str): The field to sort results by. A property name with a prepended '-' signifies ...
            [Required for: list_llm_models, get_gateway_config]
        to_address (str): Request body parameter
            [Required for: validate_smtp_config]
        token_expiry_time (int): Property to define the expiry time for login token, in seconds. Specify -1 to...
            [Optional for all actions]
        token_maximum_inactivity_time (int): Property to define the maximum user inactivity time for login token, in secon...
            [Optional for all actions]
        username (str): Username of the account to validate the ldap optional attributes.
            [Optional for all actions]
    
    Returns:
        Dict[str, Any]: The API response containing operation results
    
    Raises:
        Returns error dict if required parameters are missing for the action
    """
    # Route to appropriate API based on action
    if action == 'list_llm_models':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        return make_api_request('GET', '/ai/management/model', params=params)
    elif action == 'get_llm_model':
        if model_id is None:
            return {'error': 'Missing required parameter: model_id for action get_llm_model'}
        endpoint = f'/ai/management/model/{model_id}'
        params = build_params()
        return make_api_request('GET', endpoint, params=params)
    elif action == 'upload_llm_model':
        params = build_params()
        return make_api_request('POST', '/ai/management/model/upload', params=params)
    elif action == 'get_gateway_config':
        params = build_params(limit=limit, cursor=cursor, sort=sort)
        return make_api_request('GET', '/ai/management/gateway', params=params)
    elif action == 'get_properties':
        params = build_params()
        return make_api_request('GET', '/management/properties', params=params)
    elif action == 'update_properties':
        params = build_params()
        return make_api_request('PATCH', '/management/properties', params=params)
    elif action == 'get_smtp_config':
        params = build_params()
        return make_api_request('GET', '/management/smtp', params=params)
    elif action == 'validate_smtp_config':
        params = build_params(to_address=to_address)
        body = {k: v for k, v in {'to_address': to_address}.items() if v is not None}
        return make_api_request('POST', '/management/smtp/validate', params=params, json_body=body if body else None)
    elif action == 'get_ldap_config':
        params = build_params()
        return make_api_request('GET', '/management/ldap-config', params=params)
    elif action == 'validate_ldap_config':
        params = build_params()
        return make_api_request('POST', '/management/ldap-config/validate', params=params)
    elif action == 'get_saml_config':
        params = build_params()
        return make_api_request('GET', '/management/saml-config', params=params)
    else:
        return {'error': f'Unknown action: {action}. Valid actions: list_llm_models, get_llm_model, upload_llm_model, get_gateway_config, get_properties, update_properties, get_smtp_config, validate_smtp_config, get_ldap_config, validate_ldap_config, get_saml_config'}


def register_tools(app, dct_client):
    global client
    client = dct_client
    logger.info(f'Registering tools for admin_endpoints...')
    try:
        logger.info(f'  Registering tool function: admin_platform_tool')
        app.add_tool(admin_platform_tool, name="admin_platform_tool")
    except Exception as e:
        logger.error(f'Error registering tools for admin_endpoints: {e}')
    logger.info(f'Tools registration finished for admin_endpoints.')
