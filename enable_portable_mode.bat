@echo off
setlocal

cd /d "%~dp0"

if not exist "data" mkdir "data"
type nul > "portable.flag"

echo Portable mode enabled.
echo Data will be stored in:
echo %~dp0data
echo.
echo To disable portable mode, delete portable.flag.
pause
