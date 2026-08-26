@echo off
rem Build standalone exe (ASCII-only, CRLF line endings required)
cd /d "%~dp0"

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo [1/2] Installing build dependencies...
"%PY%" -m pip install --quiet --disable-pip-version-check -e .[dev]
if errorlevel 1 goto :err

echo [2/2] Running PyInstaller...
"%PY%" -m PyInstaller --noconfirm dafeiyu_pet.spec
if errorlevel 1 goto :err

echo.
echo Build OK: dist\dafeiyu-pet.exe
pause
exit /b 0

:err
echo.
echo Build FAILED. Check messages above.
pause
exit /b 1
