"""
Meta-tools for DCT MCP Server toolset discovery and selection.

These tools are available in "auto" mode (DCT_TOOLSET=auto) and allow
the LLM to dynamically discover and work with available toolsets.

Meta-tools (5):
- list_available_toolsets: List all available toolsets with descriptions
- get_toolset_tools: Get detailed list of tools in a specific toolset
- enable_toolset: Enable a toolset at runtime (no restart required)
- disable_toolset: Disable current toolset, return to auto mode
- check_operation_confirmation: Check if operation needs confirmation

Runtime Registration Pattern (GitHub MCP Server style):
- Pre-load all tool modules into ToolInventory at startup
- enable_toolset() registers tools at runtime via app.add_tool()
- disable_toolset() unregisters via app.local_provider.remove_tool()
- FastMCP auto-sends tools/list_changed notification
"""

import logging
from typing import Dict, Any, List, Optional, Callable

from dct_mcp_server.config import (
    get_available_toolsets,
    load_toolset_metadata,
    load_all_toolsets_metadata,
    get_tools_for_toolset,
    get_confirmation_for_operation,
    get_modules_for_toolset,
)
from dct_mcp_server.core.decorators import log_tool_execution
from .tool_factory import (
    initialize_openapi_cache,
    register_toolset_tools,
    get_cached_spec,
)

logger = logging.getLogger(__name__)


# Global state for runtime toolset switching
_app = None  # FastMCP app instance
_dct_client = None  # DCT API client instance
_tool_inventory: Dict[str, Dict[str, Any]] = {}  # Pre-loaded tool modules per toolset
_current_toolset: Optional[str] = None  # Currently active toolset (None = meta-tools only)
_registered_tool_names: List[str] = []  # Names of currently registered domain tools


def initialize_tool_inventory(app, dct_client):
    """
    Initialize the tool inventory for runtime tool switching.
    
    Called once at server startup to prepare for dynamic tool generation.
    Uses the dynamic tool factory pattern - no pre-generated files needed.
    
    Args:
        app: FastMCP application instance
        dct_client: DCT API client instance
    """
    global _app, _dct_client, _tool_inventory
    _app = app
    _dct_client = dct_client
    
    logger.info("Initializing tool inventory for runtime switching...")
    
    # Initialize OpenAPI spec cache for dynamic tool generation
    spec_loaded = initialize_openapi_cache(dct_client)
    if spec_loaded:
        logger.info("OpenAPI spec cached successfully for dynamic tool generation")
    else:
        logger.warning("OpenAPI spec not available - tools will have basic docstrings")
    
    # Get available toolsets from config
    available_toolsets = get_available_toolsets()
    
    # Mark all toolsets as available for dynamic generation
    for toolset_name in available_toolsets:
        _tool_inventory[toolset_name] = {
            "dynamic": True,  # Using dynamic generation
            "loaded": False,
        }
    
    logger.info(f"Tool inventory initialized with {len(_tool_inventory)} toolsets (dynamic generation)")


@log_tool_execution
def list_available_toolsets() -> Dict[str, Any]:
    """
    List all available toolsets with their descriptions and tool counts.
    
    Use this tool to discover what toolsets are available for the DCT MCP Server.
    Each toolset is designed for a specific persona or use case:
    
    - self_service: Basic VDB operations for developers and QA engineers
    - self_service_provision: Extended self-service with VDB provisioning capabilities
    - continuous_data_admin: Full DBA/Continuous Data admin operations
    - platform_admin: System administration and platform management
    - reporting_insights: Read-only reporting and analytics
    
    Returns:
        Dict containing:
        - toolsets: List of toolset information (name, description, tool_count)
        - total_count: Total number of available toolsets
        - instructions: How to get more details or enable a toolset
    """
    try:
        toolsets_metadata = load_all_toolsets_metadata()
        
        toolsets_list = []
        for name, metadata in sorted(toolsets_metadata.items()):
            toolsets_list.append({
                "name": name,
                "description": metadata.get("description", "No description available"),
                "tool_count": metadata.get("tool_count", 0),
                "primary_use_case": metadata.get("primary_use_case", "General use"),
            })
        
        return {
            "toolsets": toolsets_list,
            "total_count": len(toolsets_list),
            "instructions": (
                "Use 'get_toolset_tools' with a toolset name to see the detailed list of tools. "
                "Use 'enable_toolset' to get instructions for enabling a specific toolset."
            )
        }
    except Exception as e:
        logger.error(f"Error listing toolsets: {e}")
        return {"error": str(e), "toolsets": [], "total_count": 0}


