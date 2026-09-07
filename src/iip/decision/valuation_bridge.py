"""Normalized valuation bridge for existing valuation analyzers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValuationSnapshot:
    ticker: str
    fair_value: float | None = None
    market_price: float | None = None
    margin_of_safety: float | None = None
    method: str | None = None


def valuation_score(snapshot: ValuationSnapshot) -> float:
    if snapshot.fair_value is None or snapshot.market_price is None:
        return 5.0
    if snapshot.market_price <= 0:
        return 0.0
    discount = (snapshot.fair_value / snapshot.market_price) - 1.0
    return max(0.0, min(10.0, 5.0 + discount * 10.0))
