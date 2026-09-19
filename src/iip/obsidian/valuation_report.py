"""The portfolio valuation as a note in the Obsidian vault.

``iip value-portfolio`` prints its result in the terminal; this renders the same
result as ``02_Portfolio/Valuation.md`` so it can be read (and linked, filtered,
searched) in Obsidian without running a command. The note is fully generated and
overwritten on every run -- like ``Dashboard.md`` -- so it never accumulates
hand edits; the per-asset frontmatter written by ``value-portfolio --persist``
is a separate thing.

Contents: one table per asset class (columns are that class's own methods), a
list of why any method produced no value, the positions skipped and why, and a
short reading guide with each method's limits. Nothing is computed here -- every
number comes from the ``ValuationRunResult`` it is given.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from pathlib import Path

from iip.portfolio.batch_value import (
    NO_METHOD_PREFIX,
    ValuationOutcome,
    ValuationRunResult,
)
from iip.portfolio_data.valuation import ValuationMethod
from iip.portfolio_data.valuation_methods import METHODS_BY_ASSET_CLASS, first_valuation

REPORT_RELATIVE_PATH = Path("02_Portfolio") / "Valuation.md"

_CLASS_TITLES = {"equity": "Ações", "fii": "FIIs"}

_READING_GUIDE = """\
## Como ler

- **Graham** (ações): `√(22,5 × LPA × VPA)`. Parte do patrimônio; fraco para \
tecnologia e ativos intangíveis (nesses, fica sem valor).
- **Bazin** (ações): dividendo por ação (dividendos e JCP pagos no ano fiscal ÷ ações) \
dividido pela NTN-B longa real, em vez dos 6% fixos. Exige 3 anos de dividendos e \
payout de no máximo 100%.
- **NAV** (FIIs): o patrimônio por cota. Âncora de todos os FIIs.
- **Yield** (FIIs de tijolo): a renda de 12 meses por cota dividida pela NTN-B longa real. \
Compara um yield nominal com uma taxa real: use como ranking entre fundos, não como \
preço-alvo. Papel e multiestratégia não têm Yield; yield acima de 20% é tratado como \
distribuição extraordinária.
- **Método principal**: o primeiro da ordem do setor (Bazin em energia, gás, seguros e \
bancos; Graham nas demais ações; NAV nos FIIs). É o que `--persist` grava e o que alimenta a \
decisão com `--auto-valuation`.
- **Margem de segurança**: `valor / preço − 1`. Positiva = abaixo do valor calculado.

