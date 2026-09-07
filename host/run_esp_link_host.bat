@echo off
setlocal
cd /d "%~dp0.."
python -m host.host_server
endlocal
