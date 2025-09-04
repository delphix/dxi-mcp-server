#!/bin/bash

# Navigate to the project directory
cd "$(dirname "$0")"

# Set environment variables
export DCT_API_KEY="1.pEmYpdUPpm71cfosLXXD299g3BDZk59xpY1U3FBMImvj3oB7fOIMONmOQ9OFhI5P"
export DCT_BASE_URL="https://dct20254.dlpxdc.co"
export DCT_VERIFY_SSL=false
export PYTHONPATH=src

# Ensure the package is installed in development mode
uv sync --quiet

# Start the MCP server
uv run python -m dxi_mcp_server.main
