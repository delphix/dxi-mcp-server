@echo off
setlocal enabledelayedexpansion

if not exist "logs" mkdir logs

echo ====================================>>logs\mcp_server_setup.log
echo DCT MCP Server - Windows Startup (UV)>>logs\mcp_server_setup.log
echo ====================================>>logs\mcp_server_setup.log
echo.>>logs\mcp_server_setup.log

:: Navigate to the script directory
cd /d "%~dp0"

:: Set environment variables
set PYTHONPATH=src

:: Step 1: Check if Python exists
echo Checking for Python installation...>>logs\mcp_server_setup.log
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Installing Python using winget...>>logs\mcp_server_setup.log
    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements >>logs\mcp_server_setup.log 2>&1
    if %errorlevel%==1 (
        echo ERROR: Failed to install Python via winget. Please install Python manually.>>logs\mcp_server_setup.log
        echo Download from: https://www.python.org/downloads/>>logs\mcp_server_setup.log
        pause
        goto :exit
    )

    echo Python installation completed. Refreshing environment variables...>>logs\mcp_server_setup.log
    :: Refresh PATH environment variable to include newly installed Python
    for /f "usebackq tokens=2,*" %%A in (`reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH`) do set SysPath=%%B
    for /f "usebackq tokens=2,*" %%A in (`reg query "HKCU\Environment" /v PATH 2^>nul`) do set UserPath=%%B
    if defined UserPath (
        set PATH=%SysPath%;%UserPath%
    ) else (
        set PATH=%SysPath%
    )

    echo Verifying Python installation...>>logs\mcp_server_setup.log
    python --version >nul 2>&1
    if %errorlevel%==1 (
        echo ERROR: Python installation verification failed. Please restart your terminal and try again.>>logs\mcp_server_setup.log
        echo The Python installation may need a terminal restart to update the PATH.>>logs\mcp_server_setup.log
        pause
        goto :exit
    )
    echo Python installed and verified successfully.>>logs\mcp_server_setup.log
)
echo Python found: >>logs\mcp_server_setup.log
python --version >>logs\mcp_server_setup.log 2>&1

:: Step 2: Check if UV exists
echo Checking for UV installation...>>logs\mcp_server_setup.log
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo UV not found. Installing UV using pip...>>logs\mcp_server_setup.log
    pip install uv >>logs\mcp_server_setup.log 2>&1
    if %errorlevel%==1 (
        echo ERROR: Failed to install UV via pip. Please install UV manually.>>logs\mcp_server_setup.log
        echo Install with: pip install uv>>logs\mcp_server_setup.log
        echo Or visit: https://docs.astral.sh/uv/>>logs\mcp_server_setup.log
        pause
        goto :exit
    )
    echo UV installed successfully. Verifying...>>logs\mcp_server_setup.log
    uv --version >nul 2>&1
    if %errorlevel%==1 (
        echo ERROR: UV installation verification failed. Please restart your terminal and try again.>>logs\mcp_server_setup.log
        pause
        goto :exit
    )
)
echo UV found: >>logs\mcp_server_setup.log
uv --version >>logs\mcp_server_setup.log

:: Step 3: Run UV sync
echo Running uv sync...>>logs\mcp_server_setup.log
uv sync >>logs\mcp_server_setup.log 2>&1
if %errorlevel%==1 (
    echo ERROR: uv sync failed. Check the log file for details.>>logs\mcp_server_setup.log
    pause
    goto :exit
)
echo UV sync completed successfully.>>logs\mcp_server_setup.log

:: Step 4: Check environment variables
echo.>>logs\mcp_server_setup.log
echo Checking environment configuration...>>logs\mcp_server_setup.log
if "%DCT_API_KEY%"=="" (
    echo WARNING: DCT_API_KEY environment variable not set>>logs\mcp_server_setup.log
)
if "%DCT_BASE_URL%"=="" (
    echo WARNING: DCT_BASE_URL environment variable not set>>logs\mcp_server_setup.log
)

:: Step 5: Start the MCP server
echo.>>logs\mcp_server_setup.log
echo ====================================>>logs\mcp_server_setup.log
echo Starting DCT MCP Server...>>logs\mcp_server_setup.log
echo ====================================>>logs\mcp_server_setup.log
echo.>>logs\mcp_server_setup.log

uv run python -m dct_mcp_server.main

:exit
exit /b