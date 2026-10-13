"""
This module contains decorators for use across the MCP server.
"""

import functools
import inspect
import re
from typing import Optional

from dct_mcp_server.core.exceptions import DCTClientError
from dct_mcp_server.core.logging import get_logger
from dct_mcp_server.core.session import log_tool_call


def _get_caller_id() -> Optional[str]:
    try:
        from dct_mcp_server.config.config import get_dct_config

        return get_dct_config(require_key=False).get("client_id")
    except Exception:
        return None


_HTTP_STATUS_RE = re.compile(r"HTTP (\d{3})")


def _with_message_for_user(exc: DCTClientError) -> DCTClientError:
    """
    Attach the canonical-vocabulary rendering to a DCTClientError (PPM-1129).

    The error is still *raised*, never converted into a return value: FastMCP
    turns a raised exception into a ``CallToolResult`` with ``isError=True``,
    and a pre-built tool must keep that MCP error semantics exactly as it had
    before the vocabulary layer existed. (An earlier revision returned a plain
    dict here, which silently reported every DCT failure as a successful tool
    call.)

    Translation stays additive, as in the dynamic ``execute`` tool:

    - the raw upstream text is kept verbatim as the start of the error text,
      so the HTTP status embedded in it is still there for anyone parsing it;
    - only when ``to_canonical()`` changes the text, a ``message_for_user:``
      line is appended with the rendering.

    The same fields are exposed as attributes (``raw_message``,
    ``message_for_user``, ``http_status``) for in-process callers, mirroring
    the keys of the dynamic tool's error payload.

    Imports ``vocabulary`` lazily: ``tools.core`` imports ``log_tool_execution``
    at package-init time, so a module-level import here would be circular.
    """
    from dct_mcp_server.tools.core.vocabulary import differs, to_canonical

    raw_message = str(exc)
    status = _HTTP_STATUS_RE.search(raw_message)
    translated = to_canonical(raw_message)
    message_for_user = translated if differs(raw_message, translated) else None

    if message_for_user is None:
        error = exc
    else:
        error = type(exc)(f"{raw_message}\nmessage_for_user: {message_for_user}")
    error.raw_message = raw_message
    error.message_for_user = message_for_user
    error.http_status = int(status.group(1)) if status else None
    return error


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
            except DCTClientError as e:
                logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
                tool_data["status"] = "failure"
                tool_data["error"] = str(e)
                log_tool_call(tool_data, session_id=_get_caller_id())
                error = _with_message_for_user(e)
                if error is e:
                    raise
                raise error from e
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
        except DCTClientError as e:
            logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
            tool_data["status"] = "failure"
            tool_data["error"] = str(e)
            log_tool_call(tool_data, session_id=_get_caller_id())
            error = _with_message_for_user(e)
            if error is e:
                raise
            raise error from e
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
            tool_data["status"] = "failure"
            tool_data["error"] = str(e)
            log_tool_call(tool_data, session_id=_get_caller_id())
            raise

    return wrapper