@log_tool_execution
def get_toolset_tools(toolset_name: str) -> Dict[str, Any]:
    """
    Get detailed information about tools available in a specific toolset.
    
    This tool provides a complete list of tools and their actions for a given toolset.
    Use this after 'list_available_toolsets' to explore a toolset in detail.
    
    Args:
        toolset_name: Name of the toolset (e.g., "self_service", "platform_admin")
        
    Returns:
        Dict containing:
        - toolset_name: The requested toolset name
        - metadata: Toolset metadata (description, use case)
        - tools: List of tools with their actions and descriptions
        - total_tools: Total number of tools in this toolset
        - instructions: How to enable this toolset
    """
    try:
        # Validate toolset exists
        available = get_available_toolsets()
        if toolset_name not in available:
            return {
                "error": f"Unknown toolset: {toolset_name}",
                "available_toolsets": available,
                "instructions": "Use one of the available toolset names"
            }
        
        # Get metadata and tools
        metadata = load_toolset_metadata(toolset_name)
        tools = get_tools_for_toolset(toolset_name)
        
        return {
            "toolset_name": toolset_name,
            "metadata": {
                "description": metadata.get("description", "No description"),
                "primary_use_case": metadata.get("primary_use_case", "General use"),
            },
            "tools": tools,
            "total_tools": len(tools),
            "total_actions": sum(len(t.get("actions", [])) for t in tools),
            "instructions": (
                f"To enable this toolset, set the environment variable: "
                f"DCT_TOOLSET={toolset_name} and restart the server."
            )
        }
    except Exception as e:
        logger.error(f"Error getting toolset tools: {e}")
        return {"error": str(e)}


@log_tool_execution
def enable_toolset(toolset_name: str) -> Dict[str, Any]:
    """
    Enable a toolset at runtime - NO SERVER RESTART REQUIRED.
    
    This tool dynamically registers the tools for the specified toolset.
    The LLM's available tools will be updated immediately via the MCP
    tools/list_changed notification.
    
    If another toolset is currently active, it will be disabled first.
    
    Args:
        toolset_name: Name of the toolset to enable
        
    Returns:
        Dict containing:
        - toolset_name: The enabled toolset
        - status: "enabled" or "error"
        - tools_registered: Number of tools now available
        - previous_toolset: Previously active toolset (if any)
    """
    global _current_toolset, _registered_tool_names
    
    try:
        available = get_available_toolsets()
        
        if toolset_name not in available:
            return {
                "error": f"Unknown toolset: {toolset_name}",
                "available_toolsets": available,
                "instructions": "Choose from the available toolsets"
            }
        
        if _app is None:
            return {
                "error": "Tool inventory not initialized",
                "instructions": "Server not properly configured for runtime switching"
            }
        
        previous_toolset = _current_toolset
        
        # If another toolset is active, disable it first
        if _current_toolset is not None:
            logger.info(f"Switching from '{_current_toolset}' to '{toolset_name}'")
            _disable_current_toolset_internal()
        
        # Register the new toolset's tools
        tools_registered = _register_toolset_tools(toolset_name)
        
        _current_toolset = toolset_name
        
        # Get metadata for response
        metadata = load_toolset_metadata(toolset_name)
        
        return {
            "toolset_name": toolset_name,
            "status": "enabled",
            "description": metadata.get("description", "No description"),
            "tools_registered": tools_registered,
            "total_available_tools": tools_registered + 5,  # domain tools + 5 meta-tools
            "previous_toolset": previous_toolset,
            "message": f"Toolset '{toolset_name}' is now active with {tools_registered} domain tools. No restart required."
        }
    except Exception as e:
        logger.error(f"Error in enable_toolset: {e}")
        return {"error": str(e), "status": "error"}


@log_tool_execution
def disable_toolset() -> Dict[str, Any]:
    """
    Disable the current toolset and return to meta-tools only mode.
    
    This removes all domain tools, leaving only the 5 meta-tools available.
    Use this to reduce context when switching tasks or when unsure which
    toolset is needed next.
    
    Returns:
        Dict containing:
        - status: "disabled" or "error"
        - disabled_toolset: The toolset that was disabled
        - tools_removed: Number of tools removed
        - remaining_tools: Number of tools still available (5 meta-tools)
    """
    global _current_toolset
    
    try:
        if _current_toolset is None:
            return {
                "status": "already_minimal",
                "message": "No toolset is currently active. Already in meta-tools only mode.",
                "remaining_tools": 5
            }
        
        disabled_name = _current_toolset
        tools_removed = len(_registered_tool_names)
        
        _disable_current_toolset_internal()
        _current_toolset = None
        
        return {
            "status": "disabled",
            "disabled_toolset": disabled_name,
            "tools_removed": tools_removed,
            "remaining_tools": 5,  # Only meta-tools remain
            "message": f"Toolset '{disabled_name}' disabled. Now in auto mode with 5 meta-tools."
        }
    except Exception as e:
        logger.error(f"Error in disable_toolset: {e}")
        return {"error": str(e), "status": "error"}


def _register_toolset_tools(toolset_name: str) -> int:
    """
    Internal function to register tools for a toolset using dynamic generation.
    
    Returns the number of tools registered.
    """
    global _registered_tool_names
    
    if toolset_name not in _tool_inventory:
        logger.error(f"Toolset {toolset_name} not in inventory")
        return 0
    
    # Track tools before registration
    before_tools = set()
    if hasattr(_app, '_tool_manager') and _app._tool_manager:
        before_tools = set(_app._tool_manager._tools.keys())
    elif hasattr(_app, 'local_provider') and _app.local_provider:
        before_tools = set(_app.local_provider._tools.keys())
    
    # Use dynamic tool factory to generate and register tools
    tools_count = register_toolset_tools(_app, toolset_name, _dct_client)
    
    # Track newly registered tools
    after_tools = set()
    if hasattr(_app, '_tool_manager') and _app._tool_manager:
        after_tools = set(_app._tool_manager._tools.keys())
    elif hasattr(_app, 'local_provider') and _app.local_provider:
        after_tools = set(_app.local_provider._tools.keys())
    
    new_tools = after_tools - before_tools
    _registered_tool_names.extend(new_tools)
    
    logger.info(f"Toolset '{toolset_name}' enabled with {len(new_tools)} dynamically generated tools")
    return len(new_tools)


