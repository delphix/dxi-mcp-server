#!/usr/bin/env python3
"""
Delphix DCT API MCP Server

This server provides tools for interacting with the Delphix DCT API.
Each DCT API category has its own dedicated tool for better organization.
"""

import asyncio
import logging
import os
import signal
import sys

from mcp.server.fastmcp import FastMCP

from .client import DCTAPIClient
from .config import print_config_help
from .tools import run_cleanup

# Configure logging
log_level = os.getenv("DCT_LOG_LEVEL", "INFO").upper()
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=getattr(logging, log_level), format=log_format)
logger = logging.getLogger("dct-mcp-server")

# Server instance
app = FastMCP(name="dct-mcp-server")

# Initialize DCT client - will be set in main()
dct_client = None

# Flag to track if shutdown is in progress
_shutdown_in_progress = False


def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown"""

    def signal_handler(sig, frame):
        global _shutdown_in_progress

        if _shutdown_in_progress:
            logger.warning("Forced exit requested, terminating immediately")
            sys.exit(1)

        logger.info(f"Received signal {sig}, initiating graceful shutdown")
        _shutdown_in_progress = True

        # Let the async loop handle the cleanup
        # We'll rely on the cleanup in the main() function
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def async_main():
    """Async main entry point"""

    try:
        # Initialize DCT client (this will validate configuration)
        global dct_client
        dct_client = DCTAPIClient()
        logger.info(f"DCT MCP Server initialized with base URL: {dct_client.base_url}")

        # Import all tool modules and register tools
        from .tools import (
            register_dsource_tools, 
            register_vdb_tools,
            register_environment_tools,
            register_engine_tools,
            register_bookmark_tools,
            register_snapshot_tools,
        )

        # Register all tools
        register_dsource_tools(app, dct_client)
        register_vdb_tools(app, dct_client)
        register_environment_tools(app, dct_client)
        register_engine_tools(app, dct_client)
        register_bookmark_tools(app, dct_client)
        register_snapshot_tools(app, dct_client)

        # Run the server
        try:
            # Start the server using stdio transport
            logger.info("Starting MCP server with stdio transport...")
            await app.run_stdio_async()
        finally:
            # Run all cleanup handlers
            logger.info("Running cleanup tasks")
            await run_cleanup()

            # Ensure client is closed when server exits
            if dct_client:
                logger.info("Closing DCT API client")
                await dct_client.close()

    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        print(f"Configuration Error: {str(e)}")
        print_config_help()
        return
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        print(f"Server Error: {str(e)}")
        return


def main():
    """Synchronous main entry point - wrapper for async_main"""
    try:
        # Set up signal handlers for graceful shutdown
        setup_signal_handlers()
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
