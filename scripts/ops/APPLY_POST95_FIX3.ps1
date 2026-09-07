
$ErrorActionPreference = "Stop"

$source = ".\src\iip\portfolio\integration.py"
$test = ".\tests\test_post95_collection_fix3.py"

if (-not (Test-Path $source)) {
    throw "Arquivo não encontrado: $source"
}

$text = Get-Content -Raw -Path $source

$old = "from .factory import ProviderFactory"
$new = "from iip.providers.factory import ProviderFactory"

if ($text -notlike "*$old*") {
    throw "Import esperado não encontrado em $source"
}

$text = $text.Replace($old, $new)
Set-Content -Path $source -Value $text -Encoding utf8

@'
def test_portfolio_integration_uses_real_provider_factory():
    from iip.portfolio import integration
    from iip.providers.factory import ProviderFactory

    assert integration.ProviderFactory is ProviderFactory
'@ | Set-Content -Path $test -Encoding utf8

Write-Host "POST95 FIX3 aplicado com sucesso."
Write-Host "Import corrigido: iip.portfolio.integration -> iip.providers.factory"
Write-Host "Regressão criada: $test"
