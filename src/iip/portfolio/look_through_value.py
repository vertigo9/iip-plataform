"""Cola do valuation por transparência: da CDA do fundo à margem das ações que ele carrega.

Ver ``iip.portfolio_data.look_through`` para o método e os portões. Aqui só o que precisa de
rede e do caminho de avaliação de ações: buscar a carteira (CDA), buscar os fundamentos e o
preço de cada empresa subjacente e avaliá-la como o ``value-portfolio`` avalia uma ação.
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Callable
from dataclasses import dataclass

from iip.portfolio.batch_core import FetchPlan
from iip.portfolio.refresh import missing_required_market_data
from iip.portfolio_data.look_through import (
    UNDERLYINGS,
    combine_margin,
    equity_weights,
)
from iip.portfolio_data.valuation_exceptions import ValuationExceptions
from iip.portfolio_data.valuation_methods import evaluate_valuations, first_valuation
from iip.sources.cvm_cda import CdaPortfolio, recent_months


@dataclass(frozen=True)
class LookThrough:
    # look_through_margin (soma de peso x margem) e look_through_coverage (soma dos pesos
    # das empresas cuja margem foi calculada), ambos frações do patrimônio líquido
    inputs: dict[str, float | None]
    # o que foi feito, para o detalhe do resultado: mês da CDA, cobertura, cada empresa
    note: str


def default_fetch_cda(cnpj: str) -> CdaPortfolio:
    from iip.sources.cvm_cda_harvester import CvmCdaHTTPHarvester

    # data de calendário (quais meses tentar), não timestamp
    months = recent_months(_dt.date.today())  # noqa: DTZ011
    return CvmCdaHTTPHarvester().fetch(cnpj, months=months).portfolio


def look_through_inputs(
    *,
    cnpj: str,
    fetch_cda: Callable[[str], CdaPortfolio],
    fetch_equity: Callable[..., tuple[dict, object]],
    plan: FetchPlan,
    market_inputs: dict[str, float | None],
    exceptions: ValuationExceptions | None = None,
) -> LookThrough:
    """Levanta se a CDA ou a busca de uma empresa falhar (o chamador isola por posição).
    Uma empresa que foi buscada mas não deu margem (sem preço, ou nenhum método aplicável)
    não levanta: fica fora da cobertura, com o motivo na nota."""
    portfolio = fetch_cda(cnpj)
    weights, unmapped = equity_weights(portfolio)

    margins: dict[str, float | None] = {}
    parts: list[str] = []
    for code, weight in weights.items():
        underlying = UNDERLYINGS[code]
        template, _ = fetch_equity(
            underlying.ticker,
            underlying.company_cnpj,
            plan.ano_dfp,
            plan.bolsai_api_key,
            plan.brapi_token,
        )
        incomplete = missing_required_market_data(
            "equity",
            template,
            bolsai_api_key=plan.bolsai_api_key,
            brapi_token=plan.brapi_token,
        )
        if incomplete:
            margins[code] = None
            parts.append(f"{underlying.ticker} ({weight:.1%} do PL): {incomplete}")
            continue
        price = template.get("price")
        attempts = evaluate_valuations(
            ticker=underlying.ticker,
            asset_class="equity",
            sector=underlying.sector,
            industry=underlying.industry,
            price=price,
            inputs={**template.get("financials", {}), **market_inputs},
            exceptions=exceptions,
        )
        snapshot = first_valuation(attempts)
        if snapshot is None or snapshot.margin_of_safety is None:
            margins[code] = None
            why = "; ".join(
                f"{a.method.value}: {a.reason}"
                for a in attempts
                if a.status != "not_implemented"
            )
            parts.append(
                f"{underlying.ticker} ({weight:.1%} do PL): sem valor justo ({why})"
            )
            continue
        margins[code] = snapshot.margin_of_safety
        parts.append(
            f"{underlying.ticker} ({weight:.1%} do PL): {snapshot.method.value} "
            f"{snapshot.fair_value:.2f} contra o preço {price:.2f} "
            f"({snapshot.margin_of_safety:+.1%})"
        )

    margin, coverage = combine_margin(weights, margins)
    note = (
        f"CDA de {portfolio.reference_date or portfolio.month} "
        f"(PL R$ {portfolio.net_assets / 1_000_000:,.1f} mi); "
        + ("; ".join(parts) if parts else "nenhuma ação de empresa mapeada na carteira")
    )
    if unmapped > 0.005:
        note += (
            f"; {unmapped:.1%} do PL em ações sem empresa mapeada (fora da cobertura)"
        )
    return LookThrough(
        inputs={"look_through_margin": margin, "look_through_coverage": coverage},
        note=note,
    )
