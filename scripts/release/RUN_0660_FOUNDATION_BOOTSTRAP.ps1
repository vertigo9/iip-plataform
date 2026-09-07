$ErrorActionPreference = "Stop"

$Report = ".\D-OBSIDIAN-06.6_FOUNDATION_BOOTSTRAP.txt"
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

$Test = ".\tests\test_d066_foundation_targets.py"
if (-not (Test-Path $Test)) { throw "Teste 06.6 não encontrado: $Test" }

@(
    "D-OBSIDIAN-06.6 FOUNDATION BOOTSTRAP",
    ("Started: " + $Started.ToString("yyyy-MM-dd HH:mm:ss")),
    "Protected baseline: D-OBSIDIAN-06.5 / 96.57%",
    "Mode: foundation only; no production deployment",
    ""
) | Set-Content $Report -Encoding ASCII

Status 10 "Baseline protection" "96.57% floor"

Status 30 "Foundation target collection"
python -m pytest $Test --collect-only --no-cov -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0660_collect.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Status 55 "Foundation target suite"
python -m pytest $Test --no-cov -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0660_foundation.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Status 80 "Regression safety"
python -m pytest -q --no-cov 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0660_regression.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Status 100 "D-OBSIDIAN-06.6 FOUNDATION PASS" "baseline protegido"
@(
    "",
    "STATUS: D-OBSIDIAN-06.6 FOUNDATION PASS",
    "No production deployment performed.",
    "Protected baseline remains 96.57%.",
    ("Finished: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
) | Add-Content $Report -Encoding ASCII

Write-Host "Relatório: $Report"
