
$ErrorActionPreference = "Stop"

$path = ".\RUN_0633_DECISION_FOUNDATION.ps1"

if (-not (Test-Path $path)) {
    throw "Arquivo não encontrado: $path"
}

$text = Get-Content -Raw -Path $path

$bad = '        ".\tests\test_strategy_70001_85000.py",`r`n        ".\tests\test_strategy_contract_fix1.py"'
$good = @'
        ".\tests\test_strategy_70001_85000.py",
        ".\tests\test_strategy_contract_fix1.py"
'@.TrimEnd()

if (-not $text.Contains($bad)) {
    throw "Bloco Strategy inválido não encontrado em $path"
}

$text = $text.Replace($bad, $good)
Set-Content -Path $path -Value $text -Encoding utf8

Write-Host "FIX3 Decision Foundation aplicado com sucesso."
Write-Host "O erro literal ``r``n foi removido do bloco Strategy."
