
$ErrorActionPreference = "Continue"

$runner = ".\RUN_0662_BATCH_FINAL_GATE.ps1"
if (-not (Test-Path $runner)) {
    throw "Runner nao encontrado: $runner"
}

$backup = $runner + ".bak2"
Copy-Item $runner $backup -Force

$text = Get-Content -Raw -Path $runner

$old = @'
Status 85 "Coverage final gate"
python -m pytest --cov=iip --cov-fail-under=95 -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0662_coverage.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
'@

$new = @'
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
'@

if (-not $text.Contains($old)) {
    throw "Bloco de coverage esperado nao encontrado."
}

$text = $text.Replace($old, $new)
Set-Content -Path $runner -Value $text -Encoding ASCII

Write-Host "FIX2 Coverage Isolation aplicado com sucesso."
Write-Host "Correcao: coverage.py executado em estado limpo e com processo dedicado."
Write-Host "Exit code do coverage continua sendo validado explicitamente."
Write-Host "Backup: $backup"
