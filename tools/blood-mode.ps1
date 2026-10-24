# Blood mode: switch Blood back on after gaming.
#   1. Starts Ollama (the brain)
#   2. Starts the Home Assistant VM in the background (no window)
#   3. Waits until Home Assistant answers, then loads the brain so the first question is fast
# Double-click tools\blood-mode.cmd to run it.

$ErrorActionPreference = "Continue"
$vmName = "Home Assistant"
$brain = "blood-brain"

function Get-VBoxManage {
    $dir = (Get-ItemProperty "HKLM:\SOFTWARE\Oracle\VirtualBox" -ErrorAction SilentlyContinue).InstallDir
    if (-not $dir) { $dir = "C:\Program Files\Oracle\VirtualBox\" }
    return (Join-Path $dir "VBoxManage.exe")
}
$vb = Get-VBoxManage

Write-Host "== Blood mode ==" -ForegroundColor Cyan

# 1. Ollama
if (-not (Get-Process -Name "ollama app" -ErrorAction SilentlyContinue)) {
    $app = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama app.exe"
    Write-Host "Starting Ollama..."
    Start-Process $app
} else {
    Write-Host "Ollama is already running."
}

# 2. The VM (headless = no window)
if (-not ((& $vb list runningvms) -match [regex]::Escape("`"$vmName`""))) {
    Write-Host "Starting the Home Assistant VM..."
    & $vb startvm $vmName --type headless | Out-Null
} else {
    Write-Host "The VM is already running."
}

# 3. Wait for Home Assistant (up to 3 minutes)
Write-Host "Waiting for Home Assistant to answer (usually 1-2 minutes)..."
$deadline = (Get-Date).AddMinutes(3)
$ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8123/" -TimeoutSec 5
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
    Start-Sleep -Seconds 5
}
if ($ready) { Write-Host "Home Assistant is up: http://127.0.0.1:8123" -ForegroundColor Green }
else { Write-Host "Home Assistant isn't answering yet. Give it another minute, then open http://127.0.0.1:8123" -ForegroundColor Yellow }

# 4. Load the brain into the graphics card now, so the first question isn't slow
try {
    $body = @{ model = $brain; prompt = ""; keep_alive = -1 } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:11434/api/generate" -Body $body -ContentType "application/json" -TimeoutSec 120 | Out-Null
    Write-Host "Brain '$brain' is loaded." -ForegroundColor Green
} catch {
    Write-Host "Couldn't pre-load the brain (it will load on the first question instead)." -ForegroundColor Yellow
}
Write-Host "Blood is ready."
