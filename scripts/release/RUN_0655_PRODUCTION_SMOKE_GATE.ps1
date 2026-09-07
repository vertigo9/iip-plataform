$ErrorActionPreference = "Stop"

$Report = ".\D-OBSIDIAN-06.5_PRODUCTION_SMOKE_GATE.txt"
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
    "D-OBSIDIAN-06.5 PRODUCTION SMOKE GATE - LOCALHOST MODE",
    ("Started: " + $Started.ToString("yyyy-MM-dd HH:mm:ss")),
    "RC baseline: 96.57%",
    "Mode: read-only / non-destructive",
    ""
) | Set-Content $Report -Encoding ASCII

$Test = ".\tests\test_d065_production_smoke.py"
if (-not (Test-Path $Test)) {
    throw "Teste de produÃ§Ã£o nÃ£o encontrado: $Test"
}

# Safe defaults for local smoke mode.
if (-not $env:IIP_ENVIRONMENT) {
    $env:IIP_ENVIRONMENT = "production"
}

if (-not $env:IIP_PROD_HEALTH_URL) {
    $env:IIP_PROD_HEALTH_URL = "http://127.0.0.1:8000/health"
}

$url = $env:IIP_PROD_HEALTH_URL

Status 10 "Localhost configuration" ("environment=" + $env:IIP_ENVIRONMENT + " | health=" + $url)

if ($url -notmatch '^https?://(127\.0\.0\.1|localhost)(:\d+)?(/.*)?$') {
    throw "Modo localhost exige URL em 127.0.0.1 ou localhost. Atual: $url"
}

Status 30 "Localhost production smoke"
python -m pytest $Test --no-cov -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0656_localhost_smoke.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) {
    Status 30 "Localhost production smoke FALHOU" ("exit=" + $LASTEXITCODE)
    exit $LASTEXITCODE
}

Status 60 "Certified integrated suite"
python -m pytest ".\tests\test_d064_integrated_suite.py" --no-cov -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0656_integrated.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) {
    Status 60 "Certified integrated suite FALHOU" ("exit=" + $LASTEXITCODE)
    exit $LASTEXITCODE
}

if (Test-Path ".\tests\test_d065_critical_path_hardening.py") {
    Status 80 "Critical path smoke"
    python -m pytest ".\tests\test_d065_critical_path_hardening.py" --no-cov -q 2>&1 |
        Tee-Object (Join-Path $env:TEMP "iip_0656_critical.txt") |
        Tee-Object $Report -Append
    if ($LASTEXITCODE -ne 0) {
        Status 80 "Critical path smoke FALHOU" ("exit=" + $LASTEXITCODE)
        exit $LASTEXITCODE
    }
}

Status 100 "LOCALHOST SMOKE GATE PASS" "validaÃ§Ã£o local concluÃ­da"

@(
    "",
    "STATUS: LOCALHOST SMOKE GATE PASS",
    ("Environment marker: " + $env:IIP_ENVIRONMENT),
    ("Health endpoint: " + $url),
    "Mode: read-only / non-destructive",
    "This does not claim external production was tested.",
    ("Finished: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
) | Add-Content $Report -Encoding ASCII

Write-Host ""
Write-Host "RelatÃ³rio: $Report"
