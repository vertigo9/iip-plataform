"""Production portfolio cycle coordinator."""

from __future__ import annotations

from dataclasses import dataclass

from .decision_guard import DecisionGuard
from .portfolio_contract import PortfolioContract
from .reconciliation import reconcile


@dataclass(frozen=True)
class CycleResult:
    portfolio_valid: bool
    reconciliation_ok: bool
    decision_allowed: bool


def run_cycle(
    portfolio: PortfolioContract,
    observed_tickers: tuple[str, ...],
    guard: DecisionGuard,
) -> CycleResult:
    recon = reconcile(portfolio.tickers, observed_tickers)
    return CycleResult(
        portfolio.valid,
        recon.consistent,
        portfolio.valid and recon.consistent and guard.allowed,
    )
