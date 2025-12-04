@echo off
setlocal enabledelayedexpansion

echo ====================================>>mcp_server_setup_logfile.txt
echo DCT MCP Server - Windows Startup>>mcp_server_setup_logfile.txt
echo ====================================>>mcp_server_setup_logfile.txt
echo.>>mcp_server_setup_logfile.txt

:: Navigate to the script directory
cd /d "%~dp0"

:: Set environment variables
set PYTHONPATH=src

:: Quick Python check first
echo Checking for Python installation...>>mcp_server_setup_logfile.txt
python --version >nul 2>&1
if %errorlevel% == 0 (
    echo Python is already installed.>>mcp_server_setup_logfile.txt
    python --version >>mcp_server_setup_logfile.txt 2>&1
    goto :setup_venv
)

goto :run_powershell

:run_powershell
echo.>>mcp_server_setup_logfile.txt
echo Running PowerShell installation script...>>mcp_server_setup_logfile.txt
echo If this hangs, press Ctrl+C and run this script again, then choose option 2.>>mcp_server_setup_logfile.txt
echo.>>mcp_server_setup_logfile.txt
powershell -ExecutionPolicy Bypass -File "%~dp0start_mcp_server_windows.ps1" >>mcp_server_setup_logfile.txt 2>&1
goto :end

:manual_install
echo.>>mcp_server_setup_logfile.txt
echo ====================================>>mcp_server_setup_logfile.txt
echo Manual Python Installation Required>>mcp_server_setup_logfile.txt
echo ====================================>>mcp_server_setup_logfile.txt
echo.>>mcp_server_setup_logfile.txt
echo Please install Python manually:>>mcp_server_setup_logfile.txt
echo 1. Go to: https://www.python.org/downloads/>>mcp_server_setup_logfile.txt
echo 2. Download Python 3.12 or later>>mcp_server_setup_logfile.txt
echo 3. Run the installer>>mcp_server_setup_logfile.txt
echo 4. IMPORTANT: Check 'Add Python to PATH' during installation>>mcp_server_setup_logfile.txt
echo 5. After installation, run this script again>>mcp_server_setup_logfile.txt
echo.>>mcp_server_setup_logfile.txt
pause
goto :exit

:setup_venv
echo.>>mcp_server_setup_logfile.txt
echo Setting up virtual environment and dependencies with pip...>>mcp_server_setup_logfile.txt

goto :create_requirements

:create_requirements
:: Check if requirements.txt exists
if not exist "requirements.txt" (
    echo ERROR: requirements.txt not found.>>mcp_server_setup_logfile.txt
    echo Please create a requirements.txt file in the project root directory.>>mcp_server_setup_logfile.txt
    echo Example contents:>>mcp_server_setup_logfile.txt
    echo   fastmcp^>=2.13.2>>mcp_server_setup_logfile.txt
    echo   httpx^>=0.24.0>>mcp_server_setup_logfile.txt
    echo   pyyaml^>=6.0>>mcp_server_setup_logfile.txt
    echo   requests^>=2.28.0>>mcp_server_setup_logfile.txt
    pause
    goto :exit
) else (
    echo Found existing requirements.txt file.>>mcp_server_setup_logfile.txt
)

:: Check if requirements.txt exists
if not exist "requirements.txt" (
    echo ERROR: requirements.txt not found.>>mcp_server_setup_logfile.txt
    echo Please create a requirements.txt file in the project root directory.>>mcp_server_setup_logfile.txt
    echo Example contents:>>mcp_server_setup_logfile.txt
    echo   fastmcp^>=2.13.2>>mcp_server_setup_logfile.txt
    echo   httpx^>=0.24.0>>mcp_server_setup_logfile.txt
    echo   pyyaml^>=6.0>>mcp_server_setup_logfile.txt
    echo   requests^>=2.28.0>>mcp_server_setup_logfile.txt
    pause
    goto :exit
) else (
    echo Found existing requirements.txt file.>>mcp_server_setup_logfile.txt
)

:: Check if virtual environment exists
if not exist ".venv" (
    echo Creating virtual environment with pip...>>mcp_server_setup_logfile.txt
    python -m venv .venv >>mcp_server_setup_logfile.txt 2>&1
    if %errorlevel% neq 0 (
        echo Failed to create virtual environment.>>mcp_server_setup_logfile.txt
        pause
        goto :exit
    )
)

:: Activate virtual environment
echo Activating virtual environment...>>mcp_server_setup_logfile.txt
call .venv\Scripts\activate.bat

:: Install dependencies using pip
echo Installing dependencies using pip...>>mcp_server_setup_logfile.txt
echo Upgrading pip...>>mcp_server_setup_logfile.txt
pip install --upgrade pip >>mcp_server_setup_logfile.txt 2>&1

echo Installing dependencies with pip...>>mcp_server_setup_logfile.txt
pip install -r requirements.txt >>mcp_server_setup_logfile.txt 2>&1
if %errorlevel% neq 0 (
    echo Failed to install dependencies.>>mcp_server_setup_logfile.txt
    echo This might be due to missing Visual C++ Build Tools.>>mcp_server_setup_logfile.txt
    echo Please install them from: https://visualstudio.microsoft.com/visual-cpp-build-tools/>>mcp_server_setup_logfile.txt
    pause
    goto :exit
)

echo Installing project in development mode with pip...>>mcp_server_setup_logfile.txt
pip install -e . >>mcp_server_setup_logfile.txt 2>&1
if %errorlevel% neq 0 (
    echo Failed to install project.>>mcp_server_setup_logfile.txt
    pause
    goto :exit
)

:: Check environment variables
echo.>>mcp_server_setup_logfile.txt
if "%DCT_API_KEY%"=="" (
    echo WARNING: DCT_API_KEY environment variable not set>>mcp_server_setup_logfile.txt
)
if "%DCT_BASE_URL%"=="" (
    echo WARNING: DCT_BASE_URL environment variable not set>>mcp_server_setup_logfile.txt
)

:: Run the server (stdout goes to MCP client, all logging goes to mcp_server_setup_logfile.txt)
echo.>>mcp_server_setup_logfile.txt
echo ====================================>>mcp_server_setup_logfile.txt
echo Starting DCT MCP Server...>>mcp_server_setup_logfile.txt
echo ====================================>>mcp_server_setup_logfile.txt
echo.>>mcp_server_setup_logfile.txt

.venv\Scripts\python.exe -m dct_mcp_server.main

:end
echo.>>mcp_server_setup_logfile.txt
echo Server stopped.>>mcp_server_setup_logfile.txt
pause
goto :exit

:exit
exit /b
