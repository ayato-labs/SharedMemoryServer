@echo off
pushd "%~dp0.."
echo Starting Ripen (SSE on Port 8377)...
uv run ripen --sse --port 8377
popd
