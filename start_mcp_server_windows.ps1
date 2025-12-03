# DCT MCP Server - Windows PowerShell Startup Script
# Run this script as: powershell -ExecutionPolicy Bypass -File start_mcp_server_windows.ps1
# Note: All output redirected to logfile.txt to maintain MCP protocol compatibility

"====================================" | Out-File -FilePath "logfile.txt" -Encoding UTF8
"DCT MCP Server - Windows Startup" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
"====================================" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append

# Navigate to script directory
Set-Location $PSScriptRoot

# Set environment variables
$env:PYTHONPATH = "src"

# Function to check if uv is installed
function Test-UvInstallation {
    try {
        $uvVersion = & uv --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            "uv is installed: $uvVersion" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            return $true
        }
    }
    catch {
        return $false
    }
    return $false
}

# Function to install uv
function Install-Uv {
    "Installing uv (fast Python package installer)..." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append

    try {
        # Try installing via pip first
        & pip install uv *>&1 | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        if ($LASTEXITCODE -eq 0) {
            "uv installed successfully via pip." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            return $true
        }

        # Fallback: try via PowerShell script
        "Trying alternative uv installation method..." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression *>&1 | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append

        # Check if uv is now available
        if (Test-UvInstallation) {
            "uv installed successfully." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            return $true
        }
    }
    catch {
        "Failed to install uv: $($_.Exception.Message)" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        return $false
    }
    return $false
}

# Function to get user's package manager preference
function Get-PackageManagerChoice {
    "" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
    "Choose package manager for dependency installation:" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
    "1. uv (faster, modern Python package manager)" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
    "2. pip (traditional Python package manager)" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
    "" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append

    while ($true) {
        $choice = Read-Host "Enter your choice (1 for uv, 2 for pip)"
        if ($choice -eq "1") {
            return "uv"
        } elseif ($choice -eq "2") {
            return "pip"
        } else {
            "Invalid choice. Please enter 1 or 2." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        }
    }
}

# Function to create virtual environment with chosen package manager
function New-VirtualEnvironment($packageManager) {
    if ($packageManager -eq "uv") {
        "Creating virtual environment with uv..." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        & uv venv .venv *>&1 | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create virtual environment with uv"
        }

        # Activate the virtual environment
        & .\.venv\Scripts\Activate.ps1

        # Install dependencies
        "Installing dependencies with uv..." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        & uv pip install -r requirements.txt *>&1 | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        if ($LASTEXITCODE -ne 0) {
            "Failed to install dependencies with uv. Trying pip as fallback..." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            & pip install -r requirements.txt *>&1 | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to install dependencies with both uv and pip"
            }
        }
    } else {
        "Creating virtual environment with pip..." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        & python -m venv .venv *>&1 | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create virtual environment with pip"
        }

        # Activate the virtual environment
        & .\.venv\Scripts\Activate.ps1

        # Upgrade pip first
        "Upgrading pip..." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        & pip install --upgrade pip *>&1 | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append

        # Install dependencies
        "Installing dependencies with pip..." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        & pip install -r requirements.txt *>&1 | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        if ($LASTEXITCODE -ne 0) {
            "Failed to install dependencies. This might be due to missing Visual C++ Build Tools." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            "" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            "To fix this issue:" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            "1. Install Microsoft Visual C++ Build Tools from:" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            "   https://visualstudio.microsoft.com/visual-cpp-build-tools/" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            "2. Or try installing dependencies one by one to identify the problematic package" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            "" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            $response = Read-Host "Do you want to try installing dependencies without build requirements? (y/N)"
            if ($response.ToLower() -eq 'y') {
                "Trying alternative installation method..." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
                & pip install --only-binary=all -r requirements.txt *>&1 | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
                if ($LASTEXITCODE -ne 0) {
                    throw "Failed to install dependencies even with binary-only installation"
                }
            } else {
                throw "Failed to install dependencies"
            }
        }
    }

    # Install project in development mode
    "Installing project in development mode..." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
    if ($packageManager -eq "uv") {
        & uv pip install -e . *>&1 | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
    } else {
        & pip install -e . *>&1 | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install project in development mode"
    }
}

# Function to update existing virtual environment
function Update-VirtualEnvironment($packageManager) {
    "Activating existing virtual environment..." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
    & .\.venv\Scripts\Activate.ps1

    if ($packageManager -eq "uv") {
        "Updating dependencies with uv..." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        & uv pip install -r requirements.txt --upgrade *>&1 | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        if ($LASTEXITCODE -ne 0) {
            "Failed to update with uv. Trying pip as fallback..." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            & pip install -r requirements.txt --upgrade *>&1 | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        }
    } else {
        "Upgrading pip..." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        & pip install --upgrade pip *>&1 | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append

        "Updating dependencies with pip..." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        & pip install -r requirements.txt --upgrade *>&1 | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        if ($LASTEXITCODE -ne 0) {
            "Failed to update dependencies. This might be due to missing Visual C++ Build Tools." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            "" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            "To fix this issue:" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            "1. Install Microsoft Visual C++ Build Tools from:" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            "   https://visualstudio.microsoft.com/visual-cpp-build-tools/" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            "" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            $response = Read-Host "Do you want to try updating with binary-only packages? (y/N)"
            if ($response.ToLower() -eq 'y') {
                "Trying alternative update method..." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
                & pip install --only-binary=all -r requirements.txt --upgrade *>&1 | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
                if ($LASTEXITCODE -ne 0) {
                    "Warning: Some dependencies may not have been updated due to build requirements." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
                    "The server may still work with existing packages." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
                }
            } else {
                "Warning: Dependencies may be outdated, but will continue with existing packages." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            }
        }
    }
}

