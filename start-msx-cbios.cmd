@echo off
cd /d "%~dp0"
py -3.10 app.py --machine "machines\msx_cbios.py"
