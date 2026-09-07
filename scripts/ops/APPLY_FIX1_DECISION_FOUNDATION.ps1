
$ErrorActionPreference = "Stop"

$path = ".\RUN_0633_DECISION_FOUNDATION.ps1"

if (-not (Test-Path $path)) {
    throw "Arquivo não encontrado: $path"
}

$text = Get-Content -Raw -Path $path

$old = '        ".\tests\test_decision_surfaces.py"'
$new = '        ".\tests\test_decision_301_500.py"'

if ($text -notlike "*$old*") {
    throw "Referência esperada não encontrada em $path"
}

$text = $text.Replace($old, $new)
Set-Content -Path $path -Value $text -Encoding utf8

Write-Host "FIX1 Decision Foundation aplicado com sucesso."
Write-Host "Substituído: test_decision_surfaces.py"
Write-Host "Por: test_decision_301_500.py"
