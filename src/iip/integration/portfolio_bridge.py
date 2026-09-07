"""Bridge between portfolio registry and decision integration."""

from __future__ import annotations

from dataclasses import dataclass

from iip.portfolio.registry import PortfolioAsset


@dataclass(frozen=True)
class PortfolioContext:
    ticker: str
    asset_class: str
    manager: str | None
    segment: str | None
    structure: str | None
    risk_profile: str | None


def context(asset: PortfolioAsset) -> PortfolioContext:
    return PortfolioContext(
        ticker=asset.ticker,
        asset_class=asset.asset_class,
        manager=asset.manager,
        segment=asset.segment,
        structure=asset.structure,
        risk_profile=asset.risk_profile,
    )
