"""Parse the real, hand-maintained portfolio snapshot markdown into
``PortfolioState`` — the one input ``AssetE2ERunner``'s cross-asset
stage needs that no code in this project has produced from real data
before now.

Reads ``vault/02_Portfolio/Current.md`` (or an equivalent file with the
same table shape): a pipe-delimited table with columns ``ID | Ativo |
Classe | Quantidade | PM | Preço atual | Valor | Peso | Peso alvo |
Status``, BR-locale numbers (``.`` thousands, ``,`` decimal, ``R$``
prefix). Only rows with ``Status == active`` are included.

Each row's ``ID`` is looked up against ``PORTFOLIO_ASSETS`` (by ticker)
to fill ``asset_class``/``segment``/``manager``/``structure``/
``risk_profile`` from the verified registry rather than the table's own
free-text ``Classe`` column. Positions absent from the registry (bank
CDBs, and the one confirmed ID/ticker mismatch below) fall back to the
table's own ``Classe`` column, mapped through a fixed, exhaustive
vocabulary — never guessed from an unrecognised value.
"""

from __future__ import annotations

import re
from pathlib import Path

from iip.portfolio.registry import PORTFOLIO_ASSETS, PortfolioAsset
from iip.universal.portfolio_state import PortfolioState, PositionState

# Current.md labels this position by its FGTS product name; the
# registry (registry.py) tracks the same fund under its CNPJ-verified
# ticker AXIA3 — confirmed to be the fund's own reference ticker, not
# Eletrobras' equity ticker of the same name (see registry.py's note).
_ID_TO_REGISTRY_TICKER = {"FMP-FGTS-DAYCOVAL": "AXIA3"}

# Fallback only for rows with no registry match (e.g. bank CDBs, which
# the registry deliberately does not track individually). Exhaustive:
# an unmapped value is kept as-is rather than guessed.
_CLASS_MAP = {
    "acao": "equity",
    "fii": "fund",
    "fi-infra": "fund",
    "fiagro": "fund",
    "etf": "etf",
    "renda_fixa": "fixed_income",
    "fundo": "fixed_income",
}


def _parse_brl(raw: str) -> float | None:
    text = raw.strip().replace("R$", "").strip()
    if not text:
        return None
    text = text.replace(".", "").replace(",", ".")
    return float(text)


def _parse_pct(raw: str) -> float | None:
    text = raw.strip().rstrip("%").strip()
    if not text:
        return None
    text = text.replace(".", "").replace(",", ".")
    return float(text) / 100.0


def _registry_by_ticker(ticker: str) -> PortfolioAsset | None:
    return next((a for a in PORTFOLIO_ASSETS if a.ticker == ticker), None)


def _position_from_row(cells: list[str]) -> PositionState | None:
    row_id, _name, klass, quantidade, _pm, _preco, valor, peso, _peso_alvo, status = cells
    if status.strip().casefold() != "active":
        return None

    registry_ticker = _ID_TO_REGISTRY_TICKER.get(row_id.strip(), row_id.strip())
    asset = _registry_by_ticker(registry_ticker)

    market_value = _parse_brl(valor)
    weight = _parse_pct(peso)
    quantity = _parse_brl(quantidade)
    if market_value is None or weight is None:
        raise ValueError(f"{row_id}: Valor/Peso obrigatorios e ausentes na linha")

    if asset is not None:
        return PositionState(
            ticker=asset.ticker,
            quantity=quantity if quantity is not None else 0.0,
            market_value=market_value,
            weight=weight,
            asset_class=asset.asset_class,
            structure=asset.structure,
            segment=asset.segment,
            manager=asset.manager,
            risk_profile=asset.risk_profile,
        )

    return PositionState(
        ticker=row_id.strip(),
        quantity=quantity if quantity is not None else 0.0,
        market_value=market_value,
        weight=weight,
        asset_class=_CLASS_MAP.get(klass.strip().casefold(), klass.strip()),
    )


def parse_current_snapshot(path: Path | str, *, as_of: str | None = None) -> PortfolioState:
    """Parse the real operational snapshot table into ``PortfolioState``.

    ``as_of`` defaults to the file's own filesystem modification date
    (a real, verifiable fact) when not supplied — the file carries no
    explicit snapshot date in its frontmatter.
    """
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")

    lines = text.splitlines()
    header_index = next(
        (i for i, line in enumerate(lines) if line.strip().startswith("| ID ")),
        None,
    )
    if header_index is None:
        raise ValueError(f"{file_path}: cabecalho de tabela '| ID | ...' nao encontrado")

    positions: list[PositionState] = []
    for line in lines[header_index + 2 :]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            break
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 10 or re.fullmatch(r"-+:?", cells[0]):
            continue
        position = _position_from_row(cells)
        if position is not None:
            positions.append(position)

    if as_of is None:
        import datetime as _dt

        as_of = _dt.date.fromtimestamp(file_path.stat().st_mtime).isoformat()

    total_value = sum(p.market_value for p in positions)
    return PortfolioState(as_of=as_of, positions=tuple(positions), total_value=total_value)
