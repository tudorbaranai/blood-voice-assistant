# The God Hand, end to end: render the curl sweep in a background Blender, pack it to WebP,
# rebuild the single-file page and shoot the two hand moments as stills.
#   .\blender\make_hand.ps1                      full quality (24 levels, 96 samples)
#   .\blender\make_hand.ps1 -Levels 8 -Samples 24   quick preview
# The live Blender session must have saved assets\hand\hand.blend first (hand_scene.save_blend()).
param([int]$Levels = 24, [int]$Samples = 96, [int]$Quality = 82, [double[]]$Stills = @(6.8, 7.5), [switch]$NoShoot)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path          # ...\manga-v3\blender
$root = Split-Path -Parent $here                                  # ...\manga-v3
$blender = "D:\Blender\blender.exe"
$blend = Join-Path $root "assets\hand\hand.blend"
if (-not (Test-Path $blend)) { throw "missing $blend - save it from the live Blender first" }

$t0 = Get-Date
Write-Output "[1/4] sweep: $Levels levels x 2 passes at $Samples samples"
& $blender -b $blend -P (Join-Path $here "render_hand.py") -- --sweep --levels $Levels --samples $Samples 2>&1 |
  Where-Object { $_ -match "sweep |done in|Error|Traceback" }
if ($LASTEXITCODE -ne 0) { throw "sweep failed ($LASTEXITCODE)" }

Write-Output "[2/4] pack to WebP (quality $Quality)"
& $blender -b -P (Join-Path $here "pack_hand.py") -- --quality $Quality 2>&1 |
  Where-Object { $_ -match "packed|Error|Traceback" }
if ($LASTEXITCODE -ne 0) { throw "pack failed ($LASTEXITCODE)" }

Write-Output "[3/4] build the single-file page"
& (Join-Path $root "build.ps1")

if (-not $NoShoot) {
  Write-Output "[4/4] stills at $($Stills -join ', ') s"
  & (Join-Path $root "shoot.ps1") -Design eclipse -At $Stills -Parallel 2
}
Write-Output ("done in {0:n0} s" -f ((Get-Date) - $t0).TotalSeconds)
