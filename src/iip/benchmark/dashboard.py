"""Compact dashboard snapshot for decision operations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DashboardSnapshot:
    as_of: str
    portfolio_return: float
    benchmark_return: float
    excess_return: float
    max_drawdown: float
    alerts: int


def build(
    as_of: str,
    portfolio_return: float,
    benchmark_return: float,
    max_drawdown: float,
    alerts: int,
) -> DashboardSnapshot:
    return DashboardSnapshot(
        as_of=as_of,
        portfolio_return=round(portfolio_return, 12),
        benchmark_return=round(benchmark_return, 12),
        excess_return=round(portfolio_return - benchmark_return, 12),
        max_drawdown=round(max_drawdown, 12),
        alerts=max(0, int(alerts)),
    )
