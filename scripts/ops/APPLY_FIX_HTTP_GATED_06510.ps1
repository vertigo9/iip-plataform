
$ErrorActionPreference = "Stop"

$test = ".\tests\test_d065_production_smoke.py"
$runner = ".\RUN_0657_CLI_PRODUCTION_SMOKE_GATE.ps1"

if (-not (Test-Path $test)) {
    throw "Teste não encontrado: $test"
}
if (-not (Test-Path $runner)) {
    throw "Runner não encontrado: $runner"
}

Copy-Item $test ($test + ".bak-http-gate") -Force
Copy-Item $runner ($runner + ".bak-http-gate") -Force

$text = Get-Content -Raw -Path $test

$old = @'
    url = os.getenv("IIP_PROD_HEALTH_URL")
    if not url:
        pytest.skip("IIP_PROD_HEALTH_URL não configurada; smoke HTTP externo não executado.")
'@

$new = @'
    # HTTP production smoke is intentionally opt-in. This test file is also
    # imported by the broad integrated regression, where external HTTP checks
    # must not leak into the test environment.
    run_http = os.getenv("IIP_RUN_PROD_HTTP_SMOKE", "").strip().lower()
    if run_http not in {"1", "true", "yes"}:
        pytest.skip(
            "IIP_RUN_PROD_HTTP_SMOKE não habilitado; health HTTP reservado "
            "ao Production Smoke Gate standalone."
        )

    url = os.getenv("IIP_PROD_HEALTH_URL")
    if not url:
        pytest.skip("IIP_PROD_HEALTH_URL não configurada; smoke HTTP não executado.")
'@

if (-not $text.Contains($old)) {
    throw "Bloco de health HTTP esperado não encontrado."
}

$text = $text.Replace($old, $new)
Set-Content -Path $test -Value $text -Encoding utf8

$runnerText = Get-Content -Raw -Path $runner

# Standalone CLI smoke must explicitly enable the HTTP gate only when the user
# configured a health URL. Otherwise all other smoke checks remain valid.
$marker = 'if (-not $env:IIP_PROD_HEALTH_URL) {'
if (-not $runnerText.Contains($marker)) {
    # If this is the CLI runner, simply append an explicit opt-in note.
    $append = @'
# HTTP production smoke is opt-in and only runs when explicitly enabled.
if ($env:IIP_PROD_HEALTH_URL) {
    $env:IIP_RUN_PROD_HTTP_SMOKE = "1"
}
'@
    Add-Content -Path $runner -Value $append -Encoding utf8
}

Write-Host "FIX HTTP GATE aplicado com sucesso."
Write-Host "A integração ampla não executará HTTP externo/local implicitamente."
Write-Host "O smoke standalone poderá habilitar HTTP explicitamente."
Write-Host "Backups criados:"
Write-Host ".\tests\test_d065_production_smoke.py.bak-http-gate"
Write-Host ".\RUN_0657_CLI_PRODUCTION_SMOKE_GATE.ps1.bak-http-gate"
