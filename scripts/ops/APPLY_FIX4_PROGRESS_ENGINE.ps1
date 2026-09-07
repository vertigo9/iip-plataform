
$ErrorActionPreference = "Stop"

$runner = ".\RUN_0645_RELEASE_GATE_PROGRESS_ENGINE.ps1"
if (-not (Test-Path $runner)) {
    throw "Runner não encontrado: $runner"
}

$backup = $runner + ".bak4"
Copy-Item $runner $backup -Force

$newRunner = @'
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

function Invoke-PythonTracked {
    param(
        [string]$StageName,
        [string[]]$PythonArguments
    )

    $stdoutFile = Join-Path $env:TEMP ("iip_0645_{0}_stdout.txt" -f $script:Step)
    $stderrFile = Join-Path $env:TEMP ("iip_0645_{0}_stderr.txt" -f $script:Step)

    Remove-Item $stdoutFile,$stderrFile -Force -ErrorAction SilentlyContinue
    New-Item -ItemType File -Path $stdoutFile -Force | Out-Null
    New-Item -ItemType File -Path $stderrFile -Force | Out-Null

    $argString = ($PythonArguments | ForEach-Object { Quote-WindowsArgument $_ }) -join " "

    $process = Start-Process -FilePath "python.exe" `
        -ArgumentList $argString `
        -WorkingDirectory (Get-Location).Path `
        -RedirectStandardOutput $stdoutFile `
        -RedirectStandardError $stderrFile `
        -WindowStyle Hidden `
        -PassThru

    Write-Status $script:Step $script:TotalSteps $StageName ("processo iniciado (PID=" + $process.Id + ")")

    $lastOut = 0
    $lastErr = 0
    $lastHeartbeat = Get-Date

    while ($true) {
        Start-Sleep -Milliseconds 500
        $process.Refresh()

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

        if ($process.HasExited) { break }
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

    $code = $process.ExitCode

    Remove-Item $stdoutFile,$stderrFile -Force -ErrorAction SilentlyContinue

    return $code
}

$TotalSteps = 5
$script:Step = 1

$Harness = ".\tests\test_d064_integrated_suite.py"
if (-not (Test-Path $Harness)) {
    throw "Harness não encontrado: $Harness"
}

Write-Host ""
Write-Host "D-OBSIDIAN-06.4 EXECUTOR PROGRESS ENGINE FIX4"
Write-Host "Heartbeat a cada 5 segundos durante etapas longas."
Write-Host ""

Write-Status 0 $TotalSteps "Preparação" "Harness encontrado"

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
Write-Status $TotalSteps $TotalSteps "RELEASE GATE PASS" "100% concluído"
Write-Host "Relatório: $Report"
'@

Set-Content -Path $runner -Value $newRunner -Encoding utf8

Write-Host "FIX4 aplicado com sucesso."
Write-Host "O executor inteiro foi recriado; não depende de localizar o bloco anterior."
Write-Host "Backup: $backup"
