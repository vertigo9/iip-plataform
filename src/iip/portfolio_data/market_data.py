"""Normalized market data contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketQuote:
    ticker: str
    price: float
    currency: str
    as_of: str


def normalize_quote(
    ticker: str, price: float, currency: str, as_of: str
) -> MarketQuote:
    if price < 0:
        raise ValueError("price must be non-negative")
    return MarketQuote(ticker.upper(), float(price), currency.upper(), as_of)
