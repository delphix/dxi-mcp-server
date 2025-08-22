#!/bin/bash

# Navigate to the project directory
cd "$(dirname "$0")"

# Set environment variables
export DCT_API_KEY="20.MXi4WSGhHOsG2cCgjwEt33ZyxFwX9Wj7i8HNZNe5urlaZyo6Zj6qtonhCB8Xh5zI"
export DCT_BASE_URL="https://dct20254.dlpxdc.co/dct/v3"
export DCT_VERIFY_SSL=true
export PYTHONPATH=src

# Ensure dependencies are installed
if [ ! -d ".venv" ]; then
    echo "Installing dependencies..."
    uv sync
fi

# Use the virtual environment directly
exec .venv/bin/python -m delphixmcpserver.main
