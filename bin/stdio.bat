@echo off
pushd "%~dp0.."
echo.
echo [Ripen Hub] Starting Local Stdio Server...
echo ----------------------------------------
echo Communication: Standard I/O (STDIO)
echo Use this mode for direct MCP integration.
echo.

:: Using python -m instead of uv run to avoid .exe locking issues on Windows
.venv\Scripts\python.exe -m ripen.api.server --stdio

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Server exited with code %ERRORLEVEL%
    pause
)
popd
