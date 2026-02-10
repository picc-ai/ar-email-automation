@echo off
REM ============================================================================
REM AR Email Automation - Run Script
REM
REM Usage:
REM   run.bat                     Run with defaults
REM   run.bat --dry-run           Preview without exporting files
REM   run.bat --verbose           Enable debug logging
REM   run.bat --xlsx path.xlsx    Use a specific XLSX file
REM   run.bat --help              Show all options
REM ============================================================================

cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python is not installed or not on PATH.
    echo Please install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

REM Check if dependencies are installed
python -c "import openpyxl; import jinja2; import yaml" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Installing dependencies...
    pip install -r requirements.txt
    if %ERRORLEVEL% neq 0 (
        echo ERROR: Failed to install dependencies.
        pause
        exit /b 1
    )
)

REM Run the pipeline
echo.
echo Starting AR Email Automation Pipeline...
echo.
python -m src.main %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo Pipeline exited with errors. See output above.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Done.
pause
