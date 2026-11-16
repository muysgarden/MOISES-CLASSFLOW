@echo off
setlocal
cd /d "%~dp0"
title ClassFlow - Launcher

if not exist "main.py" (
    echo ERROR: main.py was not found in this folder.
    pause
    exit /b 1
)

set "PY_CMD="
if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
    goto :check_deps
)

where py >nul 2>nul
if not errorlevel 1 (
    py -3.12 -V >nul 2>nul
    if not errorlevel 1 (
        py -3.12 -m venv .venv
        goto :venv_ready
    )
    py -3 -V >nul 2>nul
    if not errorlevel 1 (
        py -3 -m venv .venv
        goto :venv_ready
    )
)

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python could not be found.
    echo Install Python 3.12 and enable the Python launcher, then try again.
    pause
    exit /b 1
)
python -m venv .venv

:venv_ready
if errorlevel 1 (
    echo ERROR: Could not create the Python virtual environment.
    pause
    exit /b 1
)
set "PY_CMD=.venv\Scripts\python.exe"

:check_deps
"%PY_CMD%" -c "import PyQt5.QtWidgets, openpyxl" >nul 2>nul
if errorlevel 1 (
    echo Installing ClassFlow requirements...
    "%PY_CMD%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Dependency installation failed. Check your internet connection
        echo and Python version. Python 3.12 is recommended.
        pause
        exit /b 1
    )
)

echo Launching ClassFlow...
"%PY_CMD%" main.py
if errorlevel 1 (
    echo.
    echo ERROR: ClassFlow stopped with an error.
    echo Please copy the error displayed above and send it for diagnosis.
    pause
    exit /b 1
)
endlocal
