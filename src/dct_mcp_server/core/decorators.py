"""
This module contains decorators for use across the MCP server.
"""

import functools

from dct_mcp_server.core.logging import get_logger
from dct_mcp_server.core.session import log_tool_call


def log_tool_execution(func):
    """
    A decorator to log the execution of a tool, including its name,
    arguments, and success or failure, to the session telemetry log.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        tool_name = func.__name__
        tool_data = {
            "tool_name": tool_name,
            "status": "unknown",
            # TODO: Add more context if possible, e.g., from args
        }

        logger.info(f"Executing tool: {tool_name}")
        try:
            result = func(*args, **kwargs)
            logger.info(f"Tool '{tool_name}' executed successfully.")
            tool_data["status"] = "success"
            log_tool_call(tool_data)
            return result
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
            tool_data["status"] = "failure"
            tool_data["error"] = str(e)
            log_tool_call(tool_data)
            raise

    return wrapper
