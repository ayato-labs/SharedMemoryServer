@echo off
pushd "%~dp0.."
echo Starting Ripen Admin Dashboard...
uv run ripen-admin-server
popd
