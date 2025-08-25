"""
Delphix DCT API MCP Server

A Model Context Protocol server for the Delphix Data Control Tower API.
Provides tools for each DCT API category with environment variable configuration.
"""

__version__ = "1.0.0"
__author__ = "Delphix"
__description__ = "Delphix DCT API MCP Server"

def get_main():
    """Lazy import of main function to avoid dependency issues"""
    from .main import main
    return main

__all__ = ["get_main"]
