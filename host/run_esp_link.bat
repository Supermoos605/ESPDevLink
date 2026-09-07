@echo off
setlocal
cd /d "%~dp0.."

where py >nul 2>nul
if %errorlevel%==0 (
    py -m host.network.heartbeat
    exit /b %errorlevel%
)

where python >nul 2>nul
if %errorlevel%==0 (
    python -m host.network.heartbeat
    exit /b %errorlevel%
)

echo Python was not found.
echo Install Python 3 for Windows, then run this file again.
pause
