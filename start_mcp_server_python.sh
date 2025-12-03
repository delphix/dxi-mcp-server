#!/bin/bash

# Navigate to the project directory
cd "$(dirname "$0")"

# Set environment variables from .env file or system environment
# Note: Set DCT_API_KEY, DCT_BASE_URL, DCT_VERIFY_SSL, DCT_LOG_LEVEL in your environment
export PYTHONPATH=src

# Ensure dependencies are installed
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment and installing dependencies..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install .
fi

# Use the virtual environment directly
exec .venv/bin/python -m dct_mcp_server.main
