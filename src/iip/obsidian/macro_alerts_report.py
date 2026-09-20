"""Os alertas macro como nota do vault: ``07_Research/Macro/Alertas_Macro.md``.

Sobrescrita a cada execução. Separa os alertas econômicos dos avisos de dado, lista o que já foi
emitido e ainda não rearmou ("em observação") e traz todas as regras com a medida atual, a
janela e o limiar, além da rastreabilidade (versão e hash das regras). É contexto: não decide
aporte nem peso.
"""

from __future__ import annotations

from pathlib import Path

from iip.macro.alerts import (
    CHANGE_KINDS,
    CONTEXT_NOTICE,
    LEVEL_ABOVE,
    LEVEL_BELOW,
    LEVEL_CHANGE,
    WINDOW_CHANGE,
    YOY_CHANGE,
    Alert,
    AlertRule,
    AlertRun,
    RuleEvaluation,
    _label,
    _num,
    _signed,
)
from iip.macro.contract import INDICATORS
from iip.obsidian.dashboard import (
    MACRO_ALERTS_ACTIVE_KEY,
    MACRO_ALERTS_DATA_KEY,
    MACRO_ALERTS_NEW_KEY,
    MACRO_ALERTS_RULES_KEY,
    MACRO_ALERTS_WATCH_KEY,
)
from iip.obsidian.frontmatter import flow_line

REPORT_RELATIVE_PATH = Path("07_Research") / "Macro" / "Alertas_Macro.md"

STATUS_LABELS = {
    "ativo": "**ATIVO**",
    "sem_alerta": "sem alerta",
    "defasado": "dado defasado",
    "sem_dados": "sem dados",
    "insuficiente": "histórico insuficiente",
}
_SEVERITY = {
    "atencao": "Atenção",
    "informativo": "Informativo",
    "dado": "Aviso de dado",
}
_KIND = {
    WINDOW_CHANGE: "variação em janela",
    YOY_CHANGE: "variação em 12 meses",
    LEVEL_ABOVE: "nível acima",
    LEVEL_BELOW: "nível abaixo",
    LEVEL_CHANGE: "mudança de nível",
}


def _window(rule: AlertRule) -> str:
    if rule.kind == WINDOW_CHANGE:
        return f"{rule.window_days} dias"
    if rule.kind == YOY_CHANGE:
        return "12 meses"
    if rule.kind == LEVEL_CHANGE:
        return f"eventos dos últimos {rule.retain_days} dias"
    return "nível atual"


def _threshold(rule: AlertRule) -> str:
    if rule.threshold is None:
        return "qualquer alteração"
    if rule.kind in CHANGE_KINDS:
        sign = {"up": "+", "down": "-", "both": "±"}[rule.direction]
        unit = " p.p." if rule.unit == "pp" else "%"
        return f"{sign}{_num(rule.threshold)}{unit}"
    return f"{'>' if rule.kind == LEVEL_ABOVE else '<'} {_num(rule.threshold)}"


def current_measure(evaluation: RuleEvaluation) -> str:
    latest = evaluation.latest
    rule = evaluation.rule
    if latest is None:
        return "—"
    if rule.kind == LEVEL_CHANGE:
        if evaluation.event_reference:
            return (
                f"última mudança {_num(evaluation.event_from)} -> "
                f"{_num(evaluation.event_to)} em {_label(evaluation.event_reference)}"
            )
        return f"nível {_num(latest.value)}, sem mudança na série"
    if rule.kind in (LEVEL_ABOVE, LEVEL_BELOW):
        return f"{_num(latest.value)} ({_label(latest.reference)})"
    if latest.measure is None:
        return (
            f"{_num(latest.value)} ({_label(latest.reference)}); sem base de comparação"
        )
    return (
        f"{_signed(latest.measure, rule.unit)} "
        f"({_num(latest.base_value)} em {_label(latest.base_reference)} -> "
        f"{_num(latest.value)} em {_label(latest.reference)})"
    )


def _alert_dict(alert: Alert) -> dict:
    return {
        "severidade": _SEVERITY[alert.severity],
        "regra": alert.rule_id,
        "indicador": alert.indicator,
        "competencia": alert.reference,
        "mensagem": alert.message,
        "desde": alert.since,
        "novo": alert.is_new,
        "por_revisao": alert.by_revision,
        "impacto": list(alert.impact),
    }


def _frontmatter(run: AlertRun) -> list[str]:
    data = [
        {
            "motivo": a.trace.get("motivo"),
            "indicador": a.indicator,
            "mensagem": a.message,
            "desde": a.since,
        }
        for a in run.data_alerts
    ]
    watching = [
        {
            "regra": w.rule_id,
            "indicador": w.indicator,
            "medida": w.measure,
            "limiar": w.threshold,
        }
        for w in run.watching
    ]
    return [
        "---",
        "type: macro_alerts",
        f"date: {run.today.isoformat()}",
        f"regras_versao: {run.rules.version}",
        f"regras_hash: {run.rules.content_hash}",
        flow_line(MACRO_ALERTS_RULES_KEY, len(run.rules.rules)),
        flow_line(MACRO_ALERTS_NEW_KEY, len(run.new_alerts)),
        flow_line(MACRO_ALERTS_ACTIVE_KEY, [_alert_dict(a) for a in run.active]),
        flow_line(MACRO_ALERTS_DATA_KEY, data),
        flow_line(MACRO_ALERTS_WATCH_KEY, watching),
        "---",
    ]


