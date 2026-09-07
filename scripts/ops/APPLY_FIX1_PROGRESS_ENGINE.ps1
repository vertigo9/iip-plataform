
$ErrorActionPreference = "Stop"

$path = ".\RUN_0645_RELEASE_GATE_PROGRESS_ENGINE.ps1"
if (-not (Test-Path $path)) { throw "Executor não encontrado: $path" }

$backup = $path + ".bak1"
Copy-Item $path $backup -Force

$text = Get-Content -Raw -Path $path

$old = @'
    foreach ($arg in $PythonArguments) {
        [void]$psi.ArgumentList.Add($arg)
    }
'@

$new = @'
    # Windows PowerShell 5.1 does not expose ProcessStartInfo.ArgumentList.
    # Build one safely quoted Arguments string instead.
    $quoted = foreach ($arg in $PythonArguments) {
        if ($arg -match '[\s"]') {
            '"' + ($arg -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"'
        } else {
            $arg
        }
    }
    $psi.Arguments = ($quoted -join ' ')
'@

if (-not $text.Contains($old.TrimEnd())) {
    throw "Bloco ArgumentList esperado não encontrado."
}

$text = $text.Replace($old.TrimEnd(), $new.TrimEnd())
Set-Content -Path $path -Value $text -Encoding utf8

Write-Host "FIX1 Progress Engine aplicado com sucesso."
Write-Host "Correção: compatibilidade com Windows PowerShell 5.1."
Write-Host "Substituído ProcessStartInfo.ArgumentList por ProcessStartInfo.Arguments."
Write-Host "Backup: $backup"
