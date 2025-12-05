#!/bin/bash

# Navigate to the project directory
cd "$(dirname "$0")"

# Set environment variables from .env file or system environment
# Note: Set DCT_API_KEY, DCT_BASE_URL, DCT_VERIFY_SSL, DCT_LOG_LEVEL in your environment
export PYTHONPATH=src

echo "DCT MCP Server - Unix/Mac Startup (UV)" >> mcp_server_setup_logfile.txt
echo "=======================================" >> mcp_server_setup_logfile.txt

# Function to check if Python is installed and install if missing
check_and_install_python() {
    if command -v python3 >/dev/null 2>&1; then
        echo "Python3 is installed: $(python3 --version)" >> mcp_server_setup_logfile.txt
        return 0
    elif command -v python >/dev/null 2>&1; then
        echo "Python is installed: $(python --version)" >> mcp_server_setup_logfile.txt
        # Create alias for consistency
        alias python3=python
        return 0
    else
        echo "Python not found. Attempting to install..." >> mcp_server_setup_logfile.txt
        install_python
        return $?
    fi
}

# Function to install Python on different systems
install_python() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew >/dev/null 2>&1; then
            echo "Installing Python via Homebrew..." >> mcp_server_setup_logfile.txt
            brew install python3 >> mcp_server_setup_logfile.txt 2>&1
        else
            echo "Homebrew not found. Please install Python manually from https://python.org" >> mcp_server_setup_logfile.txt
            return 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v apt-get >/dev/null 2>&1; then
            echo "Installing Python via apt..." >> mcp_server_setup_logfile.txt
            sudo apt-get update >> mcp_server_setup_logfile.txt 2>&1 && sudo apt-get install -y python3 python3-pip python3-venv >> mcp_server_setup_logfile.txt 2>&1
        elif command -v yum >/dev/null 2>&1; then
            echo "Installing Python via yum..." >> mcp_server_setup_logfile.txt
            sudo yum install -y python3 python3-pip >> mcp_server_setup_logfile.txt 2>&1
        elif command -v dnf >/dev/null 2>&1; then
            echo "Installing Python via dnf..." >> mcp_server_setup_logfile.txt
            sudo dnf install -y python3 python3-pip >> mcp_server_setup_logfile.txt 2>&1
        else
            echo "Package manager not found. Please install Python manually." >> mcp_server_setup_logfile.txt
            return 1
        fi
    else
        echo "Unsupported OS. Please install Python manually from https://python.org" >> mcp_server_setup_logfile.txt
        return 1
    fi

    # Verify installation
    if command -v python3 >/dev/null 2>&1; then
        echo "Python installed successfully: $(python3 --version)" >> mcp_server_setup_logfile.txt
        return 0
    else
        echo "Python installation failed" >> mcp_server_setup_logfile.txt
        return 1
    fi
}

# Function to check if uv is installed
check_uv_installation() {
    if command -v uv >/dev/null 2>&1; then
        echo "uv is installed: $(uv --version)" >> mcp_server_setup_logfile.txt
        return 0
    else
        return 1
    fi
}

# Function to install uv
install_uv() {
    echo "Installing uv (fast Python package installer)..." >> mcp_server_setup_logfile.txt

    # Try installing via pip first
    if python3 -m pip install uv >> mcp_server_setup_logfile.txt 2>&1; then
        echo "uv installed successfully via pip." >> mcp_server_setup_logfile.txt
        return 0
    fi

    # Fallback: try via curl
    echo "Trying alternative uv installation method..." >> mcp_server_setup_logfile.txt
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh >> mcp_server_setup_logfile.txt 2>&1
        # Source the shell configuration to update PATH
        export PATH="$HOME/.cargo/bin:$PATH"
        if check_uv_installation; then
            echo "uv installed successfully." >> mcp_server_setup_logfile.txt
            return 0
        fi
    fi

    echo "Failed to install uv. Please install manually or use pip version." >> mcp_server_setup_logfile.txt
    return 1
}

# Check and install Python if needed
check_and_install_python
if [ $? -ne 0 ]; then
    echo "Failed to install Python. Exiting." >> mcp_server_setup_logfile.txt
    exit 1
fi

# Check if uv is installed, install if needed
if ! check_uv_installation; then
    echo "uv not found. Installing uv..." >> mcp_server_setup_logfile.txt
    if ! install_uv; then
        echo "Failed to install uv. Please install manually or use start_mcp_server_python.sh for pip-based installation." >> mcp_server_setup_logfile.txt
        exit 1
    fi
