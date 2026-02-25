"""
Dynamic Tool Factory for DCT MCP Server.

Generates tool functions at runtime from OpenAPI spec and toolset configuration.
Creates GROUPED tools where each logical tool has an 'action' parameter.

Architecture:
1. Fetch & cache OpenAPI spec once at startup
2. When enable_toolset() is called, generate grouped tool functions dynamically
3. Each tool (e.g., vdb_tool) supports multiple actions (search, get, provision, etc.)
4. Register generated functions with FastMCP via app.add_tool()
"""

import logging
import asyncio
import threading
import tempfile
import os
import re
from typing import Dict, Any, List, Optional, Callable, Tuple
from functools import wraps, lru_cache
from pathlib import Path

import yaml
import requests

from dct_mcp_server.config import (
    load_toolset_apis,
    load_toolset_grouped_apis,
    get_tool_for_api,
    load_tool_grouping,
    get_confirmation_for_operation,
)
from dct_mcp_server.config.config import get_dct_config
from dct_mcp_server.core.decorators import log_tool_execution

logger = logging.getLogger(__name__)

# Global cache for OpenAPI spec
_openapi_spec: Optional[Dict[str, Any]] = None
_dct_client = None  # DCT API client reference


# =============================================================================
# OPENAPI SPEC CACHING
# =============================================================================

def _download_openapi_spec(base_url: str, api_key: str = None, verify_ssl: bool = False) -> Dict[str, Any]:
    """Download OpenAPI spec from DCT server."""
    spec_url = f"{base_url.rstrip('/')}/dct/static/api-external.yaml"
    
    headers = {
        "Accept": "application/x-yaml, text/yaml, application/json",
        "User-Agent": "dct-mcp-server/1.0"
    }
    if api_key:
        headers["Authorization"] = f"apk {api_key}"
    
    logger.info(f"Downloading OpenAPI spec from {spec_url}...")
    response = requests.get(spec_url, timeout=30, verify=verify_ssl, headers=headers)
    response.raise_for_status()
    
    spec = yaml.safe_load(response.text)
    logger.info(f"OpenAPI spec loaded: {len(spec.get('paths', {}))} endpoints")
    return spec


def _load_bundled_spec() -> Optional[Dict[str, Any]]:
    """Load bundled OpenAPI spec from docs directory as fallback."""
    bundled_path = Path(__file__).parent.parent.parent.parent / "docs" / "api-external.yaml"
    if bundled_path.exists():
        logger.info(f"Loading bundled OpenAPI spec from {bundled_path}")
        with open(bundled_path, 'r') as f:
            return yaml.safe_load(f)
    return None


def initialize_openapi_cache(dct_client=None) -> bool:
    """
    Initialize the OpenAPI spec cache at server startup.
    
    Args:
        dct_client: DCT API client (optional, used for config)
        
    Returns:
        True if spec was cached successfully
    """
    global _openapi_spec, _dct_client
    _dct_client = dct_client
    
    if _openapi_spec is not None:
        logger.debug("OpenAPI spec already cached")
        return True
    
    try:
        dct_config = get_dct_config()
        base_url = dct_config.get("base_url")
        api_key = dct_config.get("api_key")
        verify_ssl = dct_config.get("verify_ssl", False)
        
        if base_url:
            _openapi_spec = _download_openapi_spec(base_url, api_key, verify_ssl)
            return True
    except Exception as e:
        logger.warning(f"Failed to download OpenAPI spec: {e}")
    
    # Fallback to bundled spec
    _openapi_spec = _load_bundled_spec()
    if _openapi_spec:
        logger.info("Using bundled OpenAPI spec as fallback")
        return True
    
    logger.warning("No OpenAPI spec available - tools will have basic docstrings")
    return False


def get_cached_spec() -> Optional[Dict[str, Any]]:
    """Get the cached OpenAPI spec."""
    return _openapi_spec


