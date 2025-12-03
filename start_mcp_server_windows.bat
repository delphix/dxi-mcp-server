@echo off
setlocal enabledelayedexpansion

echo ====================================>>logfile.txt
echo DCT MCP Server - Windows Startup>>logfile.txt
echo ====================================>>logfile.txt
echo.>>logfile.txt

:: Navigate to the script directory
cd /d "%~dp0"

:: Set environment variables
set PYTHONPATH=src

:: Quick Python check first
echo Checking for Python installation...>>logfile.txt
python --version >nul 2>&1
if %errorlevel% == 0 (
    echo Python is already installed.>>logfile.txt
    python --version >>logfile.txt 2>&1
    goto :setup_venv
)

goto :run_powershell

:run_powershell
echo.>>logfile.txt
echo Running PowerShell installation script...>>logfile.txt
echo If this hangs, press Ctrl+C and run this script again, then choose option 2.>>logfile.txt
echo.>>logfile.txt
powershell -ExecutionPolicy Bypass -File "%~dp0start_mcp_server_windows.ps1" >>logfile.txt 2>&1
goto :end

:manual_install
echo.>>logfile.txt
echo ====================================>>logfile.txt
echo Manual Python Installation Required>>logfile.txt
echo ====================================>>logfile.txt
echo.>>logfile.txt
echo Please install Python manually:>>logfile.txt
echo 1. Go to: https://www.python.org/downloads/>>logfile.txt
echo 2. Download Python 3.12 or later>>logfile.txt
echo 3. Run the installer>>logfile.txt
echo 4. IMPORTANT: Check 'Add Python to PATH' during installation>>logfile.txt
echo 5. After installation, run this script again>>logfile.txt
echo.>>logfile.txt
pause
goto :exit

:setup_venv
echo.>>logfile.txt
echo Setting up virtual environment and dependencies...>>logfile.txt

:: Ask user for package manager preference
echo.>>logfile.txt
echo Choose package manager for dependency installation:>>logfile.txt
echo 1. uv (faster, modern Python package manager)>>logfile.txt
echo 2. pip (traditional Python package manager)>>logfile.txt
set PACKAGE_MANAGER=pip
:check_uv
echo.>>logfile.txt
echo Checking for uv installation...>>logfile.txt
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo uv not found. Installing uv...>>logfile.txt
    pip install uv >>logfile.txt 2>&1
    if %errorlevel% neq 0 (
        echo Failed to install uv. Falling back to pip.>>logfile.txt
        set PACKAGE_MANAGER=pip
        goto :create_requirements
    )
    echo uv installed successfully.>>logfile.txt
) else (
    echo uv is already installed.>>logfile.txt
    uv --version >>logfile.txt
)

:create_requirements

:: Create requirements.txt if it doesn't exist
if not exist "requirements.txt" (
    echo Creating requirements.txt...>>logfile.txt
    (
        echo # Core MCP Framework ^(using fastmcp, not standard mcp^)
        echo fastmcp^>=2.13.2
        echo.
        echo # HTTP Client for API requests
        echo httpx^>=0.24.0
        echo.
        echo # YAML processing for API specs
        echo pyyaml^>=6.0
        echo.
        echo # HTTP requests
        echo requests^>=2.28.0
        echo.
        echo # URL handling and SSL
        echo urllib3^>=1.26.0
        echo certifi^>=2022.12.7
        echo.
        echo # Environment variable handling
        echo python-dotenv^>=1.0.0
        echo.
        echo # JSON schema validation
        echo pydantic^>=2.0.0
        echo.
        echo # Async utilities
        echo anyio^>=3.6.0
        echo.
        echo # Additional utilities
        echo typing-extensions^>=4.0.0
    ) > requirements.txt
)

:: Check if virtual environment exists
if not exist ".venv" (
    if "%PACKAGE_MANAGER%"=="uv" (
        echo Creating virtual environment with uv...>>logfile.txt
        uv venv .venv >>logfile.txt 2>&1
        if %errorlevel% neq 0 (
            echo Failed to create virtual environment with uv. Trying pip...>>logfile.txt
            python -m venv .venv >>logfile.txt 2>&1
            if %errorlevel% neq 0 (
                echo Failed to create virtual environment.>>logfile.txt
                pause
                goto :exit
            )
            set PACKAGE_MANAGER=pip
        )
    ) else (
        echo Creating virtual environment with pip...>>logfile.txt
        python -m venv .venv >>logfile.txt 2>&1
        if %errorlevel% neq 0 (
            echo Failed to create virtual environment.>>logfile.txt
            pause
            goto :exit
        )
    )
)

:: Activate virtual environment
echo Activating virtual environment...>>logfile.txt
call .venv\Scripts\activate.bat

:: Install dependencies based on chosen package manager
if "%PACKAGE_MANAGER%"=="uv" (
    echo Installing dependencies with uv...>>logfile.txt
    uv pip install -r requirements.txt >>logfile.txt 2>&1
    if %errorlevel% neq 0 (
        echo Failed to install dependencies with uv. Trying pip...>>logfile.txt
        pip install --upgrade pip >>logfile.txt 2>&1
        pip install -r requirements.txt >>logfile.txt 2>&1
        if %errorlevel% neq 0 (
            echo Failed to install dependencies.>>logfile.txt
            echo This might be due to missing Visual C++ Build Tools.>>logfile.txt
            echo Please install them from: https://visualstudio.microsoft.com/visual-cpp-build-tools/>>logfile.txt
            pause
            goto :exit
        )
    )

    echo Installing project in development mode with uv...>>logfile.txt
    uv pip install -e . >>logfile.txt 2>&1
    if %errorlevel% neq 0 (
        echo Failed to install project with uv. Trying pip...>>logfile.txt
        pip install -e . >>logfile.txt 2>&1
        if %errorlevel% neq 0 (
            echo Failed to install project.>>logfile.txt
            pause
            goto :exit
        )
    )
) else (
    echo Upgrading pip...>>logfile.txt
    pip install --upgrade pip >>logfile.txt 2>&1

    echo Installing dependencies with pip...>>logfile.txt
    pip install -r requirements.txt >>logfile.txt 2>&1
    if %errorlevel% neq 0 (
        echo Failed to install dependencies.>>logfile.txt
        echo This might be due to missing Visual C++ Build Tools.>>logfile.txt
        echo Please install them from: https://visualstudio.microsoft.com/visual-cpp-build-tools/>>logfile.txt
        pause
        goto :exit
    )

    echo Installing project in development mode with pip...>>logfile.txt
    pip install -e . >>logfile.txt 2>&1
    if %errorlevel% neq 0 (
        echo Failed to install project.>>logfile.txt
        pause
        goto :exit
    )
)

:: Check environment variables
echo.>>logfile.txt
if "%DCT_API_KEY%"=="" (
    echo WARNING: DCT_API_KEY environment variable not set>>logfile.txt
)
if "%DCT_BASE_URL%"=="" (
    echo WARNING: DCT_BASE_URL environment variable not set>>logfile.txt
)

:: Run the server (stdout goes to MCP client, all logging goes to logfile.txt)
echo.>>logfile.txt
echo ====================================>>logfile.txt
echo Starting DCT MCP Server...>>logfile.txt
echo ====================================>>logfile.txt
echo.>>logfile.txt

.venv\Scripts\python.exe -m dct_mcp_server.main