
$ErrorActionPreference = "Stop"

$path = ".\RUN_0633_DECISION_FOUNDATION.ps1"

if (-not (Test-Path $path)) {
    throw "Arquivo não encontrado: $path"
}

$text = Get-Content -Raw -Path $path
$old = '        ".\tests\test_strategy_namespace_imports.py"'
$new = '        ".\tests\test_strategy_70001_85000.py",`r`n        ".\tests\test_strategy_contract_fix1.py"'

if ($text -notlike "*$old*") {
    throw "Referência esperada não encontrada em $path"
}

$text = $text.Replace($old, $new)
Set-Content -Path $path -Value $text -Encoding utf8

Write-Host "FIX2 Decision Foundation aplicado com sucesso."
Write-Host "Strategy agora usa os testes reais da árvore."
