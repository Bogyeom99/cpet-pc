@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo NGC CPET PC is not installed yet.
    echo Run install.bat first.
    pause
    exit /b 1
)

if not exist "data" mkdir "data"

echo ==========================================
echo NGC CPET PC
echo ==========================================
echo Local address: http://127.0.0.1:8501
echo Data stays on this PC.
echo Press Ctrl+C in this window to stop the app.
echo.

".venv\Scripts\python.exe" app.py

echo.
echo NGC CPET PC stopped.
pause
