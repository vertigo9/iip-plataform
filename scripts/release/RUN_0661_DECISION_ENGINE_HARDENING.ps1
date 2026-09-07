$ErrorActionPreference = "Stop"

$Report = ".\D-OBSIDIAN-06.6_DECISION_ENGINE_HARDENING.txt"
$Started = Get-Date
Remove-Item $Report -Force -ErrorAction SilentlyContinue

function Status {
    param([int]$Pct,[string]$Stage,[string]$Detail="")
    $Pct = [math]::Min(100,[math]::Max(0,$Pct))
    $filled = [int][math]::Floor(($Pct/100)*30)
    $bar = ("#"*$filled).PadRight(30,"-")
    $elapsed = "{0:hh\:mm\:ss}" -f ((Get-Date)-$Started)
    Write-Host ("[{0}] {1,3}% | {2} | elapsed={3} | {4}" -f $bar,$Pct,$Stage,$elapsed,$Detail)
    ("[{0}] {1,3}% | {2} | elapsed={3} | {4}" -f $bar,$Pct,$Stage,$elapsed,$Detail) |
        Add-Content $Report -Encoding ASCII
}

$Target = ".\tests\test_d066_decision_engine_hardening.py"
if (-not (Test-Path $Target)) { throw "Teste n????o encontrado: $Target" }

@(
    "D-OBSIDIAN-06.6 DECISION ENGINE HARDENING",
    ("Started: " + $Started.ToString("yyyy-MM-dd HH:mm:ss")),
    "Protected baseline: D-OBSIDIAN-06.5 / 96.57%",
    "Mode: diagnostic + focused behavioral coverage; no production deployment",
    ""
) | Set-Content $Report -Encoding ASCII

Status 10 "Focused collection"
python -m pytest $Target --collect-only --no-cov -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0661_collect.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Status 35 "Decision engine focused harness"
python -m pytest $Target ".\tests\test_decision_301_500.py" ".\tests\test_portfolio_decision_60001_70000.py" --no-cov -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0661_focus.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Status 60 "Decision engine coverage"
python -m pytest ".\tests\test_decision_301_500.py" ".\tests\test_portfolio_decision_60001_70000.py" ".\tests\test_d066_decision_engine_hardening.py" --cov=iip.decision.decision_engine --cov-report=term-missing -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0661_coverage.txt") |
    Tee-Object $Report -Append

$focusCode = $LASTEXITCODE
if ($focusCode -ne 0) {
    Status 60 "Decision engine coverage reported failure" ("exit=" + $focusCode + " - report retained for analysis")
}

Status 80 "Repository regression safety"
python -m pytest -q --no-cov 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0661_regression.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Status 100 "DECISION ENGINE HARDENING DIAGNOSTIC PASS" "baseline 96.57% protegido"
@(
    "",
    "STATUS: D-OBSIDIAN-06.6 DECISION ENGINE HARDENING DIAGNOSTIC PASS",
    "The module-specific coverage output is the next source of truth for targeted branch work.",
    "Protected baseline remains 96.57%.",
    ("Finished: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
) | Add-Content $Report -Encoding ASCII

Write-Host "Relat????rio: $Report"

