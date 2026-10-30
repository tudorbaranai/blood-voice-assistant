# Jarvis model test bench
# -----------------------
# Sends the same test questions to several model + temperature combinations
# through Ollama, and saves every answer with its response time, so we can
# compare them side by side. It changes no settings: it only asks questions.
#
# Run it:
#   powershell -NoProfile -ExecutionPolicy Bypass -File tests\test-models.ps1

param(
    [string]$PromptFile = "$PSScriptRoot\..\prompts\prompt_v2.txt",
    [string]$OllamaUrl  = "http://127.0.0.1:11434"
)

$ErrorActionPreference = "Stop"
$en = [System.Globalization.CultureInfo]::GetCultureInfo("en-US")

# --- What to compare -------------------------------------------------------
# Temp = $null means "use the model's own default temperature".
$configs = @(
    @{ Model = "qwen3:1.7b";        Temp = $null },
    @{ Model = "qwen3:1.7b";        Temp = 0.2 },
    @{ Model = "qwen3:4b-instruct"; Temp = $null },
    @{ Model = "qwen3:4b-instruct"; Temp = 0.2 }
)

# Each test is one or more things Tudor says, in order (a mini conversation).
$tests = @(
    @{ Turns = @("What is the capital of Peru?") },
    @{ Turns = @("What day is it today?") },
    @{ Turns = @("What day of the week will 29/10/2026 be?") },
    @{ Turns = @("What date is next Tuesday?") },
    @{ Turns = @("Turn on the lamp", "the ceiling one") },
    @{ Turns = @("turn the bedroom light on") },
    @{ Turns = @("give me a recipe for breakfast") },
    @{ Turns = @("wassup?") },
    @{ Turns = @("messi or ronaldo?") },
    @{ Turns = @("what can you do?") },
    @{ Turns = @("Will it rain tomorrow?") },
    @{ Turns = @("Did you just turn on a light?") }
)

# --- Fill in the template parts the way Home Assistant would ---------------
# The prompt file is written for Home Assistant (Jinja templates). Here we
# replace those two template pieces with real values ourselves.
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

# --- Talking to Ollama -----------------------------------------------------
$noThinkSupport = @{}   # models that reject the "think" switch

function Invoke-Chat([string]$model, $temp, $messages) {
    $body = @{ model = $model; messages = @($messages); stream = $false; keep_alive = "10m" }
    if (-not $noThinkSupport[$model]) { $body.think = $false }
    if ($null -ne $temp) { $body.options = @{ temperature = $temp } }
    $bytes = [Text.Encoding]::UTF8.GetBytes(($body | ConvertTo-Json -Depth 6))
    $sw = [Diagnostics.Stopwatch]::StartNew()
    try {
        $r = Invoke-RestMethod -Uri "$OllamaUrl/api/chat" -Method Post -Body $bytes -ContentType "application/json; charset=utf-8"
    } catch {
        if (-not $noThinkSupport[$model] -and "$_" -match "think") {
            $noThinkSupport[$model] = $true
            return Invoke-Chat $model $temp $messages
        }
        throw
    }
    $sw.Stop()
    return @{ Text = ($r.message.content -replace '\s+', ' ').Trim(); Seconds = [math]::Round($sw.Elapsed.TotalSeconds, 2) }
}

# --- Run all tests ---------------------------------------------------------
$results = New-Object System.Collections.ArrayList
$loaded = ""

foreach ($c in $configs) {
    $label = if ($null -eq $c.Temp) { "$($c.Model) / default temp" } else { "$($c.Model) / temp $($c.Temp)" }
    if ($loaded -ne $c.Model) {
        Write-Host "Loading $($c.Model) into the graphics card..."
        Invoke-Chat $c.Model $null @(@{ role = "user"; content = "hi" }) | Out-Null   # warm-up, not timed
        $loaded = $c.Model
    }
    Write-Host "Testing: $label"
    foreach ($t in $tests) {
        $messages = New-Object System.Collections.ArrayList
        [void]$messages.Add(@{ role = "system"; content = $systemPrompt })
        $answers = @(); $times = @()
        foreach ($turn in $t.Turns) {
            [void]$messages.Add(@{ role = "user"; content = $turn })
            $a = Invoke-Chat $c.Model $c.Temp $messages
            [void]$messages.Add(@{ role = "assistant"; content = $a.Text })
            $answers += $a.Text; $times += $a.Seconds
        }
        [void]$results.Add([pscustomobject]@{
            Question = ($t.Turns -join "  ->  ")
            Config   = $label
            Seconds  = ($times -join " + ")
            Answer   = ($answers -join "  ->  ")
        })
    }
}

# --- Save a readable report ------------------------------------------------
$outDir = Join-Path $PSScriptRoot "results"
New-Item -ItemType Directory -Force $outDir | Out-Null
$outFile = Join-Path $outDir ("results-" + (Get-Date -Format "yyyy-MM-dd_HH-mm") + ".md")

$md = @("# Jarvis model test - $(Get-Date -Format 'yyyy-MM-dd HH:mm')", "", "Prompt: $(Split-Path -Leaf $PromptFile)", "")
foreach ($q in ($results | Select-Object -ExpandProperty Question -Unique)) {
    $md += "## $q", "", "| Model / temperature | Seconds | Answer |", "|---|---|---|"
    foreach ($r in ($results | Where-Object Question -eq $q)) {
        $md += "| $($r.Config) | $($r.Seconds) | $($r.Answer -replace '\|', '/') |"
    }
    $md += ""
}
$md | Set-Content -Encoding UTF8 $outFile
Write-Host "`nSaved report: $outFile"
