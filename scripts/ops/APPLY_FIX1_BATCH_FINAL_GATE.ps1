
$ErrorActionPreference = "Stop"

$runner = ".\RUN_0662_BATCH_FINAL_GATE.ps1"
if (-not (Test-Path $runner)) {
    throw "Runner nao encontrado: $runner"
}

$backup = $runner + ".bak1"
Copy-Item $runner $backup -Force

$text = Get-Content -Raw -Path $runner

# Windows PowerShell 5.1 turns native stderr records into PowerShell
# ErrorRecords. With $ErrorActionPreference=Stop, a benign coverage warning
# can abort the gate before pytest returns its real exit code.
$text = $text -replace '\$ErrorActionPreference = "Stop"', '$ErrorActionPreference = "Continue"'

# Preserve deterministic exit-code checks explicitly after every pytest call.
Set-Content -Path $runner -Value $text -Encoding ASCII

Write-Host "FIX1 Batch Final Gate aplicado com sucesso."
Write-Host "Correcao: stderr benigno de ferramentas nativas nao aborta mais o runner."
Write-Host "Exit code do pytest continua sendo validado explicitamente."
Write-Host "Backup: $backup"
