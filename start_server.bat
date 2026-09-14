@echo off
setlocal
cd /d "%~dp0"

:menu
cls
echo ================================
echo          ESPDevLink Host
echo ================================
echo.
echo 1. Start server now
echo 2. Schedule daily start
echo 3. Cancel scheduled start
echo 4. Show current schedule
echo 5. Exit
echo.
set /p "choice=Select an option: "

if "%choice%"=="1" goto start
if "%choice%"=="2" goto schedule
if "%choice%"=="3" goto cancel
if "%choice%"=="4" goto show
if "%choice%"=="5" exit /b
goto menu

:start
set "ESPLINK_INPUT_ENABLED=1"
if not defined ESPLINK_AUTH_CODE set "ESPLINK_AUTH_CODE=DEVTEST"
python -m host.host_server
pause
goto menu

:schedule
set /p "time=Enter daily start time (HH:MM): "
schtasks /Create /TN "ESPDevLink Host" /SC DAILY /ST "%time%" /TR ""%~f0" scheduled" /F
if errorlevel 1 (
  echo.
  echo [ERROR] Could not create the scheduled task.
  pause
  goto menu
)
echo.
echo [OK] ESPDevLink scheduled daily at %time%.
pause
goto menu

:cancel
schtasks /Delete /TN "ESPDevLink Host" /F >nul 2>&1
if errorlevel 1 (
  echo.
  echo No ESPDevLink schedule was found.
) else (
  echo.
  echo [OK] ESPDevLink schedule cancelled.
)
pause
goto menu

:show
echo.
schtasks /Query /TN "ESPDevLink Host" /FO LIST 2>nul
if errorlevel 1 echo No ESPDevLink schedule is configured.
echo.
pause
goto menu

:scheduled
set "ESPLINK_INPUT_ENABLED=1"
if not defined ESPLINK_AUTH_CODE set "ESPLINK_AUTH_CODE=DEVTEST"
python -m host.host_server
exit /b
