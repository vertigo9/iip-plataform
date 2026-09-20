"""O contexto macro como nota do vault: ``07_Research/Macro/Contexto_Macro.md``.

Sobrescrita a cada execução. Só descreve o que está guardado (último valor, comparação com 12
meses antes, frescor, conferência entre fontes) e diz o que a leitura NÃO é: não é
recomendação, não decide aporte nem peso, e o dado só vale como "conhecido em tal data" a
partir da primeira coleta.
"""

from __future__ import annotations

from pathlib import Path

from iip.macro.context import MacroContext, MacroReading
from iip.macro.contract import CATEGORY_LABELS, QUARTERLY
from iip.obsidian.dashboard import (
    MACRO_COLLECTED_KEY,
    MACRO_INDICATORS_KEY,
    MACRO_PROBLEMS_KEY,
)
from iip.obsidian.frontmatter import flow_line

REPORT_RELATIVE_PATH = Path("07_Research") / "Macro" / "Contexto_Macro.md"


def _number(value: float | None, unit: str) -> str:
    if value is None:
        return "—"
    digits = 4 if abs(value) < 1 and unit == "% ao dia" else 2
    text = f"{value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return text


def _change(reading: MacroReading) -> str:
    if reading.change is None:
        return "—"
    kind = reading.indicator.change_kind
    sign = f"{reading.change:+.2f}".replace(".", ",")
    return f"{sign} p.p." if kind == "pp" else f"{sign}%"


def _state(reading: MacroReading) -> str:
    if reading.missing:
        return "**sem dados**"
    parts = []
    if reading.latest.provisional:
        parts.append("parcial (mês em curso)")
    if reading.stale:
        parts.append("**defasado**")
    return ", ".join(parts) or "em dia"


def _label(reference: str, frequency: str) -> str:
    return reference.replace("-T", " T") if frequency == QUARTERLY else reference


def _row(reading: MacroReading) -> str:
    ind = reading.indicator
    if reading.missing:
        return f"| {ind.name} | — | — | — | — | — | {_state(reading)} |"
    latest = reading.latest
    before = reading.year_ago
    return (
        f"| {ind.name} ({ind.unit}) | **{_number(latest.value, ind.unit)}** | "
        f"{_label(latest.reference, ind.frequency)} | "
        f"{_number(before.value, ind.unit) if before else '—'} | {_change(reading)} | "
        f"{reading.last_ok or '—'} | {_state(reading)} |"
    )


def _frontmatter(context: MacroContext) -> list[str]:
    indicators = [
        {
            "id": r.indicator.id,
            "nome": r.indicator.name,
            "unidade": r.indicator.unit,
            "valor": None if r.missing else r.latest.value,
            "competencia": None if r.missing else r.latest.reference,
            "variacao_12m": None if r.change is None else round(r.change, 2),
            "provisorio": bool(r.latest and r.latest.provisional),
            "defasado": r.stale,
        }
        for r in context.readings
    ]
    problems = [
        {
            "id": r.indicator.id,
            "situacao": "sem dados" if r.missing else "defasado",
            "ultima": None if r.missing else r.latest.reference,
        }
        for r in context.readings
        if r.missing or r.stale
    ]
    return [
        "---",
        "type: macro_context",
        f"date: {context.today.isoformat()}",
        flow_line(MACRO_COLLECTED_KEY, context.first_collected_at),
        flow_line(MACRO_INDICATORS_KEY, indicators),
        flow_line(MACRO_PROBLEMS_KEY, problems),
        "---",
    ]


def render_macro_report(context: MacroContext) -> str:
    lines = [
        *_frontmatter(context),
        "",
        "# Contexto macroeconômico",
        "",
        f"{len(context.readings)} indicadores, dados de {context.today:%d/%m/%Y}; "
        f"**{len(context.stale)} defasados, {len(context.missing)} sem dados**. É CONTEXTO: "
        "descreve o ambiente e não diz o que fazer com a carteira. Não decide aporte nem "
        "peso-alvo. Fontes: BACEN (SGS) e IBGE (SIDRA).",
        "",
    ]
    for category, title in CATEGORY_LABELS.items():
        group = [r for r in context.readings if r.indicator.category == category]
        if not group:
            continue
        lines += [
            f"## {title}",
            "",
            "| Indicador | Último | Competência | 12 meses antes | Variação | Coletado em | Situação |",
            "|---|---:|---|---:|---:|---|---|",
        ]
        lines += [_row(r) for r in group]
        lines.append("")

    lines += ["## Conferência entre fontes", ""]
    for check in context.source_checks:
        if check.compared == 0:
            lines.append(
                f"- `{check.a}` x `{check.b}`: sem competências em comum para comparar."
            )
            continue
        verdict = "concordam" if check.agrees else "**divergem**"
        lines.append(
            f"- `{check.a}` x `{check.b}`: {verdict} em {check.compared} competências "
            f"(maior diferença {check.max_difference:.2f})."
        )

    by_class: dict[str, list[str]] = {}
    for r in context.readings:
        for asset_class in r.indicator.relevant_for:
            by_class.setdefault(asset_class, []).append(r.indicator.name)
    lines += [
        "",
        "## Onde cada indicador pesa",
        "",
        "Mapa de LEITURA, não causal: diz quais indicadores são relevantes para cada classe da "
        "carteira, não o que vão fazer com ela.",
        "",
        "| Classe | Indicadores relevantes |",
        "|---|---|",
    ]
    for asset_class in sorted(by_class):
        lines.append(f"| {asset_class} | {'; '.join(by_class[asset_class])} |")

    revised = [r for r in context.readings if r.revisions]
    lines += [
        "",
        "## Limites",
        "",
        '- **Só vale como "conhecido em tal data" a partir da primeira coleta'
        + (f" ({context.first_collected_at})" if context.first_collected_at else "")
        + ".** As duas fontes devolvem só competência e valor, sem data de publicação nem "
        "versão: o que veio antes de começarmos a coletar não sabe quando foi conhecido, e "
        "este dado NÃO serve para reconstruir o que se sabia numa decisão do passado.",
        "- **Revisões**: quando a fonte muda um valor já coletado, a nova versão é guardada ao "
        "lado da anterior, com a data da coleta. "
        + (
            "Competências já revisadas: "
            + ", ".join(f"{r.indicator.id} ({r.revisions})" for r in revised)
            + "."
            if revised
            else "Nenhuma revisão observada ainda."
        ),
        "- **Parcial**: Selic e CDI acumulados no mês mudam até o mês fechar; o valor do mês em "
        "curso está marcado como provisório.",
        "- Indicadores conferidos com o catálogo do BCB ou entre as duas fontes estão "
        "identificados no contrato (`iip.macro.contract`, campo `verified_by`); os demais "
        "seguem a documentação do BCB.",
        "- Próximos passos da Entrega B: cenários e a ligação com as premissas de valuation. "
        "Nada disso muda aporte nem peso-alvo.",
    ]
    return "\n".join(lines) + "\n"


def write_macro_report(vault_path: Path | str, context: MacroContext) -> Path:
    path = Path(vault_path) / REPORT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_macro_report(context), encoding="utf-8")
    return path
