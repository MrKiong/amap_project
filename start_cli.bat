@echo off
setlocal

chcp 65001 >nul
cd /d "%~dp0"

if "%~1"=="" (
    set "AMAP_PROJECT_COMMAND=chat"
) else (
    set "AMAP_PROJECT_COMMAND=%*"
)

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
