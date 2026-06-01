@echo off
setlocal

cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root = (Resolve-Path '.').Path; " ^
  "$exe = Join-Path $root 'EditorBinder.exe'; " ^
  "$icon = Join-Path $root 'assets\editorbinder.ico'; " ^
  "if (-not (Test-Path $exe)) { throw 'EditorBinder.exe was not found next to this BAT file.' } " ^
  "$shell = New-Object -ComObject WScript.Shell; " ^
  "$desktop = [Environment]::GetFolderPath('Desktop'); " ^
  "$startMenu = Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs'; " ^
  "$targets = @((Join-Path $desktop 'EditorBinder.lnk'), (Join-Path $startMenu 'EditorBinder.lnk')); " ^
  "foreach ($target in $targets) { $shortcut = $shell.CreateShortcut($target); $shortcut.TargetPath = $exe; $shortcut.WorkingDirectory = $root; $shortcut.Description = 'EditorBinder'; if (Test-Path $icon) { $shortcut.IconLocation = $icon + ',0' }; $shortcut.Save() } " ^
  "Write-Host 'Shortcuts created on Desktop and in Start Menu.'"

if errorlevel 1 goto failed

echo.
echo Done. You can now search "EditorBinder" in Start Menu.
pause
exit /b 0

:failed
echo.
echo Failed to create shortcuts.
pause
exit /b 1
