@echo off
setlocal
cd /d "%~dp0"

echo.
echo ==========================================
echo   ESPDevLink Windows App Builder
echo ==========================================
echo.

set "PY="
if exist ".venv\Scripts\python.exe" set "PY=%CD%\.venv\Scripts\python.exe"

if not defined PY (
    where py >nul 2>&1
    if not errorlevel 1 set "PY=py -3"
)

if not defined PY (
    where python >nul 2>&1
    if not errorlevel 1 set "PY=python"
)

if not defined PY (
    echo Python 3 was not found.
    echo Install Python 3, then run this file again.
    pause
    exit /b 1
)

echo Using Python: %PY%
echo.

%PY% -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    %PY% -m pip install "pyinstaller>=6,<7"
    if errorlevel 1 (
        echo Failed to install PyInstaller.
        pause
        exit /b 1
    )
)

if not exist "data\espdevlink.ico" (
    echo Missing data\espdevlink.ico.
    echo The project icon is required to build the Windows app.
    pause
    exit /b 1
)

echo Building ESPDevLink.exe...
%PY% -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name ESPDevLink ^
    --icon "data\espdevlink.ico" ^
    --add-data "host\host_gui_web.html;host" ^
    --add-data "data\espdevlink.ico;data" ^
    --paths "." ^
    --distpath "bin" ^
    --workpath "build\pyinstaller" ^
    --specpath "build" ^
    "host_gui_entry.py"

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
