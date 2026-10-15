@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo NGC CPET PC - Local installation
echo ==========================================
echo.

set "PYTHON_CMD="

where py >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py"

if not defined PYTHON_CMD (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo ERROR: Python was not found.
    echo Install Python 3.12 or newer and run this file again.
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Python command: %PYTHON_CMD%
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating local Python environment...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 goto :error
) else (
    echo [1/3] Existing local Python environment found.
)

echo [2/3] Installing required packages...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo [3/3] Preparing local data folders...
if not exist "data" mkdir "data"
if not exist "backup" mkdir "backup"

echo.
echo Installation completed.
echo Run run.bat to start NGC CPET PC.
pause
exit /b 0

:error
echo.
echo ERROR: Installation failed.
echo Review the error messages above.
pause
exit /b 1