def _alert_block(alert: Alert) -> list[str]:
    tags = []
    if alert.is_new:
        tags.append("novo")
    if alert.by_revision:
        tags.append("por revisão de competência, sem notificação")
    suffix = f" _({'; '.join(tags)})_" if tags else ""
    lines = [
        f"- **{alert.rule_id}** · {INDICATORS[alert.indicator].name} · "
        f"visto desde {_label(alert.since)}{suffix}",
        f"  - {alert.message}",
    ]
    lines += [f"  - {line}" for line in alert.impact]
    trace = alert.trace
    parts = [
        f"regra `{trace['regra']}` v{trace['versao_regras']} ({trace['hash_regras']})"
    ]
    if trace.get("janela_dias"):
        parts.append(f"janela {trace['janela_dias']} dias")
    if trace.get("limiar") is not None:
        parts.append(f"limiar {_num(trace['limiar'])}")
    parts.append(
        f"confirmada em {', '.join(_label(r) for r in trace['competencias_confirmadas'])}"
    )
    lines.append(f"  - Rastreio: {'; '.join(parts)}.")
    return lines


def render_alerts_report(run: AlertRun) -> str:
    rules = run.rules
    lines = [
        *_frontmatter(run),
        "",
        "# Alertas macro",
        "",
        f"{len(run.active)} alerta(s) econômico(s) ativo(s), {len(run.data_alerts)} aviso(s) de "
        f"dado, {len(run.watching)} em observação; regras {rules.version} (hash "
        f"{rules.content_hash}), dados de {run.today:%d/%m/%Y}. São alertas INFORMATIVOS: "
        f"{CONTEXT_NOTICE} Os limiares são parâmetros de monitoramento configuráveis, não "
        "política pessoal nem juízo sobre investimentos.",
        "",
        "## Alertas ativos",
        "",
    ]
    if run.active:
        for severity in ("atencao", "informativo"):
            group = [a for a in run.active if a.severity == severity]
            if group:
                lines += [f"### {_SEVERITY[severity]}", ""]
                for alert in group:
                    lines += _alert_block(alert)
                lines.append("")
    else:
        lines += ["Nenhum alerta econômico ativo.", ""]

    lines += ["## Avisos de dado", ""]
    lines.append(
        "Separados dos alertas econômicos: dizem que o DADO tem problema (atraso, ausência ou "
        "divergência entre fontes), não que o ambiente mudou. Não notificam."
    )
    lines.append("")
    if run.data_alerts:
        lines += [
            f"- {a.message} (visto desde {_label(a.since)})" for a in run.data_alerts
        ]
    else:
        lines.append("Nenhum problema de dado.")
    lines.append("")

    lines += ["## Em observação (emitidos, ainda não rearmados)", ""]
    if run.watching:
        for w in run.watching:
            measure = (
                "sem medida agora" if w.measure is None else f"medida {_num(w.measure)}"
            )
            lines.append(
                f"- `{w.rule_id}` · {INDICATORS[w.indicator].name}: {measure}, limiar "
                f"{_num(w.threshold)}; só emite de novo depois de recuar "
                f"{rules.rearm_fraction:.0%} do limiar."
            )
    else:
        lines.append("Nada em observação.")
    lines += [
        "",
        "## Regras",
        "",
        "| Regra | Indicador | Tipo | Janela | Limiar | Confirmação | Severidade | Situação | Medida atual (janela usada) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for ev in run.evaluations:
        rule = ev.rule
        confirmation = (
            f"{rule.confirmations} observações distintas"
            if rule.confirmations > 1
            else "1 observação"
        )
        lines.append(
            f"| `{rule.id}` | {INDICATORS[rule.indicator].name} | {_KIND[rule.kind]} | "
            f"{_window(rule)} | {_threshold(rule)} | {confirmation} | {_SEVERITY[rule.severity]} | "
            f"{STATUS_LABELS[ev.status]}{' (por revisão)' if ev.by_revision else ''} | {current_measure(ev)} |"
        )
    lines += [
        "",
        "## Como as regras funcionam",
        "",
        "- **Confirmação**: N observações válidas e DISTINTAS da série (N datas ou competências "
        "diferentes). Rodar o job duas vezes sobre o mesmo dado não confirma nada.",
        "- **Revisão não é competência nova**: a condição também é avaliada sobre o primeiro "
        "valor coletado de cada competência; se só existe com o valor revisado, o alerta sai "
        "marcado e não notifica.",
        f"- **Rearme**: depois de emitido, só emite de novo quando a medida recua "
        f"{rules.rearm_fraction:.0%} do limiar. Em limite bilateral vale para o lado que "
        'disparou (passar direto ao lado oposto é alerta novo). Em regras de "qualquer '
        'alteração" não há rearme: cada mudança é um evento próprio (competência e novo '
        "nível), emitido uma vez e retirado da lista depois de `retain_days`.",
        "- **Notificação do Windows**: só alertas de Atenção novos; informativos e avisos de "
        "dado ficam aqui e no painel. Nenhum alerta faz o job falhar.",
        f"- Regras em `07_Research/Macro/alertas_macro.json` (versão {rules.version}, origem: "
        f"{rules.origin}).",
        "",
    ]
    return "\n".join(lines)


def write_alerts_report(vault_path: str | Path, run: AlertRun) -> Path:
    path = Path(vault_path) / REPORT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_alerts_report(run), encoding="utf-8")
    return path
