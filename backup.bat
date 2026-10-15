@echo off
setlocal
cd /d "%~dp0"

if not exist "data\cpet.db" (
    echo No local database exists yet.
    pause
    exit /b 0
)

if not exist "backup" mkdir "backup"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%i"

copy /Y "data\cpet.db" "backup\cpet_%STAMP%.db" >nul
if errorlevel 1 goto :error

echo Backup completed:
echo backup\cpet_%STAMP%.db
pause
exit /b 0

:error
echo Backup failed.
pause
exit /b 1
