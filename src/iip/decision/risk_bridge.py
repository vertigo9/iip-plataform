"""Risk normalization for decision engine."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskSnapshot:
    ticker: str
    overall: str
    credit: str | None = None
    market: str | None = None
    liquidity: str | None = None
    leverage: str | None = None


def risk_penalty(snapshot: RiskSnapshot) -> float:
    return {
        "Baixo": 0.0,
        "Médio": 0.5,
        "Alto": 1.5,
    }.get(snapshot.overall, 1.0)
