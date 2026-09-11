# Script executado pelo Agendador de Tarefas do Windows todo dia.
# Não rode isso manualmente pra testar automação de verdade — rode
# direto "python -m iip.cli.main refresh-portfolio" no terminal.
# Esse script aqui só existe pra dar um caminho fixo e um log pro
# Agendador de Tarefas apontar.

$ErrorActionPreference = "Stop"

# Ajuste este caminho se o repositório estiver em outro lugar.
$ProjetoDir = "D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1"

$LogDir = Join-Path $ProjetoDir "logs_atualizacao"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

$DataHoje = Get-Date -Format "yyyy-MM-dd_HHmmss"
$LogFile = Join-Path $LogDir "atualizacao_$DataHoje.log"

Set-Location $ProjetoDir

Write-Output "=== Atualização iniciada em $(Get-Date) ===" | Tee-Object -FilePath $LogFile -Append
python -m iip.cli.main refresh-portfolio 2>&1 | Tee-Object -FilePath $LogFile -Append
$ExitCode = $LASTEXITCODE
Write-Output "=== Atualização terminada em $(Get-Date) — código de saída: $ExitCode ===" | Tee-Object -FilePath $LogFile -Append

exit $ExitCode
