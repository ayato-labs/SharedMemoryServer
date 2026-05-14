@echo off
pushd "%~dp0.."
echo Registering Ripen with IDEs...

:: Using python -m instead of uv run to avoid .exe locking issues on Windows
.venv\Scripts\python.exe -m ripen.cli.register
pause
popd
