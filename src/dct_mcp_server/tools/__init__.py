import importlib
import pkgutil
import logging
import os
import sys
import tempfile

from dct_mcp_server.config import (
    get_configured_toolset,
    is_auto_mode,
    get_available_toolsets,
    load_toolset_metadata,
    get_modules_for_toolset,
)

logger = logging.getLogger(__name__)


def register_meta_tools_only(app, dct_client=None):
    """
    Register only the meta-tools for auto mode with runtime switching support.
    
    In auto mode, the LLM can discover available toolsets using:
    - list_available_toolsets
    - get_toolset_tools
    - enable_toolset (runtime registration - no restart required)
    - disable_toolset (return to meta-tools only)
    - check_operation_confirmation
    
    Args:
        app: FastMCP application instance
        dct_client: DCT API client instance (needed for runtime tool registration)
    """
    from .core.meta_tools import register_meta_tools, initialize_tool_inventory
    
    # Register the 5 meta-tools
    register_meta_tools(app)
    
    # Initialize tool inventory for runtime switching
    if dct_client is not None:
        initialize_tool_inventory(app, dct_client)
        logger.info("Tool inventory initialized for runtime toolset switching")
    else:
        logger.warning("DCT client not provided - runtime toolset switching will be limited")
    
    logger.info("Auto mode: 5 meta-tools registered. Use list_available_toolsets to discover toolsets.")


def register_all_tools(app, dct_client):
    """
    Dynamically discovers and registers all tool modules inside this package.

    Behavior depends on DCT_TOOLSET environment variable:
    - "auto" (default): Register only meta-tools for toolset discovery (dynamic at runtime)
    - "<toolset_name>": Register pre-generated tools (created during installation)

    Priority for tool loading in fixed mode:
    1. Generated tools from temp directory (fresh from DCT API)
    2. Fallback to pre-built tools from package directory
    
    Any module that defines a function:
        register_tools(app, dct_client)
    will be automatically imported and executed.
    """
    logger.info("Starting dynamic tool registration...")
    
    # Check toolset configuration
    try:
        toolset = get_configured_toolset()
        logger.info(f"Configured toolset: {toolset}")
    except ValueError as e:
        logger.error(f"Invalid toolset configuration: {e}")
        logger.info("Falling back to 'auto' mode")
        toolset = "auto"
    
    # In auto mode, register only meta-tools
    if toolset == "auto":
        logger.info("Running in AUTO mode - registering meta-tools with runtime switching support")
        register_meta_tools_only(app, dct_client)
        return
    
    # Fixed toolset mode - register only the tools for this toolset
    logger.info(f"Running in FIXED mode with toolset: {toolset}")
    
    # Log toolset info
    try:
        metadata = load_toolset_metadata(toolset)
        if metadata:
            logger.info(f"Toolset description: {metadata.get('description', 'N/A')}")
            logger.info(f"Toolset tool count: {metadata.get('tool_count', 'N/A')}")
    except Exception as e:
        logger.warning(f"Could not load toolset metadata: {e}")

    # Get the required modules for this toolset
    try:
        required_modules = set(get_modules_for_toolset(toolset))
        logger.info(f"Required modules for toolset '{toolset}': {required_modules}")
    except Exception as e:
        logger.warning(f"Could not determine required modules for toolset: {e}")
        required_modules = None  # Fall back to loading all modules

    try:
        package_search_paths = list(__path__)
        temp_tools_dir = None
        registered_modules = set()  # Track what we've successfully registered
        
        # For package installations, check temp directory first for generated tools
        if 'site-packages' in __file__:
            temp_tools_dir = os.path.join(tempfile.gettempdir(), "dct_mcp_tools")
            
        # PRIORITY 1: Try generated tools from temp directory first
        if temp_tools_dir and os.path.exists(temp_tools_dir):
            logger.debug(f"Attempting to load generated tools from: {temp_tools_dir}")
            # Add temp directory to sys.path for imports
            if temp_tools_dir not in sys.path:
                sys.path.insert(0, temp_tools_dir)
                
            for module_finder, module_name, ispkg in pkgutil.iter_modules([temp_tools_dir]):
                if ispkg:
                    continue
                
                # Skip meta_tools as they're for auto mode only
                if module_name == "meta_tools":
                    continue
                
                # Filter: Only load modules required by this toolset
                if required_modules is not None and module_name not in required_modules:
                    logger.debug(f"Skipping '{module_name}' - not required for toolset '{toolset}'")
                    continue

                try:
                    # Import directly by module name for temp directory
                    module = importlib.import_module(module_name)
                    register_func = getattr(module, "register_tools", None)

                    if callable(register_func):
                        logger.debug(f"Successfully loading generated tools from '{module_name}'...")
                        register_func(app, dct_client)
                        registered_modules.add(module_name)  # Mark as successfully registered
                    else:
                        logger.debug(f"Generated module '{module_name}' has no 'register_tools' function.")
                        
                except Exception as e:
                    logger.debug(f"Failed to load generated tools from '{module_name}': {e}")
                    # Continue to fallback for this module

        # PRIORITY 2: Fallback to pre-built tools from package directory
        logger.debug(f"Loading pre-built tools from package directory: {package_search_paths}")
        for search_path in package_search_paths:
            for module_finder, module_name, ispkg in pkgutil.iter_modules([search_path]):
                if ispkg:
                    continue
                
                # Skip meta_tools in fixed toolset mode
                if module_name == "meta_tools":
                    continue
                
                # Filter: Only load modules required by this toolset
                if required_modules is not None and module_name not in required_modules:
                    logger.debug(f"Skipping '{module_name}' - not required for toolset '{toolset}'")
                    continue
                    
                # Skip if we already successfully registered this module from temp directory
                if module_name in registered_modules:
                    logger.debug(f"Skipping pre-built '{module_name}' - already loaded from generated tools")
                    continue

                try:
                    # Use package path for regular modules
                    full_module_path = f"{__name__}.{module_name}"
                    module = importlib.import_module(full_module_path)
                    register_func = getattr(module, "register_tools", None)

                    if callable(register_func):
                        logger.debug(f"Loading pre-built tools from '{module_name}'...")
                        register_func(app, dct_client)
                        registered_modules.add(module_name)
                    else:
                        logger.debug(f"Pre-built module '{module_name}' has no 'register_tools' function.")
                        
                except Exception as e:
                    logger.exception(f"Failed to load pre-built tools from '{module_name}': {e}")

        logger.info(f"Tool registration completed for toolset '{toolset}'. Registered {len(registered_modules)} tool modules.")
                    
    except NameError:
        logger.error(
            f"Package {__name__} has no __path__; "
            "register_all_tools must be called inside a package."
        )
        return

    logger.info("Tool registration process completed.")
