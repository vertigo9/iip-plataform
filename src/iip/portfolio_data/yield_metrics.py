"""Dividend/proventos yield metrics."""

from __future__ import annotations


def yield_on_price(annual_income: float, price: float) -> float:
    if price <= 0:
        raise ValueError("price must be positive")
    return round(annual_income / price, 12)


def yield_on_cost(annual_income: float, average_cost: float) -> float:
    if average_cost <= 0:
        raise ValueError("average_cost must be positive")
    return round(annual_income / average_cost, 12)
