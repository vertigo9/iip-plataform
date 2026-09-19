"""Valuation of the whole portfolio in one run -- every position whose class
has at least one implemented valuation method, each evaluated by EVERY method
that fits it (``iip.portfolio_data.valuation_methods``), side by side.

Reuses the same live fetch functions as ``refresh_portfolio`` /
``analyze_portfolio``; no new fetching logic here, only the loop, the
per-position error isolation, and one market-wide lookup done ONCE per run:
the long NTN-B real yield that Bazin needs (a failure there degrades Bazin to
``insufficient_data`` with the reason, it never aborts the run and never
falls back to a fixed rate).

Never fabricates ``sector``/``industry`` (same rule as ``analyze_portfolio``)
and never invents a value: a position where no method can produce one is
reported as ``pulado`` with each method's reason.

Persistence is opt-in (``persist=True``). The vault's scoring note holds a
single valuation snapshot, so only the FIRST method (catalog order) that
produced a value is written; the side-by-side view is what the run returns.
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Callable
from dataclasses import dataclass, field

from iip.portfolio.batch_analyze import _sector_industry_for
from iip.portfolio.refresh import _template_type_for
from iip.portfolio.registry import PortfolioAsset, assets_refreshable_now
from iip.portfolio_data.valuation_methods import (
    MethodAttempt,
    evaluate_valuations,
    first_valuation,
    has_calculator,
)
from iip.sources.cvm_dfp_harvester import with_shared_dfp_cache
from iip.sources.tesouro_direto import NtnbRate

NO_METHOD_PREFIX = "nenhum método de valuation implementado para a classe"


@dataclass(frozen=True)
class ValuationOutcome:
    ticker: str
    status: str  # "ok" (>= 1 method produced a value), "pulado", "erro"
    detail: str
    price: float | None = None
    attempts: tuple[MethodAttempt, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ValuationRunResult:
    outcomes: tuple[ValuationOutcome, ...]
    ntnb_rate: NtnbRate | None
    ntnb_note: str

    @property
    def succeeded(self) -> tuple[ValuationOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "ok")

    @property
    def failed(self) -> tuple[ValuationOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "erro")

    @property
    def skipped(self) -> tuple[ValuationOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "pulado")


def _default_fetch_rate() -> NtnbRate | None:
    from iip.sources.tesouro_direto_harvester import TesouroDiretoHTTPHarvester

    return TesouroDiretoHTTPHarvester().fetch_long_ntnb_rate()


@with_shared_dfp_cache
def value_portfolio(
    *,
    bolsai_api_key: str | None,
    brapi_token: str | None,
    vault_path: str | None = None,
    persist: bool = False,
    ano: int | None = None,
    positions: tuple[PortfolioAsset, ...] | None = None,
    fetch_equity: Callable[..., tuple[dict, object]] | None = None,
    fetch_rate: Callable[[], NtnbRate | None] | None = None,
    bridge_cls: Callable[[str], object] | None = None,
) -> ValuationRunResult:
    from iip.cli.fetch_template import fetch_equity_template_live

    fetch_equity = fetch_equity or fetch_equity_template_live
    fetch_rate = fetch_rate or _default_fetch_rate

    rate: NtnbRate | None = None
    try:
        rate = fetch_rate()
        if rate is None:
            ntnb_note = (
                "taxa real da NTN-B indisponível (sem dado recente) — Bazin fica "
                "sem valor; não há taxa fixa de reserva."
            )
        else:
            ntnb_note = (
                f"NTN-B longa (venc. {rate.maturity:%d/%m/%Y}, ref. "
                f"{rate.reference_date:%d/%m/%Y}): IPCA + {rate.real_yield:.2%}"
            )
    except Exception as exc:  # noqa: BLE001 — a taxa é uma consulta de mercado opcional; falhar aqui não pode derrubar a rodada
        ntnb_note = f"não consegui buscar a taxa da NTN-B: {exc} — Bazin fica sem valor."

    bridge = None
    if persist:
        if not vault_path:
            raise ValueError("vault_path is required to persist")
        from iip.knowledge.bridge import KnowledgeBridge

        bridge = (bridge_cls or KnowledgeBridge)(vault_path)

    hoje = _dt.date.today()  # noqa: DTZ011 — data de calendário (ano fiscal da DFP), não timestamp
    ano_dfp = ano or (hoje.year - 1)

    market_inputs = {"ntnb_real_yield": rate.real_yield if rate else None}
    all_positions = positions if positions is not None else assets_refreshable_now()

    outcomes: list[ValuationOutcome] = []
    for position in all_positions:
        template_type = _template_type_for(position)
        if template_type is None or not has_calculator(template_type):
            outcomes.append(
                ValuationOutcome(
                    position.ticker,
                    "pulado",
                    f"{NO_METHOD_PREFIX} {template_type or position.asset_class!r}",
                )
            )
            continue

        sector, industry = _sector_industry_for(position)
        if not sector or not industry:
            outcomes.append(
                ValuationOutcome(
                    position.ticker,
                    "pulado",
                    "sem sector/industry reais no registro — preencha "
                    "PortfolioAsset.sector/.industry antes de avaliar",
                )
            )
            continue

        try:
            template, _ = fetch_equity(
                position.ticker, position.cnpj, ano_dfp, bolsai_api_key, brapi_token
            )
            price = template.get("price")
            attempts = evaluate_valuations(
                ticker=position.ticker,
                asset_class=template_type,
                sector=sector,
                industry=industry,
                price=price,
                inputs={**template.get("financials", {}), **market_inputs},
            )
        except Exception as exc:  # noqa: BLE001 — isolamento por posição, mesmo padrão de refresh_portfolio
            outcomes.append(ValuationOutcome(position.ticker, "erro", str(exc)))
            continue

        snapshot = first_valuation(attempts)
        if snapshot is None:
            why = "; ".join(f"{a.method.value}: {a.reason}" for a in attempts if a.status != "not_implemented")
            outcomes.append(
                ValuationOutcome(
                    position.ticker, "pulado", f"nenhum método produziu valor — {why}",
                    price=price, attempts=attempts,
                )
            )
            continue

        detail = ", ".join(
            f"{a.method.value}={a.snapshot.fair_value:.2f}" for a in attempts if a.snapshot
        )
        if bridge is not None:
            try:
                bridge.sync_valuation_projection(snapshot, position.ticker, template_type)
                detail += f" (persistido: {snapshot.method.value})"
            except Exception as exc:  # noqa: BLE001 — isolamento por posição
                outcomes.append(ValuationOutcome(position.ticker, "erro", str(exc), price, attempts))
                continue
        outcomes.append(ValuationOutcome(position.ticker, "ok", detail, price, attempts))

    return ValuationRunResult(tuple(outcomes), rate, ntnb_note)
