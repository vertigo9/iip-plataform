$ErrorActionPreference = "Stop"

$Report = ".\D-OBSIDIAN-06.4_EXECUTOR_PROGRESS_ENGINE.txt"
Remove-Item $Report -Force -ErrorAction SilentlyContinue

$Started = Get-Date

@(
    "D-OBSIDIAN-06.4 EXECUTOR PROGRESS ENGINE FIX4",
    ("Started: " + $Started.ToString("yyyy-MM-dd HH:mm:ss")),
    "Protected baseline: D-OBSIDIAN-06.3 / 95.48% / 739 passed / 4 skipped",
    ""
) | Set-Content -Path $Report -Encoding ASCII

function Write-Status {
    param(
        [int]$Current,
        [int]$Total,
        [string]$Stage,
        [string]$Detail = ""
    )

    $pct = [math]::Min(100,[math]::Max(0,[math]::Round(($Current/$Total)*100)))
    $barSize = 30
    $filled = [int][math]::Floor(($pct/100)*$barSize)
    $bar = ("#" * $filled).PadRight($barSize,"-")
    $elapsed = (Get-Date) - $Started
    $e = "{0:hh\:mm\:ss}" -f $elapsed

    Write-Host ("[{0}] {1,3}% | {2} | elapsed={3} | {4}" -f $bar,$pct,$Stage,$e,$Detail)
    ("[{0}] {1,3}% | {2} | elapsed={3} | {4}" -f $bar,$pct,$Stage,$e,$Detail) |
        Add-Content -Path $Report -Encoding ASCII
}

