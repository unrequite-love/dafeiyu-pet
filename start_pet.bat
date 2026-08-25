@echo off
rem Dafeiyu desktop pet launcher (ASCII-only, no codepage issues)
cd /d "%~dp0"

set "PYW="
if exist ".venv\Scripts\pythonw.exe" set "PYW=.venv\Scripts\pythonw.exe"

if defined PYW goto launch

where pythonw >nul 2>nul
if errorlevel 1 goto nopython
set "PYW=pythonw"
goto launch

:nopython
echo [ERROR] pythonw not found. Install Python 3.11+ from https://www.python.org/ and retry.
pause
exit /b 1

:launch
start "" "%PYW%" -m dafeiyu_pet
