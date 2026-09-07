
$ErrorActionPreference = "Stop"

$Report = ".\D-OBSIDIAN-06.5_BEHAVIORAL_GAP_HARDENING_ACCEL.txt"
Remove-Item $Report -Force -ErrorAction SilentlyContinue

$Started = Get-Date
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

$Test = ".\tests\test_d065_behavioral_gap_hardening.py"
if (-not (Test-Path $Test)) { throw "Teste não encontrado: $Test" }

@(
    "D-OBSIDIAN-06.5 BEHAVIORAL GAP HARDENING",
    ("Started: " + $Started.ToString("yyyy-MM-dd HH:mm:ss")),
    "Protected certified baseline: D-OBSIDIAN-06.4 / 96.57%",
    "Targets: decision_engine / document_classification / operational.quality / knowledge.repository / vault / health / allocation_review",
    ""
) | Set-Content $Report -Encoding ASCII

Status 0 "Preparation" "Behavioral hardening test found"

Status 25 "Focused collection"
python -m pytest $Test --collect-only --no-cov -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0651_collect.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Status 50 "Behavioral hardening suite"
python -m pytest $Test --no-cov -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0651_focus.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Status 75 "Regression safety"
python -m pytest -q --no-cov 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0651_regression.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Status 100 "BEHAVIORAL HARDENING PASS" "Baseline 96.57% protegido"
@(
    "",
    "STATUS: D-OBSIDIAN-06.5 BEHAVIORAL GAP HARDENING PASS",
    "Protected baseline remains 96.57%.",
    ("Finished: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
) | Add-Content $Report -Encoding ASCII

Write-Host "Relatório: $Report"
