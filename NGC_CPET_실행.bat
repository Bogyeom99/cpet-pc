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
echo 브라우저 주소: http://localhost:8501
echo 프로그램을 종료하려면 이 창에서 Ctrl+C를 누르세요.
echo.

start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://localhost:8501'"

".venv\Scripts\python.exe" -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501

echo.
echo NGC CPET PC가 종료되었습니다.
pause
