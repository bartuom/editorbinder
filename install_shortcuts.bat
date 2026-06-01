@echo off
setlocal

cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root = (Resolve-Path '.').Path; " ^
  "$launcher = Join-Path $root 'run_app.pyw'; " ^
  "$icon = Join-Path $root 'assets\editorbinder.ico'; " ^
  "$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source; " ^
  "if (-not $pythonw) { $python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source; if ($python) { $pythonw = $python -replace 'python.exe$', 'pythonw.exe' } } " ^
  "if (-not $pythonw -or -not (Test-Path $pythonw)) { throw 'pythonw.exe was not found. Install standard Python for Windows.' } " ^
  "$shell = New-Object -ComObject WScript.Shell; " ^
  "$desktop = [Environment]::GetFolderPath('Desktop'); " ^
  "$startMenu = Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs'; " ^
  "$targets = @((Join-Path $desktop 'EditorBinder.lnk'), (Join-Path $startMenu 'EditorBinder.lnk')); " ^
  "foreach ($target in $targets) { $shortcut = $shell.CreateShortcut($target); $shortcut.TargetPath = $pythonw; $shortcut.Arguments = ('\"' + $launcher + '\"'); $shortcut.WorkingDirectory = $root; $shortcut.Description = 'EditorBinder'; if (Test-Path $icon) { $shortcut.IconLocation = $icon + ',0' }; $shortcut.Save() } " ^
  "Write-Host 'Shortcuts created on Desktop and in Start Menu.'"

if errorlevel 1 goto failed

echo.
echo Done. You can now search "EditorBinder" in Start Menu.
echo To pin it to the taskbar: open it, right-click its taskbar icon, then choose "Pin to taskbar".
pause
exit /b 0

:failed
echo.
echo Failed to create shortcuts.
pause
exit /b 1
