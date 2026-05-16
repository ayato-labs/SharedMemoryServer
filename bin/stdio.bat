@echo off
pushd "%~dp0.."
echo.
echo [Ripen Proxy] Starting Local Stdio Proxy...
echo ----------------------------------------
echo This process will bridge stdio to the central Ripen Hub.
echo It will auto-start a local Hub if one isn't running.
echo.

set PYTHONPATH=%CD%\src
.\.venv\Scripts\python.exe -m ripen.api.server --stdio

popd
pause
