@echo off
setlocal
pushd "%~dp0.."

echo.
echo [Ripen Hub] Starting Server...
echo ----------------------------------------

set PORT=8377
set HOST=127.0.0.1

echo Select mode:
echo [1] Local Only (127.0.0.1) - Recommended for personal use
echo [2] Team/Public (0.0.0.0)  - Accessible from other computers
echo.

set /p choice="Choice [1]: "

if "%choice%"=="2" (
    set HOST=0.0.0.0
    echo Mode: Team/Public
) else (
    echo Mode: Local Only
)

echo.
echo Starting Ripen Hub on %HOST%:%PORT%...
uv run ripen --sse --port %PORT% --host %HOST%

popd
pause
