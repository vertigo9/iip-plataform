"""A renda projetada da carteira como nota do vault: ``02_Portfolio/Renda.md``.

Sobrescrita a cada execução. Abre com o número e o que ele cobre, depois as posições que
entram no total (com a estimativa da CVM, a do gestor e a efetiva lado a lado), os ajustes
feitos a partir do gestor, as posições sem estimativa com o motivo, e o que limita a leitura.

O total pode ser HÍBRIDO: onde a série da CVM não permite projetar (ou diverge do gestor para
mais), entra o valor declarado pelo gestor, sempre identificado como tal. A estimativa da CVM
nunca é apagada: aparece ao lado.
"""

from __future__ import annotations

from pathlib import Path

from iip.obsidian.dashboard import (
    INCOME_ADJUSTMENTS_KEY,
    INCOME_COVERAGE_KEY,
    INCOME_CVM_MONTHLY_KEY,
    INCOME_EXCLUDED_KEY,
    INCOME_HYBRID_KEY,
    INCOME_MONTHLY_KEY,
)
from iip.obsidian.frontmatter import flow_line
from iip.portfolio.income import (
    MIN_REGULAR_SHARE,
    OUTLIER_TOLERANCE,
    SOURCE_LABELS,
    STALE_AFTER_MONTHS,
    IncomeLine,
    IncomeReport,
)
from iip.portfolio.income_cross_check import STATUS_LABELS
from iip.portfolio.series_state import CODE_LABELS

REPORT_RELATIVE_PATH = Path("02_Portfolio") / "Renda.md"


def _brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _cota(value: float | None) -> str:
    return "—" if value is None else f"R$ {value:.4f}".replace(".", ",")


def _delta(line: IncomeLine) -> float:
    """O quanto o ajuste do gestor move o total em relação à CVM pura (positivo: soma o que a
    CVM não projetava; negativo: corta o excesso)."""
    return (line.effective_income or 0.0) - (line.monthly_income or 0.0)


def _signed(value: float) -> str:
    return f"{'+' if value >= 0 else '−'}{_brl(abs(value))}"


def _breakdown(report: IncomeReport) -> str:
    parts = [f"{_brl(report.cvm_monthly_income)} (CVM pura)"]
    for line in report.adjustments:
        who = (
            "estimativa do gestor"
            if line.estimate_source == "manager"
            else "limite do gestor"
        )
        parts.append(f"{_signed(_delta(line))} ({line.ticker}, {who})")
    return " ".join(parts) + f" = {_brl(report.monthly_income)}"


def _adjustment_block(line: IncomeLine) -> list[str]:
    cvm = (
        _cota(line.cvm_estimate)
        if line.cvm_estimate is not None
        else "sem projeção (série irregular)"
    )
    if line.monthly_income is not None:
        cvm += f" = {_brl(line.monthly_income)}/mês"
    return [
        f"### {line.ticker}: {SOURCE_LABELS.get(line.estimate_source, line.estimate_source)}",
        "",
        f"- **Estimativa da CVM:** {cvm}",
        f"- **Declarado pelo gestor:** {_cota(line.manager_reported_distribution)}",
        f"- **Efetiva no total:** {_cota(line.effective_estimate)} = "
        f"{_brl(line.effective_income)}/mês (diferença para a CVM pura: "
        f"{_signed(_delta(line))})",
        "- **Data / referência do gestor:** "
        + (line.manager_reference or "data do relatório não identificada no texto"),
        f"- **Fonte do gestor:** {line.manager_source_url or '—'}",
        "- **Situação da validação:** "
        + STATUS_LABELS.get(line.validation_status, line.validation_status or "—"),
        f"- **Motivo:** {line.override_reason}",
        "",
    ]


def _frontmatter(report: IncomeReport) -> list[str]:
    adjustments = [
        {
            "ticker": ln.ticker,
            "fonte": SOURCE_LABELS.get(ln.estimate_source, ln.estimate_source),
            "cvm": None if ln.cvm_estimate is None else round(ln.cvm_estimate, 4),
            "gestor": ln.manager_reported_distribution,
            "efetiva": (
                None
                if ln.effective_estimate is None
                else round(ln.effective_estimate, 4)
            ),
        }
        for ln in report.adjustments
    ]
    with_series_no_estimate = [
        {"ticker": ln.ticker, "situacao": CODE_LABELS.get(ln.code, ln.code)}
        for ln in report.excluded
        if ln.last_period
    ]
    return [
        "---",
        "type: portfolio_income",
        f"projected: {len(report.projected)}",
        f"effective: {len(report.effective_lines)}",
        f"excluded: {len(report.excluded)}",
        f"monthly_income: {report.monthly_income:.2f}",
        flow_line(INCOME_MONTHLY_KEY, round(report.monthly_income, 2)),
        flow_line(INCOME_CVM_MONTHLY_KEY, round(report.cvm_monthly_income, 2)),
        flow_line(INCOME_HYBRID_KEY, report.is_hybrid),
        flow_line(INCOME_COVERAGE_KEY, round(report.covered_share, 4)),
        flow_line(INCOME_ADJUSTMENTS_KEY, adjustments),
        flow_line(INCOME_EXCLUDED_KEY, with_series_no_estimate),
        "---",
    ]


