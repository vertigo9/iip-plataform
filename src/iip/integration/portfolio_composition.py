"""Composition boundary from economic Decisions to portfolio integration."""

from __future__ import annotations

from iip.decision.models import Decision
from iip.portfolio.registry import PortfolioAsset

from .decision_adapter import decision_to_asset_signal
from .portfolio_pipeline import IntegratedPortfolioDecision, run as run_portfolio_pipeline


class PortfolioCompositionError(ValueError):
    """Raised when Decisions and PortfolioAssets cannot be composed safely."""


def compose(
    decisions: tuple[Decision, ...],
    assets: tuple[PortfolioAsset, ...],
) -> IntegratedPortfolioDecision:
    """Coordinate existing contracts without adding economic logic."""
    asset_by_ticker: dict[str, PortfolioAsset] = {}

    for asset in assets:
        ticker = asset.ticker.upper()
        if ticker in asset_by_ticker:
            raise PortfolioCompositionError(
                f"duplicate_portfolio_asset:{ticker}"
            )
        asset_by_ticker[ticker] = asset

    seen_decisions: set[str] = set()
    signals = []

    for decision in decisions:
        ticker = decision.ticker.upper()
        if ticker in seen_decisions:
            raise PortfolioCompositionError(f"duplicate_decision:{ticker}")
        seen_decisions.add(ticker)

        asset = asset_by_ticker.get(ticker)
        if asset is None:
            raise PortfolioCompositionError(
                f"portfolio_asset_not_found:{ticker}"
            )

        signals.append(decision_to_asset_signal(decision, asset))

    return run_portfolio_pipeline(tuple(signals))
