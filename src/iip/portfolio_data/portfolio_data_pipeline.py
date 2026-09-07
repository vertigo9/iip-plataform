"""Portfolio data consolidation pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from .costs import CostSnapshot
from .income import IncomeEvent, annualized_income
from .market_data import MarketQuote
from .portfolio_report import PortfolioReport, PortfolioRow
from .valuation import ValuationSnapshot
from .yield_metrics import yield_on_price


@dataclass(frozen=True)
class AssetDataBundle:
    ticker: str
    quote: MarketQuote
    income_events: tuple[IncomeEvent, ...]
    valuation: ValuationSnapshot | None
    costs: CostSnapshot | None = None
    score: float | None = None
    action: str | None = None


def to_report(as_of: str, bundles: tuple[AssetDataBundle, ...]) -> PortfolioReport:
    rows = []
    for bundle in bundles:
        annual_income = annualized_income(bundle.income_events)
        rows.append(
            PortfolioRow(
                ticker=bundle.ticker.upper(),
                asset_class="unknown",
                market_value=bundle.quote.price,
                weight=0.0,
                annual_income=annual_income,
                yield_on_price=(
                    yield_on_price(annual_income, bundle.quote.price)
                    if bundle.quote.price > 0
                    else None
                ),
                score=bundle.score,
                action=bundle.action,
            )
        )
    return PortfolioReport(as_of, tuple(rows))
