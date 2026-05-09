@echo off
pushd "%~dp0.."
echo Registering Ripen with IDEs...
uv run ripen-register
pause
popd
