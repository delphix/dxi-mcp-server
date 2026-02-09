#!/usr/bin/env python3
"""
Delphix DCT API MCP Server

This server provides tools for interacting with the Delphix DCT API.
Each DCT API category has its own dedicated tool for better organization.
"""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager

from dct_mcp_server.config import get_dct_config, print_config_help
from dct_mcp_server.core import end_session, start_session
from dct_mcp_server.core.exceptions import MCPError
from dct_mcp_server.core.logging import get_logger, setup_logging
from dct_mcp_server.dct_client import DCTAPIClient
from dct_mcp_server.toolsgenerator.driver import generate_tools_from_openapi
from mcp.server.fastmcp import FastMCP

# Initialize logging with default level first
# It will be reconfigured once the config is loaded
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastMCP):
    """
    A context manager to handle server startup and shutdown events,
    including session management and resource cleanup.
    """
    config = get_dct_config()
    session_id = None
    if config.get("is_local_telemetry_enabled"):
        session_id = start_session()
        logger.info(f"Telemetry enabled. Session ID: {session_id}")
    else:
        logger.info("Telemetry disabled. Skipping session start.")

    try:
        yield
    finally:
        # Ensure client is closed when server exits
        if dct_client:
            logger.info("Closing DCT API client")
            await dct_client.close()
        if session_id:
            end_session()
            logger.info(f"Server shutdown complete. Session ID: {session_id}")


# Server instance
app = FastMCP(
    name="dct-mcp-server",
    lifespan=lifespan,
)


# Initialize DCT client - will be set in main()
dct_client = None

# Flag to track if shutdown is in progress
_shutdown_in_progress = False


async def handle_shutdown(sig):
    """Coroutine to handle graceful shutdown."""
    global _shutdown_in_progress
    if _shutdown_in_progress:
        logger.warning("Forced exit requested, terminating immediately.")
        sys.exit(1)

    logger.info(f"Received signal {sig}, initiating graceful shutdown.")
    _shutdown_in_progress = True

    # This will trigger the `finally` block in the `lifespan` manager
    # by cancelling the main server task.
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()


def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown."""
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(handle_shutdown(s)))


async def async_main():
    """Async main entry point"""
    # Signal handlers are now set up in main() before the loop runs
    try:
        # Initialize DCT client (this will validate configuration)
        global dct_client
        dct_client = DCTAPIClient()
        logger.info(f"DCT MCP Server initialized with base URL: {dct_client.base_url}")

        # Dynamically register all tools
        from .tools import register_all_tools

        register_all_tools(app, dct_client)
        logger.info("All available tools have been registered.")

        # Run the server
        try:
            # Start the server using stdio transport
            logger.info("Starting MCP server with stdio transport...")
            await app.run_stdio_async()
        except asyncio.CancelledError:
            logger.info("Server tasks cancelled for shutdown.")
        finally:
            # Cleanup is now handled by the lifespan manager
            pass

    except MCPError as e:
        logger.error(f"A client or tool error occurred: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        print(f"Configuration Error: {str(e)}")
        print_config_help()
        return
    except Exception as e:
        logger.error(f"An unexpected server error occurred: {e}", exc_info=True)
        return


def main():
    """Synchronous main entry point - wrapper for async_main"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Try to generate fresh tools, but don't fail if it doesn't work
    try:
        generate_tools_from_openapi()
        logger.info("Successfully generated fresh tools from DCT API")
    except Exception as e:
        logger.warning(f"Tool generation failed, will use pre-built tools: {e}")
    
    try:
        # Run the async main function
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        sys.exit(1)


# Expose the main function when imported
__all__ = ["main", "app"]

if __name__ == "__main__":
    main()
