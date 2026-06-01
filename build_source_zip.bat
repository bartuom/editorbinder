@echo off
setlocal

cd /d "%~dp0"

echo Building lightweight source/BAT release...

where py.exe > nul 2> nul
if not errorlevel 1 (
    py -3 tools\package_source_release.py
    if not errorlevel 1 exit /b 0
)

where python.exe > nul 2> nul
if not errorlevel 1 (
    python tools\package_source_release.py
    if not errorlevel 1 exit /b 0
)

echo.
echo Failed to build source ZIP.
echo Python 3 is required for the packaging helper.
pause
exit /b 1
