# Gaming mode: switch Blood off cleanly to free RAM and the graphics card.
#   1. Shuts the Home Assistant VM down properly (like pressing its power button)
#   2. Quits Ollama (the brain), which frees the graphics card memory
# Double-click tools\gaming-mode.cmd to run it. Undo with tools\blood-mode.cmd (or restart the laptop).

$ErrorActionPreference = "Continue"
$vmName = "Home Assistant"

function Get-VBoxManage {
    $dir = (Get-ItemProperty "HKLM:\SOFTWARE\Oracle\VirtualBox" -ErrorAction SilentlyContinue).InstallDir
    if (-not $dir) { $dir = "C:\Program Files\Oracle\VirtualBox\" }
    return (Join-Path $dir "VBoxManage.exe")
}
$vb = Get-VBoxManage
$before = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB

Write-Host "== Gaming mode ==" -ForegroundColor Cyan

# 1. The VM
$running = (& $vb list runningvms) -match [regex]::Escape("`"$vmName`"")
if ($running) {
    Write-Host "Shutting down the Home Assistant VM (up to 90 s)..."
    & $vb controlvm $vmName acpipowerbutton | Out-Null
    $deadline = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $deadline -and ((& $vb list runningvms) -match [regex]::Escape("`"$vmName`""))) {
        Start-Sleep -Seconds 3
    }
    if ((& $vb list runningvms) -match [regex]::Escape("`"$vmName`"")) {
        Write-Host "The VM didn't shut down in time. Saving its state instead (safe, resumes exactly where it was)." -ForegroundColor Yellow
        & $vb controlvm $vmName savestate | Out-Null
    }
    Write-Host "VM is off." -ForegroundColor Green
} else {
    Write-Host "VM was already off."
}

# 2. Ollama (the tray app first, so it doesn't restart the server)
$procs = Get-Process -Name "ollama app", "ollama" -ErrorAction SilentlyContinue
if ($procs) {
    Write-Host "Quitting Ollama..."
    Get-Process -Name "ollama app" -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 1
    Get-Process -Name "ollama" -ErrorAction SilentlyContinue | Stop-Process -Force
    Write-Host "Ollama is off." -ForegroundColor Green
} else {
    Write-Host "Ollama was already off."
}

Start-Sleep -Seconds 2
$after = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB
Write-Host ("Free RAM: {0:N1} GB -> {1:N1} GB" -f $before, $after) -ForegroundColor Cyan
Write-Host "Have fun! Run blood-mode.cmd (or restart the laptop) to bring Blood back."
