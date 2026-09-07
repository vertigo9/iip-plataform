
$ErrorActionPreference = "Stop"

$test = ".\tests\test_d064_integrated_suite.py"
if (-not (Test-Path $test)) {
    throw "Teste integrado não encontrado: $test"
}

$backup = $test + ".bak1"
Copy-Item $test $backup -Force

$text = Get-Content -Raw -Path $test

$old = 'command = [sys.executable, "-m", "pytest", *files, "-q"]'
$new = 'command = [sys.executable, "-m", "pytest", *files, "-q", "--no-cov"]'

if (-not $text.Contains($old)) {
    throw "Comando interno esperado não encontrado."
}

$text = $text.Replace($old, $new)
Set-Content -Path $test -Value $text -Encoding utf8

Write-Host "FIX coverage collision aplicado com sucesso."
Write-Host "A suíte integrada interna agora usa --no-cov."
Write-Host "Backup: $backup"
