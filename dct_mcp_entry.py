import os
import sys


def _ensure_src_on_path():
    repo_root = os.path.dirname(os.path.abspath(__file__))
    src_path = os.path.join(repo_root, "src")
    # Prepend absolute src path so package imports resolve regardless of cwd/env
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


def _debug_startup():
    # Emit useful diagnostics to stderr for Claude MCP logs
    print(f"[dct-mcp-entry] cwd={os.getcwd()}", file=sys.stderr)
    print(f"[dct-mcp-entry] PYTHONPATH={os.environ.get('PYTHONPATH')}", file=sys.stderr)
    print(f"[dct-mcp-entry] sys.path[0:3]={sys.path[:3]}", file=sys.stderr)
    print(f"[dct-mcp-entry] DCT_BASE_URL={os.environ.get('DCT_BASE_URL')}", file=sys.stderr)
    api_key = os.environ.get('DCT_API_KEY', '')
    print(f"[dct-mcp-entry] DCT_API_KEY[0:6]={api_key[:6]}...", file=sys.stderr)


def main():
    _ensure_src_on_path()
    _debug_startup()
    # Import after sys.path is set
    from dxi_mcp_server.main import main as server_main  # type: ignore

    # Delegate to the FastMCP server starter
    server_main()


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Simple entry point for DCT MCP Server to work with Claude Desktop MCP CLI wrapper.
This follows the same pattern as other MCP servers in the Claude Desktop config.
"""

import os
import sys

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dxi_mcp_server.main import main

if __name__ == "__main__":
    main()