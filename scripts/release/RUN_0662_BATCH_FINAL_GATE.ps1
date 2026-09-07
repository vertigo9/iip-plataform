$ErrorActionPreference = "Continue"

$Report = ".\D-OBSIDIAN-06.6_BATCH_FINAL_GATE.txt"
$Started = Get-Date
Remove-Item $Report -Force -ErrorAction SilentlyContinue

function Status {
    param([int]$Pct,[string]$Stage,[string]$Detail="")
    $Pct = [math]::Min(100,[math]::Max(0,$Pct))
    $filled = [int][math]::Floor(($Pct/100)*30)
    $bar = ("#"*$filled).PadRight(30,"-")
    $elapsed = "{0:hh\:mm\:ss}" -f ((Get-Date)-$Started)
    $line = "[{0}] {1,3}% | {2} | elapsed={3} | {4}" -f $bar,$Pct,$Stage,$elapsed,$Detail
    Write-Host $line
    Add-Content $Report $line -Encoding ASCII
}

@(
    "D-OBSIDIAN-06.6 BATCH IMPLEMENTATION + FINAL GATE",
    ("Started: " + $Started.ToString("yyyy-MM-dd HH:mm:ss")),
    "Protected baseline: 96.57%",
    "Current known regression: 846 passed / 5 skipped / 0 failed",
    ""
) | Set-Content $Report -Encoding ASCII

$targets = @(
    ".\tests\test_d066_foundation_targets.py",
    ".\tests\test_d066_decision_engine_hardening.py",
    ".\tests\test_d065_adapter_lifecycle.py"
) | Where-Object { Test-Path $_ }

Status 10 "Batch target collection" ("targets=" + $targets.Count)
python -m pytest $targets --collect-only --no-cov -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0662_collect.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Status 30 "Batch focused tests"
python -m pytest $targets --no-cov -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0662_focus.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Status 50 "Decision + portfolio behavior"
python -m pytest `
    ".\tests\test_decision_301_500.py" `
    ".\tests\test_portfolio_decision_60001_70000.py" `
    ".\tests\test_portfolio_decision_fix1.py" `
    ".\tests\test_portfolio_decision_fix2.py" `
    ".\tests\test_portfolio_decision_fix3_opportunity.py" `
    --no-cov -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0662_decision.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Status 70 "Full repository final regression"
python -m pytest --no-cov -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0662_regression.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Status 85 "Coverage final gate"

# Run coverage in a fresh Python process with coverage data removed first.
# This prevents the preceding regression process from affecting coverage.py.
$coverageData = ".coverage"
Remove-Item $coverageData -Force -ErrorAction SilentlyContinue
Get-ChildItem ".coverage.*" -File -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue

python -m coverage erase 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0662_coverage_erase.txt") |
    Tee-Object $Report -Append

python -m pytest --cov=iip --cov-fail-under=95 --cov-report=term-missing -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0662_coverage.txt") |
    Tee-Object $Report -Append

$coverageCode = $LASTEXITCODE
if ($coverageCode -ne 0) {
    Status 85 "Coverage final gate FAIL" ("exit=" + $coverageCode)
    exit $coverageCode
}

Status 95 "Final collection sanity"
python -m pytest --collect-only --no-cov -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0662_sanity.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Status 100 "D-OBSIDIAN-06.6 BATCH FINAL GATE PASS" "consolidated validation complete"

@(
    "",
    "STATUS: D-OBSIDIAN-06.6 BATCH FINAL GATE PASS",
    "Protected baseline: 96.57%",
    "No automatic production deployment performed.",
    ("Finished: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
) | Add-Content $Report -Encoding ASCII

Write-Host "Relat??rio: $Report"