> Valor justo não é recomendação: é um método por ativo, escolhido pelo setor, contra o \
preço no momento da coleta.
"""


def _cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _fmt(snapshot) -> str:
    if snapshot.margin_of_safety is None:
        return f"{snapshot.fair_value:.2f}"
    return f"{snapshot.fair_value:.2f} ({snapshot.margin_of_safety:+.0%})"


def _label(ticker: str, links: Mapping[str, str], *, in_table: bool = False) -> str:
    """A wikilink to the asset's score note when it exists. Inside a Markdown
    table the alias pipe must be escaped; outside one it must not be."""
    target = links.get(ticker)
    if not target:
        return ticker
    return f"[[{target}\\|{ticker}]]" if in_table else f"[[{target}|{ticker}]]"


def _class_columns(asset_class: str) -> tuple[ValuationMethod, ...]:
    return METHODS_BY_ASSET_CLASS.get(asset_class, ())


def _class_table(
    asset_class: str, outcomes: list[ValuationOutcome], links: Mapping[str, str]
) -> str:
    methods = [m for m in _class_columns(asset_class) if any(
        a.method is m and a.status != "not_implemented" for o in outcomes for a in o.attempts
    )]
    header = ["Ticker", "Setor", "Preço", "Principal", "Valor (margem)"] + [m.value for m in methods]
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    for outcome in outcomes:
        by_method = {a.method: a for a in outcome.attempts}
        lead = first_valuation(outcome.attempts)
        price = f"{outcome.price:.2f}" if outcome.price is not None else "—"
        row = [
            _label(outcome.ticker, links, in_table=True),
            _cell(outcome.segment or "—"),
            price,
            f"**{lead.method.value}**" if lead else "—",
            _fmt(lead) if lead else "—",
        ]
        for m in methods:
            attempt = by_method.get(m)
            row.append(_fmt(attempt.snapshot) if attempt and attempt.snapshot else "—")
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def render_valuation_report(
    result: ValuationRunResult,
    *,
    as_of: date,
    asset_links: Mapping[str, str] | None = None,
    source_note: str | None = None,
) -> str:
    links = asset_links or {}
    rate = result.ntnb_rate
    frontmatter = [
        "---",
        "type: valuation_report",
        "scope: portfolio",
        'schema_version: "0.1"',
        "updated_by: IIP Engine",
        f"as_of: {as_of.isoformat()}",
    ]
    if rate is not None:
        frontmatter += [
            f"ntnb_real_yield: {rate.real_yield}",
            f"ntnb_maturity: {rate.maturity.isoformat()}",
            f"ntnb_reference_date: {rate.reference_date.isoformat()}",
        ]
    frontmatter += ["tags:", "  - iip/valuation", "  - iip/portfolio", "---"]

    body = [
        "# Valuation da Carteira",
        "",
        "> Gerado pelo IIP (`iip value-portfolio --report`); sobrescrito a cada execução — "
        "não edite aqui.",
        "",
        f"**Data:** {as_of.isoformat()} · {result.ntnb_note}",
    ]
    if source_note:
        body += ["", f"> {source_note}"]
    body.append("")

    valued = [o for o in result.outcomes if o.attempts and o.status == "ok"]
    by_class: dict[str, list[ValuationOutcome]] = {}
    for outcome in valued:
        by_class.setdefault(outcome.asset_class or "equity", []).append(outcome)
    for asset_class in [c for c in ("equity", "fii") if c in by_class] + sorted(
        c for c in by_class if c not in ("equity", "fii")
    ):
        title = _CLASS_TITLES.get(asset_class, asset_class)
        body += [f"## {title}", "", _class_table(asset_class, by_class[asset_class], links), ""]

    reasons: list[str] = []
    for outcome in result.outcomes:
        for attempt in outcome.attempts:
            if attempt.status in ("not_applicable", "insufficient_data"):
                reasons.append(
                    f"- {_label(outcome.ticker, links)} · **{attempt.method.value}** sem valor: "
                    f"{_cell(attempt.reason)}"
                )
    if reasons:
        body += ["## Métodos sem valor", "", *reasons, ""]

    problems = [o for o in result.outcomes if o.status == "erro"]
    if problems:
        body += ["## Erros", ""]
        body += [f"- {_label(o.ticker, links)}: {_cell(o.detail)}" for o in problems]
        body.append("")

    no_value = [
        o for o in result.outcomes
        if o.status == "pulado" and not o.detail.startswith(NO_METHOD_PREFIX)
    ]
    class_skips: dict[str, list[str]] = {}
    for outcome in result.outcomes:
        if outcome.status == "pulado" and outcome.detail.startswith(NO_METHOD_PREFIX):
            class_skips.setdefault(outcome.detail, []).append(outcome.ticker)
    if no_value or class_skips:
        body += ["## Não avaliados", ""]
        body += [f"- {_label(o.ticker, links)}: {_cell(o.detail)}" for o in no_value]
        for detail, tickers in class_skips.items():
            body.append(f"- {detail}: {', '.join(_label(t, links) for t in tickers)}")
        body.append("")

    body.append(_READING_GUIDE)
    return "\n".join(frontmatter) + "\n\n" + "\n".join(body)


def find_asset_links(vault_path: Path | str, tickers: list[str]) -> dict[str, str]:
    """ticker -> note name ("<T> - Score e Ranking"), only for notes that exist."""
    assets = Path(vault_path) / "01_Assets"
    links: dict[str, str] = {}
    if not assets.is_dir():
        return links
    for ticker in tickers:
        name = f"{ticker} - Score e Ranking"
        if next(assets.rglob(f"{name}.md"), None) is not None:
            links[ticker] = name
    return links


def write_valuation_report(
    vault_path: Path | str,
    result: ValuationRunResult,
    *,
    as_of: date,
    source_note: str | None = None,
) -> Path:
    """Render and write ``02_Portfolio/Valuation.md`` (idempotent overwrite)."""
    links = find_asset_links(vault_path, [o.ticker for o in result.outcomes])
    path = Path(vault_path) / REPORT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_valuation_report(result, as_of=as_of, asset_links=links, source_note=source_note),
        encoding="utf-8",
    )
    return path
