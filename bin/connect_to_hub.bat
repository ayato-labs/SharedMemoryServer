@echo off
setlocal
pushd "%~dp0.."

echo.
echo [Ripen Client] Connect to Remote Team Hub
echo ----------------------------------------

set /p HUB_URL="Enter the Ripen Hub URL (e.g. http://192.168.1.50:8377): "

if "%HUB_URL%"=="" (
    echo Error: Hub URL is required.
    pause
    exit /b 1
)

echo.
echo Connecting to %HUB_URL% via Stdio Proxy...
echo (Keep this window open while using your AI Agent)
echo.

uv run ripen --stdio --hub-url %HUB_URL%

popd
pause
