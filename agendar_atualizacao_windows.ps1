# Rode ISSO UMA VEZ SO, como Administrador, pra registrar a atualizacao
# diaria no Agendador de Tarefas do Windows de verdade. Depois disso,
# o Windows chama "executar_atualizacao_diaria.ps1" sozinho, todo dia,
# mesmo sem voce ter aberto o PowerShell.
#
# Pra rodar como Administrador: botao direito no arquivo -> "Executar
# com o PowerShell" (se der erro de permissao, abre o PowerShell como
# Administrador manualmente e roda o script de la).

$ErrorActionPreference = "Stop"

$NomeTarefa = "IIP_AtualizacaoCarteiraDiaria"
$ProjetoDir = "D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1"
$ScriptExecucao = Join-Path $ProjetoDir "executar_atualizacao_diaria.ps1"
$HorarioExecucao = "08:00"

if (-not (Test-Path $ScriptExecucao)) {
    Write-Error "Nao achei $ScriptExecucao -- confere se o caminho do projeto esta certo neste script e no executar_atualizacao_diaria.ps1."
    exit 1
}

$ArgumentoAcao = '-NoProfile -ExecutionPolicy Bypass -File "' + $ScriptExecucao + '"'
$Acao = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $ArgumentoAcao

$Gatilho = New-ScheduledTaskTrigger -Daily -At $HorarioExecucao

$Configuracoes = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

$Descricao = "Atualiza dados da carteira IIP (CVM + bolsai/brapi) todo dia as " + $HorarioExecucao + "."

Register-ScheduledTask -TaskName $NomeTarefa -Action $Acao -Trigger $Gatilho -Settings $Configuracoes -Description $Descricao -Force

Write-Output ""
Write-Output ("Tarefa '" + $NomeTarefa + "' registrada -- vai rodar todo dia as " + $HorarioExecucao + ".")
Write-Output "Pra testar agora, sem esperar o horario:"
Write-Output ("  Start-ScheduledTask -TaskName '" + $NomeTarefa + "'")
Write-Output ""
Write-Output "Pra ver se rodou e o resultado:"
Write-Output ("  Get-ScheduledTaskInfo -TaskName '" + $NomeTarefa + "'")
Write-Output ""
Write-Output "Pra remover a tarefa (se precisar desfazer):"
Write-Output ("  Unregister-ScheduledTask -TaskName '" + $NomeTarefa + "' -Confirm:$false")
