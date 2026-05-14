@echo off
setlocal
pushd "%~dp0.."

echo.
echo [Ripen Client] Connect to Remote Team Hub
echo ----------------------------------------

set /p HUB_URL="Enter Hub URL (default: http://localhost:8377): "

if "%HUB_URL%"=="" (
    set HUB_URL=http://localhost:8377
)

echo.
echo Connecting to %HUB_URL% via Stdio Proxy...
echo.

:: Using python -m instead of uv run to avoid .exe locking issues on Windows
.venv\Scripts\python.exe -m ripen.api.server --stdio --hub-url %HUB_URL%

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Proxy connection failed.
    pause
)
popd
