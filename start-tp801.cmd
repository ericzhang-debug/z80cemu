@echo off
setlocal
cd /d "%~dp0"
py -3.10 app.py --machine "machines\tp801.py"
if errorlevel 1 pause
endlocal
