"""PR #44: o passo "Monitoramento de pesos-alvo" no job diário.

Estes testes são estáticos (leem o texto do ``.ps1``), como todo o resto da suíte que confere
``executar_atualizacao_diaria.ps1`` -- o script nunca é executado de verdade pelo pytest (a
validação de execução real é manual, na branch, e depois o job agendado das 08:00 confirma).

Escopo confirmado aqui: o passo existe entre Camadas e Macro, roda `--report --alert-file` sem
`--dry-run`, o Dashboard continua rodando incondicionalmente depois dele, o código de saída
entra no resumo e na agregação, há aviso dedicado de falha, a notificação de desvio novo não é
tratada como falha do job, e `decide-portfolio`/`rebalancing_alerts.py` continuam fora do que
este passo chama.
"""

from __future__ import annotations

import re
from pathlib import Path

SCRIPT_PATH = Path("executar_atualizacao_diaria.ps1")


def _script() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


def _index(script: str, marker: str) -> int:
    index = script.find(marker)
    assert index != -1, f"marcador não encontrado: {marker!r}"
    return index


# --- posição: Camadas -> Monitoramento -> Macro ---------------------------------------------


def test_the_step_sits_between_layers_and_macro():
    script = _script()

    layers = _index(script, '"--- Camadas do patrimonio ---"')
    monitoring = _index(script, '"--- Monitoramento de pesos-alvo ---"')
    macro = _index(script, '"--- Macro ---"')

    assert layers < monitoring < macro


def test_the_dashboard_step_still_runs_unconditionally_after_monitoring():
    script = _script()

    exit_code_captured = _index(script, "$MonitoringExitCode = $LASTEXITCODE")
    dashboard = _index(script, '"--- Dashboard ---"')
    assert exit_code_captured < dashboard

    # entre a captura do exit code e o Dashboard rodar, nada mais referencia
    # $MonitoringExitCode -- o Dashboard não é pulado nem condicionado a ele; roda
    # incondicional, como os outros 13 passos (mesmo padrão sequencial do script inteiro)
    between = script[
        exit_code_captured + len("$MonitoringExitCode = $LASTEXITCODE") : dashboard
    ]
    assert "$MonitoringExitCode" not in between


# --- o comando: --report --alert-file, sem --dry-run, sem decide-portfolio/rebalancing ------


def test_the_command_uses_report_and_alert_file_but_not_dry_run():
    script = _script()

    match = re.search(r"^python .*monitoring-events.*$", script, re.MULTILINE)
    assert match, "chamada a monitoring-events não encontrada"
    line = match.group(0)

    assert "--report" in line
    assert "--alert-file" in line
    assert "--dry-run" not in line


def test_the_alert_file_is_cleared_before_running_like_the_other_alert_steps():
    script = _script()

    assert (
        "if (Test-Path $AlertaMonitoramento) { Remove-Item $AlertaMonitoramento -Force }"
        in script
    )


def test_this_step_does_not_call_decide_portfolio_or_rebalancing_alerts():
    script = _script()
    monitoring = _index(script, '"--- Monitoramento de pesos-alvo ---"')
    macro = _index(script, '"--- Macro ---"')
    step = script[monitoring:macro]

    assert "decide-portfolio" not in step
    # checa INVOCAÇÃO (não o comentário do passo, que cita o nome de propósito para deixar
    # explícito que ele fica fora): nenhuma linha do script roda rebalancing_alerts.py
    assert not re.search(r"^python .*rebalancing_alerts", script, re.MULTILINE)
    # a política em si nunca é editada pelo job (só o comando de edição/validação, que segue
    # fora -- ver test_the_daily_job_does_not_run_the_target_policy_command_directly)
    assert "target-policy" not in script


# --- robustez: exit code capturado, no resumo, na agregação, com aviso dedicado -------------


def test_the_exit_code_is_captured():
    script = _script()

    assert "$MonitoringExitCode = $LASTEXITCODE" in script


def test_the_exit_code_is_in_the_final_summary_line():
    script = _script()

    summary = re.search(r"=== Atualizacao terminada.*===", script)
    assert summary, "linha de resumo final não encontrada"
    assert "monitoramento: $MonitoringExitCode" in summary.group(0)


def test_the_exit_code_is_part_of_the_success_aggregation():
    script = _script()

    aggregation = re.search(r"if \(\$HealthExitCode -eq 0.*?\) \{", script, re.DOTALL)
    assert aggregation, "condição de agregação do exit code não encontrada"
    assert "$MonitoringExitCode -eq 0" in aggregation.group(0)


def test_there_is_a_dedicated_failure_notification():
    script = _script()

    match = re.search(r"if \(\$MonitoringExitCode -ne 0\) \{(.*?)\}", script, re.DOTALL)
    assert match, "bloco de notificação de falha do monitoramento não encontrado"
    assert "Notificar-Windows" in match.group(1)
    assert '"Warning"' in match.group(1)


def test_a_failing_monitoring_step_does_not_stop_the_rest_of_the_job():
    """`$ErrorActionPreference = "Stop"` só afeta erros nativos do PowerShell -- o código de
    saída de um processo externo (`python ...`) nunca interrompe o script; é só capturado.
    Confirma isso de forma estrutural: nada entre a captura de $MonitoringExitCode e o fim do
    script está condicionado a ele, exceto o próprio aviso de falha e a agregação final.
    """
    script = _script()
    after = script[_index(script, "$MonitoringExitCode = $LASTEXITCODE") :]

    guarded_blocks = re.findall(r"if \([^)]*\$MonitoringExitCode[^)]*\)", after)
    # só os dois blocos esperados usam a variável num "if": o aviso de falha dedicado e a
    # agregação final de sucesso -- nenhum outro passo (macro, sensibilidade, dashboard...)
    # é pulado por causa dela
    assert len(guarded_blocks) == 2


# --- notificação: arquivo de alerta não é falha do job, toast Warning só para desvio novo ---


def test_the_alert_file_notification_is_not_counted_as_a_job_failure():
    script = _script()

    # "{\n" (não "{ Remove-Item") distingue este bloco do que apaga o arquivo antes de rodar
    match = re.search(
        r"if \(Test-Path \$AlertaMonitoramento\) \{\n(.*?)\n\}", script, re.DOTALL
    )
    assert match, "bloco de notificação de desvio novo não encontrado"
    body = match.group(1)

    assert (
        "ExitCode" not in body
    )  # não altera nem lê nenhuma variável de código de saída
    assert "Notificar-Windows" in body
    assert '"Warning"' in body


def test_the_alert_file_block_comes_after_the_exit_code_aggregation_condition_is_built():
    """A leitura de $AlertaMonitoramento fica junto dos outros blocos de notificação
    informativa (série, macro, decisão), não misturada com a checagem de falha."""
    script = _script()

    macro_alert_block = _index(script, "if (Test-Path $AlertaMacro)")
    monitoring_alert_block = _index(
        script, "if (Test-Path $AlertaMonitoramento) {\n    $Monitoramento"
    )
    aggregation = _index(script, "if ($HealthExitCode -eq 0")

    assert macro_alert_block < monitoring_alert_block < aggregation