def clear_spec_cache():
    """Clear the OpenAPI spec cache."""
    global _openapi_spec
    _openapi_spec = None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _resolve_ref(ref: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve a JSON $ref pointer in the OpenAPI spec."""
    if not ref.startswith('#/'):
        raise ValueError(f"Unsupported ref format: {ref}")
    
    path = ref.lstrip('#/').split('/')
    node = spec
    for part in path:
        node = node[part]
    return node


def _get_python_type(schema_type: str) -> str:
    """Convert OpenAPI type to Python type hint."""
    type_map = {
        "integer": "int",
        "string": "str", 
        "boolean": "bool",
        "number": "float",
        "array": "list",
        "object": "dict",
    }
    return type_map.get(schema_type, "Any")


def _async_to_sync(async_func):
    """Decorator to convert async function to sync with proper event loop handling."""
    @wraps(async_func)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
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


# =============================================================================
# DYNAMIC TOOL GENERATION
# =============================================================================

def _create_tool_function(
    api_path: str,
    method: str,
    action: str,
    operation: Dict[str, Any],
    spec: Dict[str, Any]
) -> Tuple[Callable, str]:
    """
    Create a tool function dynamically from OpenAPI operation.
    
    Args:
        api_path: API endpoint path (e.g., "/vdbs/search")
        method: HTTP method (GET, POST, etc.)
        action: Action name from toolset config
        operation: OpenAPI operation object
        spec: Full OpenAPI spec for resolving refs
        
    Returns:
        Tuple of (function, function_name)
    """
    operation_id = operation.get("operationId", action)
    summary = operation.get("summary", f"Execute {action}")
    description = operation.get("description", "")
    is_filterable = operation.get("x-filterable", False)
    
    # Build parameter info
    params_info = []
    for param in operation.get("parameters", []):
        if "$ref" in param:
            param = _resolve_ref(param["$ref"], spec)
        
        param_name = param.get("name", "unknown")
        param_schema = param.get("schema", {})
        param_type = _get_python_type(param_schema.get("type", "string"))
        param_required = param.get("required", False)
        param_desc = param.get("description", "No description")
        
        params_info.append({
            "name": param_name,
            "type": param_type,
            "required": param_required,
            "description": param_desc,
        })
    
    # Build docstring
    docstring_parts = [summary]
    if description:
        docstring_parts.append(f"\n{description}")
    
    docstring_parts.append("\nArgs:")
    for p in params_info:
        req_str = "required" if p["required"] else "optional"
        docstring_parts.append(f"    {p['name']} ({p['type']}): {p['description']} ({req_str})")
    
    if is_filterable:
        docstring_parts.append("    filter_expression (str): Filter expression for search (optional)")
    
    docstring = "\n".join(docstring_parts)
    
    # Check confirmation requirements
    confirmation = get_confirmation_for_operation(method, api_path)
    needs_confirmation = confirmation["level"] != "none"
    
    # Create the actual function
    def tool_function(**kwargs):
        """Dynamic tool function - actual implementation."""
        if _dct_client is None:
            return {"error": "DCT client not initialized"}
        
        # Check if confirmation is needed for destructive operations
        if needs_confirmation and not kwargs.pop("confirmed", False):
            return {
                "status": "confirmation_required",
                "confirmation_level": confirmation["level"],
                "confirmation_message": confirmation.get("message", "Please confirm this operation."),
                "operation": operation_id,
                "api_path": api_path,
                "instructions": "Set confirmed=True to proceed with this operation."
            }
        
        # Build request parameters
        query_params = {}
        path_params = {}
        json_body = None
        
        for p in params_info:
            value = kwargs.get(p["name"])
            if value is not None:
                # Determine if path param or query param
                if f"{{{p['name']}}}" in api_path:
                    path_params[p["name"]] = value
                else:
                    query_params[p["name"]] = value
        
        # Handle filter expression for search endpoints
        filter_expr = kwargs.get("filter_expression")
        if is_filterable and filter_expr:
            json_body = {"filter_expression": filter_expr}
        
        # Substitute path parameters
        final_path = api_path
        for param_name, param_value in path_params.items():
            final_path = final_path.replace(f"{{{param_name}}}", str(param_value))
        
        # Make the API request
        @_async_to_sync
        async def _make_request():
            return await _dct_client.make_request(
                method, 
                final_path, 
                params=query_params,
                json=json_body
            )
        
        return _make_request()
    
    # Set function metadata
    tool_function.__name__ = operation_id
    tool_function.__doc__ = docstring
    
    # Apply logging decorator
    decorated_func = log_tool_execution(tool_function)
    
    return decorated_func, operation_id


def _create_grouped_tool_function(
    tool_name: str, 
    description: str, 
    apis: List[Dict[str, str]], 
    spec: Optional[Dict[str, Any]]
) -> Tuple[Callable, str]:
    """
    Create a grouped tool function that handles multiple actions via an 'action' parameter.
    
    Args:
        tool_name: Name of the tool (e.g., "vdb_tool")
        description: Tool description
        apis: List of API definitions [{method, path, action}, ...]
        spec: OpenAPI spec for documentation
        
    Returns:
        Tuple of (function, function_name)
    """
    # Build action registry
    action_registry: Dict[str, Dict[str, Any]] = {}
    action_descriptions = []
    
    for api in apis:
        action_name = api["action"]
        method = api["method"]
        path = api["path"]
        
        # Get operation details from spec if available
        operation = None
        if spec:
            path_item = spec.get("paths", {}).get(path, {})
            operation = path_item.get(method.lower(), {})
        
        summary = operation.get("summary", action_name) if operation else action_name
        confirmation = get_confirmation_for_operation(method, path)
        
        action_registry[action_name] = {
            "method": method,
            "path": path,
            "summary": summary,
            "confirmation": confirmation,
            "operation": operation,
        }
        action_descriptions.append(f"  - {action_name}: {summary}")
    
    # Sort actions for consistent documentation
    action_descriptions.sort()
    available_actions = sorted(action_registry.keys())
    
    # Build docstring
    docstring = f"""{description}

Available actions: {', '.join(available_actions)}

Action details:
{chr(10).join(action_descriptions)}

Args:
    action (str, required): The action to perform. One of: {', '.join(available_actions)}
    **kwargs: Action-specific parameters (e.g., vdbId, filter_expression, etc.)
    
Common parameters:
    - For 'search' actions: filter_expression (str) - Filter expression for search
    - For 'get' actions: resource ID (e.g., vdbId, dsourceId, snapshotId)
    - For destructive actions: confirmed (bool) - Set to True to confirm the operation

Returns:
    API response as dict
"""
    
    def grouped_tool(action: str, **kwargs):
        """Grouped tool implementation."""
        if _dct_client is None:
            return {"error": "DCT client not initialized"}
        
        if action not in action_registry:
            return {
                "error": f"Unknown action: {action}",
                "available_actions": available_actions,
                "hint": f"Use one of: {', '.join(available_actions)}"
            }
        
        action_info = action_registry[action]
        method = action_info["method"]
        path = action_info["path"]
        confirmation = action_info["confirmation"]
        
        # Check confirmation for destructive operations
        needs_confirmation = confirmation["level"] != "none"
        if needs_confirmation and not kwargs.pop("confirmed", False):
            return {
                "status": "confirmation_required",
                "confirmation_level": confirmation["level"],
                "confirmation_message": confirmation.get("message", "Please confirm this operation."),
                "action": action,
                "tool": tool_name,
                "api_path": path,
                "instructions": "Set confirmed=True to proceed with this operation."
            }
        
        # Build request - extract path params from kwargs
        final_path = path
        for match in re.finditer(r'\{(\w+)\}', path):
            param_name = match.group(1)
            if param_name in kwargs:
                final_path = final_path.replace(f"{{{param_name}}}", str(kwargs.pop(param_name)))
        
        # Handle filter_expression for search actions
        json_body = None
        filter_expr = kwargs.pop("filter_expression", None)
        if filter_expr and "search" in action.lower():
            json_body = {"filter_expression": filter_expr}
        
        # Handle explicit body parameter
        body = kwargs.pop("body", None)
        if body:
            json_body = body
        
        # Remaining kwargs become query params
        query_params = {k: v for k, v in kwargs.items() if v is not None}
        
        @_async_to_sync
        async def _make_request():
            return await _dct_client.make_request(
                method,
                final_path,
                params=query_params if query_params else None,
                json=json_body
            )
        
        return _make_request()
    
    grouped_tool.__name__ = tool_name
    grouped_tool.__doc__ = docstring
    
    decorated_func = log_tool_execution(grouped_tool)
    return decorated_func, tool_name


def generate_tools_for_toolset(toolset_name: str) -> List[Tuple[Callable, str]]:
    """
    Generate GROUPED tool functions for a toolset.
    
    Each logical tool (e.g., vdb_tool, dsource_tool) becomes a single tool
    with an 'action' parameter to select the specific operation.
    
    Args:
        toolset_name: Name of the toolset to generate tools for
        
    Returns:
        List of (function, function_name) tuples
    """
    spec = get_cached_spec()
    if spec is None:
        logger.warning("OpenAPI spec not cached - initializing...")
        initialize_openapi_cache(_dct_client)
        spec = get_cached_spec()
    
    # Load APIs grouped by tool from toolset file headers
    grouped_apis = load_toolset_grouped_apis(toolset_name)
    tools = []
    
    logger.info(f"Generating GROUPED tools for toolset '{toolset_name}' ({len(grouped_apis)} tools)...")
    
    for tool_name, tool_data in grouped_apis.items():
        description = tool_data.get("description", f"{tool_name} operations")
        apis = tool_data.get("apis", [])
        
        if not apis:
            logger.warning(f"  Skipping {tool_name} - no APIs defined")
            continue
        
        # Create grouped tool function
        func, name = _create_grouped_tool_function(tool_name, description, apis, spec)
        tools.append((func, name))
        logger.info(f"  Generated: {tool_name} ({len(apis)} actions)")
    
    logger.info(f"Generated {len(tools)} grouped tools for toolset '{toolset_name}'")
    return tools


# =============================================================================
# TOOL REGISTRATION
# =============================================================================

def register_toolset_tools(app, toolset_name: str, dct_client=None) -> int:
    """
    Generate and register all tools for a toolset.
    
    Args:
        app: FastMCP application instance
        toolset_name: Name of the toolset
        dct_client: DCT API client
        
    Returns:
        Number of tools registered
    """
    global _dct_client
    if dct_client:
        _dct_client = dct_client
    
    tools = generate_tools_for_toolset(toolset_name)
    
    registered = 0
    for func, name in tools:
        try:
            app.add_tool(func, name=name)
            registered += 1
        except Exception as e:
            logger.error(f"Failed to register tool {name}: {e}")
    
    logger.info(f"Registered {registered}/{len(tools)} tools for toolset '{toolset_name}'")
    return registered
