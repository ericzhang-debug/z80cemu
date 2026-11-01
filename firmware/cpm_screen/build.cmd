@echo off
setlocal
cd /d "%~dp0"
call "..\..\reference\source\z80v2.bat"
cd source
z80asm -I"%ROOT%src\base" -b boot.asm
if errorlevel 1 exit /b 1
z80asm -I"%ROOT%src\base" -b loader.asm
if errorlevel 1 exit /b 1
zcc +z80 -Ca-I"%ROOT%src\base" --no-crt -m @cpm.lst -o cpm
if errorlevel 1 exit /b 1
z88dk-appmake +glue -b cpm --ihex --pad --filler 0x00 --clean
if errorlevel 1 exit /b 1
py -3.10 ..\pack.py
if errorlevel 1 exit /b 1
endlocal
