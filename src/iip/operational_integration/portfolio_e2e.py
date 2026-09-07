"""End-to-end operational portfolio runner."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class AssetE2EResult:
    ticker: str
    stages: tuple[str, ...]
    success: bool


@dataclass(frozen=True)
class PortfolioE2EResult:
    assets: tuple[AssetE2EResult, ...]

    @property
    def success(self) -> bool:
        return bool(self.assets) and all(item.success for item in self.assets)


def run(
    tickers: tuple[str, ...],
    asset_runner: Callable[[str], AssetE2EResult],
) -> PortfolioE2EResult:
    return PortfolioE2EResult(tuple(asset_runner(ticker.upper()) for ticker in tickers))
