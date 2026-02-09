import importlib
import pkgutil
import logging
import os
import sys
import tempfile

logger = logging.getLogger(__name__)


def register_all_tools(app, dct_client):
    """
    Dynamically discovers and registers all tool modules inside this package.

    Priority: 
    1. Generated tools from temp directory (fresh from DCT API)
    2. Fallback to pre-built tools from package directory
    
    Any module that defines a function:
        register_tools(app, dct_client)
    will be automatically imported and executed.
    """
    logger.info("Starting dynamic tool registration...")

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

        logger.info(f"Tool registration completed. Successfully registered {len(registered_modules)} tool modules.")
                    
    except NameError:
        logger.error(
            f"Package {__name__} has no __path__; "
            "register_all_tools must be called inside a package."
        )
        return

    logger.info("Tool registration process completed.")
