@echo off
REM ============================================================================
REM AR Email Automation - Start Streamlit Server
REM
REM Run this script to start the web app.
REM Laura can then access it at http://localhost:8501 (same PC)
REM or at http://<YOUR-IP>:8501 from another PC on the same network.
REM
REM Press Ctrl+C to stop the server.
REM ============================================================================

echo.
echo ============================================
echo   PICC AR Email Automation
echo ============================================
echo.

cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python is not installed or not on PATH.
    echo Please install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

REM Install / update dependencies
echo Checking dependencies...
pip install -r requirements.txt --quiet
if %ERRORLEVEL% neq 0 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo Dependencies OK.
echo.

REM Show local IP for Laura to connect
echo ============================================
echo   Laura can access the tool at:
echo.
echo     Same PC:  http://localhost:8501
echo.
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    for /f "tokens=1" %%b in ("%%a") do (
        echo     Network:  http://%%b:8501
    )
)
echo.
echo   Press Ctrl+C to stop the server.
echo ============================================
echo.

REM Start Streamlit on all interfaces so LAN users can connect
streamlit run app.py --server.address 0.0.0.0 --server.port 8501

pause
