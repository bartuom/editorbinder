@echo off
setlocal

cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root = (Resolve-Path '.').Path; " ^
  "$paths = New-Object System.Collections.Generic.List[string]; " ^
  "$paths.Add((Join-Path $root 'data\settings.json')); " ^
  "if ($env:APPDATA) { $paths.Add((Join-Path $env:APPDATA 'EditorBinder\settings.json')) } " ^
  "$updated = 0; " ^
  "foreach ($path in ($paths | Select-Object -Unique)) { " ^
  "  if (-not (Test-Path $path)) { continue } " ^
  "  try { " ^
  "    $settings = Get-Content -Raw -Path $path | ConvertFrom-Json; " ^
  "    if ($null -eq $settings) { continue } " ^
  "    if ($settings.PSObject.Properties.Name -contains 'geometry') { $settings.geometry = '' } else { $settings | Add-Member -NotePropertyName geometry -NotePropertyValue '' } " ^
  "    $settings | ConvertTo-Json -Depth 20 | Set-Content -Path $path -Encoding UTF8; " ^
  "    Write-Host ('Reset window position in: ' + $path); " ^
  "    $updated += 1; " ^
  "  } catch { Write-Warning ('Could not update ' + $path + ': ' + $_.Exception.Message) } " ^
  "} " ^
  "if ($updated -eq 0) { Write-Host 'No settings file found. The app will use default window position on next start.' }"

if errorlevel 1 goto failed

echo.
echo Done. Start the app again.
pause
exit /b 0

:failed
echo.
echo Failed to reset window position.
pause
exit /b 1
