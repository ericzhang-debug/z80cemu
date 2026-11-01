@echo off
setlocal
cd /d "%~dp0"
py -3.10 app.py --machine "machines\z80v2.py"
if errorlevel 1 pause
endlocal
