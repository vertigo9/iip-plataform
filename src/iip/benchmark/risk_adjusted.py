"""Risk-adjusted performance metrics."""

from __future__ import annotations

from math import sqrt
from statistics import mean, pstdev


def volatility(returns: tuple[float, ...]) -> float:
    if len(returns) < 2:
        return 0.0
    return pstdev(returns) * sqrt(len(returns))


def sharpe_like(
    returns: tuple[float, ...],
    risk_free: float = 0.0,
) -> float:
    if not returns:
        return 0.0
    vol = volatility(returns)
    if vol == 0:
        return 0.0
    return round((mean(returns) - risk_free) / vol, 12)