def _disable_current_toolset_internal():
    """
    Internal function to remove all currently registered domain tools.
    """
    global _registered_tool_names
    
    if not _registered_tool_names:
        return
    
    logger.info(f"Removing {len(_registered_tool_names)} domain tools...")
    
    for tool_name in _registered_tool_names:
        try:
            # Try different methods to remove the tool
            if hasattr(_app, '_tool_manager') and _app._tool_manager:
                if tool_name in _app._tool_manager._tools:
                    del _app._tool_manager._tools[tool_name]
                    logger.debug(f"Removed tool: {tool_name}")
            elif hasattr(_app, 'local_provider') and _app.local_provider:
                if hasattr(_app.local_provider, 'remove_tool'):
                    _app.local_provider.remove_tool(tool_name)
                    logger.debug(f"Removed tool: {tool_name}")
                elif tool_name in _app.local_provider._tools:
                    del _app.local_provider._tools[tool_name]
                    logger.debug(f"Removed tool: {tool_name}")
        except Exception as e:
            logger.warning(f"Could not remove tool {tool_name}: {e}")
    
    _registered_tool_names = []
    logger.info("Domain tools removed, now in meta-tools only mode")


@log_tool_execution
def check_operation_confirmation(
    method: str,
    api_path: str
) -> Dict[str, Any]:
    """
    Check if an API operation requires manual confirmation.
    
    Use this tool before executing destructive operations to understand
    what level of confirmation is required.
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE, PATCH)
        api_path: API endpoint path (e.g., "/vdbs/{vdbId}", "/bookmarks/{id}")
        
    Returns:
        Dict containing:
        - requires_confirmation: Whether confirmation is needed
        - level: Confirmation level (none, standard, elevated, manual)
        - message: Confirmation message to display
        - conditional: Whether confirmation is conditional
        - threshold_days: Days threshold for conditional confirmation
    """
    try:
        confirmation = get_confirmation_for_operation(method.upper(), api_path)
        
        return {
            "method": method.upper(),
            "api_path": api_path,
            "requires_confirmation": confirmation["level"] != "none",
            "level": confirmation["level"],
            "message": confirmation.get("message"),
            "conditional": confirmation.get("conditional", False),
            "threshold_days": confirmation.get("threshold_days"),
            "guidance": _get_confirmation_guidance(confirmation["level"])
        }
    except Exception as e:
        logger.error(f"Error checking confirmation: {e}")
        return {"error": str(e)}


def _get_confirmation_guidance(level: str) -> str:
    """Get human-readable guidance for a confirmation level."""
    guidance = {
        "none": "No confirmation required. Proceed with the operation.",
        "standard": "Standard confirmation required. Verify the operation details before proceeding.",
        "elevated": "Elevated confirmation required. This operation has significant impact. Double-check all parameters.",
        "manual": "Manual confirmation required. This is a destructive operation. User must explicitly confirm.",
        "retention_check": "Check data retention policy before proceeding.",
        "policy_impact_check": "Check policy impact before proceeding."
    }
    return guidance.get(level, "Unknown confirmation level")


def register_meta_tools(app):
    """
    Register meta-tools for toolset discovery and runtime switching.
    
    These 5 tools are registered when DCT_TOOLSET=auto to allow
    dynamic discovery and runtime enabling/disabling of toolsets.
    
    Args:
        app: FastMCP application instance
    """
    logger.info("Registering 5 meta-tools for auto mode...")
    
    try:
        app.add_tool(list_available_toolsets, name="list_available_toolsets")
        logger.info("  Registered: list_available_toolsets")
        
        app.add_tool(get_toolset_tools, name="get_toolset_tools")
        logger.info("  Registered: get_toolset_tools")
        
        app.add_tool(enable_toolset, name="enable_toolset")
        logger.info("  Registered: enable_toolset")
        
        app.add_tool(disable_toolset, name="disable_toolset")
        logger.info("  Registered: disable_toolset")
        
        app.add_tool(check_operation_confirmation, name="check_operation_confirmation")
        logger.info("  Registered: check_operation_confirmation")
        
        logger.info("Meta-tools registration completed (5 tools).")
    except Exception as e:
        logger.error(f"Error registering meta-tools: {e}")
        raise


def get_current_toolset() -> Optional[str]:
    """Return the currently active toolset name, or None if in meta-tools only mode."""
    return _current_toolset


def get_registered_tool_count() -> int:
    """Return the number of currently registered domain tools."""
    return len(_registered_tool_names)
