@echo off
pushd "%~dp0.."
echo Starting Ripen (STDIO)...
uv run ripen
popd
