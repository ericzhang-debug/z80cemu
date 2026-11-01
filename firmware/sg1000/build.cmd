@echo off
setlocal
cd /d "%~dp0"
call "..\..\reference\source\z80v2.bat"
z80asm -b sg1000_demo.asm
endlocal
