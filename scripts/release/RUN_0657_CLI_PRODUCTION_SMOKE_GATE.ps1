$ErrorActionPreference = "Stop"

$Report = ".\D-OBSIDIAN-06.5_CLI_PRODUCTION_SMOKE_GATE.txt"
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

@(
    "D-OBSIDIAN-06.5 CLI PRODUCTION SMOKE GATE",
    ("Started: " + $Started.ToString("yyyy-MM-dd HH:mm:ss")),
    "Mode: local production-like / read-only",
    "HTTP smoke disabled: project exposes CLI health/status, not an ASGI/WSGI app",
    ""
) | Set-Content $Report -Encoding ASCII

Status 10 "Environment" "IIP_ENVIRONMENT=$env:IIP_ENVIRONMENT"

Status 30 "CLI health"
python -m iip.cli.main health 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0657_cli_health.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) {
    Status 30 "CLI health FALHOU" ("exit=" + $LASTEXITCODE)
    exit $LASTEXITCODE
}

Status 50 "CLI status"
python -m iip.cli.main status 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0657_cli_status.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) {
    Status 50 "CLI status FALHOU" ("exit=" + $LASTEXITCODE)
    exit $LASTEXITCODE
}

Status 65 "CLI modules"
python -m iip.cli.main modules 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0657_cli_modules.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) {
    Status 65 "CLI modules FALHOU" ("exit=" + $LASTEXITCODE)
    exit $LASTEXITCODE
}

Status 80 "CLI knowledge status"
python -m iip.cli.main knowledge-status 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0657_cli_knowledge.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) {
    Status 80 "CLI knowledge status FALHOU" ("exit=" + $LASTEXITCODE)
    exit $LASTEXITCODE
}

Status 90 "Certified integrated suite"
python -m pytest ".\tests\test_d064_integrated_suite.py" --no-cov -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0657_integrated.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) {
    Status 90 "Certified integrated suite FALHOU" ("exit=" + $LASTEXITCODE)
    exit $LASTEXITCODE
}

Status 100 "CLI PRODUCTION SMOKE PASS" "validação local read-only concluída"

@(
    "",
    "STATUS: D-OBSIDIAN-06.5 CLI PRODUCTION SMOKE PASS",
    "No production deployment or data mutation performed.",
    "This validates the real CLI entrypoint exposed by pyproject.toml.",
    ("Finished: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
) | Add-Content $Report -Encoding ASCII

Write-Host ""
Write-Host "Relatório: $Report"
# HTTP production smoke is opt-in and only runs when explicitly enabled.
if ($env:IIP_PROD_HEALTH_URL) {
    $env:IIP_RUN_PROD_HTTP_SMOKE = "1"
}
