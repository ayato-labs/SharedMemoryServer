@echo off
setlocal

echo [SharedMemoryServer] Starting Team Hub Setup...

:: Check for Docker
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Docker is not installed or not in PATH.
    exit /b 1
)

:: Build and Start
echo [SharedMemoryServer] Building and starting container...
docker-compose up -d --build

if %errorlevel% neq 0 (
    echo Error: Docker Compose failed.
    exit /b 1
)

echo.
echo [SharedMemoryServer] Team Hub is now running!
echo URL: http://localhost:8377/sse
echo.
echo To stop the server, run: docker-compose down
echo To view logs, run: docker-compose logs -f
echo.

endlocal
