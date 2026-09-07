
$ErrorActionPreference = "Stop"

$test = ".\tests\test_post95_stabilization_700001_740000.py"

if (-not (Test-Path $test)) {
    throw "Arquivo não encontrado: $test"
}

$text = Get-Content -Raw -Path $test

$old = 'read_text(encoding="utf-8")'
$new = 'read_text(encoding="utf-8-sig")'

if ($text -notlike "*$old*") {
    throw "Trecho esperado não encontrado em $test"
}

$text = $text.Replace($old, $new)
Set-Content -Path $test -Value $text -Encoding UTF8

Write-Host "POST95 FIX2 aplicado."
Write-Host "Compatibilidade UTF-8 BOM corrigida no teste."
