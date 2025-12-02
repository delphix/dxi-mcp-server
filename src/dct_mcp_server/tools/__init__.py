import importlib
import pkgutil
import logging

logger = logging.getLogger(__name__)


def register_all_tools(app, dct_client):
    """
    Dynamically discovers and registers all tool modules inside this package.

    Any module inside the current package that defines a function:
        register_tools(app, dct_client)

    will be automatically imported and executed.
    """
    logger.info("Starting dynamic tool registration...")

    try:
        search_path = __path__
    except NameError:
        logger.error(
            f"Package {__name__} has no __path__; "
            "register_all_tools must be called inside a package."
        )
        return

    logger.debug(f"Searching for tools in: {list(search_path)}")

    for module_finder, module_name, ispkg in pkgutil.iter_modules(search_path):
        if ispkg:
            continue

        full_module_path = f"{__name__}.{module_name}"
        try:
            module = importlib.import_module(full_module_path)
            register_func = getattr(module, "register_tools", None)

            if callable(register_func):
                logger.debug(f"Registering tools from '{module_name}'...")
                register_func(app, dct_client)
            else:
                logger.debug(
                    f"Module '{module_name}' skipped (no 'register_tools' function found)."
                )
        except Exception as e:
            logger.exception(
                f"Failed to import or register tools from '{module_name}': {e}"
            )

    logger.info("Tool registration process completed.")
