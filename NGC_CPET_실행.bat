@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo 먼저 "NGC_CPET_설치.bat"을 실행하세요.
    pause
    exit /b 1
)

if not exist "data" mkdir data

echo NGC CPET PC를 실행합니다.
echo.
echo 브라우저 주소: http://127.0.0.1:8501
echo 선수 정보와 측정 자료는 이 PC 안에서만 처리됩니다.
echo 프로그램을 종료하려면 이 창에서 Ctrl+C를 누르세요.
echo.

".venv\Scripts\python.exe" app.py

echo.
echo NGC CPET PC가 종료되었습니다.
pause
