@echo off
setlocal enabledelayedexpansion

if not exist "logs" mkdir logs

echo ====================================>>logs\mcp_server_setup.log
echo DCT MCP Server - Windows Startup>>logs\mcp_server_setup.log
echo ====================================>>logs\mcp_server_setup.log
echo.>>logs\mcp_server_setup.log

:: Navigate to the script directory
cd /d "%~dp0"

:: Set environment variables
set PYTHONPATH=src

:: Quick Python check first
echo Checking for Python installation...>>logs\mcp_server_setup.log
python --version >nul 2>&1
if %errorlevel% == 0 (
    echo Python is already installed.>>logs\mcp_server_setup.log
    python --version >>logs\mcp_server_setup.log 2>&1
    goto :setup_venv
)

echo Python not found. Attempting automatic installation...>>logs\mcp_server_setup.log
goto :install_python

:install_python
echo Trying to install Python via winget...>>logs\mcp_server_setup.log
winget --version >nul 2>&1
if not errorlevel 1 (
    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements --silent >>logs\mcp_server_setup.log 2>&1
    if not errorlevel 1 (
        echo Python installed successfully via winget.>>logs\mcp_server_setup.log
        goto :verify_python
    )
)

echo Trying to install Python via chocolatey...>>logs\mcp_server_setup.log
choco --version >nul 2>&1
if not errorlevel 1 (
    choco install python -y >>logs\mcp_server_setup.log 2>&1
    if not errorlevel 1 (
        echo Python installed successfully via chocolatey.>>logs\mcp_server_setup.log
        goto :verify_python
    )
)

goto :manual_install

:verify_python
echo Verifying Python installation...>>logs\mcp_server_setup.log
python --version >nul 2>&1
if %errorlevel% == 0 (
    echo Python verification successful.>>logs\mcp_server_setup.log
    python --version >>logs\mcp_server_setup.log 2>&1
    goto :setup_venv
) else (
    echo Python installation verification failed.>>logs\mcp_server_setup.log
    goto :manual_install
)

:manual_install
echo.>>logs\mcp_server_setup.log
echo ====================================>>logs\mcp_server_setup.log
echo Manual Python Installation Required>>logs\mcp_server_setup.log
echo ====================================>>logs\mcp_server_setup.log
echo.>>logs\mcp_server_setup.log
echo Please install Python manually:>>logs\mcp_server_setup.log
echo 1. Go to: https://www.python.org/downloads/>>logs\mcp_server_setup.log
echo 2. Download Python 3.12 or later>>logs\mcp_server_setup.log
echo 3. Run the installer>>logs\mcp_server_setup.log
echo 4. IMPORTANT: Check 'Add Python to PATH' during installation>>logs\mcp_server_setup.log
echo 5. After installation, run this script again>>logs\mcp_server_setup.log
echo.>>logs\mcp_server_setup.log
pause
goto :exit

:setup_venv
echo.>>logs\mcp_server_setup.log
echo Setting up virtual environment and dependencies with pip...>>logs\mcp_server_setup.log

goto :create_requirements

:create_requirements
:: Check if requirements.txt exists
if not exist "requirements.txt" (
    echo ERROR: requirements.txt not found.>>logs\mcp_server_setup.log
    echo Please create a requirements.txt file in the project root directory.>>logs\mcp_server_setup.log
    echo Example contents:>>logs\mcp_server_setup.log
    echo   fastmcp^>=2.13.2>>logs\mcp_server_setup.log
    echo   httpx^>=0.24.0>>logs\mcp_server_setup.log
    echo   pyyaml^>=6.0>>logs\mcp_server_setup.log
    echo   requests^>=2.28.0>>logs\mcp_server_setup.log
    pause
    goto :exit
) else (
    echo Found existing requirements.txt file.>>logs\mcp_server_setup.log
)

:: Check if virtual environment exists
if not exist ".venv" (
    echo Creating virtual environment with pip...>>logs\mcp_server_setup.log
    python -m venv .venv >>logs\mcp_server_setup.log 2>&1
    if %errorlevel% neq 0 (
        echo Failed to create virtual environment.>>logs\mcp_server_setup.log
        pause
        goto :exit
    )
)

:: Activate virtual environment
echo Activating virtual environment...>>logs\mcp_server_setup.log
call .venv\Scripts\activate.bat

:: Install dependencies using pip
echo Installing dependencies using pip...>>logs\mcp_server_setup.log
echo Upgrading pip...>>logs\mcp_server_setup.log
pip install --upgrade pip >>logs\mcp_server_setup.log 2>&1

echo Installing dependencies with pip...>>logs\mcp_server_setup.log
pip install -r requirements.txt >>logs\mcp_server_setup.log 2>&1
if %errorlevel% neq 0 (
    echo Failed to install dependencies.>>logs\mcp_server_setup.log
    echo This might be due to missing Visual C++ Build Tools.>>logs\mcp_server_setup.log
    echo Please install them from: https://visualstudio.microsoft.com/visual-cpp-build-tools/>>logs\mcp_server_setup.log
    pause
    goto :exit
)

echo Installing project in development mode with pip...>>logs\mcp_server_setup.log
pip install -e . >>logs\mcp_server_setup.log 2>&1
if %errorlevel% neq 0 (
    echo Failed to install project.>>logs\mcp_server_setup.log
    pause
    goto :exit
)

:: Check environment variables
echo.>>logs\mcp_server_setup.log
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

python -m dct_mcp_server.main

:exit
endlocal