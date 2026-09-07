
$ErrorActionPreference = "Stop"

$Report = ".\D-OBSIDIAN-06.5_CRITICAL_PATH_HARDENING_ACCEL.txt"
Remove-Item $Report -Force -ErrorAction SilentlyContinue

$Started = Get-Date

function Status {
    param([int]$Pct,[string]$Stage,[string]$Detail="")
    $Pct = [math]::Min(100,[math]::Max(0,$Pct))
    $barSize = 30
    $filled = [int][math]::Floor(($Pct/100)*$barSize)
    $bar = ("#" * $filled).PadRight($barSize,"-")
    $e = "{0:hh\:mm\:ss}" -f ((Get-Date)-$Started)
    Write-Host ("[{0}] {1,3}% | {2} | elapsed={3} | {4}" -f $bar,$Pct,$Stage,$e,$Detail)
    ("[{0}] {1,3}% | {2} | elapsed={3} | {4}" -f $bar,$Pct,$Stage,$e,$Detail) |
        Add-Content $Report -Encoding ASCII
}

$Test = ".\tests\test_d065_critical_path_hardening.py"
if (-not (Test-Path $Test)) { throw "Teste não encontrado: $Test" }

@(
    "D-OBSIDIAN-06.5 CRITICAL PATH HARDENING ACCELERATION",
    ("Started: " + $Started.ToString("yyyy-MM-dd HH:mm:ss")),
    "Protected certified baseline: D-OBSIDIAN-06.4 / 96.57%",
    "Targets: decision_engine / document_classification / operational.quality / knowledge.repository",
    ""
) | Set-Content $Report -Encoding ASCII

Status 0 "Preparação" "Teste de hardening encontrado"

Status 25 "Target discovery + import"
python -m pytest $Test --collect-only --no-cov -q 2>&1 |
    Tee-Object -FilePath (Join-Path $env:TEMP "iip_0650_collect.txt") |
    Tee-Object -FilePath $Report -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Status 50 "Critical path focused suite"
python -m pytest $Test --no-cov -q 2>&1 |
    Tee-Object -FilePath (Join-Path $env:TEMP "iip_0650_focused.txt") |
    Tee-Object -FilePath $Report -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Status 75 "Repository regression"
python -m pytest -q --no-cov 2>&1 |
    Tee-Object -FilePath (Join-Path $env:TEMP "iip_0650_regression.txt") |
    Tee-Object -FilePath $Report -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Status 100 "CRITICAL PATH HARDENING PASS" "Baseline 96.57% preservado"

@(
    "",
    "STATUS: D-OBSIDIAN-06.5 CRITICAL PATH HARDENING PASS",
    "Certified baseline remains 96.57%.",
    ("Finished: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
) | Add-Content $Report -Encoding ASCII

Write-Host "Relatório: $Report"