# Function to check if Python is installed
function Test-PythonInstallation {
    try {
        $pythonVersion = & python --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            "Python is installed: $pythonVersion" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            return $true
        }
    }
    catch {
        "Python not found." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        return $false
    }
    return $false
}

# Function to install Python using winget
function Install-PythonWinget {
    "Installing Python using winget (Windows Package Manager)..." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append

    try {
        & winget install Python.Python.3.12 --silent *>&1 | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        if ($LASTEXITCODE -eq 0) {
            "Python installed successfully via winget." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            # Refresh environment variables
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
            return $true
        }
    }
    catch {
        "Failed to install Python via winget." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        return $false
    }
    return $false
}

# Function to install Python using Chocolatey
function Install-PythonChocolatey {
    "Trying to install Python via Chocolatey..." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append

    try {
        & choco --version 2>$null
        if ($LASTEXITCODE -ne 0) {
            "Chocolatey not found. Please install Python manually from https://python.org" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            return $false
        }

        & choco install python -y *>&1 | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        if ($LASTEXITCODE -eq 0) {
            "Python installed successfully via Chocolatey." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            # Refresh environment variables
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
            return $true
        }
    }
    catch {
        "Failed to install Python via Chocolatey." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
        return $false
    }
    return $false
}

# Function to create requirements.txt
function New-RequirementsFile {
    if (!(Test-Path "requirements.txt")) {
        "Creating requirements.txt with project dependencies..." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append

        $requirements = @"
# Core MCP Framework (using fastmcp, not standard mcp)
fastmcp>=2.13.2

# HTTP Client for API requests
httpx>=0.24.0

# YAML processing for API specs (used in toolsgenerator/driver.py)
pyyaml>=6.0

# HTTP requests (for synchronous operations and SSL cert download)
requests>=2.28.0

# URL handling and SSL
urllib3>=1.26.0
certifi>=2022.12.7

# Environment variable handling
python-dotenv>=1.0.0

# JSON schema validation (if needed by MCP framework)
pydantic>=2.0.0

# Async utilities (required by fastmcp)
anyio>=3.6.0

# Additional utilities that might be needed
typing-extensions>=4.0.0

# Optional: Development dependencies (uncomment if needed)
# pytest>=7.0.0
# pytest-asyncio>=0.21.0
# black>=22.0.0
# flake8>=5.0.0
"@

        $requirements | Out-File -FilePath "requirements.txt" -Encoding UTF8
        "requirements.txt created successfully." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
    }
}

# Main execution
try {
    # Check if Python is installed
    if (!(Test-PythonInstallation)) {
        "Attempting to install Python..." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append

        if (!(Install-PythonWinget)) {
            if (!(Install-PythonChocolatey)) {
                "Failed to install Python automatically. Please install manually from https://python.org" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
                Read-Host "Press Enter to exit"
                exit 1
            }
        }

        # Verify installation
        if (!(Test-PythonInstallation)) {
            "Python installation verification failed. Please restart your terminal and try again." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            Read-Host "Press Enter to exit"
            exit 1
        }
    }

    # Create requirements.txt if needed
    New-RequirementsFile

    # Get user's package manager preference
    $packageManager = Get-PackageManagerChoice

    # If user chose uv, make sure it's installed
    if ($packageManager -eq "uv") {
        if (!(Test-UvInstallation)) {
            "uv is not installed. Installing it now..." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
            if (!(Install-Uv)) {
                "Failed to install uv. Falling back to pip." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
                $packageManager = "pip"
            }
        }
    }

    "Using $packageManager for package management." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append

    # Check if virtual environment exists
    if (!(Test-Path ".venv")) {
        New-VirtualEnvironment $packageManager
    }
    else {
        Update-VirtualEnvironment $packageManager
    }

    # Check environment variables
    "" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
    "Checking environment configuration..." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
    if (!$env:DCT_API_KEY) {
        "WARNING: DCT_API_KEY environment variable not set" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
    }
    if (!$env:DCT_BASE_URL) {
        "WARNING: DCT_BASE_URL environment variable not set" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
    }

    # Run the MCP server
    "" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
    "====================================" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
    "Starting DCT MCP Server..." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
    "====================================" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
    "" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append

    & .\.venv\Scripts\python.exe -m dct_mcp_server.main

    # If we get here, the server stopped
    "" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
    "Server stopped." | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
    Read-Host "Press Enter to exit"
}
catch {
    "Error: $($_.Exception.Message)" | Out-File -FilePath "logfile.txt" -Encoding UTF8 -Append
    Read-Host "Press Enter to exit"
    exit 1
}