#!/bin/bash

# Navigate to the project directory
cd "$(dirname "$0")"

# Set environment variables from .env file or system environment
# Note: Set DCT_API_KEY, DCT_BASE_URL, DCT_VERIFY_SSL, DCT_LOG_LEVEL in your environment
export PYTHONPATH=src

echo "DCT MCP Server - Unix/Mac Startup (PIP)" >> mcp_server_setup_logfile.txt
echo "========================================" >> mcp_server_setup_logfile.txt

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

# Check and install Python if needed
check_and_install_python
if [ $? -ne 0 ]; then
    echo "Failed to install Python. Exiting." >> mcp_server_setup_logfile.txt
    exit 1
fi

# Ensure dependencies are installed using pip only
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment and installing dependencies with pip..." >> mcp_server_setup_logfile.txt
    python3 -m venv .venv >> mcp_server_setup_logfile.txt 2>&1
    source .venv/bin/activate

    # Install dependencies from requirements.txt
    echo "Upgrading pip..." >> mcp_server_setup_logfile.txt
    pip install --upgrade pip >> mcp_server_setup_logfile.txt 2>&1
    echo "Installing dependencies from requirements.txt..." >> mcp_server_setup_logfile.txt
    pip install -r requirements.txt >> mcp_server_setup_logfile.txt 2>&1

    # Also install the project in development mode
    echo "Installing project in development mode..." >> mcp_server_setup_logfile.txt
    pip install -e . >> mcp_server_setup_logfile.txt 2>&1
else
    # Activate existing virtual environment and ensure dependencies are up to date
    source .venv/bin/activate
    echo "Updating dependencies from requirements.txt with pip..." >> mcp_server_setup_logfile.txt
    pip install --upgrade pip >> mcp_server_setup_logfile.txt 2>&1
    pip install -r requirements.txt --upgrade >> mcp_server_setup_logfile.txt 2>&1
fi

# Check environment variables
echo "Checking environment configuration..." >> mcp_server_setup_logfile.txt
if [ -z "$DCT_API_KEY" ]; then
    echo "WARNING: DCT_API_KEY environment variable not set" >> mcp_server_setup_logfile.txt
fi
if [ -z "$DCT_BASE_URL" ]; then
    echo "WARNING: DCT_BASE_URL environment variable not set" >> mcp_server_setup_logfile.txt
fi

# Run the server
echo "Starting MCP server..." >> mcp_server_setup_logfile.txt
exec .venv/bin/python -m dct_mcp_server.main
    echo "Creating virtual environment and installing dependencies..." >> mcp_server_setup_logfile.txt
    python3 -m venv .venv
    source .venv/bin/activate
    pip install .
fi

# Use the virtual environment directly
# Check for USE_PIP_DEPENDENCIES environment variable
if [ "${USE_PIP_DEPENDENCIES}" = "true" ]; then
    echo "USE_PIP_DEPENDENCIES is set to true, using pip for dependency management..." >> mcp_server_setup_logfile.txt
    if [ ! -d ".venv" ]; then
        echo "Creating virtual environment..." >> mcp_server_setup_logfile.txt
        python3 -m venv .venv
        source .venv/bin/activate
        pip install -r requirements.txt
        pip install -e .
    else
        source .venv/bin/activate
        pip install -r requirements.txt --upgrade
    fi
else
    echo "USE_PIP_DEPENDENCIES not set to true, using uv sync for dependency management..." >> mcp_server_setup_logfile.txt
    if [ ! -d ".venv" ]; then
        echo "Creating virtual environment..." >> mcp_server_setup_logfile.txt
        # Check if pyproject.toml exists for uv sync
        if [ -f "pyproject.toml" ]; then
            echo "Using uv sync for dependency management..." >> mcp_server_setup_logfile.txt
            # Install uv if not available
            if ! command -v uv >/dev/null 2>&1; then
                echo "Installing uv..." >> mcp_server_setup_logfile.txt
                python3 -m pip install uv
            fi
            uv sync
        else
            echo "pyproject.toml not found, falling back to pip..." >> mcp_server_setup_logfile.txt
            python3 -m venv .venv
            source .venv/bin/activate
            pip install -r requirements.txt
            pip install -e .
        fi
    else
        # Check if pyproject.toml exists for uv sync
        if [ -f "pyproject.toml" ]; then
            echo "Using uv sync for dependency management..." >> mcp_server_setup_logfile.txt
            # Install uv if not available
            if ! command -v uv >/dev/null 2>&1; then
                echo "Installing uv..." >> mcp_server_setup_logfile.txt
                source .venv/bin/activate
                pip install uv
            fi
            uv sync
        else
            echo "pyproject.toml not found, falling back to pip..." >> mcp_server_setup_logfile.txt
            source .venv/bin/activate
            pip install -r requirements.txt --upgrade
        fi
    fi
fi

# Run the server
echo "Starting MCP server..." >> mcp_server_setup_logfile.txt
exec .venv/bin/python -m dct_mcp_server.main
