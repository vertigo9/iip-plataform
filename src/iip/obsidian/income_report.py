"""A renda projetada da carteira como nota do vault: ``02_Portfolio/Renda.md``.

Sobrescrita a cada execução. Abre com o número e o que ele cobre, depois as posições
projetadas (por cota e por mês), as sem projeção com o motivo, e o que limita a leitura.
"""

from __future__ import annotations

from pathlib import Path

from iip.portfolio.income import (
    MIN_REGULAR_SHARE,
    OUTLIER_TOLERANCE,
    STALE_AFTER_MONTHS,
    IncomeReport,
)

REPORT_RELATIVE_PATH = Path("02_Portfolio") / "Renda.md"


def _brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _cota(value: float) -> str:
    return f"R$ {value:.4f}".replace(".", ",")


def render_income_report(report: IncomeReport) -> str:
    projected, excluded = report.projected, report.excluded
    lines = [
        "---",
        "type: portfolio_income",
        f"projected: {len(projected)}",
        f"excluded: {len(excluded)}",
        f"monthly_income: {report.monthly_income:.2f}",
        "---",
        "",
        "# Renda mensal projetada",
        "",
        f"**{_brl(report.monthly_income)} por mês (bruto)**, somando {len(projected)} "
        f"posições que cobrem **{report.covered_share:.1%}** do valor da carteira. As outras "
        f"{len(excluded)} posições não entram no número (motivos abaixo).",
        "",
        "É uma estimativa: a MEDIANA das últimas distribuições por cota de cada fundo vezes a "
        "quantidade do snapshot. Não é promessa nem previsão de mercado, e não desconta "
        "imposto.",
        "",
    ]
    if report.as_of is not None:
        lines.append(
            f"- Quantidades do snapshot de {report.as_of:%d/%m/%Y} "
            f"({(report.today - report.as_of).days} dias)."
        )
    if report.stale_series:
        lines.append(
            "- **Série defasada** (última competência há mais de "
            f"{STALE_AFTER_MONTHS} meses): "
            + ", ".join(ln.ticker for ln in report.stale_series)
        )
    latest = sorted({ln.last_period for ln in projected if ln.last_period})
    if latest:
        lines.append(
            f"- Última competência das séries: {latest[0]}"
            + (f" a {latest[-1]}" if latest[-1] != latest[0] else "")
            + ". A CVM publica com cerca de um mês de defasagem; para atualizar as séries: "
            "`iip collect-fii-history`."
        )

    lines += [
        "",
        "## Projetadas",
        "",
        "| Ticker | Quantidade | Por cota (mediana) | Renda/mês | Janela | Meses atípicos |",
        "|---|---:|---:|---:|---|---|",
    ]
    for ln in projected:
        window = f"{ln.months[0].period} a {ln.months[-1].period} ({len(ln.months)})"
        notes = ", ".join(ln.unusual) or "—"
        if ln.repeated:
            notes += f"; repetidos descartados: {', '.join(ln.repeated)}"
        lines.append(
            f"| {ln.ticker} | {ln.quantity:.0f} | {_cota(ln.per_unit)} | "
            f"{_brl(ln.monthly_income)} | {window} | {notes} |"
        )

    lines += ["", "## Sem projeção", ""]
    fund_lines = [ln for ln in excluded if ln.last_period]
    other = [ln for ln in excluded if not ln.last_period]
    if fund_lines:
        lines.append(
            "**Fundos com série, mas sem número confiável** (o dado da CVM não permite "
            "projetar; o valor de verdade está no relatório do gestor):"
        )
        lines.append("")
        lines += [f"- {ln.ticker}: {ln.reason}" for ln in fund_lines]
        lines.append("")
    if other:
        lines.append(
            f"**Sem série mensal de distribuição por cota** ({len(other)} posições, "
            f"{sum(ln.market_value for ln in other) / report.total_value:.1%} do valor): "
            + ", ".join(ln.ticker for ln in other)
            + ". Ações têm dividendo anual no balanço, não uma série mensal; FI-Infra, FI-Agro, "
            "ETF, o FMP-FGTS e a renda fixa bancária não têm a série nas fontes atuais."
        )

    lines += [
        "",
        "## Como ler",
        "",
        "- **Por cota** = rendimento do mês (CVM) x cota patrimonial do mesmo mês, conferido "
        "contra o balanço da CVM (`Rendimentos_Distribuir / Cotas_Emitidas`) em HGRU11 e "
        "KNRI11, com diferença menor que 0,5%.",
        f"- **Mediana** da janela, para que uma distribuição extra ou parcial não mova o "
        f"número. Um mês é atípico se fica mais de {OUTLIER_TOLERANCE:.0%} fora da mediana.",
        f"- Uma posição só é projetada se a série for regular: ao menos "
        f"{MIN_REGULAR_SHARE:.0%} dos meses da janela dentro dessa tolerância. Meses com "
        "rendimento zero ou negativo (que a CVM traz para alguns fundos) são descartados; "
        "meses idênticos ao anterior (informe reapresentado) só contam uma vez.",
        "- A renda real do mês depende da decisão do gestor; um fundo pode cortar ou "
        "aumentar sem aviso.",
    ]
    return "\n".join(lines) + "\n"


def write_income_report(vault_path: Path | str, report: IncomeReport) -> Path:
    path = Path(vault_path) / REPORT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_income_report(report), encoding="utf-8")
    return path
