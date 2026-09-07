"""Class-aware valuation bridge."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ValuationMethod(StrEnum):
    DCF = "DCF"
    GORDON = "Gordon"
    BAZIN = "Bazin"
    NAV = "NAV"
    FFO = "FFO"
    YIELD = "Yield"
    BOOK = "Book"
    RELATIVE = "Relative"


@dataclass(frozen=True)
class ValuationSnapshot:
    ticker: str
    method: ValuationMethod
    fair_value: float | None
    market_price: float | None
    margin_of_safety: float | None


def margin_of_safety(fair_value: float, market_price: float) -> float:
    if market_price <= 0:
        raise ValueError("market_price must be positive")
    return round((fair_value / market_price) - 1.0, 12)


def build_snapshot(
    ticker: str,
    method: ValuationMethod,
    fair_value: float | None,
    market_price: float | None,
) -> ValuationSnapshot:
    mos = (
        margin_of_safety(fair_value, market_price)
        if fair_value is not None and market_price is not None
        else None
    )
    return ValuationSnapshot(ticker.upper(), method, fair_value, market_price, mos)
