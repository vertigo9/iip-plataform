$ErrorActionPreference = "Stop"

$Report = ".\D-OBSIDIAN-06.5_KNOWLEDGE_ADAPTER_LIFECYCLE_FIX.txt"
$Started = Get-Date
Remove-Item $Report -Force -ErrorAction SilentlyContinue

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

$Test = ".\tests\test_d065_adapter_lifecycle.py"
if (-not (Test-Path $Test)) { throw "Teste não encontrado: $Test" }

Status 0 "Preparação" "Lifecycle test encontrado"

Status 30 "Adapter lifecycle"
python -m pytest $Test --no-cov -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_06510_lifecycle.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) {
    Status 30 "Adapter lifecycle FALHOU" ("exit=" + $LASTEXITCODE)
    exit $LASTEXITCODE
}

Status 60 "CLI health"
python -m iip.cli.main health 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_06510_health.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) {
    Status 60 "CLI health FALHOU" ("exit=" + $LASTEXITCODE)
    exit $LASTEXITCODE
}

Status 80 "Certified integrated suite"
python -m pytest ".\tests\test_d064_integrated_suite.py" --no-cov -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_06510_integrated.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) {
    Status 80 "Integrated suite FALHOU" ("exit=" + $LASTEXITCODE)
    exit $LASTEXITCODE
}

Status 100 "KNOWLEDGE ADAPTER LIFECYCLE FIX PASS" "Runtime inicializado e health verificado"

@(
    "",
    "STATUS: KNOWLEDGE ADAPTER LIFECYCLE FIX PASS",
    "Production smoke blocker addressed with minimal lifecycle methods.",
    ("Finished: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
) | Add-Content $Report -Encoding ASCII

Write-Host "Relatório: $Report"
