@echo off
pushd "%~dp0.."
echo Running Ripen Test Suite...
uv run pytest tests -v
pause
popd
