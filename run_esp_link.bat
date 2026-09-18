@echo off
setlocal
cd /d "%~dp0"

rem ESPDevLink graphical control center.
rem Prefer the packaged Windows executable so the taskbar uses the
rem ESPDevLink icon embedded in the executable.

if exist "bin\ESPDevLink.exe" (
    start "" /b "bin\ESPDevLink.exe"
    exit /b 0
)

rem The packaged app has not been built yet. Fall back to the Python GUI.
if exist ".venv\Scripts\pythonw.exe" (
    start "" /b ".venv\Scripts\pythonw.exe" -m host.host_gui_web
    exit /b 0
)

where pythonw >nul 2>&1
if not errorlevel 1 (
    start "" /b pythonw -m host.host_gui_web
    exit /b 0
)

where pyw >nul 2>&1
if not errorlevel 1 (
    start "" /b pyw -3 -m host.host_gui_web
    exit /b 0
)

echo ESPDevLink is not built and Python was not found.
echo Run build_espdevlink.bat once to create the Windows app.
pause
endlocal
