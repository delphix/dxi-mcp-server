@echo off
setlocal enabledelayedexpansion

echo ====================================>>mcp_server_setup_logfile.txt
echo DCT MCP Server - Windows Startup (UV)>>mcp_server_setup_logfile.txt
echo ====================================>>mcp_server_setup_logfile.txt
echo.>>mcp_server_setup_logfile.txt

:: Navigate to the script directory
cd /d "%~dp0"

:: Set environment variables
set PYTHONPATH=src

:: Step 1: Check if Python exists
echo Checking for Python installation...>>mcp_server_setup_logfile.txt
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Installing Python using winget...>>mcp_server_setup_logfile.txt
    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements >>mcp_server_setup_logfile.txt 2>&1
    if %errorlevel%==1 (
        echo ERROR: Failed to install Python via winget. Please install Python manually.>>mcp_server_setup_logfile.txt
        echo Download from: https://www.python.org/downloads/>>mcp_server_setup_logfile.txt
        pause
        goto :exit
    )

    echo Python installation completed. Refreshing environment variables...>>mcp_server_setup_logfile.txt
    :: Refresh PATH environment variable to include newly installed Python
    for /f "usebackq tokens=2,*" %%A in (`reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH`) do set SysPath=%%B
    for /f "usebackq tokens=2,*" %%A in (`reg query "HKCU\Environment" /v PATH 2^>nul`) do set UserPath=%%B
    if defined UserPath (
        set PATH=%SysPath%;%UserPath%
    ) else (
        set PATH=%SysPath%
    )

    echo Verifying Python installation...>>mcp_server_setup_logfile.txt
    python --version >nul 2>&1
    if %errorlevel%==1 (
        echo ERROR: Python installation verification failed. Please restart your terminal and try again.>>mcp_server_setup_logfile.txt
        echo The Python installation may need a terminal restart to update the PATH.>>mcp_server_setup_logfile.txt
        pause
        goto :exit
    )
    echo Python installed and verified successfully.>>mcp_server_setup_logfile.txt
)
echo Python found: >>mcp_server_setup_logfile.txt
python --version >>mcp_server_setup_logfile.txt 2>&1

:: Step 2: Check if UV exists
echo Checking for UV installation...>>mcp_server_setup_logfile.txt
uv --version >nul 2>&1
if %errorlevel% neq 1 (
    echo UV not found. Installing UV using pip...>>mcp_server_setup_logfile.txt
    pip install uv >>mcp_server_setup_logfile.txt 2>&1
    if %errorlevel%==1 (
        echo ERROR: Failed to install UV via pip. Please install UV manually.>>mcp_server_setup_logfile.txt
        echo Install with: pip install uv>>mcp_server_setup_logfile.txt
        echo Or visit: https://docs.astral.sh/uv/>>mcp_server_setup_logfile.txt
        pause
        goto :exit
    )
    echo UV installed successfully. Verifying...>>mcp_server_setup_logfile.txt
    uv --version >nul 2>&1
    if %errorlevel%==1 (
        echo ERROR: UV installation verification failed. Please restart your terminal and try again.>>mcp_server_setup_logfile.txt
        pause
        goto :exit
    )
)
echo UV found: >>mcp_server_setup_logfile.txt
uv --version >>mcp_server_setup_logfile.txt

:: Step 3: Run UV sync
echo Running uv sync...>>mcp_server_setup_logfile.txt
uv sync >>mcp_server_setup_logfile.txt 2>&1
if %errorlevel%==1 (
    echo ERROR: uv sync failed. Check the log file for details.>>mcp_server_setup_logfile.txt
    pause
    goto :exit
)
echo UV sync completed successfully.>>mcp_server_setup_logfile.txt

:: Step 4: Check environment variables
echo.>>mcp_server_setup_logfile.txt
echo Checking environment configuration...>>mcp_server_setup_logfile.txt
if "%DCT_API_KEY%"=="" (
    echo WARNING: DCT_API_KEY environment variable not set>>mcp_server_setup_logfile.txt
)
if "%DCT_BASE_URL%"=="" (
    echo WARNING: DCT_BASE_URL environment variable not set>>mcp_server_setup_logfile.txt
)

:: Step 5: Start the MCP server
echo.>>mcp_server_setup_logfile.txt
echo ====================================>>mcp_server_setup_logfile.txt
echo Starting DCT MCP Server...>>mcp_server_setup_logfile.txt
echo ====================================>>mcp_server_setup_logfile.txt
echo.>>mcp_server_setup_logfile.txt

.venv\Scripts\python.exe -m dct_mcp_server.main

:exit
exit /b