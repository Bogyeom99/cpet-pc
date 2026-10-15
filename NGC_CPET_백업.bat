@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if not exist "data\cpet.db" (
    echo 아직 백업할 데이터베이스가 없습니다.
    pause
    exit /b 0
)

if not exist "backup" mkdir backup

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%i"

copy /Y "data\cpet.db" "backup\cpet_%STAMP%.db" >nul

if %errorlevel% neq 0 (
    echo 백업에 실패했습니다.
    pause
    exit /b 1
)

echo 백업 완료:
echo backup\cpet_%STAMP%.db
echo.
echo 안전한 백업을 위해 프로그램을 종료한 상태에서 실행하는 것을 권장합니다.
pause
