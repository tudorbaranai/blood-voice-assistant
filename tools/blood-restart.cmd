@echo off
rem Restart Blood's voice program, e.g. after changing blood\settings.toml.
rem It runs hidden (no window); see logs\blood.log for what it's doing.
powershell -NoProfile -Command "Stop-ScheduledTask -TaskName 'Blood - Voice program' -ErrorAction SilentlyContinue; Get-CimInstance Win32_Process -Filter \"Name like 'python%%'\" | Where-Object { $_.CommandLine -match 'blood\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }; Start-Sleep 2; Start-ScheduledTask -TaskName 'Blood - Voice program'; Write-Host 'Blood restarted.'"
timeout /t 3 >nul
