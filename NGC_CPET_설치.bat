@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ==========================================
echo NGC CPET PC 설치
echo ==========================================
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=py"
) else (
    where python >nul 2>nul
    if %errorlevel% neq 0 (
        echo Python을 찾을 수 없습니다.
        echo Python 3.12 이상을 설치한 뒤 다시 실행하세요.
        echo https://www.python.org/downloads/
        pause
        exit /b 1
    )
    set "PYTHON_CMD=python"
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Python 가상환경을 생성합니다...
    %PYTHON_CMD% -m venv .venv
    if %errorlevel% neq 0 goto :error
) else (
    echo [1/3] 기존 가상환경을 사용합니다.
)

echo [2/3] 필요한 패키지를 설치합니다...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if %errorlevel% neq 0 goto :error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if %errorlevel% neq 0 goto :error

echo [3/3] 로컬 데이터 폴더를 준비합니다...
if not exist "data" mkdir data
if not exist "backup" mkdir backup

echo.
echo 설치가 완료되었습니다.
echo 앞으로는 "NGC_CPET_실행.bat"을 더블클릭해서 사용하세요.
pause
exit /b 0

:error
echo.
echo 설치 중 오류가 발생했습니다.
echo 위 오류 내용을 확인한 뒤 다시 시도하세요.
pause
exit /b 1
