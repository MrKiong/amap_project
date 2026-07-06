@echo off
setlocal

chcp 65001 >nul
cd /d "%~dp0"

if not "%~1"=="" (
    set "AMAP_PROJECT_COMMAND=%*"
    goto run_command
)

:menu
echo.
echo Select startup mode:
echo 1. CLI chat
echo 2. Web server
echo.
set /p "AMAP_PROJECT_CHOICE=Enter 1 or 2: "

if "%AMAP_PROJECT_CHOICE%"=="1" (
    set "AMAP_PROJECT_COMMAND=chat"
    goto run_command
)

if "%AMAP_PROJECT_CHOICE%"=="2" (
    set "AMAP_PROJECT_COMMAND=web"
    goto run_command
)

echo.
echo Invalid choice. Please enter 1 or 2.
goto menu

:run_command
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py %AMAP_PROJECT_COMMAND%
    goto done
)

where uv >nul 2>nul
if %ERRORLEVEL%==0 (
    set "UV_CACHE_DIR=%CD%\.uv-cache"
    uv run python main.py %AMAP_PROJECT_COMMAND%
    if %ERRORLEVEL%==0 goto done
    echo.
    echo uv failed; trying system python instead.
)

python main.py %AMAP_PROJECT_COMMAND%

:done
echo.
echo Process exited. Press any key to close this window.
pause >nul