fi

echo "Using uv for dependency management." >> mcp_server_setup_logfile.txt

# Check if pyproject.toml exists for uv sync, otherwise use requirements.txt
if [ -f "pyproject.toml" ]; then
    echo "Found pyproject.toml, using uv sync..." >> mcp_server_setup_logfile.txt

    if [ ! -d ".venv" ]; then
        echo "Creating virtual environment and syncing dependencies with uv..." >> mcp_server_setup_logfile.txt
        uv sync >> mcp_server_setup_logfile.txt 2>&1
    else
        echo "Virtual environment exists, syncing dependencies with uv..." >> mcp_server_setup_logfile.txt
        uv sync >> mcp_server_setup_logfile.txt 2>&1
    fi
else
    echo "pyproject.toml not found, checking for requirements.txt..." >> mcp_server_setup_logfile.txt

    if [ ! -f "requirements.txt" ]; then
        echo "ERROR: Neither pyproject.toml nor requirements.txt found." >> mcp_server_setup_logfile.txt
        echo "Please create one of these files in the project root directory:" >> mcp_server_setup_logfile.txt
        echo "  - For uv sync: create pyproject.toml with dependencies" >> mcp_server_setup_logfile.txt
        echo "  - For uv pip install: create requirements.txt with dependencies" >> mcp_server_setup_logfile.txt
        exit 1
    fi

    echo "Found requirements.txt, using uv pip install..." >> mcp_server_setup_logfile.txt

    # Create virtual environment if it doesn't exist
    if [ ! -d ".venv" ]; then
        echo "Creating virtual environment with uv..." >> mcp_server_setup_logfile.txt
        uv venv .venv >> mcp_server_setup_logfile.txt 2>&1
        if [ $? -ne 0 ]; then
            echo "Failed to create virtual environment with uv. Falling back to python..." >> mcp_server_setup_logfile.txt
            python3 -m venv .venv >> mcp_server_setup_logfile.txt 2>&1
        fi
    fi

    # Activate virtual environment
    source .venv/bin/activate

    # Install dependencies using uv pip
    echo "Installing dependencies using uv pip..." >> mcp_server_setup_logfile.txt
    uv pip install -r requirements.txt >> mcp_server_setup_logfile.txt 2>&1
    if [ $? -ne 0 ]; then
        echo "Failed to install dependencies with uv. Trying pip as fallback..." >> mcp_server_setup_logfile.txt
        pip install --upgrade pip >> mcp_server_setup_logfile.txt 2>&1
        pip install -r requirements.txt >> mcp_server_setup_logfile.txt 2>&1
        if [ $? -ne 0 ]; then
            echo "Failed to install dependencies with both uv and pip." >> mcp_server_setup_logfile.txt
            exit 1
        fi
    fi

    # Install project in development mode
    echo "Installing project in development mode..." >> mcp_server_setup_logfile.txt
    uv pip install -e . >> mcp_server_setup_logfile.txt 2>&1
    if [ $? -ne 0 ]; then
        echo "Failed to install project with uv. Trying pip as fallback..." >> mcp_server_setup_logfile.txt
        pip install -e . >> mcp_server_setup_logfile.txt 2>&1
        if [ $? -ne 0 ]; then
            echo "Failed to install project." >> mcp_server_setup_logfile.txt
            exit 1
        fi
    fi
fi

# Check environment variables
echo "" >> mcp_server_setup_logfile.txt
echo "Checking environment configuration..." >> mcp_server_setup_logfile.txt
if [ -z "$DCT_API_KEY" ]; then
    echo "WARNING: DCT_API_KEY environment variable not set" >> mcp_server_setup_logfile.txt
fi
if [ -z "$DCT_BASE_URL" ]; then
    echo "WARNING: DCT_BASE_URL environment variable not set" >> mcp_server_setup_logfile.txt
fi

# Run the server
echo "" >> mcp_server_setup_logfile.txt
echo "========================================" >> mcp_server_setup_logfile.txt
echo "Starting DCT MCP Server with uv..." >> mcp_server_setup_logfile.txt
echo "========================================" >> mcp_server_setup_logfile.txt
echo "" >> mcp_server_setup_logfile.txt

# Ensure we're using the virtual environment
if [ -d ".venv" ]; then
    exec .venv/bin/python -m dct_mcp_server.main
else
    # For uv sync, the environment is managed by uv
    exec uv run python -m dct_mcp_server.main
fi
