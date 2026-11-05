@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo VideoRefiner Studio is not set up yet.
    echo Run: setup.bat
    pause
    exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" "main.py"
