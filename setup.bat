@echo off
setlocal
cd /d "%~dp0"
title VideoRefiner Studio Setup

where powershell.exe >nul 2>nul
if errorlevel 1 (
    echo Windows PowerShell was not found. Windows 10 or 11 is required.
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1" %*
set "SETUP_EXIT=%ERRORLEVEL%"

if not "%SETUP_EXIT%"=="0" (
    echo.
    echo Setup did not finish successfully. See the messages above and SHARING.md.
    pause
    exit /b %SETUP_EXIT%
)

exit /b 0
