"""O estado das séries mensais como nota do vault: ``02_Portfolio/Series.md``.

Uma linha por FII: situação, última competência, meses, data da última atualização e se está
defasada. Sobrescrita a cada atualização das séries.
"""

from __future__ import annotations

from pathlib import Path

from iip.portfolio.income import STALE_AFTER_MONTHS
from iip.portfolio.series_state import HEALTHY, SeriesAlert, SeriesState

REPORT_RELATIVE_PATH = Path("02_Portfolio") / "Series.md"


def render_series_report(
    states: tuple[SeriesState, ...], alerts: tuple[SeriesAlert, ...], *, today_iso: str
) -> str:
    ordered = sorted(
        states, key=lambda s: (s.code in HEALTHY and not s.stale, s.ticker)
    )
    problems = [s for s in states if s.code not in HEALTHY or s.stale]
    lines = [
        "---",
        "type: series_state",
        f"date: {today_iso}",
        f"series: {len(states)}",
        f"with_problems: {len(problems)}",
        "---",
        "",
        "# Séries mensais da CVM (FIIs)",
        "",
        f"{len(states)} séries; **{len(problems)} com problema**. São elas que alimentam a "
        "renda projetada (`Renda.md`) e o painel de distribuições. Atualizar: "
        "`iip collect-fii-history`.",
        "",
    ]
    if alerts:
        lines += ["## Mudanças desta atualização", ""]
        lines += [f"- {a.line()}" for a in alerts]
        lines.append("")
    lines += [
        "| Ticker | Situação | Última competência | Meses | Atualizada em | Defasada |",
        "|---|---|---|---:|---|---|",
    ]
    lines += [
        f"| {s.ticker} | {s.label} | {s.last_period or '—'} | {s.months} | "
        f"{s.refreshed_at or 'nunca'} | {'sim' if s.stale else 'não'} |"
        for s in ordered
    ]
    lines += [
        "",
        "## Como ler",
        "",
        f"- **Defasada**: a última competência tem mais de {STALE_AFTER_MONTHS} meses de "
        "calendário; a CVM publica o mês M por volta da metade de M+1.",
        "- **Zero ou negativo / irregular**: o mesmo critério da renda projetada. A série "
        "existe, mas o dado da CVM deste fundo não permite projetar.",
        "- O alerta sai só quando a situação **muda para pior**; uma série que já estava "
        "com problema continua aqui, mas não reavisa toda semana.",
    ]
    return "\n".join(lines) + "\n"


def write_series_report(
    vault_path: Path | str,
    states: tuple[SeriesState, ...],
    alerts: tuple[SeriesAlert, ...],
    *,
    today_iso: str,
) -> Path:
    path = Path(vault_path) / REPORT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_series_report(states, alerts, today_iso=today_iso), encoding="utf-8"
    )
    return path
