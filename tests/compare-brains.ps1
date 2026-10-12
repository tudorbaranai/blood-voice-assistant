# Blood brain comparison
# ----------------------
# Asks several brains (Ollama models) the same questions with the same system
# prompt, and saves a side-by-side table of their answers and response times.
# It changes no settings: it only asks Ollama questions.
#
# Run it:
#   powershell -NoProfile -ExecutionPolicy Bypass -File "D:\Claude Projects\jarvis\tests\compare-brains.ps1"

param(
    [string]$PromptFile    = "$PSScriptRoot\..\prompts\prompt_v5.txt",
    [string]$QuestionsFile = "$PSScriptRoot\questions-limits.txt",
    # "model" = normal, "model+think" = with thinking switched on
    [string[]]$Brains      = @("qwen3:1.7b", "qwen3:4b-instruct", "qwen3:4b-thinking+think"),
    [string]$OllamaUrl     = "http://127.0.0.1:11434"
)

$ErrorActionPreference = "Stop"
$en = [System.Globalization.CultureInfo]::GetCultureInfo("en-US")

# --- Fill in the template parts the way Home Assistant would ---------------
function Render-Prompt([string]$text) {
    $now = Get-Date
    $text = $text -replace '\{\{\s*now\(\)\.strftime\([^)]*\)\s*\}\}', $now.ToString("dddd, dd MMMM yyyy, HH:mm", $en)
    $lines = for ($i = 0; $i -le 28; $i++) {
        $line = $now.AddDays($i).ToString("dddd dd MMMM yyyy", $en)
        if ($i -eq 0) { $line += " (today)" } elseif ($i -eq 1) { $line += " (tomorrow)" }
        $line
    }
    $calendar = "`n" + ($lines -join "`n")
    return [regex]::Replace($text, '\{%-\s*for[\s\S]*?\{%-\s*endfor\s*%\}', { param($m) $calendar })
}

$systemPrompt = Render-Prompt (Get-Content -Raw -Encoding UTF8 $PromptFile)

# --- Load the questions ----------------------------------------------------
$tests = foreach ($line in (Get-Content -Encoding UTF8 $QuestionsFile)) {
    $line = $line.Trim()
    if (-not $line -or $line.StartsWith("#")) { continue }
    $parts = $line -split '\s*\|\s*', 2
    [pscustomobject]@{ Turns = @($parts[0] -split '\s*>>\s*'); Ideal = $(if ($parts.Count -gt 1) { $parts[1] } else { "" }) }
}

# --- Talking to Ollama -----------------------------------------------------
function Invoke-Chat([string]$model, [bool]$think, $messages) {
    $body = @{ model = $model; messages = @($messages); stream = $false; keep_alive = "10m"; think = $think }
    $bytes = [Text.Encoding]::UTF8.GetBytes(($body | ConvertTo-Json -Depth 6))
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $r = Invoke-RestMethod -Uri "$OllamaUrl/api/chat" -Method Post -Body $bytes -ContentType "application/json; charset=utf-8" -TimeoutSec 600
    $sw.Stop()
    return @{ Text = ($r.message.content -replace '\s+', ' ').Trim(); Seconds = [math]::Round($sw.Elapsed.TotalSeconds, 1) }
}

# --- Run -------------------------------------------------------------------
$answers = @{}   # key "brain|testIndex" -> "answer (seconds)"
$totals  = @{}
foreach ($brain in $Brains) {
    $model = $brain -replace '\+think$', ''
    $think = $brain.EndsWith("+think")
    Write-Host "Loading $brain ..."
    Invoke-Chat $model $false @(@{ role = "user"; content = "hi" }) | Out-Null   # warm-up, not timed
    Invoke-Chat $model $think @(@{ role = "system"; content = $systemPrompt }, @{ role = "user"; content = "hi" }) | Out-Null  # caches the prompt
    $totals[$brain] = 0.0
    for ($t = 0; $t -lt $tests.Count; $t++) {
        $messages = New-Object System.Collections.ArrayList
        [void]$messages.Add(@{ role = "system"; content = $systemPrompt })
        $texts = @(); $secs = 0.0
        foreach ($turn in $tests[$t].Turns) {
            [void]$messages.Add(@{ role = "user"; content = $turn })
            $a = Invoke-Chat $model $think $messages
            [void]$messages.Add(@{ role = "assistant"; content = $a.Text })
            $texts += $a.Text; $secs += $a.Seconds
        }
        $answers["$brain|$t"] = "$($texts -join '  >>  ') **($([math]::Round($secs,1)) s)**"
        $totals[$brain] += $secs
        Write-Host ("  {0,2}. {1,5:N1} s  {2}" -f ($t + 1), $secs, ($texts -join '  >>  '))
    }
}

# --- Save a side-by-side report --------------------------------------------
$outDir = Join-Path $PSScriptRoot "results"
New-Item -ItemType Directory -Force $outDir | Out-Null
$outFile = Join-Path $outDir ("brains-" + (Get-Date -Format "yyyy-MM-dd_HH-mm") + ".md")
$md = @("# Blood brain comparison - $(Get-Date -Format 'yyyy-MM-dd HH:mm')", "", "Prompt: $(Split-Path -Leaf $PromptFile)", "")
$md += "| # | Question | Ideal answer | " + ($Brains -join " | ") + " |"
$md += "|---|---|---|" + ("---|" * $Brains.Count)
for ($t = 0; $t -lt $tests.Count; $t++) {
    $cells = foreach ($brain in $Brains) { $answers["$brain|$t"] -replace '\|', '/' }
    $md += "| $($t + 1) | $($tests[$t].Turns -join ' >> ') | $($tests[$t].Ideal) | " + ($cells -join " | ") + " |"
}
$md += "", "| Total time | " + (($Brains | ForEach-Object { "$_ : $([math]::Round($totals[$_],1)) s" }) -join " / ") + " |"
$md | Set-Content -Encoding UTF8 $outFile
Write-Host "`nSaved report: $outFile"
