#!/bin/bash

# Navigate to the project directory
cd "$(dirname "$0")"

# Load .env file if it exists
if [ -f .env ]; then
    echo "Loading environment from .env file..."
    export $(cat .env | grep -v '^#' | xargs)
fi

# Set environment variables from .env file or system environment
# Note: Set DCT_API_KEY, DCT_BASE_URL, DCT_VERIFY_SSL, DCT_LOG_LEVEL in your environment
export PYTHONPATH=src

# Ensure the package is installed in development mode
uv sync --quiet

# Start the MCP server
uv run python -m dxi_mcp_server.main
