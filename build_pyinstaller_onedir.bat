@echo off
setlocal

cd /d "%~dp0"

echo Building versioned Windows EXE release...
echo.

if exist ".build-venv\Scripts\python.exe" (
    ".build-venv\Scripts\python.exe" tools\package_windows_release.py
    if not errorlevel 1 goto done
    goto failed
)

where py.exe > nul 2> nul
if not errorlevel 1 (
    py -3 tools\package_windows_release.py
    if not errorlevel 1 goto done
    goto failed
)

where python.exe > nul 2> nul
if not errorlevel 1 (
    python tools\package_windows_release.py
    if not errorlevel 1 goto done
    goto failed
)

echo.
echo Failed to build Windows EXE release.
echo Python 3 and PyInstaller are required.
echo.
echo Recommended local build environment:
echo.
echo   py -3 -m venv .build-venv
echo   .build-venv\Scripts\python -m pip install pyinstaller
echo   .build-venv\Scripts\python tools\package_windows_release.py
echo.
pause
exit /b 1

:done
echo.
echo Done. The versioned package is in dist\EditorBinder-^<version^>-win-x64.
pause
exit /b 0

:failed
echo.
echo Windows EXE release build failed.
pause
exit /b 1
