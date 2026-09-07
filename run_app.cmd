@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHON=%CD%\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=%CD%\venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo No project Python environment was found.
    echo Running first-time setup...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%CD%\setup_app.ps1"
    if errorlevel 1 (
        echo Setup failed. Install Python 3.12 or newer and run this file again.
        pause
        exit /b 1
    )
    set "PYTHON=%CD%\.venv\Scripts\python.exe"
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%CD%\start_app.ps1"
if errorlevel 1 (
    echo The application did not start. See the message above.
    pause
    exit /b 1
)
endlocal
