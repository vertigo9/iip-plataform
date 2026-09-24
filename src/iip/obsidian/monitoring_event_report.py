"""A leitura estruturada do monitoramento como nota do vault: ``02_Portfolio/Monitoramento.md``.

Sobrescrita a cada execução de ``iip monitoring-events --report``. Mostra os eventos que
``build_monitoring_events`` gera (um por linha, todas as linhas da política): peso atual, faixa,
estado e tipo de desvio. É informação, não ordem: nada aqui decide, executa ou notifica --
``automatic_action`` é sempre ``"nenhuma"``. Este comando roda manualmente; não faz parte do
job diário e não chama ``decide-portfolio``.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

from iip.portfolio.monitoring_event import SEVERITY_DEVIATION, MonitoringEvent
from iip.portfolio.target_policy import STAGE_BUILDING, TargetPolicy

REPORT_RELATIVE_PATH = Path("02_Portfolio") / "Monitoramento.md"


def _pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}".replace(".", ",") + "%"


def render_monitoring_report(
    events: tuple[MonitoringEvent, ...], policy: TargetPolicy, today: _dt.date
) -> str:
    deviations = [e for e in events if e.severity == SEVERITY_DEVIATION]
    lines = [
        "---",
        "type: monitoring_event_note",
        f"date: {today.isoformat()}",
        f"politica_hash: {policy.content_hash}",
        f"monitoramento_ativo: {str(policy.monitoring_enabled).lower()}",
        f"eventos: {len(events)}",
        f"desvios: {len(deviations)}",
        "---",
        "",
        "# Monitoramento de pesos-alvo — leitura estruturada",
        "",
        f"Gerado manualmente em {today:%d/%m/%Y} a partir da política {policy.version} (hash "
        f"{policy.content_hash}) contra o snapshot atual. É leitura, não ordem: nenhum evento "
        'decide, executa ou notifica -- `automatic_action` é sempre "nenhuma". Decisões de '
        "investimento (REDUZIR, VENDER, MANTER, aporte) continuam só em `decide-portfolio`, "
        "camada separada.",
        "",
        f"- **Monitoramento** (campo da política): "
        f"{'LIGADO' if policy.monitoring_enabled else 'desligado'}.",
        "- **Este comando**: roda manualmente; não faz parte do job diário e não envia "
        "notificação.",
        "",
        f"## Desvios ({len(deviations)})",
        "",
    ]
    if deviations:
        lines += [
            "| Linha | Peso atual | Faixa | Mínimo | Máximo | Estado | Tipo de desvio |",
            "|---|---:|---:|---:|---:|---|---|",
        ]
        for event in sorted(deviations, key=lambda e: -e.current_weight_pct):
            band = (
                "—"
                if event.band_low is None
                else f"{_pct(event.band_low)}–{_pct(event.band_high)}"
            )
            lines.append(
                f"| `{event.line_id}` {'' if event.line_name == event.line_id else '· ' + event.line_name} | "
                f"{_pct(event.current_weight_pct)} | {band} | {_pct(event.min_pct)} | "
                f"{_pct(event.max_pct)} | {event.state} | {event.deviation_type} |"
            )
    else:
        lines.append("Nenhuma linha em desvio.")
    lines += ["", f"## Todas as linhas ({len(events)})", ""]
    lines += [
        "| Linha | Peso atual | Alvo | Estágio | Estado | Severidade |",
        "|---|---:|---:|---|---|---|",
    ]
    for event in sorted(events, key=lambda e: -e.current_weight_pct):
        stage_label = (
            "em construção" if event.stage == STAGE_BUILDING else "estabelecida"
        )
        lines.append(
            f"| `{event.line_id}` | {_pct(event.current_weight_pct)} | "
            f"{_pct(event.target_pct)} | {stage_label} | {event.state} | {event.severity} |"
        )
    lines += [
        "",
        "Nada aqui compra, vende, aporta ou rebalanceia. `automatic_action` é sempre "
        '"nenhuma" em todas as linhas, mesmo nos desvios.',
        "",
    ]
    return "\n".join(lines)


def write_monitoring_report(
    vault_path: str | Path,
    events: tuple[MonitoringEvent, ...],
    policy: TargetPolicy,
    today: _dt.date,
) -> Path:
    path = Path(vault_path) / REPORT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_monitoring_report(events, policy, today), encoding="utf-8")
    return path
