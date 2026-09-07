
$ErrorActionPreference = "Stop"

$runner = ".\RUN_0645_RELEASE_GATE_PROGRESS_ENGINE.ps1"
if (-not (Test-Path $runner)) { throw "Runner não encontrado: $runner" }

$backup = $runner + ".bak5"
Copy-Item $runner $backup -Force

$text = Get-Content -Raw -Path $runner

$old = '    $code = $process.ExitCode'
$new = @'
    # Capture the process exit code deterministically before Dispose().
    $process.WaitForExit()
    $rawExitCode = $process.ExitCode
    if ($null -eq $rawExitCode) {
        throw "Python terminou, mas o exit code não pôde ser obtido."
    }
    $code = [int]$rawExitCode
'@

if (-not $text.Contains($old)) {
    throw "Linha de captura de ExitCode não encontrada."
}

$text = $text.Replace($old, $new.TrimEnd())
Set-Content -Path $runner -Value $text -Encoding utf8

Write-Host "FIX5 aplicado com sucesso."
Write-Host "Correção: captura determinística do exit code do Python."
Write-Host "Backup: $backup"
