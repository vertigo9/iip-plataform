"""Batch-refresh every portfolio position this project can fetch data for.

Reuses ``iip.cli.fetch_template.fetch_fii_template_live`` /
``fetch_etf_template_live`` / ``fetch_fixed_income_template_live`` /
``fetch_equity_template_live`` / ``fetch_fiagro_template_live`` per
position — no new fetching logic here, just the loop, per-position
error isolation (one bad position must not abort the whole run), and
dated snapshot output.

Every refreshable position needs a verified CNPJ (see
``iip.portfolio.registry.assets_with_cnpj``/``assets_refreshable_now``)
— fund/ETF/fixed_income/fiagro look themselves up in their own CVM
dataset by CNPJ, and equity does too since 18/09/2026 (CVM DFP
fundamentals, looked up by CNPJ same as everything else; price alone
is still fetched by ticker via bolsai/brapi). Positions outside these
classes are skipped with a clear reason, never silently guessed.
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass, field
from pathlib import Path

from iip.portfolio.registry import PortfolioAsset, assets_refreshable_now


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


def _template_type_for(position: PortfolioAsset) -> str | None:
    """Which live-fetch function a position should use.

    Real bug found and fixed here (12/09/2026): ``asset_class="fund"``
    was routing EVERY subtype through the FII-specific CVM Informe
    Mensal — but FI-Infra positions (CDII11, JURO11, CPTI11) are NOT
    registered under that regulatory category at all (confirmed live:
    CDII11's real CNPJ does not appear in the FII dataset). They ARE
    registered as general ICVM 555 funds (confirmed live: CDII11's
    CNPJ DOES appear in the Informe Diário) — the same dataset ETF and
    fixed_income already use. Before this fix, ``refresh-portfolio``
    reported "ok" for these positions while silently finding zero real
    data, since an empty CNPJ match doesn't raise an error, just
    leaves fields at their defaults with a buried warning.

    FI-Agro (CRAA11) needed a THIRD dataset (confirmed live: its CNPJ
    appears in neither the FII nor the Informe Diário dataset) — CVM's
    own dedicated FIAGRO Informe Mensal, now wired via
    ``fetch_fiagro_template_live``.
    """
    if position.asset_class == "fund":
        if position.subtype == "FI-Infra":
            return "fixed_income"
        if position.subtype == "FI-Agro":
            return "fiagro"
        return "fii"
    if position.asset_class in ("etf", "fixed_income", "equity"):
        return position.asset_class
    return None


def _refreshable_positions(
    positions: tuple[PortfolioAsset, ...],
) -> tuple[PortfolioAsset, ...]:
    return tuple(p for p in positions if _template_type_for(p) is not None)


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
    fetch_fixed_income=None,
    fetch_equity=None,
    fetch_fiagro=None,
) -> RefreshRunResult:
    """Refresh every refreshable position, writing one JSON snapshot per
    ticker under ``output_dir/{data}/{ticker}.json``.

    ``fetch_fii``/``fetch_etf``/``fetch_fixed_income``/``fetch_equity``/
    ``fetch_fiagro`` are injectable (default to the real live-fetch
    functions) purely for testability — same pattern as the
    harvesters' injectable ``opener``.
    """
    from iip.cli.fetch_template import (
        fetch_equity_template_live,
        fetch_etf_template_live,
        fetch_fiagro_template_live,
        fetch_fii_template_live,
        fetch_fixed_income_template_live,
    )

    fetch_fii = fetch_fii or fetch_fii_template_live
    fetch_etf = fetch_etf or fetch_etf_template_live
    fetch_fixed_income = fetch_fixed_income or fetch_fixed_income_template_live
    fetch_equity = fetch_equity or fetch_equity_template_live
    fetch_fiagro = fetch_fiagro or fetch_fiagro_template_live

    hoje = _dt.date.today()  # noqa: DTZ011 — data de calendário (data de referência do snapshot), não timestamp
    ano_efetivo = ano or hoje.year
    mes_efetivo = mes or hoje.month
    # DFP de um ano fiscal só sai meses depois do fim desse ano -- ver
    # mesmo comentário em iip.cli.main's fetch-template equity branch.
    ano_dfp_efetivo = ano or (hoje.year - 1)
    run_date = hoje.isoformat()

    all_positions = positions if positions is not None else assets_refreshable_now()
    refreshable = _refreshable_positions(all_positions)

    snapshot_dir = output_dir / run_date
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    outcomes: list[PositionOutcome] = []
    for position in refreshable:
        template_type = _template_type_for(position)
        try:
            if template_type == "fii":
                template, resultado = fetch_fii(
                    position.ticker, position.cnpj, ano_efetivo, bolsai_api_key
                )
            elif template_type == "etf":
                template, resultado = fetch_etf(
                    position.ticker,
                    position.cnpj,
                    ano_efetivo,
                    mes_efetivo,
                    brapi_token,
                )
            elif template_type == "equity":
                template, resultado = fetch_equity(
                    position.ticker,
                    position.cnpj,
                    ano_dfp_efetivo,
                    bolsai_api_key,
                    brapi_token,
                )
            elif template_type == "fiagro":
                template, resultado = fetch_fiagro(
                    position.ticker,
                    position.cnpj,
                    ano_efetivo,
                    mes_efetivo,
                    brapi_token,
                )
            else:  # fixed_income
                template, resultado = fetch_fixed_income(
                    position.ticker,
                    position.cnpj,
                    ano_efetivo,
                    mes_efetivo,
                )
        except Exception as exc:  # noqa: BLE001 — isolamento por posição, ver docstring do módulo
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
                detail="classe de ativo sem fetch automático ainda (só fund/etf/fixed_income/equity/fiagro)",
            )
        )

    return RefreshRunResult(run_date=run_date, outcomes=tuple(outcomes))
