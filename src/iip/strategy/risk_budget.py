"""Portfolio risk budget allocation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskBudget:
    ticker: str
    current_weight: float
    max_weight: float
    risk_score: float
    breach: bool


def assess(
    ticker: str,
    current_weight: float,
    max_weight: float,
    risk_score: float,
) -> RiskBudget:
    current = max(0.0, min(1.0, current_weight))
    maximum = max(0.0, min(1.0, max_weight))
    risk = max(0.0, min(10.0, risk_score))
    return RiskBudget(
        ticker.upper(),
        round(current, 12),
        round(maximum, 12),
        round(risk, 12),
        current > maximum,
    )
