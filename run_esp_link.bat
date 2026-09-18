@echo off
setlocal
cd /d "%~dp0"

rem ESPDevLink graphical control center.
rem Run the WebView2 GUI with pythonw so the command prompt stays hidden.
rem If the GUI exits with an error, fall back to normal Python so the error is visible.

if exist ".venv\Scripts\pythonw.exe" (
    ".venv\Scripts\pythonw.exe" -m host.host_gui_web
    if errorlevel 1 (
        echo.
        echo ESPDevLink GUI exited with an error.
        echo Restarting in visible error mode...
        ".venv\Scripts\python.exe" -m host.host_gui_web
        pause
    )
    exit /b
)

where pyw >nul 2>&1
if not errorlevel 1 (
    pyw -3 -m host.host_gui_web
    if errorlevel 1 (
        echo.
        echo ESPDevLink GUI exited with an error.
        echo Restarting in visible error mode...
        py -3 -m host.host_gui_web
        pause
    )
    exit /b
)

where pythonw >nul 2>&1
if not errorlevel 1 (
    pythonw -m host.host_gui_web
    if errorlevel 1 (
        echo.
        echo ESPDevLink GUI exited with an error.
        echo Restarting in visible error mode...
        python -m host.host_gui_web
        pause
    )
    exit /b
)

echo Python was not found.
echo Install Python 3 and run this launcher again.
pause
endlocal
