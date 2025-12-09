#!/bin/bash

# Navigate to the project directory
cd "$(dirname "$0")"

# Create logs directory if it doesn't exist
mkdir -p logs

# Set environment variables from .env file or system environment
# Note: Set DCT_API_KEY, DCT_BASE_URL, DCT_VERIFY_SSL, DCT_LOG_LEVEL in your environment
export PYTHONPATH=src

echo "DCT MCP Server - Unix/Mac Startup (UV)" >> logs/mcp_server_setup.log
echo "=======================================" >> logs/mcp_server_setup.log

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

# Function to check if uv is installed
check_uv_installation() {
    if command -v uv >/dev/null 2>&1; then
        echo "uv is installed: $(uv --version)" >> logs/mcp_server_setup.log
        return 0
    else
        return 1
    fi
}

# Function to install uv
install_uv() {
    echo "Installing uv (fast Python package installer)..." >> logs/mcp_server_setup.log

    # Try installing via pip first
    if python3 -m pip install uv >> logs/mcp_server_setup.log 2>&1; then
        echo "uv installed successfully via pip." >> logs/mcp_server_setup.log
        return 0
    fi

    # Fallback: try via curl
    echo "Trying alternative uv installation method..." >> logs/mcp_server_setup.log
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh >> logs/mcp_server_setup.log 2>&1
        # Source the shell configuration to update PATH
        export PATH="$HOME/.cargo/bin:$PATH"
        if check_uv_installation; then
            echo "uv installed successfully." >> logs/mcp_server_setup.log
            return 0
        fi
    fi

    echo "Failed to install uv. Please install manually or use pip version." >> logs/mcp_server_setup.log
    return 1
}

# Check and install Python if needed
check_and_install_python
if [ $? -ne 0 ]; then
    echo "Failed to install Python. Exiting." >> logs/mcp_server_setup.log
    exit 1
fi

# Check if uv is installed, install if needed
if ! check_uv_installation; then
    echo "uv not found. Installing uv..." >> logs/mcp_server_setup.log
    if ! install_uv; then
        echo "Failed to install uv. Please install manually or use start_mcp_server_python.sh for pip-based installation." >> logs/mcp_server_setup.log
        exit 1
    fi
fi

echo "Using uv for dependency management." >> logs/mcp_server_setup.log

# Check if pyproject.toml exists for uv sync, otherwise use requirements.txt
if [ -f "pyproject.toml" ]; then
    echo "Found pyproject.toml, using uv sync..." >> logs/mcp_server_setup.log

    if [ ! -d ".venv" ]; then
        echo "Creating virtual environment and syncing dependencies with uv..." >> logs/mcp_server_setup.log
        uv sync >> logs/mcp_server_setup.log 2>&1
    else
        echo "Virtual environment exists, syncing dependencies with uv..." >> logs/mcp_server_setup.log
        uv sync >> logs/mcp_server_setup.log 2>&1
    fi
else
    echo "pyproject.toml not found, checking for requirements.txt..." >> logs/mcp_server_setup.log

    if [ ! -f "requirements.txt" ]; then
        echo "ERROR: Neither pyproject.toml nor requirements.txt found." >> logs/mcp_server_setup.log
        echo "Please create one of these files in the project root directory:" >> logs/mcp_server_setup.log
        echo "  - For uv sync: create pyproject.toml with dependencies" >> logs/mcp_server_setup.log
        echo "  - For uv pip install: create requirements.txt with dependencies" >> logs/mcp_server_setup.log
        exit 1
    fi

    echo "Found requirements.txt, using uv pip install..." >> logs/mcp_server_setup.log

    # Create virtual environment if it doesn't exist
    if [ ! -d ".venv" ]; then
        echo "Creating virtual environment with uv..." >> logs/mcp_server_setup.log
        uv venv .venv >> logs/mcp_server_setup.log 2>&1
        if [ $? -ne 0 ]; then
            echo "Failed to create virtual environment with uv. Falling back to python..." >> logs/mcp_server_setup.log
            python3 -m venv .venv >> logs/mcp_server_setup.log 2>&1
        fi
    fi

    # Activate virtual environment
    source .venv/bin/activate

    # Install dependencies using uv pip
    echo "Installing dependencies using uv pip..." >> logs/mcp_server_setup.log
    uv pip install -r requirements.txt >> logs/mcp_server_setup.log 2>&1
    if [ $? -ne 0 ]; then
        echo "Failed to install dependencies with uv. Trying pip as fallback..." >> logs/mcp_server_setup.log
        pip install --upgrade pip >> logs/mcp_server_setup.log 2>&1
        pip install -r requirements.txt >> logs/mcp_server_setup.log 2>&1
        if [ $? -ne 0 ]; then
            echo "Failed to install dependencies with both uv and pip." >> logs/mcp_server_setup.log
            exit 1
        fi
    fi

    # Install project in development mode
    echo "Installing project in development mode..." >> logs/mcp_server_setup.log
    uv pip install -e . >> logs/mcp_server_setup.log 2>&1
    if [ $? -ne 0 ]; then
        echo "Failed to install project with uv. Trying pip as fallback..." >> logs/mcp_server_setup.log
        pip install -e . >> logs/mcp_server_setup.log 2>&1
        if [ $? -ne 0 ]; then
            echo "Failed to install project." >> logs/mcp_server_setup.log
            exit 1
        fi
    fi
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
echo "Starting DCT MCP Server with uv..." >> logs/mcp_server_setup.log
echo "========================================" >> logs/mcp_server_setup.log
echo "" >> logs/mcp_server_setup.log

# Ensure we're using the virtual environment
if [ -d ".venv" ]; then
    exec .venv/bin/python -m dct_mcp_server.main
else
    # For uv sync, the environment is managed by uv
    exec uv run python -m dct_mcp_server.main
fi
