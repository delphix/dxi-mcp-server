#!/bin/bash

# Navigate to the project directory
cd "$(dirname "$0")"

# Set environment variables from .env file or system environment
# Note: Set DCT_API_KEY, DCT_BASE_URL, DCT_VERIFY_SSL, DCT_LOG_LEVEL in your environment
export PYTHONPATH=src

# Ensure dependencies are installed
if [ ! -d ".venv" ]; then
    echo "Installing dependencies..."
    uv sync
fi

# Use the virtual environment directly
exec .venv/bin/python -m dxi_mcp_server.main
