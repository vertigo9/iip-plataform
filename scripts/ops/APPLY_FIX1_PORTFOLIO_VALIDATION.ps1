
$ErrorActionPreference = "Stop"

$source = ".\src\iip\portfolio\validation.py"
$test = ".\tests\test_portfolio_validation_import_fix1.py"

if (-not (Test-Path $source)) {
    throw "Arquivo de produção não encontrado: $source"
}

$text = Get-Content -Raw -Path $source

$old = "from .operations import ProviderOperations"
$new = "from iip.providers.operations import ProviderOperations"

if ($text -notlike "*$old*") {
    throw "Import esperado não encontrado em $source"
}

$text = $text.Replace($old, $new)
Set-Content -Path $source -Value $text -Encoding UTF8

@'
def test_portfolio_provider_validation_uses_real_provider_operations():
    from iip.portfolio.validation import ProviderValidator
    from iip.providers.operations import ProviderOperations

    assert ProviderValidator
    assert ProviderOperations
'@ | Set-Content -Path $test -Encoding UTF8

Write-Host "FIX1 PortfolioValidation aplicado com sucesso."
Write-Host "Produção corrigida: $source"
Write-Host "Regressão criada: $test"
