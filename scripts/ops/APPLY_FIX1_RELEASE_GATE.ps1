
$ErrorActionPreference = "Stop"

$path = ".\RUN_0645_RELEASE_GATE_CERTIFICATION.ps1"
if (-not (Test-Path $path)) { throw "Executor não encontrado: $path" }

$backup = $path + ".bak1"
Copy-Item $path $backup -Force

$text = Get-Content -Raw -Path $path

# Replace the fragile function/parameter pattern with a runner that uses
# explicitly named arguments, avoiding collision with PowerShell's automatic
# $args variable.
$start = $text.IndexOf('function Run-Step {')
$end = $text.IndexOf('$total = 4')

if ($start -lt 0 -or $end -lt 0 -or $end -le $start) {
    throw "Bloco Run-Step esperado não encontrado."
}

$replacement = @'
function Run-Step {
    param(
        [string]$Stage,
        [string[]]$PythonArguments
    )

    Write-Host ""
    Status $script:step $script:total $Stage "executando"

    & python @PythonArguments 2>&1 |
        Tee-Object -FilePath (Join-Path $env:TEMP ("iip_064_gate_{0}.txt" -f $script:step)) |
        Tee-Object -FilePath $report -Append

    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        Status $script:step $script:total ($Stage + " FALHOU") ("exit=" + $exitCode)
        exit $exitCode
    }

    $script:step++
    Status $script:step $script:total ($Stage + " PASSOU") "exit=0"
}

'@

$text = $text.Substring(0, $start) + $replacement + $text.Substring($end)
Set-Content -Path $path -Value $text -Encoding utf8

Write-Host "FIX1 Release Gate aplicado com sucesso."
Write-Host "Correção: parâmetro Args renomeado para PythonArguments."
Write-Host "Backup: $backup"
