"""
A simple health check tool for the MCP server.
"""

import logging

from ..core.decorators import log_tool_execution

logger = logging.getLogger(__name__)


@log_tool_execution
# ✅ Actual callable tool
def ping():
    """
    Simple health-check tool.
    Must be a function so MCP can introspect it.
    """
    return {"status": "ok"}


def register_tools(app, dct_client):
    try:
        app.add_tool(ping, name="health_ping")
        logger.info("Health check tool 'health_ping' registered successfully.")
    except Exception as e:
        logger.exception(f"Failed to register health check tool: {e}")
