@echo off
setlocal enabledelayedexpansion

if not exist "logs" mkdir logs

echo ====================================>>logs\mcp_server_setup.log
echo DCT MCP Server - Windows Startup>>logs\mcp_server_setup.log
echo ====================================>>logs\mcp_server_setup.log
echo.>>logs\mcp_server_setup.log

:: Navigate to the script directory
cd /d "%~dp0"

set flag_python=0
:test_python_install

python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Installing Python using winget...>>logs\mcp_server_setup.log
    winget install Python.Python.3.12 --location "%LocalAppData%\Programs\Python\Python312" --silent --accept-package-agreements --accept-source-agreements
    set PYTHON_DIR="%LocalAppData%\Programs\Python\Python312"
    set "PATH=%LocalAppData%\Programs\Python\Python312;%LocalAppData%\Programs\Python\Python312\Scripts;%PATH%"
    python --version > nul 2>&1
    if %errorlevel% neq 0 (
        if flag_python==1 (
            echo Failed to install Python via winget after retry. Please install Python manually.>>logs\mcp_server_setup.log
            echo Download from: https://www.python.org/downloads/>>logs\mcp_server_setup.log
            pause
            goto :exit
        )
        set /a flag_python=1
        goto :test_python_install
    )
) else (
    echo Python installed and verified successfully.>>logs\mcp_server_setup.log
)

:: Step 2: Install dependencies
set flag_deps=0
:setup_dependencies
echo Installing Python dependencies...>>logs\mcp_server_setup.log
pip install -r requirements.txt >>logs\mcp_server_setup.log 2>&1
if %errorlevel% neq 0 (
    if flag_deps==1 (
        echo Failed to install dependencies after retry. Please check requirements.txt and install manually.>>logs\mcp_server_setup.log
        pause
        goto :exit
    )
    set /a flag_deps=1
    goto :setup_dependencies
) else (
    echo Dependencies installed successfully.>>logs\mcp_server_setup.log

    :: Check environment variables
    if "%DCT_API_KEY%"=="" (
        echo WARNING: DCT_API_KEY environment variable not set>>logs\mcp_server_setup.log
    )
    if "%DCT_BASE_URL%"=="" (
        echo WARNING: DCT_BASE_URL environment variable not set>>logs\mcp_server_setup.log
    )

    :: Run the server (stdout goes to MCP client, all logging goes to logs\mcp_server_setup.log)
    echo.>>logs\mcp_server_setup.log
    echo ====================================>>logs\mcp_server_setup.log
    echo Starting DCT MCP Server...>>logs\mcp_server_setup.log
    echo ====================================>>logs\mcp_server_setup.log
    echo.>>logs\mcp_server_setup.log
    cd src
    python -m dct_mcp_server.main
    if %errorlevel% neq 0 (
        echo Python server command failed unexpectedly.>>logs\mcp_server_setup.log
        pause
        goto :exit
    )
)

:exit
endlocal