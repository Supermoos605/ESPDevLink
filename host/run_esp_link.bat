@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

title ESPLink Launcher

set "PYTHON="
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"
if not defined PYTHON (
    where py >nul 2>nul
    if not errorlevel 1 set "PYTHON=py -3"
)
if not defined PYTHON (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON=python"
)
if not defined PYTHON (
    echo Python 3 was not found. Install Python 3 and run this file again.
    pause
    exit /b 1
)

:menu
cls
echo ================================
echo          ESPLink Launcher
echo ================================
echo 1. Start host server
echo 2. Start network heartbeat
echo 3. Start ESPLink simulator
echo 4. Install host dependencies
echo 5. Run tests
echo 6. Open local web interface
echo 7. Create virtual environment
echo 8. Exit
echo.
choice /C 12345678 /N /M "Choose an operation: "

if errorlevel 8 exit /b 0
if errorlevel 7 goto venv
if errorlevel 6 goto open
if errorlevel 5 goto tests
if errorlevel 4 goto install
if errorlevel 3 goto simulator
if errorlevel 2 goto heartbeat
if errorlevel 1 goto host

goto menu

:host
cls
echo Starting ESPLink host server...
echo Press Ctrl+C in this window to stop it.
%PYTHON% -m host.host_server
pause
goto menu

:heartbeat
cls
echo Starting ESPLink network heartbeat...
echo Press Ctrl+C in this window to stop it.
%PYTHON% -m host.network.heartbeat
pause
goto menu

:simulator
cls
echo Starting ESPLink simulator...
echo Press Ctrl+C in this window to stop it.
%PYTHON% simulator\esp_link_simulator.py
pause
goto menu

:install
cls
if not exist requirements.txt (
    echo requirements.txt was not found.
    pause
    goto menu
)
echo Installing or updating host dependencies...
%PYTHON% -m pip install -r requirements.txt
pause
goto menu

:tests
cls
echo Running ESPLink tests...
%PYTHON% -m pytest
pause
goto menu

:open
start "" "http://127.0.0.1:8765/"
goto menu

:venv
cls
if exist ".venv\Scripts\python.exe" (
    echo The virtual environment already exists.
    pause
    goto menu
)
echo Creating ESPLink virtual environment...
%PYTHON% -m venv .venv
if errorlevel 1 (
    echo Failed to create the virtual environment.
    pause
    goto menu
)
set "PYTHON=.venv\Scripts\python.exe"
echo Virtual environment created.
echo Installing host dependencies...
%PYTHON% -m pip install --upgrade pip
%PYTHON% -m pip install -r requirements.txt
pause
goto menu
