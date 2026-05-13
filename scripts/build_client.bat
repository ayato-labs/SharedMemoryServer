@echo off
setlocal
pushd "%~dp0.."

echo.
echo [Ripen] Building Lightweight Client EXE...
echo ------------------------------------------

:: Check for PyInstaller
uv run pip install pyinstaller >nul 2>&1

:: Build command
:: --onefile: Bundle everything into a single EXE
:: --name: Name of the output
:: --icon: Use the project icon
uv run pyinstaller --onefile ^
    --name ripen-client ^
    --icon "%CD%\logo.ico" ^
    --distpath dist/client ^
    --workpath build/client ^
    --specpath build/client ^
    scripts/ripen-client.py

if %errorlevel% neq 0 (
    echo.
    echo Error: Build failed!
    pause
    exit /b 1
)

echo.
echo ------------------------------------------
echo Success! Client binary created.
echo Location: dist/client/ripen-client.exe
echo.
echo Share the 'dist/client' folder with your team.
echo ------------------------------------------

popd
pause
