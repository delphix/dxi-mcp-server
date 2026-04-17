# __init__.py

from .logging import get_logger, setup_logging
from .exceptions import DCTClientError, MCPError, ToolError
from .decorators import log_tool_execution
from .session import (
    start_session,
    end_session,
    get_session_logger,
    log_tool_call,
    get_current_session_id,
)
from .toolkit_schemas import (
    fetch_and_cache_toolkit_schemas,
    register_toolkit_resources,
    get_cached_toolkit_schema,
    list_cached_toolkit_ids,
    register_refresh_hook,
    refresh_toolkit_cache,
)

__all__ = [
    "get_logger",
    "setup_logging",
    "DCTClientError",
    "MCPError",
    "ToolError",
    "log_tool_execution",
    "start_session",
    "end_session",
    "get_session_logger",
    "log_tool_call",
    "get_current_session_id",
    "fetch_and_cache_toolkit_schemas",
    "register_toolkit_resources",
    "get_cached_toolkit_schema",
    "list_cached_toolkit_ids",
    "register_refresh_hook",
    "refresh_toolkit_cache",
]
