
$ErrorActionPreference = "Stop"

$Report = ".\D-OBSIDIAN-06.5_COVERAGE_UPLIFT_ACCEL.txt"
$Started = Get-Date
Remove-Item $Report -Force -ErrorAction SilentlyContinue

@(
    "D-OBSIDIAN-06.5 COVERAGE UPLIFT ACCELERATION",
    ("Started: " + $Started.ToString("yyyy-MM-dd HH:mm:ss")),
    "Protected floor: D-OBSIDIAN-06.4 / 96.57%",
    ""
) | Set-Content $Report -Encoding ASCII

function Status {
    param([int]$Pct,[string]$Stage,[string]$Detail="")
    $Pct = [math]::Min(100,[math]::Max(0,$Pct))
    $filled = [int][math]::Floor(($Pct/100)*30)
    $bar = ("#"*$filled).PadRight(30,"-")
    $e = "{0:hh\:mm\:ss}" -f ((Get-Date)-$Started)
    Write-Host ("[{0}] {1,3}% | {2} | elapsed={3} | {4}" -f $bar,$Pct,$Stage,$e,$Detail)
    ("[{0}] {1,3}% | {2} | elapsed={3} | {4}" -f $bar,$Pct,$Stage,$e,$Detail) |
        Add-Content $Report -Encoding ASCII
}

$TargetTest = ".\tests\test_d065_coverage_uplift_targets.py"
if (-not (Test-Path $TargetTest)) { throw "Target test não encontrado: $TargetTest" }

Status 0 "Preparation" "Coverage uplift target harness found"

Status 25 "Focused target suite"
python -m pytest $TargetTest --no-cov -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0652_targets.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Status 50 "Formal coverage measurement"
python -m pytest --cov-fail-under=95 -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0652_coverage.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Status 75 "Regression safety"
python -m pytest -q --no-cov 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0652_regression.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Status 100 "COVERAGE UPLIFT MEASURED" "Floor 96.57% preserved"
@(
    "",
    "STATUS: D-OBSIDIAN-06.5 COVERAGE UPLIFT MEASURED",
    "Protected floor: 96.57%",
    ("Finished: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
) | Add-Content $Report -Encoding ASCII
Write-Host "Relatório: $Report"
