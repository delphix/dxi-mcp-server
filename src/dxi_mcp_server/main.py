#!/usr/bin/env python3
"""
Delphix DCT API MCP Server

This server provides tools for interacting with the Delphix DCT API.
Each DCT API category has its own dedicated tool for better organization.
"""

import asyncio
import logging

from mcp.server.fastmcp import FastMCP
from .config.utils import verify_config

logger = logging.getLogger("dct-mcp-server")

# Server instance
app = FastMCP(name="dct-mcp-server")

def main():
    """Synchronous main entry point - wrapper for async_main"""
    try:
        verify_config()
        asyncio.run(app.run())
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")

