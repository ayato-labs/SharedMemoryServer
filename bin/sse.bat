@echo off
setlocal
pushd "%~dp0.."

echo.
echo [Ripen Hub] Starting Server (SSE Mode)...
echo ----------------------------------------

set PORT=8377
set HOST=127.0.0.1

echo [1] Local Only (127.0.0.1) - Recommended
echo [2] Team/Public (0.0.0.0)  - Accessible from Network
echo.

choice /C 12 /T 3 /D 1 /M "Select mode (auto-default to 1 in 3s):"

if errorlevel 2 (
    set HOST=0.0.0.0
    echo Mode: Team/Public
) else (
    set HOST=127.0.0.1
    echo Mode: Local Only
)

echo.
echo Starting Ripen Hub on %HOST%:%PORT%...
:: Using python -m instead of uv run to avoid .exe locking issues on Windows
.venv\Scripts\python.exe -m ripen.api.server --sse --port %PORT% --host %HOST%

popd
pause