def render_income_report(report: IncomeReport) -> str:
    effective, excluded = report.effective_lines, report.excluded
    hybrid = report.is_hybrid
    lines = [
        *_frontmatter(report),
        "",
        "# Renda mensal projetada",
        "",
        f"**{_brl(report.monthly_income)} por mês (bruto)**"
        + (" — **estimativa HÍBRIDA**" if hybrid else "")
        + f", somando {len(effective)} posições que cobrem **{report.covered_share:.1%}** do "
        f"valor da carteira. As outras {len(excluded)} posições não entram no número (motivos "
        "abaixo).",
        "",
    ]
    if hybrid:
        lines += [
            "**Por que híbrida:** o total mistura a projeção da série da CVM com valores "
            "declarados pelo gestor onde a CVM não serve ou diverge. Composição: "
            + _breakdown(report)
            + '. Só a coluna "Fonte" diz de onde vem cada linha; nada do gestor substitui a '
            "CVM em silêncio, e o valor da CVM fica registrado ao lado.",
            "",
        ]
    lines += [
        "É uma estimativa: a MEDIANA das últimas distribuições por cota de cada fundo vezes a "
        "quantidade do snapshot (a CVM), com os ajustes acima. Não é promessa nem previsão de "
        "mercado, e não desconta imposto.",
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
    latest = sorted({ln.last_period for ln in report.projected if ln.last_period})
    if latest:
        lines.append(
            f"- Última competência das séries: {latest[0]}"
            + (f" a {latest[-1]}" if latest[-1] != latest[0] else "")
            + ". A CVM publica com cerca de um mês de defasagem; para atualizar as séries: "
            "`iip collect-fii-history`."
        )

    lines += [
        "",
        "## Entram no total",
        "",
        "| Ticker | Qtd | CVM (por cota) | Gestor (por cota) | Efetiva (por cota) | Renda/mês | Fonte | Validação |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for ln in effective:
        cvm = "sem projeção" if ln.cvm_estimate is None else _cota(ln.cvm_estimate)
        flag = "" if ln.estimate_source == "cvm" else " ⚠"
        validation = (
            STATUS_LABELS.get(ln.validation_status, ln.validation_status)
            if ln.validation_status
            else "—"
        )
        lines.append(
            f"| {ln.ticker} | {ln.quantity:.0f} | {cvm} | "
            f"{_cota(ln.manager_reported_distribution)} | {_cota(ln.effective_estimate)} | "
            f"{_brl(ln.effective_income)} | "
            f"**{SOURCE_LABELS.get(ln.estimate_source, ln.estimate_source)}**{flag} | "
            f"{validation} |"
        )

    detail = [ln for ln in effective if ln.unusual or ln.repeated]
    if detail:
        lines += ["", "Meses atípicos ou repetidos na janela da CVM:", ""]
        for ln in detail:
            note = ", ".join(ln.unusual) or "—"
            if ln.repeated:
                note += f"; repetidos descartados: {', '.join(ln.repeated)}"
            lines.append(f"- {ln.ticker}: {note}")

    if report.adjustments:
        lines += ["", "## Ajustes a partir do gestor", ""]
        for ln in report.adjustments:
            lines += _adjustment_block(ln)

    lines += ["", "## Sem estimativa", ""]
    fund_lines = [ln for ln in excluded if ln.last_period]
    other = [ln for ln in excluded if not ln.last_period]
    if fund_lines:
        lines += [
            "**Fundos com série, mas sem número confiável** (o dado da CVM não permite "
            "projetar e não há valor do gestor lido; o valor de verdade está no relatório "
            "do gestor):",
            "",
        ]
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
        "- **CVM (por cota)** = rendimento do mês (CVM) x cota patrimonial do mesmo mês, "
        "conferido contra o balanço da CVM (`Rendimentos_Distribuir / Cotas_Emitidas`) em "
        "HGRU11 e KNRI11, com diferença menor que 0,5%. É a mediana da janela, para que uma "
        "distribuição extra ou parcial não mova o número.",
        "- **Gestor (por cota)** = o que a gestora escreve no relatório mais recente "
        "(`iip validate-income`). É outra fonte, com proveniência e validação próprias.",
        "- **Efetiva** = o que entra no total. Regras: (1) a CVM não projeta e o gestor "
        "declara: vale o gestor; (2) a validação diverge e o gestor declara MENOS que a CVM: "
        "vale o gestor, como limite conservador provisório; se declara mais, vale a CVM; "
        "(3) nos demais casos vale a CVM. Nada disso muda aporte nem peso.",
        f"- Um mês da CVM é atípico se fica mais de {OUTLIER_TOLERANCE:.0%} fora da mediana. "
        f"Uma posição só é projetada pela CVM se ao menos {MIN_REGULAR_SHARE:.0%} dos meses da "
        "janela ficam dentro dessa tolerância; meses zero ou negativos são descartados e "
        "meses idênticos ao anterior (informe reapresentado) contam uma vez.",
        "- A renda real do mês depende da decisão do gestor; um fundo pode cortar ou "
        "aumentar sem aviso.",
    ]
    return "\n".join(lines) + "\n"


def write_income_report(vault_path: Path | str, report: IncomeReport) -> Path:
    path = Path(vault_path) / REPORT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_income_report(report), encoding="utf-8")
    return path
