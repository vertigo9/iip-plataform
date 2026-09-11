"""Batch-refresh every portfolio position with a known CNPJ.

Reuses ``iip.cli.fetch_template.fetch_fii_template_live`` /
``fetch_etf_template_live`` per position — no new fetching logic here,
just the loop, per-position error isolation (one bad fund must not
abort the whole run), and dated snapshot output.

Only ``fund``/``etf``-class positions from
``iip.portfolio.registry.assets_with_cnpj()`` are refreshed —
``equity``/``fixed_income`` positions aren't wired to automatic
fetching yet (see the CLI's own ``fetch-template`` docstring for that
gap), and positions with no verified CNPJ are skipped with a clear
reason, never silently guessed.
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from iip.portfolio.registry import PortfolioAsset, assets_with_cnpj


@dataclass(frozen=True)
class PositionOutcome:
    ticker: str
    status: str  # "ok", "erro", "pulado"
    detail: str
    fetched_fields: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RefreshRunResult:
    run_date: str
    outcomes: tuple[PositionOutcome, ...]

    @property
    def succeeded(self) -> tuple[PositionOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "ok")

    @property
    def failed(self) -> tuple[PositionOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "erro")

    @property
    def skipped(self) -> tuple[PositionOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "pulado")


_ASSET_CLASS_TO_TEMPLATE_TYPE = {
    "fund": "fii",  # PORTFOLIO_ASSETS uses "fund" for FIIs; subtype narrows further
    "etf": "etf",
}


def _refreshable_positions(
    positions: tuple[PortfolioAsset, ...],
) -> tuple[PortfolioAsset, ...]:
    return tuple(
        p
        for p in positions
        if _ASSET_CLASS_TO_TEMPLATE_TYPE.get(p.asset_class) is not None
    )


def refresh_portfolio(
    output_dir: Path,
    *,
    bolsai_api_key: str | None,
    brapi_token: str | None,
    ano: int | None = None,
    mes: int | None = None,
    positions: tuple[PortfolioAsset, ...] | None = None,
    fetch_fii=None,
    fetch_etf=None,
) -> RefreshRunResult:
    """Refresh every position with a known CNPJ, writing one JSON
    snapshot per ticker under ``output_dir/{data}/{ticker}.json``.

    ``fetch_fii``/``fetch_etf`` are injectable (default to the real
    live-fetch functions) purely for testability — same pattern as the
    harvesters' injectable ``opener``.
    """
    from iip.cli.fetch_template import fetch_etf_template_live, fetch_fii_template_live

    fetch_fii = fetch_fii or fetch_fii_template_live
    fetch_etf = fetch_etf or fetch_etf_template_live

    hoje = _dt.date.today()
    ano_efetivo = ano or hoje.year
    mes_efetivo = mes or hoje.month
    run_date = hoje.isoformat()

    all_positions = positions if positions is not None else assets_with_cnpj()
    refreshable = _refreshable_positions(all_positions)

    snapshot_dir = output_dir / run_date
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    outcomes: list[PositionOutcome] = []
    for position in refreshable:
        template_type = _ASSET_CLASS_TO_TEMPLATE_TYPE[position.asset_class]
        try:
            if template_type == "fii":
                template, resultado = fetch_fii(
                    position.ticker, position.cnpj, ano_efetivo, bolsai_api_key
                )
            else:
                template, resultado = fetch_etf(
                    position.ticker,
                    position.cnpj,
                    ano_efetivo,
                    mes_efetivo,
                    brapi_token,
                )
        except Exception as exc:
            outcomes.append(
                PositionOutcome(
                    ticker=position.ticker,
                    status="erro",
                    detail=str(exc),
                )
            )
            continue

        snapshot_path = snapshot_dir / f"{position.ticker}.json"
        snapshot_path.write_text(
            json.dumps(template, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        outcomes.append(
            PositionOutcome(
                ticker=position.ticker,
                status="ok",
                detail=str(snapshot_path),
                fetched_fields=resultado.fetched_fields,
            )
        )

    skipped_tickers = {p.ticker for p in all_positions} - {p.ticker for p in refreshable}
    for ticker in sorted(skipped_tickers):
        outcomes.append(
            PositionOutcome(
                ticker=ticker,
                status="pulado",
                detail="classe de ativo sem fetch automático ainda (só fund/etf)",
            )
        )

    return RefreshRunResult(run_date=run_date, outcomes=tuple(outcomes))
