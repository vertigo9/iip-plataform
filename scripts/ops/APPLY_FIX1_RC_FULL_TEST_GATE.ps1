
$ErrorActionPreference = "Stop"

$runner = ".\RUN_0653_RC_FULL_TEST_GATE.ps1"
if (-not (Test-Path $runner)) {
    throw "Runner não encontrado: $runner"
}

$backup = $runner + ".bak1"
Copy-Item $runner $backup -Force

$newRunner = @'
$ErrorActionPreference = "Stop"

$Report = ".\D-OBSIDIAN-06.5_RC_FULL_TEST_GATE.txt"
$Started = Get-Date
Remove-Item $Report -Force -ErrorAction SilentlyContinue

@(
    "D-OBSIDIAN-06.5 RELEASE CANDIDATE FULL TEST GATE",
    ("Started: " + $Started.ToString("yyyy-MM-dd HH:mm:ss")),
    "Certified floor: 96.57%",
    ""
) | Set-Content $Report -Encoding ASCII

function Status {
    param(
        [int]$Pct,
        [string]$Stage,
        [string]$Detail = ""
    )

    $Pct = [math]::Min(100,[math]::Max(0,$Pct))
    $filled = [int][math]::Floor(($Pct/100)*30)
    $bar = ("#"*$filled).PadRight(30,"-")
    $e = "{0:hh\:mm\:ss}" -f ((Get-Date)-$Started)

    Write-Host ("[{0}] {1,3}% | {2} | elapsed={3} | {4}" -f $bar,$Pct,$Stage,$e,$Detail)
    ("[{0}] {1,3}% | {2} | elapsed={3} | {4}" -f $bar,$Pct,$Stage,$e,$Detail) |
        Add-Content $Report -Encoding ASCII
}

function Run-Stage {
    param(
        [int]$Pct,
        [string]$Stage,
        [string[]]$PythonArguments
    )

    Status $Pct $Stage "iniciando"

    & python.exe @PythonArguments 2>&1 |
        Tee-Object -FilePath (Join-Path $env:TEMP ("iip_0653_{0}.txt" -f $Pct)) |
        Tee-Object -FilePath $Report -Append

    $ExitCode = $LASTEXITCODE

    if ($ExitCode -ne 0) {
        Status $Pct ($Stage + " FALHOU") ("exit=" + $ExitCode)
        exit $ExitCode
    }

    Status $Pct ($Stage + " PASSOU") "exit=0"
}

Run-Stage 10 "Integrated suite" @("-m","pytest",".\tests\test_d064_integrated_suite.py","--no-cov","-q")

Run-Stage 20 "Behavioral hardening" @("-m","pytest",".\tests\test_d065_behavioral_gap_hardening.py","--no-cov","-q")

Run-Stage 30 "Coverage uplift targets" @("-m","pytest",".\tests\test_d065_coverage_uplift_targets.py","--no-cov","-q")

Run-Stage 55 "Full repository regression" @("-m","pytest","--no-cov","-q")

Run-Stage 80 "Formal coverage gate >=95%" @("-m","pytest","--cov-fail-under=95","-q")

Run-Stage 90 "Final collection sanity" @("-m","pytest","--collect-only","--no-cov","-q")

if (Test-Path ".\tests\test_d065_critical_path_hardening.py") {
    Run-Stage 95 "Critical path confirmation" @("-m","pytest",".\tests\test_d065_critical_path_hardening.py","--no-cov","-q")
}

Status 100 "D-OBSIDIAN-06.5 RC GATE PASS" "todos os gates concluídos"

@(
    "",
    "STATUS: D-OBSIDIAN-06.5 RC GATE PASS",
    "All configured test gates returned exit=0.",
    "RC decision can be made from this single consolidated run.",
    ("Finished: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
) | Add-Content $Report -Encoding ASCII

Write-Host ""
Write-Host "Relatório: $Report"
'@

Set-Content -Path $runner -Value $newRunner -Encoding utf8

Write-Host "FIX1 RC aplicado com sucesso."
Write-Host "Correção: removido o parâmetro PowerShell `$Args`, que colidia com a variável automática."
Write-Host "O executor foi recriado integralmente."
Write-Host "Backup: $backup"
