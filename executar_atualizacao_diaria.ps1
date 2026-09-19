# Script executado pelo Agendador de Tarefas do Windows todo dia.
# Nao rode isso manualmente pra testar automacao de verdade -- rode
# direto "python -m iip.cli.main refresh-portfolio" no terminal.
# Esse script aqui so existe pra dar um caminho fixo, um log, e um
# alerta de verdade (notificacao do Windows) pro Agendador de Tarefas
# apontar.

$ErrorActionPreference = "Stop"

# Corrige a leitura de acentos vindos do Python (sem isso, os acentos
# aparecem embaralhados no console/log -- so cosmetico, os JSONs salvos
# ja estavam corretos, mas o log fica ilegivel sem isso).
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

# Ajuste este caminho se o repositorio estiver em outro lugar.
$ProjetoDir = "D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1"

$LogDir = Join-Path $ProjetoDir "logs_atualizacao"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

# Cache das respostas do bolsai SO neste processo (o plano gratuito permite 200
# chamadas/dia e o refresh + o valuation buscam dados em comum). O TTL curto garante
# que nenhum preco fique mais velho que 2 h. Nao mexe no .env.
$env:IIP_BOLSAI_CACHE_DIR = Join-Path $ProjetoDir "data\cache\bolsai"
$env:IIP_BOLSAI_CACHE_TTL_MINUTES = "120"

$DataHoje = Get-Date -Format "yyyy-MM-dd_HHmmss"
$LogFile = Join-Path $LogDir "atualizacao_$DataHoje.log"

function Notificar-Windows {
    param($Titulo, $Mensagem, $Icone)
    try {
        Add-Type -AssemblyName System.Windows.Forms
        $notify = New-Object System.Windows.Forms.NotifyIcon
        $notify.Icon = [System.Drawing.SystemIcons]::$Icone
        $notify.Visible = $true
        $notify.ShowBalloonTip(15000, $Titulo, $Mensagem, [System.Windows.Forms.ToolTipIcon]::$Icone)
        Start-Sleep -Seconds 1
    } catch {
        Write-Output "(nao consegui mostrar notificacao do Windows: $_)"
    }
}

Set-Location $ProjetoDir

Write-Output "=== Atualizacao iniciada em $(Get-Date) ===" | Tee-Object -FilePath $LogFile -Append

Write-Output "--- Checando conectividade com as fontes de dado ---" | Tee-Object -FilePath $LogFile -Append
python -m iip.cli.main health --sources 2>&1 | Tee-Object -FilePath $LogFile -Append
$HealthExitCode = $LASTEXITCODE

Write-Output "--- Atualizando carteira ---" | Tee-Object -FilePath $LogFile -Append
python -m iip.cli.main refresh-portfolio 2>&1 | Tee-Object -FilePath $LogFile -Append
$RefreshExitCode = $LASTEXITCODE

# Valuation da carteira -> vault/02_Portfolio/Valuation.md (e destaques do Dashboard).
# Se nenhuma posicao for avaliada (ex.: cota do bolsai esgotada) a nota anterior e mantida.
Write-Output "--- Valuation da carteira ---" | Tee-Object -FilePath $LogFile -Append
python -m iip.cli.main value-portfolio --report 2>&1 | Tee-Object -FilePath $LogFile -Append
$ValueExitCode = $LASTEXITCODE

Write-Output "=== Atualizacao terminada em $(Get-Date) -- health: $HealthExitCode, refresh: $RefreshExitCode, valuation: $ValueExitCode ===" | Tee-Object -FilePath $LogFile -Append

if ($HealthExitCode -ne 0) {
    # O health falha por mais de um motivo: fonte de dado fora do ar OU plugin
    # (IIP_PLUGINS) que nao carregou. A mensagem nao pode culpar so as fontes.
    $msg1 = "O health check falhou hoje: uma fonte de dado (CVM, BACEN, bolsai, etc.) nao respondeu ou um plugin (IIP_PLUGINS) nao carregou. Veja " + $LogFile
    Notificar-Windows "IIP: health check falhou" $msg1 "Warning"
}

if ($RefreshExitCode -ne 0) {
    $msg2 = "Uma ou mais posicoes falharam ao atualizar hoje. Veja " + $LogFile
    Notificar-Windows "IIP: falha na atualizacao da carteira" $msg2 "Error"
}

if ($ValueExitCode -ne 0) {
    $msg3 = "O valuation da carteira teve posicoes com erro hoje (a nota Valuation.md pode estar parcial ou desatualizada). Veja " + $LogFile
    Notificar-Windows "IIP: falha no valuation da carteira" $msg3 "Warning"
}

if ($HealthExitCode -eq 0 -and $RefreshExitCode -eq 0 -and $ValueExitCode -eq 0) {
    exit 0
}
exit 1
