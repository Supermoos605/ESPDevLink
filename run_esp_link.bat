@echo off
setlocal
cd /d "%~dp0"

rem ESPDevLink graphical control center.
rem Prefer the virtual environment, but keep a visible console so startup
rem errors are not silently hidden.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m host.host_gui
    if errorlevel 1 (
        echo.
        echo ESPDevLink GUI exited with an error.
        pause
    )
    exit /b %errorlevel%
)

where py >nul 2>&1
if not errorlevel 1 (
    py -3 -m host.host_gui
    if errorlevel 1 (
        echo.
        echo ESPDevLink GUI exited with an error.
        pause
    )
    exit /b %errorlevel%
)

where python >nul 2>&1
if not errorlevel 1 (
    python -m host.host_gui
    if errorlevel 1 (
        echo.
        echo ESPDevLink GUI exited with an error.
        pause
    )
    exit /b %errorlevel%
)

echo Python was not found.
echo Install Python 3 and run this launcher again.
pause
endlocal
