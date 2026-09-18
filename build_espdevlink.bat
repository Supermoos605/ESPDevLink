@echo off
setlocal
cd /d "%~dp0"

echo.
echo ==========================================
echo   ESPDevLink Windows App Builder
echo ==========================================
echo.

rem Keep the Python executable and its arguments separate so paths containing
rem spaces work correctly.
set "PYTHON="
set "PYTHON_ARGS="

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=%CD%\.venv\Scripts\python.exe"
) else (
    where py >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON=py"
        set "PYTHON_ARGS=-3"
    )
)

if not defined PYTHON (
    where python >nul 2>&1
    if not errorlevel 1 set "PYTHON=python"
)

if not defined PYTHON (
    echo Python 3 was not found.
    echo Install Python 3, then run this file again.
    pause
    exit /b 1
)

echo Using Python: "%PYTHON%" %PYTHON_ARGS%
echo.

"%PYTHON%" %PYTHON_ARGS% -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    "%PYTHON%" %PYTHON_ARGS% -m pip install "pyinstaller>=6,<7"
    if errorlevel 1 (
        echo Failed to install PyInstaller.
        pause
        exit /b 1
    )
)

if not exist "%CD%\data\espdevlink.ico" (
    echo Missing data\espdevlink.ico.
    echo The project icon is required to build the Windows app.
    pause
    exit /b 1
)

if not exist "%CD%\host\host_gui_web.html" (
    echo Missing host\host_gui_web.html.
    echo The control-center HTML file is required to build the Windows app.
    pause
    exit /b 1
)

if not exist "%CD%\host_gui_entry.py" (
    echo Missing host_gui_entry.py.
    echo The PyInstaller entry point is required to build the Windows app.
    pause
    exit /b 1
)

echo Building ESPDevLink.exe...
"%PYTHON%" %PYTHON_ARGS% -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name ESPDevLink ^
    --icon "%CD%\data\espdevlink.ico" ^
    --add-data "%CD%\host\host_gui_web.html;host" ^
    --add-data "%CD%\data\espdevlink.ico;data" ^
    --paths "%CD%" ^
    --distpath "%CD%\bin" ^
    --workpath "%CD%\build\pyinstaller" ^
    --specpath "%CD%\build" ^
    "%CD%\host_gui_entry.py"

if errorlevel 1 (
    echo.
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Build complete:
echo   %CD%\bin\ESPDevLink.exe
echo.
echo The normal run_esp_link.bat launcher will now use this executable.
pause
endlocal
