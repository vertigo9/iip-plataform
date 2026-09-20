"""A validação cruzada da renda como nota do vault: ``02_Portfolio/Validacao_Renda.md``.

Uma linha por FII: o que a gestora declara, o que a CVM projeta, a diferença e a situação,
com a cobertura no topo e o que a validação NÃO cobre. Sobrescrita a cada execução.
"""

from __future__ import annotations

from pathlib import Path

from iip.portfolio.income_cross_check import TOLERANCE, CrossCheck

REPORT_RELATIVE_PATH = Path("02_Portfolio") / "Validacao_Renda.md"

# a ordem em que as situações aparecem: o que pede atenção primeiro
_ORDER = (
    "diverge",
    "so_gestor",
    "mudanca_recente",
    "leitura_falhou",
    "confere",
    "sem_gestor",
)


def _cota(value: float | None) -> str:
    return "—" if value is None else f"R$ {value:.4f}".replace(".", ",")


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:+.1%}".replace(".", ",")


def render_validation_report(checks: tuple[CrossCheck, ...]) -> str:
    ordered = sorted(
        checks,
        key=lambda c: (
            _ORDER.index(c.status) if c.status in _ORDER else len(_ORDER),
            c.ticker,
        ),
    )
    counts = {s: sum(1 for c in checks if c.status == s) for s in _ORDER}
    checked = (
        counts["confere"]
        + counts["diverge"]
        + counts["so_gestor"]
        + counts["mudanca_recente"]
    )
    lines = [
        "---",
        "type: income_validation",
        f"funds: {len(checks)}",
        f"confere: {counts['confere']}",
        f"mudanca_recente: {counts['mudanca_recente']}",
        f"diverge: {counts['diverge']}",
        f"so_gestor: {counts['so_gestor']}",
        "---",
        "",
        "# Validação cruzada da renda: CVM contra o gestor",
        "",
        f"**{checked} de {len(checks)} FIIs têm um número do gestor para comparar**: "
        f"{counts['confere']} conferem (até {TOLERANCE:.0%}), "
        f"{counts['mudanca_recente']} conferem só com o mês recente (a mediana ficou para "
        f"trás de uma mudança), {counts['diverge']} divergem, "
        f"{counts['so_gestor']} têm número só do gestor (a CVM não projeta). "
        f"{counts['sem_gestor'] + counts['leitura_falhou']} não têm como conferir.",
        "",
        "A projeção da renda (`Renda.md`) continua sendo a da CVM; esta nota só registra se "
        "ela bate com o que o gestor escreve. **Usar o número do gestor quando a CVM falha "
        "é decisão do usuário**, não é feito aqui.",
        "",
        "| Ticker | Situação | Gestor (R$/cota) | CVM projeção | Diferença | CVM último mês | Fonte |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for c in ordered:
        last = (
            f"{_cota(c.cvm_last)} ({c.cvm_last_period})"
            if c.cvm_last is not None
            else "—"
        )
        source = c.source_url or "—"
        if len(source) > 60:
            source = source[:57] + "..."
        lines.append(
            f"| {c.ticker} | {c.label} | {_cota(c.declared)} | {_cota(c.cvm_projection)} | "
            f"{_pct(c.diff_projection)} | {last} | {source} |"
        )

    notes = [c for c in ordered if c.note]
    if notes:
        lines += ["", "## Observações", ""]
        lines += [f"- {c.ticker}: {c.note}" for c in notes]

    evidence = [c for c in ordered if c.evidence]
    if evidence:
        lines += ["", "## O que cada relatório diz (para conferir a leitura)", ""]
        lines += [f'- {c.ticker}: "{c.evidence}"' for c in evidence]

    lines += [
        "",
        "## Limites",
        "",
        "- O leitor de cada relatório é específico do layout; se a gestora mudar o texto, o "
        "fundo passa a `leitura falhou` (nunca a um número adivinhado).",
        "- Comparo o número declarado no relatório mais recente com a projeção da CVM (mediana "
        "dos últimos meses); o mês a que o relatório se refere pode diferir do último mês da "
        "CVM em um mês.",
        "- Sem leitor: HGRU11 e LVBI11 (a planilha da Pátria de tijolo não traz o "
        "rendimento), MANA11, AFHI11 e VGIP11.",
        "- Conferir com UM relatório não prova a série inteira: um mês pode conferir e outros "
        "estarem errados na CVM.",
    ]
    return "\n".join(lines) + "\n"


def write_validation_report(
    vault_path: Path | str, checks: tuple[CrossCheck, ...]
) -> Path:
    path = Path(vault_path) / REPORT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_validation_report(checks), encoding="utf-8")
    return path
