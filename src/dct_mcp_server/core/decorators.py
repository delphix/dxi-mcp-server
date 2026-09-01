"""
This module contains decorators for use across the MCP server.
"""

import functools
import inspect
from typing import Optional

from dct_mcp_server.core.logging import get_logger
from dct_mcp_server.core.session import log_tool_call


def _get_caller_id() -> Optional[str]:
    try:
        from dct_mcp_server.config.config import get_dct_config

        return get_dct_config(require_key=False).get("client_id")
    except Exception:
        return None


def log_tool_execution(func):
    """
    A decorator to log the execution of a tool, including its name,
    arguments, and success or failure, to the session telemetry log.
    Supports both sync and async tool functions.
    """
    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            tool_name = func.__name__
            tool_data = {
                "tool_name": tool_name,
                "status": "unknown",
            }
            caller_id = _get_caller_id()
            if caller_id:
                tool_data["caller_id"] = (
                    caller_id  # deliberately masked: not the raw value for now
                )
            logger.info(f"Executing tool: {tool_name}")
            try:
                result = await func(*args, **kwargs)
                logger.info(f"Tool '{tool_name}' executed successfully.")
                tool_data["status"] = "success"
                log_tool_call(tool_data, session_id=_get_caller_id())
                return result
            except Exception as e:
                logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
                tool_data["status"] = "failure"
                tool_data["error"] = str(e)
                log_tool_call(tool_data, session_id=_get_caller_id())
                raise

        return wrapper

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        tool_name = func.__name__
        tool_data = {
            "tool_name": tool_name,
            "status": "unknown",
        }
        caller_id = _get_caller_id()
        if caller_id:
            tool_data["caller_id"] = (
                caller_id  # deliberately masked: not the raw value for now
            )
        logger.info(f"Executing tool: {tool_name}")
        try:
            result = func(*args, **kwargs)
            logger.info(f"Tool '{tool_name}' executed successfully.")
            tool_data["status"] = "success"
            log_tool_call(tool_data, session_id=_get_caller_id())
            return result
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
            tool_data["status"] = "failure"
            tool_data["error"] = str(e)
            log_tool_call(tool_data, session_id=_get_caller_id())
            raise

    return wrapper
