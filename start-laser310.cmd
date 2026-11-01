@echo off
cd /d "%~dp0"
py -3.10 app.py --machine "machines\laser310.py"
if errorlevel 1 pause
