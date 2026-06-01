@echo off
setlocal

cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
set "LAUNCHER=%~dp0run_app.pyw"

where pythonw.exe > nul 2> nul
if not errorlevel 1 (
    start "" pythonw.exe "%LAUNCHER%"
    exit /b 0
)

where pyw.exe > nul 2> nul
if not errorlevel 1 (
    start "" pyw.exe "%LAUNCHER%"
    exit /b 0
)

echo Starting EditorBinder...
py -3 -m editorbinder
if not errorlevel 1 exit /b 0

echo Python launcher failed, trying python...
python -m editorbinder
if not errorlevel 1 exit /b 0

echo.
echo Failed to start EditorBinder.
echo Make sure Python 3 is installed and includes tkinter.
echo Press any key to close this window.
pause > nul
exit /b 1
