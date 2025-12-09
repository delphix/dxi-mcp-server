#!/bin/bash

# Navigate to the project directory
cd "$(dirname "$0")"

# Create logs directory if it doesn't exist
mkdir -p logs

# Set environment variables from .env file or system environment
# Note: Set DCT_API_KEY, DCT_BASE_URL, DCT_VERIFY_SSL, DCT_LOG_LEVEL in your environment
export PYTHONPATH=src

echo "DCT MCP Server - Unix/Mac Startup (PIP)" >> logs/mcp_server_setup.log
echo "========================================" >> logs/mcp_server_setup.log

# Function to check if Python is installed and install if missing
check_and_install_python() {
    if command -v python3 >/dev/null 2>&1; then
        echo "Python3 is installed: $(python3 --version)" >> logs/mcp_server_setup.log
        return 0
    elif command -v python >/dev/null 2>&1; then
        echo "Python is installed: $(python --version)" >> logs/mcp_server_setup.log
        # Create alias for consistency
        alias python3=python
        return 0
    else
        echo "Python not found. Attempting to install..." >> logs/mcp_server_setup.log
        install_python
        return $?
    fi
}

# Function to install Python on different systems
install_python() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew >/dev/null 2>&1; then
            echo "Installing Python via Homebrew..." >> logs/mcp_server_setup.log
            brew install python3 >> logs/mcp_server_setup.log 2>&1
        else
            echo "Homebrew not found. Please install Python manually from https://python.org" >> logs/mcp_server_setup.log
            return 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v apt-get >/dev/null 2>&1; then
            echo "Installing Python via apt..." >> logs/mcp_server_setup.log
            sudo apt-get update >> logs/mcp_server_setup.log 2>&1 && sudo apt-get install -y python3 python3-pip python3-venv >> logs/mcp_server_setup.log 2>&1
        elif command -v yum >/dev/null 2>&1; then
            echo "Installing Python via yum..." >> logs/mcp_server_setup.log
            sudo yum install -y python3 python3-pip >> logs/mcp_server_setup.log 2>&1
        elif command -v dnf >/dev/null 2>&1; then
            echo "Installing Python via dnf..." >> logs/mcp_server_setup.log
            sudo dnf install -y python3 python3-pip >> logs/mcp_server_setup.log 2>&1
        else
            echo "Package manager not found. Please install Python manually." >> logs/mcp_server_setup.log
            return 1
        fi
    else
        echo "Unsupported OS. Please install Python manually from https://python.org" >> logs/mcp_server_setup.log
        return 1
    fi

    # Verify installation
    if command -v python3 >/dev/null 2>&1; then
        echo "Python installed successfully: $(python3 --version)" >> logs/mcp_server_setup.log
        return 0
    else
        echo "Python installation failed" >> logs/mcp_server_setup.log
        return 1
    fi
}

# Check and install Python if needed
check_and_install_python
if [ $? -ne 0 ]; then
    echo "Failed to install Python. Exiting." >> logs/mcp_server_setup.log
    exit 1
fi

# Ensure dependencies are installed using pip only
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment and installing dependencies with pip..." >> logs/mcp_server_setup.log
    python3 -m venv .venv >> logs/mcp_server_setup.log 2>&1
    source .venv/bin/activate

    # Install dependencies from requirements.txt
    echo "Upgrading pip..." >> logs/mcp_server_setup.log
    pip install --upgrade pip >> logs/mcp_server_setup.log 2>&1
    echo "Installing dependencies from requirements.txt..." >> logs/mcp_server_setup.log
    pip install -r requirements.txt >> logs/mcp_server_setup.log 2>&1

    # Also install the project in development mode
    echo "Installing project in development mode..." >> logs/mcp_server_setup.log
    pip install -e . >> logs/mcp_server_setup.log 2>&1
else
    # Activate existing virtual environment and ensure dependencies are up to date
    source .venv/bin/activate
    echo "Updating dependencies from requirements.txt with pip..." >> logs/mcp_server_setup.log
    pip install --upgrade pip >> logs/mcp_server_setup.log 2>&1
    pip install -r requirements.txt --upgrade >> logs/mcp_server_setup.log 2>&1
fi

# Check environment variables
echo "" >> logs/mcp_server_setup.log
echo "Checking environment configuration..." >> logs/mcp_server_setup.log
if [ -z "$DCT_API_KEY" ]; then
    echo "WARNING: DCT_API_KEY environment variable not set" >> logs/mcp_server_setup.log
fi
if [ -z "$DCT_BASE_URL" ]; then
    echo "WARNING: DCT_BASE_URL environment variable not set" >> logs/mcp_server_setup.log
fi

# Run the server
echo "" >> logs/mcp_server_setup.log
echo "========================================" >> logs/mcp_server_setup.log
echo "Starting DCT MCP Server with pip..." >> logs/mcp_server_setup.log
echo "========================================" >> logs/mcp_server_setup.log
python3 -m dct_mcp_server.main
