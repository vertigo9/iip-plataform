"""Consolidated portfolio reporting."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioRow:
    ticker: str
    asset_class: str
    market_value: float
    weight: float
    annual_income: float
    yield_on_price: float | None
    score: float | None
    action: str | None


@dataclass(frozen=True)
class PortfolioReport:
    as_of: str
    rows: tuple[PortfolioRow, ...]

    @property
    def total_value(self) -> float:
        return round(sum(row.market_value for row in self.rows), 12)

    @property
    def total_income(self) -> float:
        return round(sum(row.annual_income for row in self.rows), 12)
