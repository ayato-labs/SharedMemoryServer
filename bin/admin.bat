@echo off
pushd "%~dp0.."
echo Starting Ripen Admin CLI...
uv run ripen-admin
pause
popd
