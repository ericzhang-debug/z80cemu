@echo off
setlocal
cd /d "%~dp0"
py -3.10 app.py %*
if errorlevel 1 (
  echo.
  echo Specify a machine, for example: start.cmd --machine machines\generic.py
  pause
)
endlocal
