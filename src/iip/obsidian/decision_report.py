"""A decisão da carteira como nota do vault: ``02_Portfolio/Decisoes.md``.

Uma tabela com a decisão de cada posição (e a anterior, para se ver o que mudou), a nota da
análise, o valuation usado, o estado da saída de tese e quantas evidências foram citadas;
depois o que mudou desde a última decisão e as posições puladas ou com erro, com o motivo.
Sobrescrita a cada execução, como o ``Valuation.md``.
"""

from __future__ import annotations

from pathlib import Path

from iip.obsidian.valuation_report import find_asset_links
from iip.portfolio.batch_decide import THESIS_SIGNAL, DecisionOutcome, DecisionRunResult

REPORT_RELATIVE_PATH = Path("02_Portfolio") / "Decisoes.md"

# do mais favorável ao menos, para a tabela sair agrupada por decisão
_VERDICT_ORDER = ("COMPRAR", "MANTER", "AGUARDAR", "REDUZIR", "VENDER")

_READING_GUIDE = f"""\
## Como ler

- **Decisão** é a saída do `decision_engine` (nota de 0 a 10 e confiança). É um resumo \
ordenado do que o projeto mede, não uma ordem de compra ou venda.
- **Análise** é a nota geral (0 a 100) do analisador do tipo de ativo; **Valuation** é a \
nota de 0 a 10 do método principal do catálogo (a mesma margem do `Valuation.md`). Sem valor \
de valuation, a nota fica neutra (5,0) e a linha diz isso.
- **Tese** é o estado da saída de tese calculado a partir da própria análise. O sinal de \
tese usado é sempre `{THESIS_SIGNAL}`: nenhum código julga a tese, então isso não é uma \
opinião de que ela se manteve.
- **Evidências** são as mais recentes, de fontes diferentes, que já existem no vault; a \
decisão nunca cria evidência.
- **Anterior** é a decisão gravada mais recente com data anterior à de hoje. Uma mudança \
pode vir do dado, mas também de a regra de cálculo ter mudado entre as duas datas.
"""


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _label(ticker: str, links: dict[str, str]) -> str:
    return f"[[{links[ticker]}\\|{ticker}]]" if ticker in links else ticker


def _num(value: float | None, digits: int = 2) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def _sort_key(outcome: DecisionOutcome) -> tuple[int, float, str]:
    order = (
        _VERDICT_ORDER.index(outcome.verdict)
        if outcome.verdict in _VERDICT_ORDER
        else len(_VERDICT_ORDER)
    )
    return (order, -(outcome.score or 0.0), outcome.ticker)


def render_decision_report(
    result: DecisionRunResult, *, links: dict[str, str] | None = None
) -> str:
    links = links or {}
    ok = sorted(result.succeeded, key=_sort_key)
    counts = {v: sum(1 for o in ok if o.verdict == v) for v in _VERDICT_ORDER}

    lines = [
        "---",
        "type: portfolio_decisions",
        f"date: {result.decision_date.isoformat()}",
        f"decided: {len(ok)}",
        f"skipped: {len(result.skipped)}",
        f"errors: {len(result.failed)}",
        "---",
        "",
        f"# Decisões da carteira — {result.decision_date:%d/%m/%Y}",
        "",
        "Resumo: "
        + ", ".join(f"{n} {v}" for v, n in counts.items() if n)
        + f" ({len(ok)} decididas, {len(result.skipped)} puladas, "
        f"{len(result.failed)} com erro).",
        "",
        f"_{result.ntnb_note}_",
        "",
        "| Ticker | Decisão | Anterior | Score | Conf. | Análise | Valuation | Tese | Evid. |",
        "|---|---|---|---:|---:|---:|---:|---|---:|",
    ]
    for o in ok:
        arrow = ""
        if o.previous_verdict and o.previous_verdict != o.verdict:
            arrow = f"{o.previous_verdict} →"
        lines.append(
            f"| {_label(o.ticker, links)} | **{o.verdict}** | "
            f"{arrow or (o.previous_verdict or '—')} | {_num(o.score)} | "
            f"{_num(o.confidence)} | {_num(o.analysis_score, 1)} | "
            f"{_num(o.valuation_score)} | {o.thesis_exit_state or '—'} | "
            f"{len(o.evidence_ids)} |"
        )

    if result.changed:
        lines += ["", "## Mudanças desde a decisão anterior", ""]
        for o in sorted(result.changed, key=lambda x: x.ticker):
            lines.append(
                f"- {_label(o.ticker, links)}: {o.previous_verdict} → **{o.verdict}**"
            )

    lines += ["", "## Valuation usado em cada decisão", ""]
    lines += [
        f"- {_label(o.ticker, links)} ({o.asset_class}): {_cell(o.valuation_note)}"
        for o in ok
    ]

    if result.skipped or result.failed:
        lines += ["", "## Puladas e com erro", ""]
        lines += [
            f"- {_label(o.ticker, links)} ({o.status}): {_cell(o.detail)}"
            for o in (*result.skipped, *result.failed)
        ]

    lines += ["", _READING_GUIDE]
    return "\n".join(lines)


def write_decision_report(vault_path: Path | str, result: DecisionRunResult) -> Path:
    links = find_asset_links(vault_path, [o.ticker for o in result.outcomes])
    path = Path(vault_path) / REPORT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_decision_report(result, links=links), encoding="utf-8")
    return path
