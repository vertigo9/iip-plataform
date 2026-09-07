"""Portfolio risk radar."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskPoint:
    ticker: str
    overall: str
    weight: float
    risk_score: float


def sort_risk(points: tuple[RiskPoint, ...]) -> tuple[RiskPoint, ...]:
    return tuple(sorted(points, key=lambda p: (-p.risk_score, -p.weight, p.ticker)))
