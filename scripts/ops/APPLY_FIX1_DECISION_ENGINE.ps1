
$ErrorActionPreference = "Stop"

$runner = ".\RUN_0661_DECISION_ENGINE_HARDENING.ps1"
if (-not (Test-Path $runner)) {
    throw "Runner nao encontrado: $runner"
}

$backup = $runner + ".bak1"
Copy-Item $runner $backup -Force

$text = Get-Content -Raw -Path $runner

# Replace the UTF-8/non-ASCII status string that breaks Windows PowerShell 5.1
# parser compatibility when the file is saved/decoded inconsistently.
$text = [regex]::Replace(
    $text,
    'Status 60 "Decision engine coverage".*?if \(\$focusCode -ne 0\) \{\s*Status 60.*?\r?\n\}',
    @'
Status 60 "Decision engine coverage"
python -m pytest ".\tests\test_decision_301_500.py" ".\tests\test_portfolio_decision_60001_70000.py" ".\tests\test_d066_decision_engine_hardening.py" --cov=iip.decision.decision_engine --cov-report=term-missing -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0661_coverage.txt") |
    Tee-Object $Report -Append

$focusCode = $LASTEXITCODE
if ($focusCode -ne 0) {
    Status 60 "Decision engine coverage reported failure" ("exit=" + $focusCode + " - report retained for analysis")
}
'@,
    [System.Text.RegularExpressions.RegexOptions]::Singleline
)

# Normalize the runner to ASCII so Windows PowerShell 5.1 cannot misread
# accented characters later in the file.
$ascii = [System.Text.Encoding]::ASCII.GetString(
    [System.Text.Encoding]::UTF8.GetBytes($text)
)
Set-Content -Path $runner -Value $ascii -Encoding ASCII

Write-Host "FIX1 Decision Engine aplicado com sucesso."
Write-Host "Correcao: runner normalizado para ASCII e string nao-ASCII removida."
Write-Host "Compatibilidade: Windows PowerShell 5.1."
Write-Host "Backup: $backup"
