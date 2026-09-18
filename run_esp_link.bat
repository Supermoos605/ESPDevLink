@echo off
setlocal
cd /d "%~dp0"

rem ESPDevLink graphical control center.
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" -m host.host_gui
    exit /b 0
)

where pyw >nul 2>&1
if not errorlevel 1 (
    start "" pyw -3 -m host.host_gui
    exit /b 0
)

where pythonw >nul 2>&1
if not errorlevel 1 (
    start "" pythonw -m host.host_gui
    exit /b 0
)

echo Python was not found.
echo Install Python 3 and run this launcher again.
pause
endlocal