function Quote-WindowsArgument {
    param([string]$Value)
    if ($Value -notmatch '[\s"]') { return $Value }
    return '"' + ($Value -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"'
}

function Quote-CmdArgument {
    param([string]$Value)

    if ($Value -notmatch '[\s"&|<>^]') {
        return $Value
    }

    return '"' + ($Value -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"'
}

function Invoke-PythonTracked {
    param(
        [string]$StageName,
        [string[]]$PythonArguments
    )

    $id = $script:Step
    $work = Join-Path $env:TEMP ("iip_0645_{0}_{1}" -f $id, ([guid]::NewGuid().ToString("N")))
    New-Item -ItemType Directory -Path $work -Force | Out-Null

    $stdoutFile = Join-Path $work "stdout.txt"
    $stderrFile = Join-Path $work "stderr.txt"
    $exitFile = Join-Path $work "exit.txt"
    $cmdFile = Join-Path $work "run.cmd"

    $quotedArgs = $PythonArguments | ForEach-Object { Quote-CmdArgument $_ }
    $argString = ($quotedArgs -join " ")

    $cmdText = "@echo off`r`npython.exe $argString > `"$stdoutFile`" 2> `"$stderrFile`"`r`necho %ERRORLEVEL% > `"$exitFile`"`r`n"
    Set-Content -Path $cmdFile -Value $cmdText -Encoding ASCII

    $process = Start-Process -FilePath "cmd.exe" `
        -ArgumentList @("/c", $cmdFile) `
        -WorkingDirectory (Get-Location).Path `
        -WindowStyle Hidden `
        -PassThru

    Write-Status $script:Step $script:TotalSteps $StageName ("processo iniciado (PID=" + $process.Id + ")")

    $lastOut = 0
    $lastErr = 0
    $lastHeartbeat = Get-Date

    while (-not $process.HasExited) {
        Start-Sleep -Milliseconds 500

        $out = Get-Content $stdoutFile -Raw -ErrorAction SilentlyContinue
        $err = Get-Content $stderrFile -Raw -ErrorAction SilentlyContinue
        if ($null -eq $out) { $out = "" }
        if ($null -eq $err) { $err = "" }

        if ($out.Length -gt $lastOut) {
            $delta = $out.Substring($lastOut)
            if ($delta.Trim().Length -gt 0) {
                Write-Host $delta.TrimEnd()
                Add-Content -Path $Report -Value $delta.TrimEnd() -Encoding ASCII
            }
            $lastOut = $out.Length
        }

        if ($err.Length -gt $lastErr) {
            $delta = $err.Substring($lastErr)
            if ($delta.Trim().Length -gt 0) {
                Write-Host ("[stderr] " + $delta.TrimEnd())
                Add-Content -Path $Report -Value ("[stderr] " + $delta.TrimEnd()) -Encoding ASCII
            }
            $lastErr = $err.Length
        }

        if (((Get-Date) - $lastHeartbeat).TotalSeconds -ge 5 -and -not $process.HasExited) {
            $elapsed = (Get-Date) - $Started
            $e = "{0:hh\:mm\:ss}" -f $elapsed
            Write-Host ("    ... ainda executando | etapa=" + $StageName + " | elapsed=" + $e + " | PID=" + $process.Id)
            Add-Content -Path $Report -Value ("    ... ainda executando | etapa=" + $StageName + " | elapsed=" + $e + " | PID=" + $process.Id) -Encoding ASCII
            $lastHeartbeat = Get-Date
        }
    }

    Start-Sleep -Milliseconds 250

    $out = Get-Content $stdoutFile -Raw -ErrorAction SilentlyContinue
    $err = Get-Content $stderrFile -Raw -ErrorAction SilentlyContinue
    if ($null -eq $out) { $out = "" }
    if ($null -eq $err) { $err = "" }

    if ($out.Length -gt $lastOut) {
        $delta = $out.Substring($lastOut)
        if ($delta.Trim().Length -gt 0) {
            Write-Host $delta.TrimEnd()
            Add-Content -Path $Report -Value $delta.TrimEnd() -Encoding ASCII
        }
    }

    if ($err.Length -gt $lastErr) {
        $delta = $err.Substring($lastErr)
        if ($delta.Trim().Length -gt 0) {
            Write-Host ("[stderr] " + $delta.TrimEnd())
            Add-Content -Path $Report -Value ("[stderr] " + $delta.TrimEnd()) -Encoding ASCII
        }
    }

    if (-not (Test-Path $exitFile)) {
        throw "Arquivo de exit code nÃ£o foi gerado: $exitFile"
    }

    $rawExit = (Get-Content $exitFile -Raw).Trim()
    if ($rawExit -notmatch '^\d+$') {
        throw "Exit code invÃ¡lido no arquivo: '$rawExit'"
    }

    $code = [int]$rawExit

    Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue

    return $code
}
$TotalSteps = 5
$script:Step = 1

$Harness = ".\tests\test_d064_integrated_suite.py"
if (-not (Test-Path $Harness)) {
    throw "Harness nÃ£o encontrado: $Harness"
}

Write-Host ""
Write-Host "D-OBSIDIAN-06.4 EXECUTOR PROGRESS ENGINE FIX4"
Write-Host "Heartbeat a cada 5 segundos durante etapas longas."
Write-Host ""

Write-Status 0 $TotalSteps "PreparaÃ§Ã£o" "Harness encontrado"

$code = Invoke-PythonTracked "Integrated functional suite" @("-m","pytest",$Harness,"-q","--no-cov")
if ($code -ne 0) {
    Write-Status $script:Step $TotalSteps "Integrated functional suite FALHOU" ("exit=" + $code)
    exit $code
}
$script:Step++
Write-Status $script:Step $TotalSteps "Integrated functional suite PASSOU" "exit=0"

$code = Invoke-PythonTracked "Complete repository suite" @("-m","pytest","-q","--no-cov")
if ($code -ne 0) {
    Write-Status $script:Step $TotalSteps "Complete repository suite FALHOU" ("exit=" + $code)
    exit $code
}
$script:Step++
Write-Status $script:Step $TotalSteps "Complete repository suite PASSOU" "exit=0"

$code = Invoke-PythonTracked "Coverage gate >=95%" @("-m","pytest","--cov-fail-under=95","-q")
if ($code -ne 0) {
    Write-Status $script:Step $TotalSteps "Coverage gate FALHOU" ("exit=" + $code)
    exit $code
}
$script:Step++
Write-Status $script:Step $TotalSteps "Coverage gate PASSOU" "exit=0"

$code = Invoke-PythonTracked "Final collection sanity" @("-m","pytest","--collect-only","-q","--no-cov")
if ($code -ne 0) {
    Write-Status $script:Step $TotalSteps "Final collection sanity FALHOU" ("exit=" + $code)
    exit $code
}
$script:Step++
Write-Status $script:Step $TotalSteps "Final collection sanity PASSOU" "exit=0"

@(
    "",
    "STATUS: RELEASE GATE EXECUTED",
    "All configured stages completed with exit code 0.",
    ("Finished: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
) | Add-Content -Path $Report -Encoding ASCII

Write-Host ""
Write-Status $TotalSteps $TotalSteps "RELEASE GATE PASS" "100% concluÃ­do"
Write-Host "RelatÃ³rio: $Report"


