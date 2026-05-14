@echo off
pushd "%~dp0.."
echo.
echo [Ripen Admin] Starting Admin Control Plane...
echo ----------------------------------------
echo This server provides advanced maintenance and diagnostic tools.
echo.

:: Using python -m instead of uv run to avoid .exe locking issues on Windows
.venv\Scripts\python.exe -m ripen.api.admin_server

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Admin server exited with code %ERRORLEVEL%
    pause
)
popd
