"""Portfolio-wide system simulation over injected asset pipelines."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .models import SystemResult


@dataclass(frozen=True)
class PortfolioSystemResult:
    results: tuple[SystemResult, ...]

    @property
    def success_count(self) -> int:
        return sum(item.success for item in self.results)

    @property
    def failure_count(self) -> int:
        return sum(not item.success for item in self.results)


def run_portfolio(
    tickers: tuple[str, ...],
    runner: Callable[[str], SystemResult],
) -> PortfolioSystemResult:
    return PortfolioSystemResult(tuple(runner(ticker) for ticker in tickers))
