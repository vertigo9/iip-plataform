# Rode ISSO UMA VEZ SÓ, como Administrador, pra registrar a atualização
# diária no Agendador de Tarefas do Windows de verdade. Depois disso,
# o Windows chama "executar_atualizacao_diaria.ps1" sozinho, todo dia,
# mesmo sem você ter aberto o PowerShell.
#
# Pra rodar como Administrador: botão direito no arquivo -> "Executar
# com o PowerShell" (se der erro de permissão, abre o PowerShell como
# Administrador manualmente e roda o script de lá).

$ErrorActionPreference = "Stop"

$NomeTarefa = "IIP_AtualizacaoCarteiraDiaria"
$ProjetoDir = "D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1"
$ScriptExecucao = Join-Path $ProjetoDir "executar_atualizacao_diaria.ps1"
$HorarioExecucao = "08:00"

if (-not (Test-Path $ScriptExecucao)) {
    Write-Error "Não achei $ScriptExecucao — confere se o caminho do projeto está certo neste script e no executar_atualizacao_diaria.ps1."
    exit 1
}

$Acao = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptExecucao`""

$Gatilho = New-ScheduledTaskTrigger -Daily -At $HorarioExecucao

$Configuracoes = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask `
    -TaskName $NomeTarefa `
    -Action $Acao `
    -Trigger $Gatilho `
    -Settings $Configuracoes `
    -Description "Atualiza dados da carteira IIP (CVM + bolsai/brapi) todo dia às $HorarioExecucao." `
    -Force

Write-Output ""
Write-Output "Tarefa '$NomeTarefa' registrada — vai rodar todo dia às $HorarioExecucao."
Write-Output "Pra testar agora, sem esperar o horário:"
Write-Output "  Start-ScheduledTask -TaskName '$NomeTarefa'"
Write-Output ""
Write-Output "Pra ver se rodou e o resultado:"
Write-Output "  Get-ScheduledTaskInfo -TaskName '$NomeTarefa'"
Write-Output ""
Write-Output "Pra remover a tarefa (se precisar desfazer):"
Write-Output "  Unregister-ScheduledTask -TaskName '$NomeTarefa' -Confirm:`$false"
