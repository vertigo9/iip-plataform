"""A decision's valuation score, from the valuation catalog.

``analysis_to_intelligence_input`` takes a 0-10 ``valuation_score`` and, without
one, uses a neutral 5.0. The catalog (``iip.portfolio_data.valuation_methods``)
can now supply a real one: the LEAD method for the asset's sector (Bazin for
dividend-centric businesses, Graham elsewhere) gives a fair value / ceiling
price, whose margin of safety against the market price becomes the score via
the existing ``iip.decision.valuation_bridge.valuation_score`` (5.0 at a zero
margin, +1.0 per +10% margin, clamped to 0-10).

Nothing is invented: when no method can produce a value (not applicable, data
missing, no price) the result carries no score and says why, so the caller
keeps the neutral value and reports the reasons.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from iip.decision.valuation_bridge import ValuationSnapshot as DecisionSnapshot
from iip.decision.valuation_bridge import valuation_score
from iip.portfolio_data.valuation_methods import evaluate_valuations, first_valuation


@dataclass(frozen=True)
class CatalogValuation:
    score: float | None  # 0-10, or None when no method produced a value
    method: str | None
    fair_value: float | None
    market_price: float | None
    margin_of_safety: float | None
    explanation: str


def catalog_valuation_for_decision(
    *,
    ticker: str,
    asset_class: str,
    sector: str,
    industry: str,
    price: float | None,
    financials: Mapping[str, float | None],
    ntnb_real_yield: float | None,
) -> CatalogValuation:
    attempts = evaluate_valuations(
        ticker=ticker,
        asset_class=asset_class,
        sector=sector,
        industry=industry,
        price=price,
        inputs={**financials, "ntnb_real_yield": ntnb_real_yield},
    )
    snapshot = first_valuation(attempts)
    if snapshot is None:
        why = "; ".join(
            f"{a.method.value}: {a.reason}"
            for a in attempts
            if a.status != "not_implemented"
        )
        return CatalogValuation(
            None, None, None, price, None, why or "nenhum método de valuation aplicável"
        )
    if snapshot.market_price is None or snapshot.margin_of_safety is None:
        return CatalogValuation(
            None,
            snapshot.method.value,
            snapshot.fair_value,
            snapshot.market_price,
            None,
            f"{snapshot.method.value}: valor {snapshot.fair_value}, mas sem preço de "
            "mercado para medir a margem de segurança",
        )
    score = round(
        valuation_score(
            DecisionSnapshot(
                ticker=ticker,
                fair_value=snapshot.fair_value,
                market_price=snapshot.market_price,
                margin_of_safety=snapshot.margin_of_safety,
                method=snapshot.method.value,
            )
        ),
        2,
    )
    return CatalogValuation(
        score,
        snapshot.method.value,
        snapshot.fair_value,
        snapshot.market_price,
        snapshot.margin_of_safety,
        f"{snapshot.method.value}: {snapshot.fair_value:.2f} vs preço "
        f"{snapshot.market_price:.2f} ({snapshot.margin_of_safety:+.0%}) → nota {score:.2f}/10",
    )
